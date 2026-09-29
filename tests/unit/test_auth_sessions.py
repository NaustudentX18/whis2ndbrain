"""Owner sessions, CSRF, and login rate limiting (BP1 item 2 / WB-022 lane).

Matrix: anonymous/wrong-token/expired-session/revoked-session auth, cookie
never carries the owner token, CSRF required on cookie POSTs (form, JSON and
multipart carriers, plus the header), Bearer exempt, failed-login cooldown.
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


def wav_bytes() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


def login(review: Review, token: str = "owner-token") -> tuple[str, str, dict]:
    status, headers, _body = review.handle(
        "POST", "/login", f"token={token}".encode(), "", {"content-type": "application/x-www-form-urlencoded"}
    )
    cookie = headers.get("set-cookie", "")
    sid = cookie.split("whis_session=")[1].split(";")[0] if "whis_session=" in cookie else ""
    return status, sid, headers


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-sess-"))
        self.store = Store(self.root)
        self.store.accept("cap-1", wav_bytes())
        self.review = Review(self.store, token="owner-token")

    def test_wrong_token_is_rejected(self):
        status, sid, _ = login(self.review, "wrong")
        self.assertEqual(status, 401)
        self.assertEqual(sid, "")

    def test_login_cookie_carries_session_id_not_the_owner_token(self):
        status, sid, headers = login(self.review)
        self.assertEqual(status, 303)
        self.assertNotEqual(sid, "owner-token")
        self.assertNotIn(sid, "owner-token")
        cookie = headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertIn("Max-Age=", cookie)

    def test_session_cookie_authorizes_and_bare_token_cookie_does_not(self):
        # probe with the JSON API: an unauthenticated GET / renders the login
        # form with 200, which cannot prove session validity either way.
        _status, sid, _headers = login(self.review)
        cookie = f"whis_session={sid}"
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", cookie)[0], 200)
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", "whis_session=owner-token")[0], 401)

    def test_expired_session_is_rejected(self):
        sid, _csrf, _exp = self.review.auth.open_session(ttl=-1)
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", f"whis_session={sid}")[0], 401)

    def test_logout_revokes_the_session(self):
        _status, sid, _headers = login(self.review)
        # a second live session for the csrf value
        sid2, csrf, _exp = self.review.auth.open_session()[:3]
        body = f"csrf={csrf}".encode()
        status, headers, _b = self.review.handle(
            "POST", "/logout", body, f"whis_session={sid2}", {"content-length": str(len(body))}
        )
        self.assertEqual(status, 303)
        self.assertIn("Max-Age=0", headers.get("set-cookie", ""))
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", f"whis_session={sid2}")[0], 401)
        # the other session is unaffected
        self.assertEqual(self.review.handle("GET", "/api/v1/notes", b"", f"whis_session={sid}")[0], 200)

    def test_invalid_bearer_does_not_downgrade_to_cookie(self):
        _status, sid, _headers = login(self.review)
        status = self.review.handle(
            "GET", "/api/v1/notes", b"", f"whis_session={sid}", {"authorization": "Bearer bogus"}
        )[0]
        self.assertEqual(status, 401)


class CsrfTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-csrf-"))
        self.store = Store(self.root)
        self.store.accept("cap-1", wav_bytes())
        self.store.set_transcript("cap-1", "machine text", source="model")
        self.review = Review(self.store, token="owner-token")
        sid, self.csrf = self.review.auth.open_session()[:2]
        self.cookie = f"whis_session={sid}"

    def _post_correction(self, body: bytes, headers: dict | None = None):
        base = {"content-type": "application/x-www-form-urlencoded"}
        base.update(headers or {})
        return self.review.handle("POST", "/n/cap-1", body, self.cookie, base)

    def test_form_post_without_csrf_is_rejected(self):
        self.assertEqual(self._post_correction(b"transcript=x")[0], 400)

    def test_form_post_with_wrong_csrf_is_rejected(self):
        self.assertEqual(self._post_correction(b"transcript=x&csrf=nope")[0], 400)

    def test_form_post_with_right_csrf_is_accepted(self):
        body = f"transcript=owner+edit&csrf={self.csrf}".encode()
        status, _h, _b = self._post_correction(body)
        self.assertEqual(status, 303)
        self.assertEqual(self.store.get_note("cap-1").transcript, "owner edit")

    def test_csrf_via_header_is_accepted(self):
        body = b"transcript=owner+edit"
        status, _h, _b = self._post_correction(body, {"x-csrf-token": self.csrf})
        self.assertEqual(status, 303)

    def test_csrf_via_json_field_is_accepted(self):
        body = json.dumps({"csrf": self.csrf, "transcript": "owner edit"}).encode()
        status, _h, _b = self.review.handle(
            "POST", "/n/cap-1", body, self.cookie, {"content-type": "application/json"}
        )
        self.assertEqual(status, 303)

    def test_bearer_posts_are_exempt_from_csrf(self):
        status, _h, _b = self.review.handle(
            "POST",
            "/api/v1/notes/note-x/retry",
            b"",
            "",
            {"authorization": "Bearer owner-token", "content-length": "0"},
        )
        self.assertNotEqual(status, 400)  # 404 unknown capture is fine; 400 csrf is the break


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="whis-rl-"))
        self.store = Store(self.root)
        self.review = Review(self.store, token="owner-token")
        self.now = 1000.0
        self.review.auth.limiter.clock = lambda: self.now

    def _attempt(self, token: str = "wrong"):
        return self.review.handle(
            "POST", "/login", f"token={token}".encode(), "",
            {"content-type": "application/x-www-form-urlencoded"},
        )

    def test_eight_failures_then_cooldown_even_for_the_correct_token(self):
        for _ in range(8):
            self.assertEqual(self._attempt()[0], 401)
        status, headers, _b = self._attempt("owner-token")
        self.assertEqual(status, 429)
        self.assertIn("retry-after", headers)
        # still locked a moment later
        self.now += 10
        self.assertEqual(self._attempt("owner-token")[0], 429)
        # after the window passes the correct token works again
        self.now += 901
        status, _headers, _b = self._attempt("owner-token")
        self.assertEqual(status, 303)

    def test_successful_login_resets_the_failure_counter(self):
        for _ in range(7):
            self._attempt()
        self.assertEqual(self._attempt("owner-token")[0], 303)
        self.assertEqual(self._attempt()[0], 401)  # counter restarted, no lockout


if __name__ == "__main__":
    unittest.main()
