"""Review page behavior. Each test names the break it catches."""

import json
import tempfile
import threading
import time
import unittest
import wave
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from server.jobs import Jobs, run_once
from server.pass1 import Store, purge_expired
from server.review import Review


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-review-"))
        self.store = Store(self.root)
        self.body = wav_bytes()
        self.store.accept("cap-1", self.body)
        self.store.set_transcript("cap-1", "<script>secret</script>", source="model")
        self.review = Review(self.store, token="owner-token")

    def test_missing_token_does_not_return_the_recording_or_transcript(self):
        # Break: a tailnet visitor can read audio or speech without the owner token.
        status, _headers, body = self.review.handle("GET", "/n/cap-1/audio", b"", "")
        self.assertEqual(status, 401)
        self.assertNotIn(self.body, body)
        page = self.review.handle("GET", "/", b"", "")[2]
        self.assertNotIn(b"secret", page)
        self.assertNotIn(b"<script>", page)

    def test_correction_replaces_the_shown_transcript_and_audio_is_the_accepted_wav(self):
        # Break: save does not stick, or playback returns a different file.
        cookie = "whis_session=owner-token"
        status, _headers, audio = self.review.handle("GET", "/n/cap-1/audio", b"", cookie)
        self.assertEqual(status, 200)
        self.assertEqual(audio, self.body)
        status, _headers, _page = self.review.handle(
            "POST",
            "/n/cap-1",
            b"transcript=owner+said+hello",
            cookie,
        )
        self.assertEqual(status, 303)
        note = self.store.get_note("cap-1")
        self.assertEqual(note.transcript, "owner said hello")
        self.assertEqual(note.transcript_source, "owner")
        shown = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertIn(b"owner said hello", shown)
        self.assertNotIn(b"secret", shown)

    def test_bad_id_is_not_a_file_read(self):
        # Break: a capture id can escape the audio directory.
        cookie = "whis_session=owner-token"
        for path in ("/n/..%2F..%2Fetc%2Fpasswd/audio", "/n/..%2Fsecret/audio", "/n/nope/audio"):
            status, _headers, body = self.review.handle("GET", path, b"", cookie)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"root:", body)

    def test_saved_correction_keeps_the_original_audio_and_says_so(self):
        # Break: a text correction replaces the recording, or the page hides that it did not.
        cookie = "whis_session=owner-token"
        self.review.handle("POST", "/n/cap-1", b"transcript=owner+said+hello", cookie)
        shown = self.review.handle("GET", "/n/cap-1?saved=1", b"", cookie)[2]
        self.assertIn(b"Original recording", shown)
        self.assertIn(b"owner said hello", shown)
        self.assertEqual(self.review.handle("GET", "/n/cap-1/audio", b"", cookie)[2], self.body)

    def test_upload_adds_a_capture_and_does_not_replace_an_existing_one(self):
        # Break: a new phone upload overwrites the note already on the page.
        cookie = "whis_session=owner-token"
        fresh_bytes = bytearray(wav_bytes())
        fresh_bytes[-1] ^= 1
        fresh = bytes(fresh_bytes)
        boundary = "bound"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="audio"; filename="note.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + fresh + f"\r\n--{boundary}--\r\n".encode()
        status, headers, _page = self.review.handle(
            "POST",
            "/upload",
            body,
            cookie,
            {"content-type": f"multipart/form-data; boundary={boundary}"},
        )
        self.assertEqual(status, 303)
        new_id = headers["location"].rsplit("/", 1)[-1]
        self.assertNotEqual(new_id, "cap-1")
        self.assertEqual(self.store.audio_path("cap-1").read_bytes(), self.body)
        self.assertEqual(self.store.audio_path(new_id).read_bytes(), fresh)
        anon = self.review.handle("POST", "/upload", body, "")
        self.assertEqual(anon[0], 401)

    def _upload(self, body: bytes, cookie: str):
        boundary = "bound"
        payload = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="audio"; filename="note.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode() + body + f"\r\n--{boundary}--\r\n".encode()
        return self.review.handle(
            "POST",
            "/upload",
            payload,
            cookie,
            {"content-type": f"multipart/form-data; boundary={boundary}"},
        )

    def test_upload_page_says_transcribing_until_the_runner_finishes(self):
        # Break: the note page hides that transcription is still running.
        cookie = "whis_session=owner-token"
        gate = threading.Event()

        def block(path):
            gate.wait(5)
            return "machine text"

        status, headers, _body = self._upload(wav_bytes(), cookie)
        self.assertEqual(status, 303)
        new_id = headers["location"].rsplit("/", 1)[-1]
        self.assertEqual(self.store.get_note(new_id).status, "received")
        worker = threading.Thread(target=run_once, args=(self.store, block, Jobs(self.store)))
        worker.start()
        for _ in range(50):
            if self.store.get_note(new_id).status == "transcribing":
                break
            time.sleep(0.01)
        self.assertEqual(self.store.get_note(new_id).status, "transcribing")
        page = self.review.handle("GET", f"/n/{new_id}", b"", cookie)[2]
        self.assertIn(b"Transcribing.", page)
        self.assertIn(b'<meta http-equiv="refresh" content="2">', page)
        gate.set()
        worker.join(timeout=5)
        for _ in range(50):
            if self.store.get_note(new_id).status != "transcribing":
                break
            time.sleep(0.05)
        self.assertEqual(self.store.get_note(new_id).status, "transcribed")

    def test_received_note_does_not_refresh(self):
        # Break: a note that is not transcribing reloads forever.
        cookie = "whis_session=owner-token"
        page = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertNotIn(b"http-equiv=\"refresh\"", page)
        self.assertNotIn(b"Transcribing.", page)

    def test_not_transcribed_page_says_so_and_does_not_refresh(self):
        # Break: a failed transcript is a blank page, or the page keeps reloading.
        cookie = "whis_session=owner-token"
        self.store.mark_not_transcribed("cap-1")
        page = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertIn(b"Not transcribed.", page)
        self.assertNotIn(b'http-equiv="refresh"', page)

    def test_purged_note_keeps_the_correction_and_hides_the_player(self):
        # Break: the page still offers playback, or a correction POST dies after the hold ends.
        cookie = "whis_session=owner-token"
        now = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE captures SET received_at = ?, transcript = ?, transcript_source = ?, status = ? WHERE capture_id = ?",
                ("2026-09-19T12:00:00Z", "owner said hello", "owner", "reviewed", "cap-1"),
            )
        purge_expired(self.store, now)
        page = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertIn(b"Audio hold ended. The note is kept.", page)
        self.assertNotIn(b"<audio", page)
        saved = self.review.handle("POST", "/n/cap-1", b"transcript=still+mine", cookie)
        self.assertEqual(saved[0], 303)
        self.assertEqual(self.store.get_note("cap-1").transcript, "still mine")
        audio = self.review.handle("GET", "/n/cap-1/audio", b"", cookie)
        self.assertEqual(audio[0], 404)

    def test_opening_an_old_note_does_not_purge_it(self):
        # Break: the page deletes audio on GET.
        cookie = "whis_session=owner-token"
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE captures SET received_at = ? WHERE capture_id = 'cap-1'",
                ("2020-01-01T00:00:00Z",),
            )
        page = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertIsNone(self.store.get_note("cap-1").audio_purged_at)
        self.assertTrue(self.store.audio_path("cap-1").is_file())
        self.assertIn(b"Audio held until 2020-01-08T00:00:00Z.", page)

    def test_missing_file_does_not_claim_the_hold_ended(self):
        # Break: a missing WAV is described as an ended hold.
        cookie = "whis_session=owner-token"
        self.store.audio_path("cap-1").unlink()
        page = self.review.handle("GET", "/n/cap-1", b"", cookie)[2]
        self.assertNotIn(b"Audio hold ended", page)
        self.assertNotIn(b"<audio", page)
        audio = self.review.handle("GET", "/n/cap-1/audio", b"", cookie)
        self.assertEqual(audio[0], 404)

    def test_health_endpoints_are_public_and_return_json(self):
        # Break: health check requires authentication or is broken.
        status, headers, body = self.review.handle("GET", "/api/v1/health/live", b"", "")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body.decode()), {"status": "live"})

        status, headers, body = self.review.handle("GET", "/api/v1/health/ready", b"", "")
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body.decode()), {"status": "ready"})

    def test_api_captures_requires_auth(self):
        # Break: unauthenticated callers can ingest audio via API.
        status, headers, _body = self.review.handle(
            "POST",
            "/api/v1/captures",
            self.body,
            "",
            headers={"content-type": "audio/wav"},
        )
        self.assertEqual(status, 401)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")

    def test_api_captures_bearer_auth_and_replay_idempotency(self):
        # Break: Bearer token is rejected, or duplicate upload creates duplicate/error.
        auth_header = {"authorization": "Bearer owner-token", "content-type": "audio/wav", "x-capture-id": "api-cap-1"}
        status, _headers, body = self.review.handle(
            "POST",
            "/api/v1/captures",
            self.body,
            "",
            headers=auth_header,
        )
        self.assertEqual(status, 201)
        resp1 = json.loads(body.decode())
        self.assertEqual(resp1["capture_id"], "api-cap-1")
        self.assertEqual(resp1["byte_count"], len(self.body))
        self.assertEqual(resp1["status"], "received")

        # Same replay returns 200 and identical receipt
        status2, _headers2, body2 = self.review.handle(
            "POST",
            "/api/v1/captures",
            self.body,
            "",
            headers=auth_header,
        )
        self.assertEqual(status2, 200)
        resp2 = json.loads(body2.decode())
        self.assertEqual(resp1["receipt_id"], resp2["receipt_id"])
        self.assertEqual(resp1["sha256"], resp2["sha256"])

        # Replay with different audio bytes returns 409 Conflict
        other_wav = wav_bytes() + b"\x00" * 4  # different bytes
        status3, _headers3, _body3 = self.review.handle(
            "POST",
            "/api/v1/captures",
            other_wav,
            "",
            headers=auth_header,
        )
        self.assertEqual(status3, 409)

    def test_api_captures_get_status(self):
        # Break: status reconciliation endpoint fails or leaks non-existent captures.
        auth_header = {"authorization": "Bearer owner-token"}
        status, _headers, body = self.review.handle(
            "GET",
            "/api/v1/captures/cap-1",
            b"",
            "",
            headers=auth_header,
        )
        self.assertEqual(status, 200)
        resp = json.loads(body.decode())
        self.assertEqual(resp["capture_id"], "cap-1")
        self.assertEqual(resp["byte_count"], len(self.body))

        status_nf, _, _ = self.review.handle(
            "GET",
            "/api/v1/captures/non-existent-cap",
            b"",
            "",
            headers=auth_header,
        )
        self.assertEqual(status_nf, 404)


if __name__ == "__main__":
    unittest.main()
