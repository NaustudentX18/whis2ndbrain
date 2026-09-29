"""Subprocess entry for isolated transcription (WB-023 lane).

Exit codes: 0 success (JSON on stdout), 3 model/runtime missing,
5 no speech, anything else is an unexpected failure. The parent
(``server.pipeline.transcriber.IsolatedTranscriber``) owns the timeout kill;
this child owns its own memory cap via RLIMIT_AS before any model loads.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODEL_MISSING_EXIT = 3
NO_SPEECH_EXIT = 5


def _apply_memory_limit(limit_bytes: int) -> None:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except (ValueError, OSError):
        # A cap we cannot apply is reported, not silently dropped.
        print("warning: could not apply RLIMIT_AS", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolated Whisper transcription")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model-dir", type=Path, default=None)
    args = parser.parse_args()

    limit = None
    raw = getattr(resource, "RLIMIT_AS", None)
    import os

    raw_env = os.environ.get("WHIS_TRANSCRIBER_MEMORY_LIMIT")
    if raw and raw_env and raw_env.isdigit():
        limit = int(raw_env)
    if limit:
        _apply_memory_limit(limit)

    from server.pass1 import MODEL_DIR, MODEL_ID

    try:
        from faster_whisper import WhisperModel
    except Exception:  # noqa: BLE001 - any import failure means model unavailable
        sys.exit(MODEL_MISSING_EXIT)

    model_dir = args.model_dir if args.model_dir is not None else MODEL_DIR
    try:
        model = WhisperModel(
            MODEL_ID,
            device="cpu",
            compute_type="int8",
            download_root=str(model_dir),
            local_files_only=True,
        )
    except Exception:  # noqa: BLE001 - any load failure means weights unavailable
        sys.exit(MODEL_MISSING_EXIT)

    segments, _info = model.transcribe(str(args.audio), language="en", vad_filter=True)
    text = "".join(segment.text for segment in segments).strip()
    if not text:
        sys.exit(NO_SPEECH_EXIT)
    json.dump({"transcript": text}, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
