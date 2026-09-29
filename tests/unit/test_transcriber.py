"""IsolatedTranscriber contract tests using stub subprocesses.

No model weights, network or real speech: the child processes are
``python -c`` stubs that speak the exit-code contract of
``scripts/run_transcriber.py``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from server.pipeline.transcriber import (
    IsolatedTranscriber,
    TranscriberTimeout,
    TranscriberUnavailable,
)

AUDIO = Path(tempfile.gettempdir()) / "whis-transcriber-stub.wav"


def stub(source: str) -> tuple[str, ...]:
    return (sys.executable, "-c", source)


class IsolatedTranscriberTests(unittest.TestCase):
    def setUp(self):
        AUDIO.write_bytes(b"RIFF----WAVEfmt ")

    def test_success_returns_transcript(self):
        runner = IsolatedTranscriber(
            argv=stub("import json,sys; print(json.dumps({'transcript': 'hello world'}))")
        )
        self.assertEqual(runner(AUDIO), "hello world")

    def test_empty_transcript_is_valid_success(self):
        runner = IsolatedTranscriber(
            argv=stub("import json,sys; print(json.dumps({'transcript': ''}))")
        )
        self.assertEqual(runner(AUDIO), "")

    def test_no_speech_exit_returns_empty_not_error(self):
        runner = IsolatedTranscriber(argv=stub("import sys; sys.exit(5)"))
        self.assertEqual(runner(AUDIO), "")

    def test_model_missing_raises_unavailable(self):
        runner = IsolatedTranscriber(argv=stub("import sys; sys.exit(3)"))
        with self.assertRaises(TranscriberUnavailable):
            runner(AUDIO)

    def test_unexpected_exit_is_error(self):
        runner = IsolatedTranscriber(argv=stub("import sys; sys.exit(7)"))
        with self.assertRaises(RuntimeError):
            runner(AUDIO)

    def test_crashed_child_is_error(self):
        runner = IsolatedTranscriber(argv=stub("import sys; sys.stderr.write('boom'); sys.exit(1)"))
        with self.assertRaises(RuntimeError):
            runner(AUDIO)

    def test_garbage_stdout_is_error(self):
        runner = IsolatedTranscriber(argv=stub("print('not json at all')"))
        with self.assertRaises(RuntimeError):
            runner(AUDIO)

    def test_missing_transcript_field_is_error(self):
        runner = IsolatedTranscriber(argv=stub("print('{\"other\": 1}')"))
        with self.assertRaises(RuntimeError):
            runner(AUDIO)

    def test_oversized_transcript_is_error(self):
        runner = IsolatedTranscriber(
            argv=stub(
                "import json,sys; print(json.dumps({'transcript': 'x' * 200000}))"
            )
        )
        with self.assertRaises(RuntimeError):
            runner(AUDIO)

    def test_hard_timeout_kills_hung_child(self):
        pid_file = AUDIO.with_suffix(".pid")
        source = (
            "import os,sys,time;"
            f"open({str(pid_file)!r},'w').write(str(os.getpid()));"
            "time.sleep(60)"
        )
        runner = IsolatedTranscriber(argv=stub(source), timeout_seconds=1.0)
        started = time.monotonic()
        with self.assertRaises(TranscriberTimeout):
            runner(AUDIO)
        self.assertLess(time.monotonic() - started, 15)
        child_pid = int(pid_file.read_text().strip())
        pid_file.unlink(missing_ok=True)
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)  # the hung child is genuinely dead

    def test_memory_limit_env_reaches_child_and_is_enforced(self):
        # The child applies RLIMIT_AS from WHIS_TRANSCRIBER_MEMORY_LIMIT before
        # allocating, mirroring scripts/run_transcriber.py's own startup.
        source = (
            "import json,os,resource,sys\n"
            "raw=os.environ.get('WHIS_TRANSCRIBER_MEMORY_LIMIT')\n"
            "if raw and raw.isdigit():\n"
            "    limit=int(raw)\n"
            "    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))\n"
            "try:\n"
            "    bytearray(256*1024*1024)\n"
            "except MemoryError:\n"
            "    sys.exit(9)\n"
            "print(json.dumps({'transcript':'allocated'}))\n"
        )
        capped = IsolatedTranscriber(
            argv=stub(source), memory_limit_bytes=64 * 1024 * 1024
        )
        with self.assertRaises(RuntimeError):
            capped(AUDIO)
        uncapped = IsolatedTranscriber(argv=stub(source), memory_limit_bytes=None)
        self.assertEqual(uncapped(AUDIO), "allocated")

    def test_real_child_script_reports_missing_model(self):
        # Exercises the actual scripts/run_transcriber.py exit-code contract:
        # local-files-only load from a nonexistent model dir must exit 3,
        # proving no download path and honest unavailability.
        script = Path(__file__).resolve().parents[2] / "scripts" / "run_transcriber.py"
        runner = IsolatedTranscriber(
            argv=(sys.executable, str(script), "--model-dir", str(AUDIO.parent / "no-such-model"))
        )
        with self.assertRaises(TranscriberUnavailable):
            runner(AUDIO)


if __name__ == "__main__":
    unittest.main()
