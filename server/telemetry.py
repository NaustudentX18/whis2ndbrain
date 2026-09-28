"""Device telemetry store for Whis2ndBrain host.

The Pi spool uploader POSTs a heartbeat to the host after each sync attempt.
The host stores the latest telemetry record in memory (not persisted to DB —
we want the last-seen timestamp to age naturally across restarts).

Thread safety: all mutations are protected by a threading.Lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TelemetrySnapshot:
    device_id: str | None = None
    last_seen_at: float | None = None          # Unix timestamp
    queue_depth: int | None = None             # notes waiting to sync
    battery_pct: float | None = None           # 0.0–100.0 or None = unknown
    wifi_rssi_dbm: int | None = None           # dBm or None = unknown
    firmware_version: str | None = None
    spool_errors: int | None = None

    def age_seconds(self) -> float | None:
        if self.last_seen_at is None:
            return None
        return time.time() - self.last_seen_at

    def connection_quality(self) -> str:
        """Human-readable connection quality based on last-seen age."""
        age = self.age_seconds()
        if age is None:
            return "unknown"
        if age < 30:
            return "online"
        if age < 120:
            return "recent"
        if age < 600:
            return "stale"
        return "offline"

    def to_dict(self) -> dict:
        import datetime
        last_seen_iso = (
            datetime.datetime.fromtimestamp(
                self.last_seen_at, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            if self.last_seen_at is not None
            else None
        )
        return {
            "device_id": self.device_id,
            "last_seen_at": last_seen_iso,
            "age_seconds": self.age_seconds(),
            "connection_quality": self.connection_quality(),
            "queue_depth": self.queue_depth,
            "battery_pct": self.battery_pct,
            "wifi_rssi_dbm": self.wifi_rssi_dbm,
            "firmware_version": self.firmware_version,
            "spool_errors": self.spool_errors,
        }


class TelemetryStore:
    """In-memory store for the latest device telemetry snapshot."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = TelemetrySnapshot()

    def update(self, data: dict) -> TelemetrySnapshot:
        """Merge *data* into the current snapshot and return the updated copy."""
        with self._lock:
            s = self._snapshot
            self._snapshot = TelemetrySnapshot(
                device_id=data.get("device_id", s.device_id),
                last_seen_at=time.time(),
                queue_depth=data.get("queue_depth", s.queue_depth),
                battery_pct=_float_or_none(data.get("battery_pct")),
                wifi_rssi_dbm=_int_or_none(data.get("wifi_rssi_dbm")),
                firmware_version=data.get("firmware_version", s.firmware_version),
                spool_errors=_int_or_none(data.get("spool_errors")),
            )
            return self._snapshot

    def get(self) -> TelemetrySnapshot:
        with self._lock:
            return self._snapshot


# ── SSE subscriber list ───────────────────────────────────────────────────────


class SSEBroker:
    """Broadcast server-sent events to all connected owner sessions.

    Each subscriber is a queue.SimpleQueue[str | None].
    Sending None signals the subscriber to close its connection.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list = []

    def subscribe(self):
        """Return a new subscriber queue and register it."""
        import queue
        q: queue.SimpleQueue = queue.SimpleQueue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, event: str, data: str) -> None:
        """Publish an SSE event to all connected subscribers."""
        message = f"event: {event}\ndata: {data}\n\n"
        with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put(message)
                except Exception:  # noqa: BLE001
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def close_all(self) -> None:
        with self._lock:
            for q in self._subscribers:
                q.put(None)
            self._subscribers.clear()


def _float_or_none(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
