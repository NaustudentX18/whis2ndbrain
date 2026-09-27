"""Pass-1 host behavior. Each test names the break it catches."""

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import wave
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from server.pass1 import (
    Conflict,
    Rejected,
    Store,
    abandon_inflight,
    export_note,
    load_runner,
    prepare_host,
    purge_expired,
    render_note,
    transcribe,
)


def wav_bytes(n_frames: int = 160) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x01" * n_frames)
    return buf.getvalue()


class TempCase(unittest.TestCase):
    def tmp(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="whis-pass1-"))


class ModelLoadTests(unittest.TestCase):
    def test_runtime_never_downloads_weights_implicitly(self):
        with patch("faster_whisper.WhisperModel") as model:
            load_runner(Path("/nonexistent/disposable-model-cache"))
        self.assertTrue(model.call_args.kwargs["local_files_only"])


class AcceptTests(TempCase):
    def test_accept_keeps_the_bytes_and_reports_an_independent_hash(self):
        # Break: a receipt is returned before the WAV is durable, or the hash is not the file's hash.
        body = wav_bytes()
        store = Store(self.tmp())
        receipt = store.accept("cap-1", body)
        self.assertEqual(receipt.sha256, hashlib.sha256(body).hexdigest())
        self.assertEqual(receipt.byte_count, len(body))
        self.assertEqual(store.audio_path("cap-1").read_bytes(), body)

    def test_retry_of_the_same_bytes_returns_the_same_receipt(self):
        # Break: a lost response followed by retry creates a second note.
        body = wav_bytes()
        store = Store(self.tmp())
        first = store.accept("cap-1", body)
        second = store.accept("cap-1", body)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(len(list(store.audio_dir.glob("*.wav"))), 1)

    def test_same_id_with_different_bytes_keeps_the_original(self):
        # Break: a conflicting retry overwrites the accepted recording.
        store = Store(self.tmp())
        original = wav_bytes(160)
        store.accept("cap-1", original)
        with self.assertRaises(Conflict):
            store.accept("cap-1", wav_bytes(320))
        self.assertEqual(store.audio_path("cap-1").read_bytes(), original)

    def test_empty_and_non_wav_are_rejected_and_leave_no_file(self):
        # Break: garbage is acknowledged as a capture.
        store = Store(self.tmp())
        with self.assertRaises(Rejected):
            store.accept("cap-empty", b"")
        with self.assertRaises(Rejected):
            store.accept("cap-text", b"not a wav")
        self.assertEqual(list(store.audio_dir.glob("*")), [])
        self.assertIsNone(store.get("cap-empty"))


