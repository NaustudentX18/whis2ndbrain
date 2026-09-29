"""Manual retry of exhausted transcription jobs: queue, API and HTML flows."""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from server.jobs import Jobs, run_once
from server.pass1 import Store
from server.review import Review

BEARER = {"authorization": "Bearer test-token"}


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


def exhaust(jobs: Jobs, capture_id: str) -> None:
    """Drive a job to the failed terminal state through real fail() calls."""
    t = 100.0
    for _ in range(jobs.max_attempts):
        job = jobs.claim(now=t)
        assert job is not None and job.capture_id == capture_id
        jobs.fail(job, RuntimeError("stub model unavailable"), now=t)
        t += max(1, jobs._backoff(job.attempt))


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-retry-"))
        self.store = Store(self.root)
        self.jobs = Jobs(self.store, max_attempts=2, lease_seconds=10)
        self.review = Review(self.store, token="test-token", jobs=self.jobs)
        _sid, self.csrf = self.review.auth.open_session()[:2]
        self.token_cookie = f"whis_session={_sid}"

    def _post_retry(self, capture_id: str):
        return self.review.handle(
            "POST", f"/api/v1/notes/{capture_id}/retry", b"", self.token_cookie,
            {**BEARER, "content-length": "0"},
        )

    def test_failed_job_can_be_manually_retried_and_then_transcribes(self):
        self.store.accept("capture-1", wav_bytes())
        exhaust(self.jobs, "capture-1")
        self.assertEqual(self.store.get_note("capture-1").status, "not_transcribed")

        status, _, body = self._post_retry("capture-1")
        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body)["status"], "queued")
        self.assertEqual(self.store.get_note("capture-1").status, "received")

        with self.store._connect() as conn:
            row = conn.execute(
                "SELECT state, attempt FROM transcription_jobs"
            ).fetchone()
        self.assertEqual(row["state"], "queued")
        self.assertEqual(row["attempt"], 0)

        self.assertTrue(run_once(self.store, lambda _p: "retried ok", self.jobs))
        note = self.store.get_note("capture-1")
        self.assertEqual(note.status, "transcribed")
        self.assertEqual(note.transcript, "retried ok")

    def test_retry_only_applies_to_failed_jobs(self):
        self.store.accept("capture-1", wav_bytes())
        status, _, _ = self._post_retry("capture-1")
        self.assertEqual(status, 409)  # still queued, not failed

        self.assertTrue(run_once(self.store, lambda _p: "done", self.jobs))
        status, _, _ = self._post_retry("capture-1")
        self.assertEqual(status, 409)  # already done

    def test_retry_unknown_capture_is_404(self):
        status, _, _ = self._post_retry("no-such-capture")
        self.assertEqual(status, 404)

    def test_retry_requires_authentication(self):
        self.store.accept("capture-1", wav_bytes())
        status, _, _ = self.review.handle(
            "POST", "/api/v1/notes/capture-1/retry", b"", "",
            {"content-length": "0"},
        )
        self.assertEqual(status, 401)

    def test_retry_unavailable_without_jobs_object(self):
        bare = Review(self.store, token="test-token")
        self.store.accept("capture-2", wav_bytes())
        status, _, _ = bare.handle(
            "POST", "/api/v1/notes/capture-2/retry", b"", self.token_cookie,
            {**BEARER, "content-length": "0"},
        )
        self.assertEqual(status, 409)

    def test_owner_corrected_capture_is_never_retried(self):
        self.store.accept("capture-1", wav_bytes())
        exhaust(self.jobs, "capture-1")
        self.store.set_transcript("capture-1", "owner text", "owner")
        self.assertFalse(self.jobs.retry_failed("capture-1"))
        status, _, _ = self._post_retry("capture-1")
        self.assertEqual(status, 409)
        note = self.store.get_note("capture-1")
        self.assertEqual(note.transcript, "owner text")
        self.assertEqual(note.status, "reviewed")

    def test_html_retry_flow_redirects(self):
        self.store.accept("capture-1", wav_bytes())
        exhaust(self.jobs, "capture-1")

        body = f"csrf={self.csrf}".encode()
        status, headers, _ = self.review.handle(
            "POST", "/n/capture-1/retry", body, self.token_cookie,
            {"content-length": str(len(body))},
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["location"], "/n/capture-1?retry=queued")
        self.assertEqual(self.store.get_note("capture-1").status, "received")

    def test_note_page_offers_retry_button_only_for_failed_notes(self):
        self.store.accept("capture-1", wav_bytes())
        exhaust(self.jobs, "capture-1")
        status, _, page = self.review.handle(
            "GET", "/n/capture-1", b"", self.token_cookie, BEARER
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Retry transcription", page)

        # A queued (not failed) note does not get the button.
        self.store.accept("capture-2", wav_bytes())
        status, _, page = self.review.handle(
            "GET", "/n/capture-2", b"", self.token_cookie, BEARER
        )
        self.assertEqual(status, 200)
        self.assertNotIn(b"Retry transcription", page)


if __name__ == "__main__":
    unittest.main()
