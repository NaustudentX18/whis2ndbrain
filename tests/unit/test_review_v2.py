"""Tests for the new settings, telemetry, heartbeat and SSE endpoints in review.py."""

import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from server.pass1 import Store
from server.review import Review


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


def make_review(root: Path) -> Review:
    store = Store(root)
    return Review(store, token="test-token")


TOKEN_COOKIE = "whis_session=test-token"
BEARER = {"authorization": "Bearer test-token"}


class SettingsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-settings-"))
        self.review = make_review(self.root)

    def _get(self, path, cookie=TOKEN_COOKIE, headers=None):
        return self.review.handle("GET", path, b"", cookie, headers or BEARER)

    def _patch(self, path, body: dict, cookie=TOKEN_COOKIE):
        data = json.dumps(body).encode()
        return self.review.handle("PATCH", path, data, cookie, {
            **BEARER,
            "content-type": "application/json",
            "content-length": str(len(data)),
        })

    def test_get_settings_returns_defaults(self):
        status, _, body = self._get("/api/v1/settings")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["retention_hours"], 168)
        self.assertFalse(data["encryption_enabled"])
        self.assertFalse(data["drive_enabled"])

    def test_get_settings_requires_auth(self):
        status, _, _ = self.review.handle("GET", "/api/v1/settings", b"", "", {})
        self.assertEqual(status, 401)

    def test_patch_settings_updates_field(self):
        status, _, body = self._patch("/api/v1/settings", {"retention_hours": 48})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["retention_hours"], 48)

    def test_patch_settings_persists_to_disk(self):
        self._patch("/api/v1/settings", {"retention_hours": 72})
        # Create a fresh Review from same root — should read persisted value
        review2 = make_review(self.root)
        _, _, body = review2.handle("GET", "/api/v1/settings", b"", TOKEN_COOKIE, BEARER)
        self.assertEqual(json.loads(body)["retention_hours"], 72)

    def test_patch_unknown_field_returns_400(self):
        status, _, body = self._patch("/api/v1/settings", {"does_not_exist": True})
        self.assertEqual(status, 400)
        self.assertIn("unknown", json.loads(body)["error"])

    def test_patch_invalid_retention_returns_400(self):
        status, _, _body = self._patch("/api/v1/settings", {"retention_hours": 0})
        self.assertEqual(status, 400)

    def test_patch_relative_vault_path_returns_400(self):
        status, _, _body = self._patch("/api/v1/settings", {"vault_export_path": "relative/path"})
        self.assertEqual(status, 400)

    def test_patch_absolute_vault_path_accepted(self):
        status, _, body = self._patch("/api/v1/settings", {"vault_export_path": "/tmp/inbox"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["vault_export_path"], "/tmp/inbox")

    def test_patch_empty_body_returns_400(self):
        status, _, _ = self.review.handle("PATCH", "/api/v1/settings", b"{}", TOKEN_COOKIE, {
            **BEARER,
            "content-type": "application/json",
            "content-length": "2",
        })
        self.assertEqual(status, 400)

    def test_patch_invalid_json_returns_400(self):
        status, _, _ = self.review.handle("PATCH", "/api/v1/settings", b"not-json", TOKEN_COOKIE, {
            **BEARER,
            "content-type": "application/json",
            "content-length": "8",
        })
        self.assertEqual(status, 400)

    def test_settings_method_not_allowed(self):
        status, _, _ = self.review.handle("DELETE", "/api/v1/settings", b"", TOKEN_COOKIE, BEARER)
        self.assertEqual(status, 405)


class TelemetryEndpointTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-telem-"))
        self.review = make_review(self.root)

    def _get(self, path):
        return self.review.handle("GET", path, b"", TOKEN_COOKIE, BEARER)

    def _post(self, path, body: dict):
        data = json.dumps(body).encode()
        return self.review.handle("POST", path, data, TOKEN_COOKIE, {
            **BEARER,
            "content-type": "application/json",
            "content-length": str(len(data)),
        })

    def test_get_telemetry_returns_empty_initially(self):
        status, _, body = self._get("/api/v1/device/telemetry")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsNone(data["device_id"])
        self.assertEqual(data["connection_quality"], "unknown")

    def test_get_telemetry_requires_auth(self):
        status, _, _ = self.review.handle("GET", "/api/v1/device/telemetry", b"", "", {})
        self.assertEqual(status, 401)

    def test_heartbeat_updates_telemetry(self):
        self._post("/api/v1/device/heartbeat", {"device_id": "pi-001", "queue_depth": 2})
        _, _, body = self._get("/api/v1/device/telemetry")
        data = json.loads(body)
        self.assertEqual(data["device_id"], "pi-001")
        self.assertEqual(data["queue_depth"], 2)
        self.assertEqual(data["connection_quality"], "online")

    def test_heartbeat_returns_200_with_snapshot(self):
        status, _, body = self._post("/api/v1/device/heartbeat", {"battery_pct": 85.5})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["battery_pct"], 85.5)

    def test_heartbeat_empty_body_still_updates_last_seen(self):
        # Pi can send an empty POST as a keepalive
        status, _, body = self.review.handle(
            "POST", "/api/v1/device/heartbeat", b"", TOKEN_COOKIE,
            {**BEARER, "content-length": "0"}
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsNotNone(data["last_seen_at"])

    def test_heartbeat_invalid_json_returns_400(self):
        status, _, _ = self.review.handle(
            "POST", "/api/v1/device/heartbeat", b"bad-json", TOKEN_COOKIE,
            {**BEARER, "content-type": "application/json", "content-length": "8"}
        )
        self.assertEqual(status, 400)

    def test_heartbeat_publishes_sse_event(self):
        """A heartbeat should fan out a device_heartbeat event to SSE subscribers."""
        q = self.review.sse_broker.subscribe()
        self._post("/api/v1/device/heartbeat", {"device_id": "pi-001"})
        msg = q.get_nowait()
        self.assertIn("device_heartbeat", msg)

    def test_heartbeat_requires_auth(self):
        status, _, _ = self.review.handle("POST", "/api/v1/device/heartbeat", b"", "", {})
        self.assertEqual(status, 401)


class SSEEndpointTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-sse-"))
        self.review = make_review(self.root)

    def test_sse_returns_200_and_event_stream_content_type(self):
        # Close the broker immediately so the generator terminates
        self.review.sse_broker.close_all()
        status, headers, _payload = self.review.handle(
            "GET", "/api/v1/events", b"", TOKEN_COOKIE, BEARER
        )
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers.get("content-type", ""))

    def test_sse_requires_auth(self):
        status, _, _ = self.review.handle("GET", "/api/v1/events", b"", "", {})
        self.assertEqual(status, 401)

    def test_sse_generator_sends_initial_ping(self):
        import types
        self.review.sse_broker.close_all()
        _, _, payload = self.review.handle(
            "GET", "/api/v1/events", b"", TOKEN_COOKIE, BEARER
        )
        self.assertIsInstance(payload, types.GeneratorType)
        # First chunk is the ping
        first = next(payload)
        self.assertIn(b"ping", first)
        payload.close()