class ExportAndReviewTests(TempCase):
    def test_repeat_export_is_one_file_and_an_edit_is_a_conflict(self):
        # Break: export duplicates a note, or a hand edit is silently overwritten.
        root = self.tmp()
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        dest = root / "inbox"
        first = export_note(store, "cap-1", dest)
        second = export_note(store, "cap-1", dest)
        self.assertEqual(first, second)
        self.assertEqual(len(list(dest.glob("*.md"))), 1)
        first.write_text(first.read_text() + "\nowner edit\n")
        with self.assertRaises(Conflict):
            export_note(store, "cap-1", dest)
        self.assertIn("owner edit", first.read_text())

    def test_correction_is_what_export_writes(self):
        # Break: a later export puts the raw machine text back over the owner's correction.
        root = self.tmp()
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "machine said hello", source="model")
        store.set_transcript("cap-1", "owner said hello", source="owner")
        text = export_note(store, "cap-1", root / "inbox").read_text()
        self.assertIn("owner said hello", text)
        self.assertNotIn("machine said hello", text)

    def test_model_failure_keeps_audio_and_marks_not_transcribed(self):
        # Break: a model error deletes the capture or pretends a transcript exists.
        store = Store(self.tmp())
        body = wav_bytes()
        store.accept("cap-1", body)

        def boom(_path: Path) -> str:
            raise RuntimeError("model down")

        note = transcribe(store, "cap-1", boom)
        self.assertEqual(note.status, "not_transcribed")
        self.assertIsNone(note.transcript)
        self.assertEqual(store.audio_path("cap-1").read_bytes(), body)

    def test_review_html_escapes_the_transcript(self):
        # Break: a transcript is rendered as HTML.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "<script>alert(1)</script>", source="model")
        html = render_note(store.get_note("cap-1"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)



class SchemaTests(TempCase):
    def test_old_database_gains_columns_and_does_not_backfill(self):
        # Break: opening an old queue invents a receipt time and the live notes become purgeable.
        root = self.tmp()
        db = sqlite3.connect(root / "queue.sqlite")
        db.execute(
            """
            CREATE TABLE captures (
                capture_id TEXT PRIMARY KEY,
                receipt_id TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                byte_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                transcript TEXT,
                transcript_source TEXT
            )
            """
        )
        db.execute(
            """
            INSERT INTO captures
                (capture_id, receipt_id, sha256, byte_count, status, transcript, transcript_source)
            VALUES ('old', 'r1', 'abc', 3, 'reviewed', 'kept', 'owner')
            """
        )
        db.commit()
        db.close()
        (root / "audio").mkdir()
        store = Store(root)
        with store._connect() as conn:
            row = conn.execute(
                "SELECT received_at, audio_purged_at FROM captures WHERE capture_id = 'old'"
            ).fetchone()
        self.assertIsNone(row["received_at"])
        self.assertIsNone(row["audio_purged_at"])
        note = store.get_note("old")
        self.assertEqual(note.transcript, "kept")
        self.assertIsNone(note.received_at)
        self.assertIsNone(note.audio_purged_at)

    def test_accept_writes_a_zulu_receipt_time(self):
        # Break: a new capture has no host receipt time, so the 7-day hold cannot start.
        store = Store(self.tmp())
        before = datetime.now(timezone.utc).replace(microsecond=0)
        store.accept("cap-1", wav_bytes())
        after = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=1)
        note = store.get_note("cap-1")
        parsed = datetime.strptime(note.received_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertRegex(note.received_at, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertGreaterEqual(parsed, before - timedelta(seconds=1))
        self.assertLessEqual(parsed, after)
        self.assertIsNone(note.audio_purged_at)


class CrashTests(TempCase):
    def test_raise_after_write_returns_no_receipt_and_leaves_the_wav(self):
        # Break: a kill between the file write and the insert is reported as a receipt.
        root = self.tmp()
        store = Store(root)

        def boom() -> None:
            raise RuntimeError("killed")

        with self.assertRaises(RuntimeError):
            store.accept("cap-1", wav_bytes(), after_write=boom)
        self.assertTrue((root / "audio" / "cap-1.wav").is_file())
        self.assertIsNone(store.get("cap-1"))

    def test_next_open_quarantines_the_orphan_and_does_not_receipt_it(self):
        # Break: an unacked WAV becomes a note on restart.
        root = self.tmp()
        body = wav_bytes()
        (root / "audio").mkdir()
        (root / "audio" / "cap-1.wav").write_bytes(body)
        store = Store(root)
        self.assertFalse((root / "audio" / "cap-1.wav").exists())
        self.assertEqual((root / "orphans" / "cap-1.wav").read_bytes(), body)
        self.assertIsNone(store.get("cap-1"))
        self.assertEqual(store.list_notes(), [])

    def test_part_file_is_quarantined_without_becoming_a_wav(self):
        # Break: a partial write is renamed into a playable capture.
        root = self.tmp()
        (root / "audio").mkdir()
        (root / "audio" / "cap-1.wav.part").write_bytes(b"partial")
        Store(root)
        self.assertFalse((root / "audio" / "cap-1.wav.part").exists())
        self.assertFalse((root / "orphans" / "cap-1.wav").exists())
        self.assertEqual((root / "orphans" / "cap-1.wav.part").read_bytes(), b"partial")

    def test_existing_orphan_destination_is_not_replaced(self):
        # Break: quarantine overwrites an older unacked file.
        root = self.tmp()
        (root / "orphans").mkdir()
        (root / "orphans" / "cap-1.wav").write_bytes(b"older")
        (root / "audio").mkdir()
        (root / "audio" / "cap-1.wav").write_bytes(b"newer")
        store = Store(root)
        self.assertEqual((root / "orphans" / "cap-1.wav").read_bytes(), b"older")
        self.assertEqual((root / "audio" / "cap-1.wav").read_bytes(), b"newer")
        self.assertIsNone(store.get("cap-1"))

    def test_retry_after_quarantine_is_a_new_receipt(self):
        # Break: a retry revives the quarantined bytes or keeps the old receipt id.
        root = self.tmp()
        (root / "audio").mkdir()
        (root / "audio" / "cap-1.wav").write_bytes(b"RIFF----WAVE")
        Store(root)
        quarantined = (root / "orphans" / "cap-1.wav").read_bytes()
        store = Store(root)
        fresh = wav_bytes()
        receipt = store.accept("cap-1", fresh)
        self.assertEqual(store.audio_path("cap-1").read_bytes(), fresh)
        self.assertEqual((root / "orphans" / "cap-1.wav").read_bytes(), quarantined)
        self.assertNotEqual(receipt.sha256, hashlib.sha256(quarantined).hexdigest())

    def test_insert_error_still_unlinks_the_wav(self):
        # Break: a database error leaves an acked-looking file with no row.
        store = Store(self.tmp())
        with store._connect() as conn:
            conn.execute(
                """
                CREATE TRIGGER fail_insert BEFORE INSERT ON captures
                BEGIN
                    SELECT RAISE(ABORT, 'boom');
                END
                """
            )
        with self.assertRaises(sqlite3.Error):
            store.accept("cap-1", wav_bytes())
        self.assertFalse(store.audio_path("cap-1").exists())
        self.assertIsNone(store.get("cap-1"))


class OwnerWinsTests(TempCase):
    def test_model_finish_does_not_replace_an_owner_correction(self):
        # Break: the background runner writes the machine text over the owner's correction.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "owner said hello", "owner")
        note = transcribe(store, "cap-1", lambda path: "machine said otherwise")
        self.assertEqual(note.transcript, "owner said hello")
        self.assertEqual(note.transcript_source, "owner")
        self.assertEqual(note.status, "reviewed")

    def test_model_failure_does_not_clear_an_owner_correction(self):
        # Break: a runner exception nulls the correction and marks the note not transcribed.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "owner said hello", "owner")

        def fail(path: Path) -> str:
            raise RuntimeError("model down")

        note = transcribe(store, "cap-1", fail)
        self.assertEqual(note.transcript, "owner said hello")
        self.assertEqual(note.status, "reviewed")

    def test_late_model_annotation_cannot_replace_owner_annotation(self):
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_suggestions("cap-1", "idea", "high", True, source="owner")
        store.set_suggestions("cap-1", "todo", "low", False, source="model")
        note = store.get_note("cap-1")
        self.assertEqual((note.category, note.urgency, note.actionable), ("idea", "high", True))

    def test_late_model_failure_cannot_clear_reviewed_note(self):
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "owner correction", "owner")
        store.mark_not_transcribed("cap-1")
        note = store.get_note("cap-1")
        self.assertEqual((note.status, note.transcript), ("reviewed", "owner correction"))


class TranscribingTests(TempCase):
    def test_mark_transcribing_only_moves_received(self):
        # Break: a late mark regresses a reviewed note back to transcribing.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.mark_transcribing("cap-1")
        self.assertEqual(store.get_note("cap-1").status, "transcribing")
        store.mark_transcribing("cap-1")
        self.assertEqual(store.get_note("cap-1").status, "transcribing")
        store.set_transcript("cap-1", "owner said hello", "owner")
        store.mark_transcribing("cap-1")
        self.assertEqual(store.get_note("cap-1").status, "reviewed")
        with self.assertRaises(Rejected):
            store.mark_transcribing("missing")


class PurgeTests(TempCase):
    def _age(self, store: Store, capture_id: str, raw: str) -> None:
        with store._connect() as conn:
            conn.execute(
                "UPDATE captures SET received_at = ? WHERE capture_id = ?",
                (raw, capture_id),
            )

    def test_one_second_before_168_hours_keeps_the_file(self):
        # Break: purge deletes audio early.
        store = Store(self.tmp())
        body = wav_bytes()
        store.accept("cap-1", body)
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        received = (now - timedelta(hours=168) + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._age(store, "cap-1", received)
        purge_expired(store, now)
        self.assertEqual(store.audio_path("cap-1").read_bytes(), body)
        self.assertIsNone(store.get_note("cap-1").audio_purged_at)

    def test_168_hours_unlinks_audio_and_keeps_the_note(self):
        # Break: purge deletes the row or the owner text, or leaves the WAV.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "owner said hello", "owner")
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        received = (now - timedelta(hours=168)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._age(store, "cap-1", received)
        purge_expired(store, now)
        self.assertFalse(store.audio_path("cap-1").exists())
        note = store.get_note("cap-1")
        self.assertEqual(note.transcript, "owner said hello")
        self.assertEqual(note.status, "reviewed")
        self.assertEqual(note.audio_purged_at, "2026-09-26T12:00:00Z")

    def test_null_and_garbage_receipt_times_are_not_purged(self):
        # Break: a missing or bad stamp is treated as already expired.
        store = Store(self.tmp())
        store.accept("cap-null", wav_bytes())
        store.accept("cap-bad", wav_bytes())
        with store._connect() as conn:
            conn.execute("UPDATE captures SET received_at = NULL WHERE capture_id = 'cap-null'")
            conn.execute("UPDATE captures SET received_at = 'yesterday' WHERE capture_id = 'cap-bad'")
        purge_expired(store, datetime(2026, 9, 26, tzinfo=timezone.utc))
        self.assertTrue(store.audio_path("cap-null").is_file())
        self.assertTrue(store.audio_path("cap-bad").is_file())
        self.assertIsNone(store.get_note("cap-null").audio_purged_at)
        self.assertIsNone(store.get_note("cap-bad").audio_purged_at)

    def test_second_purge_does_not_change_the_stamp(self):
        # Break: a later sweep rewrites the expiry time or raises on a missing file.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        self._age(store, "cap-1", "2026-09-19T12:00:00Z")
        purge_expired(store, now)
        later = now + timedelta(hours=1)
        purge_expired(store, later)
        self.assertEqual(store.get_note("cap-1").audio_purged_at, "2026-09-26T12:00:00Z")
        self.assertFalse(store.audio_path("cap-1").exists())

    def test_later_purge_unlinks_a_file_put_back_after_the_stamp(self):
        # Break: a WAV put back after the hold ended stays playable, or the stamp moves.
        store = Store(self.tmp())
        store.accept("cap-1", wav_bytes())
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        self._age(store, "cap-1", "2026-09-19T12:00:00Z")
        purge_expired(store, now)
        store.audio_path("cap-1").write_bytes(wav_bytes())
        purge_expired(store, now + timedelta(hours=1))
        self.assertFalse(store.audio_path("cap-1").exists())
        self.assertEqual(store.get_note("cap-1").audio_purged_at, "2026-09-26T12:00:00Z")

    def test_purge_does_not_eat_orphans(self):
        # Break: the hold sweep deletes unacked audio in orphans/.
        root = self.tmp()
        (root / "audio").mkdir()
        (root / "audio" / "cap-1.wav").write_bytes(wav_bytes())
        store = Store(root)
        purge_expired(store, datetime(2099, 1, 1, tzinfo=timezone.utc))
        self.assertTrue((root / "orphans" / "cap-1.wav").is_file())


class PrepareTests(TempCase):
    def test_abandon_flips_only_transcribing(self):
        # Break: restart marks a reviewed note not transcribed, or resumes a dead job.
        store = Store(self.tmp())
        store.accept("cap-live", wav_bytes())
        store.mark_transcribing("cap-live")
        store.accept("cap-kept", wav_bytes())
        store.set_transcript("cap-kept", "owner said hello", "owner")
        abandon_inflight(store)
        self.assertEqual(store.get_note("cap-live").status, "not_transcribed")
        self.assertIsNone(store.get_note("cap-live").transcript)
        self.assertEqual(store.get_note("cap-kept").status, "reviewed")
        self.assertEqual(store.get_note("cap-kept").transcript, "owner said hello")

    def test_prepare_host_abandons_and_purges(self):
        # Break: startup leaves a dead transcribing row, or skips an already expired file.
        store = Store(self.tmp())
        store.accept("cap-dead", wav_bytes())
        store.mark_transcribing("cap-dead")
        store.accept("cap-old", wav_bytes())
        with store._connect() as conn:
            conn.execute(
                "UPDATE captures SET received_at = ? WHERE capture_id = 'cap-old'",
                ("2026-09-19T12:00:00Z",),
            )
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        prepare_host(store, now)
        self.assertEqual(store.get_note("cap-dead").status, "not_transcribed")
        self.assertFalse(store.audio_path("cap-old").exists())
        self.assertEqual(store.get_note("cap-old").audio_purged_at, "2026-09-26T12:00:00Z")

    def test_purge_command_prints_no_note_text(self):
        # Break: the purge command prints a transcript.
        root = self.tmp()
        store = Store(root)
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "secret cheese", "owner")
        repo = Path(__file__).resolve().parents[2]
        proc = subprocess.run(
            [sys.executable, "-m", "server", "purge", "--root", str(root)],
            cwd=repo,
            env={**os.environ, "PYTHONPATH": str(repo)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("secret cheese", proc.stdout)
        self.assertNotIn("secret cheese", proc.stderr)


class VaultExportTests(TempCase):
    def test_export_into_a_vault_root_creates_nothing(self):
        # Break: export mkdir's a note inside the vault.
        root = self.tmp()
        vault = root / "vault"
        vault.mkdir()
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        with self.assertRaises(Rejected):
            export_note(store, "cap-1", vault / "00-Inbox", forbidden=vault)
        self.assertFalse((vault / "00-Inbox").exists())
        self.assertEqual(list(vault.iterdir()), [])

    def test_symlink_into_the_vault_is_refused(self):
        # Break: a symlink outside the vault still receives the note.
        root = self.tmp()
        vault = root / "vault"
        vault.mkdir()
        outside = root / "outside"
        outside.mkdir()
        link = outside / "notes"
        link.symlink_to(vault)
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        with self.assertRaises(Rejected):
            export_note(store, "cap-1", link, forbidden=vault)
        self.assertEqual(list(vault.iterdir()), [])

    def test_disposable_export_still_conflicts_on_a_hand_edit(self):
        # Break: the vault guard rejects a normal folder, or a hand edit is overwritten.
        root = self.tmp()
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "owner said hello", "owner")
        dest = root / "inbox"
        first = export_note(store, "cap-1", dest, forbidden=root / "vault")
        second = export_note(store, "cap-1", dest, forbidden=root / "vault")
        self.assertEqual(first, second)
        self.assertEqual(len(list(dest.glob("*.md"))), 1)
        first.write_text(first.read_text() + "\nhand edit\n")
        with self.assertRaises(Conflict):
            export_note(store, "cap-1", dest, forbidden=root / "vault")

    def test_default_forbidden_root_is_the_live_vault_path(self):
        # Break: the default guard points somewhere other than the owner's vault.
        from server.pass1 import VAULT_ROOT
        self.assertEqual(VAULT_ROOT, Path.home() / "Documents" / "Vault")

    def test_export_command_exits_2_without_the_transcript(self):
        # Break: a refused export exits 0 or prints the note.
        # Do not point --dest at the live vault. The CLI has no stand-in flag.
        # Patch the imported export_note so Rejected is what the command catches.
        root = self.tmp()
        store = Store(root / "data")
        store.accept("cap-1", wav_bytes())
        store.set_transcript("cap-1", "secret cheese", "owner")
        from io import StringIO
        from unittest.mock import patch

        import server.__main__ as cli
        err = StringIO()
        argv = [
            "server", "export",
            "--root", str(root / "data"),
            "--id", "cap-1",
            "--dest", str(root / "inbox"),
        ]
        with (
            patch.object(cli, "export_note", side_effect=Rejected("no")),
            patch("sys.argv", argv),
            patch("sys.stderr", err),
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("export refused", err.getvalue())
        self.assertNotIn("secret cheese", err.getvalue())
        self.assertFalse((root / "inbox").exists())

if __name__ == "__main__":
    unittest.main()
