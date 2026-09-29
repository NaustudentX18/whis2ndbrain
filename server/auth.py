"""Pair-once device credentials, owner sessions, and login rate limiting.

BP1 item 2 (WB-022 lane). Design facts:

- The owner token never rides in a cookie. Login opens a server-side session
  and the cookie carries only a random session id; sessions expire and can be
  revoked. Each session carries its own CSRF token for cookie-authenticated
  HTML form POSTs.
- Devices pair once via a short-lived single-use pairing code the owner
  generates in the review UI. The device receives ``device_id`` + ``token``
  exactly once; only a SHA-256 digest of the token is stored. Device tokens
  authorize capture upload and heartbeat only - never the review surface.
- Rotate/revoke a device at any time; rotation keeps the ``device_id`` and
  invalidates the old token atomically.
- All secret comparisons are constant-time. Failed logins are rate limited
  globally (single-owner host: no per-peer addressing inside ``handle()``;
  the limit is on failures, so it cannot lock out a correct token except
  during the cooldown window itself).

This module owns its sqlite tables in the shared review database.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

SESSION_TTL_SECONDS = 24 * 3600
PAIRING_CODE_TTL_SECONDS = 600
LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW_SECONDS = 900
_NAME_RE = re.compile(r"[\x00-\x1f\x7f]")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    """Who is calling: an owner session, the owner bearer token, or a device."""

    kind: str  # "owner_session" | "owner_bearer" | "device"
    session: sqlite3.Row | None = None
    device: sqlite3.Row | None = None

    @property
    def is_owner(self) -> bool:
        return self.kind in ("owner_session", "owner_bearer")

    @property
    def via_session(self) -> bool:
        return self.kind == "owner_session"


class LoginLimiter:
    """Global sliding-window limiter over failed logins (and pair attempts)."""

    def __init__(
        self,
        max_failures: int = LOGIN_MAX_FAILURES,
        window: float = LOGIN_WINDOW_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.max_failures = max_failures
        self.window = window
        self.clock = clock
        self._failures: deque[float] = deque()
        self._lock = threading.Lock()

    def cooldown_remaining(self) -> float:
        now = self.clock()
        with self._lock:
            while self._failures and now - self._failures[0] > self.window:
                self._failures.popleft()
            if len(self._failures) >= self.max_failures:
                return max(0.0, self.window - (now - self._failures[0]))
        return 0.0

    def record_failure(self) -> None:
        now = self.clock()
        with self._lock:
            self._failures.append(now)
            while self._failures and now - self._failures[0] > self.window:
                self._failures.popleft()

    def record_success(self) -> None:
        with self._lock:
            self._failures.clear()


class AuthStore:
    """Devices, pairing codes, and owner sessions in the review database."""

    def __init__(self, store, owner_token: str) -> None:
        if not owner_token:
            raise ValueError("owner token is required")
        self.store = store
        self._owner_hash = _hash(owner_token)
        self.limiter = LoginLimiter()
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS auth_devices (
                       device_id TEXT PRIMARY KEY,
                       name TEXT NOT NULL,
                       token_hash TEXT NOT NULL UNIQUE,
                       created_at REAL NOT NULL,
                       last_seen_at REAL,
                       rotated_at REAL,
                       revoked_at REAL
                   )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS auth_pairing_codes (
                       code_hash TEXT PRIMARY KEY,
                       created_at REAL NOT NULL,
                       expires_at REAL NOT NULL,
                       used_at REAL
                   )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS auth_sessions (
                       sid_hash TEXT PRIMARY KEY,
                       csrf TEXT NOT NULL,
                       created_at REAL NOT NULL,
                       expires_at REAL NOT NULL,
                       revoked_at REAL
                   )"""
            )

    # The store connection is the review database; same pattern as jobs.py.
    def _connect(self):
        return self.store._connect()

    # ── owner ──────────────────────────────────────────────────────────

    def owner_token_matches(self, given: str) -> bool:
        return hmac.compare_digest(_hash(given), self._owner_hash)

    def open_session(
        self, *, ttl: float = SESSION_TTL_SECONDS, now: float | None = None
    ) -> tuple[str, str, float]:
        """Create a session; returns (sid, csrf, expires_at). The sid and csrf
        plaintext values are returned exactly once - only digests are stored."""
        now = time.time() if now is None else now
        sid = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        expires = now + ttl
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_sessions (sid_hash, csrf, created_at, expires_at) VALUES (?,?,?,?)",
                (_hash(sid), csrf, now, expires),
            )
            # opportunistic prune of long-dead rows
            conn.execute("DELETE FROM auth_sessions WHERE expires_at < ?", (now - 3600,))
        return sid, csrf, expires

    def get_session(self, sid: str, *, now: float | None = None):
        now = time.time() if now is None else now
        if not sid:
            return None
        with self._connect() as conn:
            return _session_row(conn, sid, now)

    def revoke_session(self, sid: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if not sid:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE sid_hash = ? AND revoked_at IS NULL",
                (now, _hash(sid)),
            )

    # ── pairing ────────────────────────────────────────────────────────

    def create_pairing_code(
        self, *, ttl: float = PAIRING_CODE_TTL_SECONDS, now: float | None = None
    ) -> tuple[str, float]:
        """Generate a single-use pairing code; plaintext shown once."""
        now = time.time() if now is None else now
        code = secrets.token_hex(5)
        expires = now + ttl
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_pairing_codes (code_hash, created_at, expires_at) VALUES (?,?,?)",
                (_hash(code), now, expires),
            )
            conn.execute("DELETE FROM auth_pairing_codes WHERE expires_at < ?", (now - 3600,))
        return code, expires

    def redeem_pairing_code(
        self, code: str, device_name: str, *, now: float | None = None
    ) -> tuple[str, str] | None:
        """Redeem a pairing code once for a fresh device credential.

        Returns (device_id, token) exactly once, or None when the code is
        unknown, expired, or already used.
        """
        now = time.time() if now is None else now
        name = _NAME_RE.sub("", device_name).strip()[:64] or "unnamed device"
        code_hash = _hash(code)
        token = "wdev_" + secrets.token_urlsafe(24)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT expires_at, used_at FROM auth_pairing_codes WHERE code_hash = ?",
                (code_hash,),
            ).fetchone()
            if row is None or row["used_at"] is not None or row["expires_at"] < now:
                conn.execute("ROLLBACK")
                return None
            conn.execute(
                "UPDATE auth_pairing_codes SET used_at = ? WHERE code_hash = ? AND used_at IS NULL",
                (now, code_hash),
            )
            device_id = "dev_" + secrets.token_hex(6)
            conn.execute(
                """INSERT INTO auth_devices (device_id, name, token_hash, created_at)
                   VALUES (?,?,?,?)""",
                (device_id, name, _hash(token), now),
            )
        return device_id, token

    # ── devices ────────────────────────────────────────────────────────

    def authenticate_device(self, token: str, *, now: float | None = None):
        """Return the active device row for a valid token, else None.

        Updates last_seen_at at most once per minute per device to avoid a
        write on every request.
        """
        now = time.time() if now is None else now
        if not token:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM auth_devices WHERE token_hash = ? AND revoked_at IS NULL",
                (_hash(token),),
            ).fetchone()
            if row is None:
                return None
            if row["last_seen_at"] is None or now - row["last_seen_at"] > 60:
                conn.execute(
                    "UPDATE auth_devices SET last_seen_at = ? WHERE device_id = ?",
                    (now, row["device_id"]),
                )
                row = conn.execute(
                    "SELECT * FROM auth_devices WHERE device_id = ?", (row["device_id"],)
                ).fetchone()
            return row

    def list_devices(self):
        with self._connect() as conn:
            return conn.execute(
                "SELECT device_id, name, created_at, last_seen_at, rotated_at, revoked_at "
                "FROM auth_devices ORDER BY created_at DESC"
            ).fetchall()

    def revoke_device(self, device_id: str, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE auth_devices SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL",
                (now, device_id),
            )
            return cur.rowcount > 0

    def rotate_device(self, device_id: str, *, now: float | None = None) -> str | None:
        """Issue a fresh token for a device; the old token dies atomically.

        Returns the new plaintext token exactly once, or None if the device is
        unknown or already revoked.
        """
        now = time.time() if now is None else now
        token = "wdev_" + secrets.token_urlsafe(24)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                "UPDATE auth_devices SET token_hash = ?, rotated_at = ? "
                "WHERE device_id = ? AND revoked_at IS NULL",
                (_hash(token), now, device_id),
            )
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                return None
        return token


def _session_row(conn, sid: str, now: float):
    row = conn.execute(
        """SELECT sid_hash, csrf, created_at, expires_at, revoked_at
           FROM auth_sessions WHERE sid_hash = ?""",
        (_hash(sid),),
    ).fetchone()
    if row is None or row["revoked_at"] is not None or row["expires_at"] < now:
        return None
    return row
