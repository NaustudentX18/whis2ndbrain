"""Isolated, killable model execution for the transcription worker.

The runner keeps the ``callable(audio_path) -> str`` contract so it drops into
``run_once``/``transcribe`` unchanged, but the model now runs in a disposable
subprocess with a hard wall-clock timeout and a child-side memory cap.

Exit-code contract of ``scripts/run_transcriber.py``:

=====  ==================================================================
exit   meaning
=====  ==================================================================
0      success; stdout is UTF-8 JSON ``{"transcript": "..."}`` (may be "")
3      model weights/runtime unavailable on this host
5      valid audio, nothing transcribed (no speech) - not an error
other  unexpected failure the queue may retry
=====  ==================================================================

A killed, hung, oversized or unparseable child never becomes a fake
transcript: it raises, the job fails, and the capture stays reviewable.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MODEL_MISSING_EXIT = 3
NO_SPEECH_EXIT = 5
MAX_TRANSCRIPT_CHARS = 100_000

DEFAULT_TIMEOUT_SECONDS = 900.0
DEFAULT_MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024  # 4 GiB guard: 3 GiB broke real loads (MKL VA reservation measured 2026-09-29)

_REPO_ROOT = Path(__file__).resolve().parents[2]


class TranscriberUnavailable(Exception):
    """Weights/runtime missing; the capture must stay reviewable, not faked."""


class TranscriberTimeout(Exception):
    """The subprocess exceeded the hard wall-clock limit and was killed."""


@dataclass(frozen=True)
class IsolatedTranscriber:
    """Run transcription in a short-lived subprocess.

    ``argv`` is overridable so tests substitute stub processes; the default is
    this repo's own ``scripts/run_transcriber.py``. The memory cap is enforced
    inside the child (RLIMIT_AS before the model loads), so the parent stays
    safe to call from threaded servers.
    """

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    memory_limit_bytes: int | None = DEFAULT_MEMORY_LIMIT_BYTES
    argv: tuple[str, ...] | None = None

    def _command(self, audio_path: Path) -> list[str]:
        if self.argv is not None:
            return [*self.argv, str(audio_path)]
        script = _REPO_ROOT / "scripts" / "run_transcriber.py"
        return [sys.executable, str(script), str(audio_path)]

    def __call__(self, audio_path: Path) -> str:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(_REPO_ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        if self.memory_limit_bytes is not None:
            env["WHIS_TRANSCRIBER_MEMORY_LIMIT"] = str(self.memory_limit_bytes)
        proc = subprocess.Popen(
            self._command(audio_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
        try:
            stdout, _stderr = proc.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            self._kill_group(proc)
            raise TranscriberTimeout(
                f"transcriber exceeded {self.timeout_seconds}s and was killed"
            ) from None
        if proc.returncode == MODEL_MISSING_EXIT:
            raise TranscriberUnavailable("transcriber subprocess reported missing model")
        if proc.returncode == NO_SPEECH_EXIT:
            return ""
        if proc.returncode != 0:
            raise RuntimeError(f"transcriber subprocess exited {proc.returncode}")
        try:
            payload = json.loads(stdout.decode("utf-8", "strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("transcriber output is not valid UTF-8 JSON") from exc
        transcript = payload.get("transcript") if isinstance(payload, dict) else None
        if not isinstance(transcript, str):
            raise RuntimeError("transcriber output missing transcript field")  # noqa: TRY004 - untrusted subprocess output, not a caller type error
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            raise RuntimeError("transcriber transcript exceeds size contract")
        return transcript

    @staticmethod
    def _kill_group(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - group kill always lands
            proc.kill()
