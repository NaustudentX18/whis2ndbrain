"""A2 / WB-042 observability: metrics endpoint, queue/latency facts,
redaction canary. The payload is numbers by construction - the canary
proves hostile transcripts and error strings can never leak into it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from server.jobs import Jobs
from server.pass1 import Store
from server.review import Review

OWNER = {"authorization": "Bearer owner-token"}
HOSTILE = "TOPSEEKRET-ALPHA do not ever leak \U0001f9ea"


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-metrics-"))
        self.store = Store(self.root)
        self.jobs = Jobs(self.store, max_attempts=2, lease_seconds=120)
        self.review = Review(self.store, token="owner-token", jobs=self.jobs)

    def _metrics(self, headers=None, cookie=""):
        hdrs = dict(OWNER) if headers is None else headers
        status, _h, body = self.review.handle("GET", "/api/v1/metrics", b"", cookie, hdrs)
        return status, (json.loads(body) if status == 200 else body)

    def test_metrics_requires_owner(self):
        self.assertEqual(self._metrics(headers={})[0], 401)  # {} is explicit: no auth at all
        paired = self._pair_device()
        dev = {"authorization": f"Bearer {paired}"}
        self.assertEqual(self._metrics(headers=dev)[0], 403)
        self.assertEqual(self._metrics()[0], 200)

    def _pair_device(self) -> str:
        code, _exp = self.review.auth.create_pairing_code()
        body = json.dumps({"code": code, "device_name": "x"}).encode()
        _s, _h, out = self.review.handle(
            "POST", "/api/v1/pair", body, "", {"content-type": "application/json"}
        )
        return json.loads(out)["token"]

    def test_queue_depth_and_oldest_age_track_real_transitions(self):
        for cid in ("m-1", "m-2", "m-3"):
            self.store.accept(cid, wav_bytes())
        status, data = self._metrics()
        self.assertEqual(status, 200)
        self.assertEqual(data["jobs"]["by_state"], {"queued": 3})
        self.assertIsNotNone(data["jobs"]["oldest_queued_age_s"])

        t = 500.0
        job = self.jobs.claim(now=t)
        self.assertIsNotNone(job)
        self.assertTrue(self.jobs.complete(job, "text", now=t + 7))
        # a second job fails terminally with a hostile error message
        job2 = self.jobs.claim(now=t)
        self.assertIsNotNone(job2)
        for _ in range(2):
            j = self.jobs.claim(now=t)
            if j is None or j.capture_id != job2.capture_id:
                break
            self.jobs.fail(j, RuntimeError("SECRET-ERROR-TEXT " + HOSTILE), now=t)
        _status, data = self._metrics()
        self.assertEqual(data["jobs"]["by_state"].get("running", 0) + data["jobs"]["by_state"].get("queued", 0), 2)
        self.assertIn("done", data["jobs"]["by_state"])
        self.assertEqual(data["model"]["latency_sample"], 1)
        self.assertEqual(data["model"]["latency_p50_s"], 7.0)
        self.assertEqual(data["model"]["latency_p95_s"], 7.0)

    def test_latency_percentiles_over_many_samples(self):
        durations = [3, 3, 3, 5, 9, 20]
        t = 100.0
        for i, d in enumerate(durations):
            cid = f"lat-{i}"
            self.store.accept(cid, wav_bytes())
            job = self.jobs.claim(now=t)
            self.assertIsNotNone(job)
            self.assertTrue(self.jobs.complete(job, "x", now=t + d))
        _s, data = self._metrics()
        self.assertEqual(data["model"]["latency_sample"], 6)
        self.assertLessEqual(data["model"]["latency_p50_s"], 5)
        self.assertGreaterEqual(data["model"]["latency_p95_s"], 9)

    def test_redaction_canary_no_speech_or_secrets_in_metrics(self):
        self.store.accept("canary-1", wav_bytes())
        # drive the job to terminal failure with hostile error text
        t = 10.0
        for _ in range(2):
            job = self.jobs.claim(now=t)
            self.assertIsNotNone(job)
            self.jobs.fail(job, RuntimeError("leaky " + HOSTILE), now=t + 1)
            t += 10
        # hostile transcript exists in the store but must never reach metrics
        self.store.set_transcript("canary-1", HOSTILE, source="owner")
        _status, _h, body = self.review.handle("GET", "/api/v1/metrics", b"", "", dict(OWNER))
        raw = body.decode()
        self.assertNotIn("TOPSEEKRET", raw)
        self.assertNotIn("leaky", raw)
        # the stored job error is the exception TYPE only, never the message
        with self.store._connect() as conn:
            errors = [r["error"] for r in conn.execute(
                "SELECT error FROM transcription_jobs WHERE error IS NOT NULL")]
        for e in errors:
            self.assertNotIn("TOPSEEKRET", e)
            self.assertNotIn("leaky", e)

    def test_capture_and_auth_counts_present(self):
        self.store.accept("c-1", wav_bytes())
        self.store.delete_note("c-1")
        code, _exp = self.review.auth.create_pairing_code()
        body = json.dumps({"code": code, "device_name": "d"}).encode()
        self.review.handle("POST", "/api/v1/pair", body, "", {"content-type": "application/json"})
        _s, data = self._metrics()
        self.assertIn("received", data["captures"])
        self.assertEqual(data["captures"]["tombstoned"], 1)
        self.assertEqual(data["auth"]["devices_active"], 1)
        self.assertEqual(data["auth"]["devices_revoked"], 0)


if __name__ == "__main__":
    unittest.main()
