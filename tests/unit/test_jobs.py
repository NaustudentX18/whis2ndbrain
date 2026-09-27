"""Durable job-queue behavior using only synthetic recordings."""

import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from server.jobs import Jobs, run_once
from server.pass1 import Store


def wav_bytes():
    stream = BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 160)
    return stream.getvalue()


class JobTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-jobs-"))
        self.store = Store(self.root)
        self.jobs = Jobs(self.store, max_attempts=2, lease_seconds=10)

    def test_accept_and_job_are_atomic_and_duplicate_receipt_does_not_duplicate_job(self):
        self.store.accept("capture-1", wav_bytes())
        self.store.accept("capture-1", wav_bytes())
        with self.store._connect() as conn:
            rows = conn.execute("SELECT capture_id, state FROM transcription_jobs").fetchall()
        self.assertEqual([(row["capture_id"], row["state"]) for row in rows], [("capture-1", "queued")])

    def test_restart_backfills_only_unfinished_legacy_captures(self):
        self.store.accept("unfinished", wav_bytes())
        self.store.accept("finished", wav_bytes())
        self.store.set_transcript("finished", "already done", "model")
        with self.store._connect() as conn:
            conn.execute("DELETE FROM transcription_jobs")
        restarted = Store(self.root)
        with restarted._connect() as conn:
            rows = conn.execute("SELECT capture_id FROM transcription_jobs").fetchall()
        self.assertEqual([row["capture_id"] for row in rows], ["unfinished"])

    def test_expired_lease_reclaims_and_fences_stale_token(self):
        self.store.accept("capture-1", wav_bytes())
        first = self.jobs.claim(now=100)
        self.assertIsNone(self.jobs.claim(now=111))
        second = self.jobs.claim(now=112)
        self.assertEqual(first.attempt, 1)
        self.assertEqual(second.attempt, 2)
        self.assertNotEqual(first.token, second.token)
        self.assertFalse(self.jobs.complete(first, "stale transcript", ("idea", "high", True), now=112))
        self.assertIsNone(self.store.get_note("capture-1").transcript)
        self.assertTrue(self.jobs.complete(second, "current transcript", ("thought", "normal", False), now=112))
        note = self.store.get_note("capture-1")
        self.assertEqual(note.transcript, "current transcript")
        self.assertEqual(note.category, "thought")

    def test_expired_token_cannot_publish_before_reclaim(self):
        self.store.accept("capture-1", wav_bytes())
        job = self.jobs.claim(now=100)
        self.assertFalse(self.jobs.complete(job, "late result", now=111))
        self.assertIsNone(self.store.get_note("capture-1").transcript)

    def test_failure_cannot_overwrite_a_successful_model_result(self):
        self.store.accept("capture-1", wav_bytes())
        job = self.jobs.claim()
        self.store.set_transcript("capture-1", "successful result", "model")
        self.assertTrue(self.jobs.fail(job, RuntimeError("late failure")))
        note = self.store.get_note("capture-1")
        self.assertEqual(note.status, "transcribed")
        self.assertEqual(note.transcript, "successful result")
        with self.store._connect() as conn:
            row = conn.execute("SELECT state FROM transcription_jobs").fetchone()
        self.assertEqual(row["state"], "done")

    def test_failures_retry_with_backoff_then_become_reviewable_terminal(self):
        self.store.accept("capture-1", wav_bytes())
        first = self.jobs.claim(now=100)
        self.assertTrue(self.jobs.fail(first, RuntimeError("/private/path with transcript"), now=100))
        self.assertIsNone(self.jobs.claim(now=100))
        second = self.jobs.claim(now=101)
        self.assertEqual(second.attempt, 2)
        self.assertTrue(self.jobs.fail(second, RuntimeError("still broken"), now=101))
        note = self.store.get_note("capture-1")
        self.assertEqual(note.status, "not_transcribed")
        with self.store._connect() as conn:
            row = conn.execute("SELECT state, error FROM transcription_jobs").fetchone()
        self.assertEqual(row["state"], "failed")
        self.assertEqual(row["error"], "RuntimeError")

    def test_worker_processes_job_using_injected_runner(self):
        self.store.accept("capture-1", wav_bytes())
        self.assertTrue(run_once(self.store, lambda _path: "hello", self.jobs))
        self.assertEqual(self.store.get_note("capture-1").transcript, "hello")
        self.assertFalse(run_once(self.store, lambda _path: "unused", self.jobs))

    def test_invalid_runner_result_never_finishes_as_transcribed(self):
        self.store.accept("capture-1", wav_bytes())
        self.assertTrue(run_once(self.store, lambda _path: None, self.jobs))
        with self.store._connect() as conn:
            job = conn.execute("SELECT state, error FROM transcription_jobs").fetchone()
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["error"], "ValueError")
        self.assertNotEqual(self.store.get_note("capture-1").status, "transcribed")
        self.assertTrue(self.store.audio_path("capture-1").is_file())

    def test_previously_transcribed_capture_is_not_reprocessed(self):
        self.store.accept("capture-1", wav_bytes())
        self.store.set_transcript("capture-1", "already transcribed", "model")
        self.assertIsNone(self.jobs.claim())


if __name__ == "__main__":
    unittest.main()
