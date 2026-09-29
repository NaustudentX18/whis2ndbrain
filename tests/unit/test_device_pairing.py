"""Pair-once device credentials and their ingest-only scope (BP1 item 2).

Matrix: pairing code lifecycle (create/redeem/reuse/expiry), device upload,
device denial on every review surface, rotate (old dies, id survives),
revoke, and device exclusion from owner management APIs.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from server.pass1 import Store
from server.review import Review

OWNER = {"authorization": "Bearer owner-token"}


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


class PairingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-pair-"))
        self.store = Store(self.root)
        self.review = Review(self.store, token="owner-token")
        self.body = wav_bytes()

    def _new_code(self, ttl=None):
        if ttl is None:
            status, _h, b = self.review.handle("POST", "/api/v1/pairing-codes", b"", "", dict(OWNER))
            self.assertEqual(status, 201)
            return json.loads(b)["code"]
        return self.review.auth.create_pairing_code(ttl=ttl)[0]

    def _pair(self, code: str, name: str = "pi-zero"):
        body = json.dumps({"code": code, "device_name": name}).encode()
        return self.review.handle(
            "POST", "/api/v1/pair", body, "", {"content-type": "application/json"}
        )

    def _device_upload(self, token: str):
        return self.review.handle(
            "POST", "/api/v1/captures", self.body, "",
            {**OWNER, "authorization": f"Bearer {token}", "content-type": "audio/wav", "x-capture-id": "dev-cap-1"},
        )

    def test_pair_redeem_and_upload_roundtrip(self):
        code = self._new_code()
        status, _h, body = self._pair(code)
        self.assertEqual(status, 201)
        cred = json.loads(body)
        self.assertTrue(cred["device_id"].startswith("dev_"))
        self.assertTrue(cred["token"].startswith("wdev_"))
        status, _h, _b = self._device_upload(cred["token"])
        self.assertEqual(status, 201)
        self.assertEqual(self.store.get_note("dev-cap-1").status, "received")

    def test_wrong_code_is_rejected(self):
        self._new_code()
        self.assertEqual(self._pair("0000000000")[0], 401)

    def test_code_is_single_use(self):
        code = self._new_code()
        self.assertEqual(self._pair(code)[0], 201)
        self.assertEqual(self._pair(code)[0], 401)

    def test_expired_code_is_rejected(self):
        code = self._new_code(ttl=-1)
        self.assertEqual(self._pair(code)[0], 401)

    def test_anonymous_cannot_pair_or_upload(self):
        self.assertEqual(self._pair("whatever")[0], 401)
        status = self.review.handle(
            "POST", "/api/v1/captures", self.body, "", {"content-type": "audio/wav"}
        )[0]
        self.assertEqual(status, 401)

    def test_device_credentials_are_ingest_only(self):
        cred = json.loads(self._pair(self._new_code())[2])
        auth = {"authorization": f"Bearer {cred['token']}"}
        self.assertEqual(self._device_upload(cred["token"])[0], 201)
        # the whole review surface is closed to devices
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", "", dict(auth))[0], 403)
        self.assertEqual(self.review.handle("GET", "/n/dev-cap-1/audio", b"", "", dict(auth))[0], 403)
        self.assertEqual(self.review.handle("GET", "/", b"", "", dict(auth))[0], 403)
        self.assertEqual(self.review.handle("GET", "/api/v1/devices", b"", "", dict(auth))[0], 403)
        self.assertEqual(
            self.review.handle("POST", "/api/v1/devices/dev-x/revoke", b"", "", dict(auth))[0], 403
        )
        # heartbeat is allowed: it is device telemetry, not review data
        status, _h, _b = self.review.handle(
            "POST", "/api/v1/device/heartbeat", b"{}", "", {**auth, "content-type": "application/json"}
        )
        self.assertEqual(status, 200)

    def test_revoke_kills_the_device(self):
        cred = json.loads(self._pair(self._new_code())[2])
        self.assertEqual(self._device_upload(cred["token"])[0], 201)
        status, _h, _b = self.review.handle(
            "POST", f"/api/v1/devices/{cred['device_id']}/revoke", b"", "", dict(OWNER)
        )
        self.assertEqual(status, 204)
        self.assertEqual(self._device_upload(cred["token"])[0], 401)
        # revoking twice reports not-found
        self.assertEqual(
            self.review.handle("POST", f"/api/v1/devices/{cred['device_id']}/revoke", b"", "", dict(OWNER))[0],
            404,
        )

    def test_rotate_keeps_device_id_and_kills_old_token(self):
        cred = json.loads(self._pair(self._new_code())[2])
        status, _h, body = self.review.handle(
            "POST", f"/api/v1/devices/{cred['device_id']}/rotate", b"", "", dict(OWNER)
        )
        self.assertEqual(status, 200)
        new = json.loads(body)
        self.assertEqual(new["device_id"], cred["device_id"])
        self.assertNotEqual(new["token"], cred["token"])
        self.assertEqual(self._device_upload(cred["token"])[0], 401)
        self.assertEqual(self._device_upload(new["token"])[0], 201)

    def test_devices_list_shows_pairing_state(self):
        cred = json.loads(self._pair(self._new_code(), name="bench pi")[2])
        status, _h, body = self.review.handle("GET", "/api/v1/devices", b"", "", dict(OWNER))
        self.assertEqual(status, 200)
        items = json.loads(body)["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "bench pi")
        self.assertIsNone(items[0]["revoked_at"])
        self.assertEqual(items[0]["device_id"], cred["device_id"])

    def test_owner_bearer_upload_still_works_alongside_devices(self):
        status = self.review.handle(
            "POST", "/api/v1/captures", self.body, "",
            {**OWNER, "content-type": "audio/wav", "x-capture-id": "owner-cap"},
        )[0]
        self.assertEqual(status, 201)

    def test_pair_attempts_share_the_login_rate_limit(self):
        self.review.auth.limiter.clock = lambda: 1000.0
        for _ in range(8):
            self._pair("bogus-code")
        code = self._new_code()
        self.assertEqual(self._pair(code)[0], 429)


if __name__ == "__main__":
    unittest.main()
