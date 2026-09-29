"""A3 / WB-031 backup/restore rehearsal (integration).

Proves the documented procedure end-to-end on synthetic data: build a store,
capture + transcribe + export, take a manifest backup, destroy nothing,
restore into a clean root, and reconcile hashes/jobs/exports from the backup
alone. Also proves the restore is fail-closed against a tampered backup.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO))

from server.export import export_note_to_dir
from server.pass1 import Store


def wav_bytes(tag: bytes = b"\x00\x01") -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(tag * 160)
    return buf.getvalue()


class BackupRestoreRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-a3-"))
        self.root = self.tmp / "review"
        self.store = Store(self.root)
        for i, tag in enumerate((b"\x00\x01", b"\x02\x03", b"\x04\x05")):
            cid = f"a3-cap-{i}"
            self.store.accept(cid, wav_bytes(tag))
        self.store.set_transcript("a3-cap-0", "owner words", source="owner")
        self.store.set_transcript("a3-cap-1", "model words", source="model")
        # a token-like file must never enter the backup set
        (self.root / "token").write_text("OWNER-TOKEN-NEVER-BACKED-UP")

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *map(str, args)],
            capture_output=True,
            text=True,
            cwd=REPO,
            check=False,
        )

    def test_roundtrip_reproduces_identical_hashes_and_exports(self):
        # reference exports before backup
        pre = self.tmp / "pre-exports"
        digests = {}
        for cid in ("a3-cap-0", "a3-cap-1", "a3-cap-2"):
            note = self.store.get_note(cid)
            receipt = self.store.get(cid)
            path = export_note_to_dir(note, receipt, pre)
            digests[cid] = path.read_bytes()

        backup = self.tmp / "backup"
        result = self._run("scripts/backup_manifest.py", "--root", self.root, "--out", backup)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["captures"], 3)
        self.assertTrue((backup / "manifest.json").is_file())
        # the owner token never entered the backup set
        self.assertFalse((backup / "token").exists())
        self.assertNotIn("token", json.dumps(json.loads((backup / "manifest.json").read_text())))

        target = self.tmp / "restored"
        exports = self.tmp / "post-exports"
        result = self._run(
            "scripts/restore_backup.py", "--backup", backup, "--target", target, "--export-dir", exports
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["captures_reconciled"], 3)
        self.assertEqual(report["exports_verified"], 3)

        # identical receipt hashes from the backup alone
        restored = Store(target)
        for cid in ("a3-cap-0", "a3-cap-1", "a3-cap-2"):
            self.assertEqual(restored.get(cid).sha256, self.store.get(cid).sha256)
        # restored audio bytes identical
        for cid in ("a3-cap-0", "a3-cap-1", "a3-cap-2"):
            self.assertEqual(
                (target / "audio" / f"{cid}.wav").read_bytes(),
                (self.root / "audio" / f"{cid}.wav").read_bytes(),
            )
        # exports reproduced from the restored store are byte-identical to pre-backup
        for cid, expected_bytes in digests.items():
            self.assertEqual((exports / "pass1" / f"{cid}.md").read_bytes(), expected_bytes)

    def test_tampered_backup_refuses_to_restore(self):
        backup = self.tmp / "backup"
        self.assertEqual(
            self._run("scripts/backup_manifest.py", "--root", self.root, "--out", backup).returncode, 0
        )
        wav = backup / "audio" / "a3-cap-0.wav"
        raw = bytearray(wav.read_bytes())
        raw[-1] ^= 1
        wav.write_bytes(bytes(raw))
        target = self.tmp / "restored-tamper"
        result = self._run("scripts/restore_backup.py", "--backup", backup, "--target", target)
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(any("hash mismatch" in p for p in report["problems"]))
        # nothing was written: the target is absent or empty
        self.assertFalse(target.exists() and any(target.iterdir()))

    def test_restore_refuses_a_non_empty_target(self):
        backup = self.tmp / "backup"
        self.assertEqual(
            self._run("scripts/backup_manifest.py", "--root", self.root, "--out", backup).returncode, 0
        )
        target = self.tmp / "dirty"
        target.mkdir()
        (target / "stray.txt").write_text("x")
        result = self._run("scripts/restore_backup.py", "--backup", backup, "--target", target)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
