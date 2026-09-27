"""Disposable real-loopback coverage for the production HTTP request handler.

No model, live service, vault path, or physical device is used. Requests go
through the actual BaseHTTPRequestHandler produced by create_handler().
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from device.src.spool import DeviceSpool, SpoolUploader
from server.pass1 import Store
from server.review import create_handler


def synthetic_wav(frequency: int = 440) -> bytes:
    """A tiny deterministic, non-speech WAV used only in a temporary store."""
    del frequency  # Keep fixture bytes fixed; content is silence, not speech.
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 160)
    return out.getvalue()


class ReviewHttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="whis-http-test-")
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "store")
        self.token = "synthetic-test-owner-token"
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(self.store, self.token, runner=None)
        )
        self.addCleanup(self.httpd.server_close)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.wav = synthetic_wav()

    def _stop_server(self):
        self.httpd.shutdown()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, body: bytes = b"", *, auth=True, headers=None):
        request_headers = dict(headers or {})
        if auth:
            request_headers["Authorization"] = f"Bearer {self.token}"
        req = Request(self.base + path, data=body if method in {"POST", "PATCH"} else None,
                      headers=request_headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
        except HTTPError as error:
            with error:
                return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()

    def test_upload_replay_conflict_and_auth_are_real_http(self):
        # Break: HTTP adapter loses receipts on retry, accepts changed bytes, or leaks unauthenticated API.
        cid = "loopback-capture-001"
        status, _, payload = self.request(
            "POST", "/api/v1/captures", self.wav,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": cid},
        )
        first = json.loads(payload)
        self.assertEqual(status, 201)
        self.assertEqual(first["capture_id"], cid)
        self.assertEqual(first["sha256"], hashlib.sha256(self.wav).hexdigest())

        status, _, payload = self.request(
            "POST", "/api/v1/captures", self.wav,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": cid},
        )
        replay = json.loads(payload)
        self.assertEqual(status, 200)
        self.assertEqual(replay["receipt_id"], first["receipt_id"])

        changed_wav = synthetic_wav() + b"changed"
        status, _, payload = self.request(
            "POST", "/api/v1/captures", changed_wav,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": cid},
        )
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(payload)["error"], "conflict")

        status, _, payload = self.request("GET", f"/api/v1/captures/{cid}", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(payload)["error"], "unauthorized")

    def test_patch_correction_and_markdown_round_trip_over_http(self):
        # Break: PWA PATCH is unsupported at the socket boundary or export misses an owner edit.
        cid = "loopback-correction-001"
        status, _, _ = self.request(
            "POST", "/api/v1/captures", self.wav,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": cid},
        )
        self.assertEqual(status, 201)
        status, _, payload = self.request(
            "PATCH", f"/api/v1/notes/{cid}",
            json.dumps({"transcript": "Owner corrected synthetic note", "category": "idea"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        edited = json.loads(payload)
        self.assertEqual(edited["transcript"], "Owner corrected synthetic note")
        self.assertEqual(edited["transcript_source"], "owner")

        status, headers, markdown = self.request("GET", f"/api/v1/notes/{cid}/markdown")
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers["content-type"])
        self.assertIn(b"type: permanent-note", markdown)
        self.assertIn(b"Owner corrected synthetic note", markdown)

    def test_spool_to_host_retries_after_lost_response(self):
        # A committed host receipt must survive a lost client ACK without duplicating notes.
        spool = DeviceSpool(Path(self.temp.name) / "device")
        capture_id = "loopback-device-001"
        spool.start_capture(capture_id)
        spool.finalize_capture(capture_id, self.wav)
        uploader = SpoolUploader(spool, self.base, self.token, allow_insecure_loopback=True)

        from device.src.spool import _open_request

        def lose_first_response(request, timeout):
            with _open_request(request, timeout=timeout) as response:
                self.assertEqual(response.status, 201)
                response.read()
            raise URLError("simulated response loss after host commit")

        with patch("device.src.spool._open_request", side_effect=lose_first_response):
            first = uploader.sync_pending()
        self.assertEqual(first[0]["status"], "network_error")
        host_receipt = self.store.get(capture_id)
        self.assertIsNotNone(host_receipt)
        self.assertEqual(spool.get_record(capture_id).status, "pending")

        spool.reconcile_on_boot()
        retry = uploader.sync_pending()
        self.assertEqual(retry[0]["status"], "acknowledged")
        self.assertEqual(retry[0]["receipt"]["receipt_id"], host_receipt.receipt_id)
        self.assertEqual(spool.get_record(capture_id).receipt_id, host_receipt.receipt_id)
        self.assertEqual(len(self.store.list_notes()), 1)
        self.assertEqual((spool.synced_dir / f"{capture_id}.wav").read_bytes(), self.wav)

    def test_pwa_shell_does_not_interpolate_capture_ids_server_side(self):
        # Break: an untrusted transcript value can become executable PWA markup.
        hostile_text = '<img src=x onerror="alert(1)">'
        cid = "loopback-xss-check"
        self.store.accept(cid, self.wav)
        self.store.set_transcript(cid, hostile_text, source="owner")
        hostile_id = '<img src=x onerror="alert(1)">'
        status, _, _ = self.request(
            "POST", "/api/v1/captures", self.wav,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": hostile_id},
        )
        self.assertEqual(status, 400)
        status, _, shell = self.request("GET", "/pwa")
        self.assertEqual(status, 200)
        self.assertNotIn(hostile_text.encode(), shell)
        self.assertNotIn(hostile_id.encode(), shell)
        # Feed-derived transcript/ID values must cross an HTML-safe text boundary;
        # URL uses a separate component-encoding boundary.
        self.assertIn(b"escapeHtml(transcript)", shell)
        self.assertIn(b"escapeHtml(id)", shell)
        self.assertIn(b"encodeURIComponent(id)", shell)


if __name__ == "__main__":
    unittest.main()
