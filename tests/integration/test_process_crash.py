"""Real subprocess crash check for the durable-write-before-receipt boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from server.pass1 import Store
from tests.integration.test_http_review import synthetic_wav


class ProcessCrashTests(unittest.TestCase):
    def test_kill_after_audio_publish_never_invents_a_receipt(self):
        with tempfile.TemporaryDirectory(prefix="whis-kill-test-") as temp:
            root = Path(temp) / "store"
            source = Path(temp) / "synthetic.wav"
            marker = Path(temp) / "written.marker"
            source.write_bytes(synthetic_wav())
            child_code = """
import sys, time
from pathlib import Path
from server.pass1 import Store
root, source, marker = map(Path, sys.argv[1:])
def after_write():
    marker.write_text('published')
    time.sleep(60)
Store(root).accept('kill-boundary-001', source.read_bytes(), after_write=after_write)
"""
            child = subprocess.Popen(
                [sys.executable, "-c", child_code, str(root), str(source), str(marker)],
                cwd=Path(__file__).resolve().parents[2],
                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:
                for _ in range(100):
                    if marker.exists() or child.poll() is not None:
                        break
                    time.sleep(0.05)
                self.assertTrue(marker.exists(), "child never reached post-write boundary")
                child.kill()
                child.wait(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                if child.stderr is not None:
                    child.stderr.close()

            restarted = Store(root)
            self.assertIsNone(restarted.get("kill-boundary-001"))
            self.assertFalse(restarted.audio_path("kill-boundary-001").exists())
            self.assertTrue((root / "orphans" / "kill-boundary-001.wav").is_file())
            receipt = restarted.accept("kill-boundary-001", source.read_bytes())
            self.assertTrue(receipt.receipt_id)
            self.assertEqual(restarted.get("kill-boundary-001"), receipt)


if __name__ == "__main__":
    unittest.main()
