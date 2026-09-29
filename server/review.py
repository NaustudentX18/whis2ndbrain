"""One-owner review page. Audio and transcripts stay behind the owner token."""

from __future__ import annotations

import html
import json
import queue
import sqlite3
import threading
import uuid
from email import message_from_bytes
from email.policy import default
from pathlib import Path
from urllib.parse import parse_qs, unquote

from contracts.schemas import CaptureManifest, Category, SchemaValidationError, Urgency
from server.pass1 import (
    HOLD,
    MAX_WAV_BYTES,
    STAMP,
    Conflict,
    Rejected,
    Store,
    _is_wav,
    _parse_stamp,
)
from server.pwa import get_manifest_json, get_pwa_html, get_service_worker_js
from server.settings import SettingsStore
from server.telemetry import SSEBroker, TelemetryStore

COOKIE = "whis_session"
MAX_PATCH_BYTES = 256 * 1024
MAX_MULTIPART_OVERHEAD = 64 * 1024


class Review:
    def __init__(
        self,
        store: Store,
        token: str,
        runner=None,
        settings_store: SettingsStore | None = None,
        telemetry_store: TelemetryStore | None = None,
        sse_broker: SSEBroker | None = None,
        jobs=None,
    ):
        if not token:
            raise ValueError("owner token is required")
        self.store = store
        self.token = token
        self.runner = runner
        self.settings_store = settings_store or SettingsStore(store.root)
        self.telemetry_store = telemetry_store or TelemetryStore()
        self.sse_broker = sse_broker or SSEBroker()
        self.jobs = jobs


    def handle(self, method: str, path: str, body: bytes, cookie: str, headers=None):
        raw = path
        path = unquote(raw.split("?", 1)[0])
        saved = "saved=1" in raw
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        if method in ("POST", "PATCH"):
            length = headers.get("content-length")
            if length is not None:
                if len(length) > 12 or not length.isascii() or not length.isdecimal():
                    return 400, _json(), b'{"error":"invalid content length"}'
                if int(length) != len(body):
                    return 400, _json(), b'{"error":"content length mismatch"}'
                maximum = MAX_PATCH_BYTES if method == "PATCH" else MAX_WAV_BYTES + MAX_MULTIPART_OVERHEAD
                if int(length) > maximum:
                    return 413, _json(), b'{"error":"request too large"}'
            elif len(body) > (MAX_PATCH_BYTES if method == "PATCH" else MAX_WAV_BYTES + MAX_MULTIPART_OVERHEAD):
                return 413, _json(), b'{"error":"request too large"}'
        if method == "GET" and path == "/api/v1/health/live":
            return 200, _json(), b'{"status":"live"}'
        if method == "GET" and path == "/api/v1/health/ready":
            try:
                with self.store._connect() as conn:
                    conn.execute("SELECT 1").fetchone()
                return 200, _json(), b'{"status":"ready"}'
            except (sqlite3.Error, OSError):
                return 503, _json(), b'{"status":"unready"}'

        if method == "GET" and path == "/manifest.json":
            return 200, {"content-type": "application/manifest+json; charset=utf-8"}, get_manifest_json()
        if method == "GET" and path == "/sw.js":
            return 200, {"content-type": "application/javascript; charset=utf-8"}, get_service_worker_js()
        if method == "GET" and path == "/brand/mark.svg":
            mark_path = Path(__file__).resolve().parent.parent / "brand" / "mark.svg"
            if mark_path.is_file():
                return 200, {"content-type": "image/svg+xml"}, mark_path.read_bytes()
            return 404, _html(), b"not found"

        if method == "POST" and path == "/login":
            return self._login(body)
        if not self._is_authorized(cookie, headers):
            if path.startswith("/api/"):
                return 401, _json(), b'{"error":"unauthorized"}'
            if method == "GET" and path in ("/", "/pwa"):
                return 200, _html(), _page(_login_form())
            return 401, _html(), b"sign in required"

        if method == "GET" and path == "/pwa":
            return 200, _html(), get_pwa_html()

        if method == "POST" and path == "/api/v1/captures":
            return self._api_capture_upload(body, headers)
        if path.startswith("/api/v1/captures/"):
            capture_id = path[len("/api/v1/captures/") :]
            return self._api_capture_get(method, capture_id)

        if path == "/api/v1/notes":
            if method == "GET":
                query_params = parse_qs(raw.split("?", 1)[1]) if "?" in raw else {}
                return self._api_notes_list(query_params)
            return 405, _json(), b'{"error":"method not allowed"}'

        if path.startswith("/api/v1/notes/"):
            subpath = path[len("/api/v1/notes/") :]
            if subpath.endswith("/retry"):
                cid = subpath[: -len("/retry")]
                if method == "POST":
                    return self._api_note_retry(cid)
                return 405, _json(), b'{"error":"method not allowed"}'
            if "/markdown" in subpath:
                cid = subpath.replace("/markdown", "")
                if method == "GET":
                    return self._api_note_markdown(cid)
            else:
                cid = subpath
                if method == "GET":
                    return self._api_note_get(cid)
                if method == "PATCH":
                    return self._api_note_patch(cid, body, headers)
                return 405, _json(), b'{"error":"method not allowed"}'

        if method == "POST" and path == "/upload":
            return self._upload(body, headers.get("content-type", ""))

        if path == "/api/v1/settings":
            if method == "GET":
                return self._api_settings_get()
            if method == "PATCH":
                return self._api_settings_patch(body, headers)
            return 405, _json(), b'{"error":"method not allowed"}'

        if method == "GET" and path == "/api/v1/device/telemetry":
            return self._api_telemetry_get()
        if method == "POST" and path == "/api/v1/device/heartbeat":
            return self._api_device_heartbeat(body, headers)
        if method == "GET" and path == "/api/v1/events":
            return self._api_sse(headers)


        if method == "GET" and path == "/":
            return 200, _html(), _page(self._list())
        capture_id, kind = _route(path)
        if capture_id is None:
            return 404, _html(), b"not found"
        try:
            self.store.audio_path(capture_id)
        except Rejected:
            return 404, _html(), b"not found"
        if self.store.get(capture_id) is None:
            return 404, _html(), b"not found"
        if method == "GET" and kind == "audio":
            note = self.store.get_note(capture_id)
            path = self.store.audio_path(capture_id)
            if note is None or note.audio_purged_at is not None or not path.is_file():
                return 404, _html(), b"not found"
            data = path.read_bytes()
            return 200, {"content-type": "audio/wav", "cache-control": "private, no-store"}, data
        if method == "GET" and kind == "note":
            inner, head = self._note(capture_id, saved)
            return 200, _html(), _page(inner, head)
        if method == "POST" and kind == "note":
            text = parse_qs(body.decode("utf-8", "replace")).get("transcript", [""])[0]
            self.store.set_transcript(capture_id, text, source="owner")
            return 303, {"location": f"/n/{capture_id}?saved=1"}, b""
        if method == "POST" and kind == "retry":
            if self.jobs is None or not self.jobs.retry_failed(capture_id):
                return 303, {"location": f"/n/{capture_id}?retry=rejected"}, b""
            return 303, {"location": f"/n/{capture_id}?retry=queued"}, b""
        return 404, _html(), b"not found"

    def _authed(self, cookie: str) -> bool:
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE and value == self.token:
                return True
        return False

    def _is_authorized(self, cookie: str, headers: dict[str, str]) -> bool:
        if self._authed(cookie):
            return True
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            if token == self.token:
                return True
        return False

    def _login(self, body: bytes):
        given = parse_qs(body.decode("utf-8", "replace")).get("token", [""])[0]
        if given != self.token:
            return 401, _html(), _page(_login_form("Wrong token."))
        headers = _html()
        headers["set-cookie"] = f"{COOKIE}={self.token}; HttpOnly; Secure; SameSite=Strict; Path=/"
        headers["location"] = "/"
        return 303, headers, b""

    def _list(self) -> str:
        notes = self.store.list_notes()
        upload = (
            '<form method="post" action="/upload" enctype="multipart/form-data">'
            '<label>New recording <input name="audio" type="file" accept="audio/wav,.wav"></label>'
            '<button type="submit">Upload</button></form>'
        )
        if not notes:
            return upload + "<p>No captures yet.</p>"
        items = "".join(
            f'<li><a href="/n/{html.escape(note.capture_id, quote=True)}">{html.escape(note.capture_id)}</a>'
            f" · {html.escape(note.status)}</li>"
            for note in notes
        )
        return upload + f"<ul>{items}</ul>"

    def _note(self, capture_id: str, saved: bool) -> tuple[str, str]:
        note = self.store.get_note(capture_id)
        assert note is not None
        shown = html.escape(note.transcript or "", quote=True)
        ident = html.escape(capture_id, quote=True)
        kind = "Your correction" if note.transcript_source == "owner" else "Machine transcript"
        banner = "<p>Saved. The player is still the original recording.</p>" if saved else ""
        status_line = ""
        head = ""
        if note.status == "transcribing":
            status_line = "<p>Transcribing.</p>"
            head = '<meta http-equiv="refresh" content="2">'
        elif note.status == "not_transcribed":
            status_line = "<p>Not transcribed.</p>"
            if self.jobs is not None:
                status_line += (
                    f'<form method="post" action="/n/{ident}/retry">'
                    '<button type="submit">Retry transcription</button></form>'
                )
        hold_line = ""
        player = ""
        if note.audio_purged_at:
            hold_line = "<p>Audio hold ended. The note is kept.</p>"
        else:
            received = _parse_stamp(note.received_at)
            if received is not None:
                expiry = (received + HOLD).strftime(STAMP)
                hold_line = f"<p>Audio held until {expiry}.</p>"
            if self.store.audio_path(capture_id).is_file():
                player = f'<audio controls src="/n/{ident}/audio"></audio>'
        inner = (
            f'<p><a href="/">All notes</a></p>'
            f"<h1>{ident}</h1>"
            f"{banner}"
            f"{status_line}"
            f"{hold_line}"
            f"<p>Original recording</p>"
            f"{player}"
            f"<p>{html.escape(kind)}</p>"
            f"<p>{shown}</p>"
            f'<form method="post" action="/n/{ident}">'
            f'<textarea name="transcript" rows="8">{shown}</textarea>'
            f'<button type="submit">Save correction</button></form>'
        )
        return inner, head

    def _upload(self, body: bytes, content_type: str):
        wav = _file_field(body, content_type)
        capture_id = uuid.uuid4().hex
        try:
            self.store.accept(capture_id, wav)
        except Rejected:
            return 400, _html(), _page("<p>That file is not a WAV.</p>" + self._list())
        return 303, {"location": f"/n/{capture_id}"}, b""

    def _api_capture_upload(self, body: bytes, headers: dict[str, str]):
        content_type = headers.get("content-type", "")
        wav = b""
        fields: dict[str, str] = {}
        if "multipart/form-data" in content_type:
            wav, fields = _multipart_fields(body, content_type)
        elif _is_wav(body):
            wav = body

        header_capture_id = headers.get("x-capture-id") or fields.get("capture_id")
        metadata_str = fields.get("metadata")

        # Provisional v1 manifest envelope (docs/CONTRACT-NOTES.md). A present
        # metadata part must be a fully valid manifest; it is validated against
        # the uploaded bytes before any receipt is issued.
        manifest = None
        if metadata_str is not None:
            if len(metadata_str.encode("utf-8")) > 16 * 1024:
                return 400, _json(), b'{"error":"rejected","message":"metadata exceeds 16 KiB"}'
            try:
                meta = json.loads(metadata_str)
                if not isinstance(meta, dict) or meta.get("schema_version") != 1:
                    raise SchemaValidationError("unsupported schema version")
                manifest = CaptureManifest.from_dict(meta)
            except (json.JSONDecodeError, TypeError, AttributeError, SchemaValidationError) as exc:
                return 400, _json(), json.dumps(
                    {"error": "rejected", "message": f"invalid capture manifest: {exc}"}
                ).encode()
            capture_id = manifest.capture_id
            if header_capture_id and header_capture_id != manifest.capture_id:
                return 400, _json(), b'{"error":"rejected","message":"capture_id does not match manifest"}'
        elif header_capture_id:
            capture_id = header_capture_id
        else:
            capture_id = uuid.uuid4().hex

        if manifest is not None:
            reason = _validate_manifest_envelope(manifest, wav)
            if reason is not None:
                return 400, _json(), json.dumps({"error": "rejected", "message": reason}).encode()

        manifest_json = (
            json.dumps(manifest.to_dict(), sort_keys=True) if manifest is not None else None
        )
        is_replay = self.store.get(capture_id) is not None
        if is_replay and manifest is not None:
            stored_manifest = self.store.get_manifest(capture_id)
            if stored_manifest is not None and stored_manifest != manifest_json:
                return (
                    409,
                    _json(),
                    b'{"error":"conflict","message":"capture_id exists with a different manifest"}',
                )
        try:
            receipt = self.store.accept(capture_id, wav, manifest_json=manifest_json)
        except Conflict:
            return 409, _json(), b'{"error":"conflict","message":"capture_id exists with different audio"}'
        except Rejected as exc:
            return 400, _json(), json.dumps({"error": "rejected", "message": str(exc)}).encode()

        note = self.store.get_note(capture_id)
        status_code = 200 if is_replay else 201
        payload = {
            "capture_id": receipt.capture_id,
            "receipt_id": receipt.receipt_id,
            "sha256": receipt.sha256,
            "byte_count": receipt.byte_count,
            "received_at": note.received_at if note else None,
            "status": note.status if note else "received",
        }
        return status_code, _json(), json.dumps(payload).encode()

    def _api_capture_get(self, method: str, capture_id: str):
        if method != "GET":
            return 405, _json(), b'{"error":"method not allowed"}'
        try:
            self.store.audio_path(capture_id)
        except Rejected:
            return 404, _json(), b'{"error":"not found"}'
        receipt = self.store.get(capture_id)
        note = self.store.get_note(capture_id)
        if receipt is None or note is None:
            return 404, _json(), b'{"error":"not found"}'
        payload = {
            "capture_id": receipt.capture_id,
            "receipt_id": receipt.receipt_id,
            "sha256": receipt.sha256,
            "byte_count": receipt.byte_count,
            "received_at": note.received_at,
            "status": note.status,
            "transcript": note.transcript,
            "transcript_source": note.transcript_source,
            "audio_purged_at": note.audio_purged_at,
            "manifest": json.loads(m) if (m := self.store.get_manifest(capture_id)) else None,
        }
        return 200, _json(), json.dumps(payload).encode()

    def _api_notes_list(self, params: dict[str, list[str]]):
        try:
            limit = int(params.get("limit", ["50"])[0])
            offset = int(params.get("offset", ["0"])[0])
        except (TypeError, ValueError):
            return 400, _json(), b'{"error":"invalid pagination"}'
        if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
            return 400, _json(), b'{"error":"invalid pagination"}'
        status = params.get("status", [None])[0]
        search = params.get("search", [None])[0]

        notes = self.store.list_notes(status=status, search=search, limit=limit, offset=offset)
        total = self.store.count_notes(status=status, search=search)

        items = []
        for note in notes:
            items.append({
                "capture_id": note.capture_id,
                "status": note.status,
                "transcript": note.transcript,
                "transcript_source": note.transcript_source,
                "received_at": note.received_at,
                "audio_purged_at": note.audio_purged_at,
                "category": getattr(note, "category", None),
                "urgency": getattr(note, "urgency", None),
                "actionable": getattr(note, "actionable", None),
            })
        resp = {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
        return 200, _json(), json.dumps(resp).encode()

    def _api_note_get(self, capture_id: str):
        note = self.store.get_note(capture_id)
        if note is None:
            return 404, _json(), b'{"error":"not found"}'
        receipt = self.store.get(capture_id)
        resp = {
            "capture_id": note.capture_id,
            "status": note.status,
            "transcript": note.transcript,
            "transcript_source": note.transcript_source,
            "received_at": note.received_at,
            "audio_purged_at": note.audio_purged_at,
            "category": getattr(note, "category", None),
            "urgency": getattr(note, "urgency", None),
            "actionable": getattr(note, "actionable", None),
            "sha256": receipt.sha256 if receipt else None,
            "byte_count": receipt.byte_count if receipt else None,
        }
        return 200, _json(), json.dumps(resp).encode()

    def _api_note_retry(self, capture_id: str):
        note = self.store.get_note(capture_id)
        if note is None:
            return 404, _json(), b'{"error":"not found"}'
        if self.jobs is None:
            return 409, _json(), b'{"error":"retry unavailable"}'
        accepted = self.jobs.retry_failed(capture_id)
        if not accepted:
            return 409, _json(), b'{"error":"job not retryable"}'
        return 202, _json(), b'{"status":"queued"}'

    def _api_note_patch(self, capture_id: str, body: bytes, headers: dict[str, str]):
        note = self.store.get_note(capture_id)
        if note is None:
            return 404, _json(), b'{"error":"not found"}'
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, _json(), b'{"error":"invalid json"}'

        if not isinstance(data, dict) or not data or set(data) - {"transcript", "category", "urgency", "actionable"}:
            return 400, _json(), b'{"error":"invalid patch fields"}'
        if "transcript" in data and (
            not isinstance(data["transcript"], str) or len(data["transcript"]) > 100_000
        ):
            return 400, _json(), b'{"error":"invalid transcript"}'
        if "category" in data and (
            not isinstance(data["category"], str)
            or data["category"] not in {item.value for item in Category}
        ):
            return 400, _json(), b'{"error":"invalid category"}'
        if "urgency" in data and (
            not isinstance(data["urgency"], str)
            or data["urgency"] not in {item.value for item in Urgency}
        ):
            return 400, _json(), b'{"error":"invalid urgency"}'
        if "actionable" in data and not isinstance(data["actionable"], bool):
            return 400, _json(), b'{"error":"invalid actionable"}'

        if "transcript" in data:
            self.store.set_transcript(capture_id, data["transcript"], source="owner")

        if any(key in data for key in ("category", "urgency", "actionable")):
            cat = data.get("category", getattr(note, "category", None) or "unreviewed")
            urg = data.get("urgency", getattr(note, "urgency", None) or "normal")
            act = data.get("actionable", getattr(note, "actionable", None) or False)
            self.store.set_suggestions(capture_id, cat, urg, act, source="owner")

        updated = self.store.get_note(capture_id)
        resp = {
            "capture_id": updated.capture_id,
            "status": updated.status,
            "transcript": updated.transcript,
            "transcript_source": updated.transcript_source,
            "category": updated.category,
            "urgency": updated.urgency,
            "actionable": updated.actionable,
        }
        return 200, _json(), json.dumps(resp).encode()

    def _api_note_markdown(self, capture_id: str):
        note = self.store.get_note(capture_id)
        receipt = self.store.get(capture_id)
        if note is None or receipt is None:
            return 404, _json(), b'{"error":"not found"}'
        from server.export import build_markdown_body

        body = build_markdown_body(note, receipt)
        return 200, {"content-type": "text/markdown; charset=utf-8"}, body.encode("utf-8")

    # ── Settings ──────────────────────────────────────────────────────────

    def _api_settings_get(self):
        settings = self.settings_store.load()
        return 200, _json(), json.dumps(settings.to_dict()).encode()

    def _api_settings_patch(self, body: bytes, headers: dict[str, str]):
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, _json(), b'{"error":"invalid json"}'
        if not isinstance(data, dict) or not data:
            return 400, _json(), b'{"error":"empty or non-object body"}'
        unknown = set(data) - self.settings_store.load().PATCHABLE
        if unknown:
            return 400, _json(), json.dumps({"error": f"unknown fields: {sorted(unknown)}"}).encode()
        try:
            settings = self.settings_store.patch(data)
        except ValueError as exc:
            return 400, _json(), json.dumps({"error": str(exc)}).encode()
        return 200, _json(), json.dumps(settings.to_dict()).encode()

    # ── Device telemetry & heartbeat ──────────────────────────────────────

    def _api_telemetry_get(self):
        snapshot = self.telemetry_store.get()
        return 200, _json(), json.dumps(snapshot.to_dict()).encode()

    def _api_device_heartbeat(self, body: bytes, headers: dict[str, str]):
        """Accept a heartbeat POST from the Pi spool uploader.

        Body is optional JSON: {device_id?, queue_depth?, battery_pct?,
        wifi_rssi_dbm?, firmware_version?, spool_errors?}
        """
        data: dict = {}
        if body:
            try:
                parsed = json.loads(body.decode("utf-8"))
                if isinstance(parsed, dict):
                    data = parsed
            except (UnicodeDecodeError, json.JSONDecodeError):
                return 400, _json(), b'{"error":"invalid json"}'
        snapshot = self.telemetry_store.update(data)
        # Publish SSE event to connected browser clients
        self.sse_broker.publish("device_heartbeat", json.dumps(snapshot.to_dict()))
        return 200, _json(), json.dumps(snapshot.to_dict()).encode()

    # ── Server-sent events ────────────────────────────────────────────────

    def _api_sse(self, headers: dict[str, str]):
        """Return a streaming SSE response.

        The HTTP handler must recognise the special sentinel and stream the
        queue rather than buffering. This method returns a generator-based
        response that the ThreadingHTTPServer handler writes incrementally.

        Returns (200, sse_headers, generator).
        """
        q = self.sse_broker.subscribe()

        def _generate():
            # Send an initial ping so the client knows we're live
            yield b"event: ping\ndata: {}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    if msg is None:
                        break
                    yield msg.encode()
                except queue.Empty:  # timeout → send keepalive
                    yield b": keepalive\n\n"

        sse_headers = {
            "content-type": "text/event-stream; charset=utf-8",
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
        }
        return 200, sse_headers, _generate()


def _route(path: str) -> tuple[str | None, str]:
    if not path.startswith("/n/"):
        return None, ""
    rest = path[3:]
    if rest.endswith("/audio"):
        return rest[: -len("/audio")], "audio"
    if rest.endswith("/retry"):
        return rest[: -len("/retry")], "retry"
    return rest, "note"


def _login_form(message: str = "") -> str:
    note = f"<p>{html.escape(message)}</p>" if message else ""
    return (
        f'{note}<form method="post" action="/login">'
        '<label>Owner token <input name="token" type="password" autocomplete="current-password"></label>'
        '<button type="submit">Open</button></form>'
    )


def _page(inner: str, head: str = "") -> bytes:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"{head}"
        "<title>Whis2ndBrain</title>"
        "<style>body{font:18px/1.4 sans-serif;margin:1.2rem;max-width:40rem}"
        "button,input,textarea{font:inherit}textarea,audio{width:100%}"
        "button{min-height:3rem;margin-top:1rem}</style></head>"
        f"<body><main>{inner}</main></body></html>"
    ).encode()


def _html() -> dict[str, str]:
    return {"content-type": "text/html; charset=utf-8"}


def _json() -> dict[str, str]:
    return {"content-type": "application/json; charset=utf-8"}


def _multipart_fields(body: bytes, content_type: str) -> tuple[bytes, dict[str, str]]:
    if "multipart/form-data" not in content_type:
        return b"", {}
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = message_from_bytes(header + body, policy=default)
    if not message.is_multipart():
        return b"", {}
    wav = b""
    fields: dict[str, str] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if part.get_filename() or name == "audio":
            payload = part.get_payload(decode=True)
            if payload:
                wav = payload
        elif name:
            payload = part.get_payload(decode=True)
            if payload:
                fields[name] = payload.decode("utf-8", "replace")
    return wav, fields


def _validate_manifest_envelope(manifest, wav: bytes) -> str | None:
    """Check immutable manifest facts against the actual uploaded WAV bytes.

    Returns None when the envelope is truthful, else a short rejection reason.
    Metadata is never trusted over bytes (docs/CONTRACT-NOTES.md).
    """
    import hashlib as _hashlib
    import io as _io
    import wave as _wave

    digest = _hashlib.sha256(wav).hexdigest()
    if manifest.audio.sha256 != digest:
        return "manifest audio hash does not match uploaded bytes"
    if manifest.audio.bytes != len(wav):
        return "manifest byte count does not match uploaded bytes"
    try:
        with _wave.open(_io.BytesIO(wav), "rb") as audio:
            channels = audio.getnchannels()
            rate = audio.getframerate()
            width = audio.getsampwidth()
            frames = audio.getnframes()
    except (_wave.Error, EOFError):
        return "uploaded audio is not a readable WAV"
    if manifest.audio.channels != channels:
        return "manifest channels do not match uploaded WAV"
    if manifest.audio.sample_rate_hz != rate:
        return "manifest sample rate does not match uploaded WAV"
    if manifest.audio.sample_width_bits != width * 8:
        return "manifest sample width does not match uploaded WAV"
    actual_ms = round((frames / rate) * 1000) if rate else 0
    if abs(manifest.duration_ms - actual_ms) > 100:
        return "manifest duration does not match uploaded WAV"
    return None


def _file_field(body: bytes, content_type: str) -> bytes:
    wav, _ = _multipart_fields(body, content_type)
    return wav


def create_handler(store: Store, token: str, runner=None, settings_store=None, telemetry_store=None, sse_broker=None, jobs=None):
    """Build the production HTTP handler without starting host maintenance or a listener."""
    from http.server import BaseHTTPRequestHandler

    review = Review(
        store,
        token,
        runner=runner,
        settings_store=settings_store,
        telemetry_store=telemetry_store,
        sse_broker=sse_broker,
        jobs=jobs,
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._dispatch("GET", b"")

        def do_POST(self) -> None:
            self._read_and_dispatch("POST")

        def do_PATCH(self) -> None:
            self._read_and_dispatch("PATCH")

        def _read_and_dispatch(self, method: str) -> None:
            if self.headers.get("Transfer-Encoding") is not None:
                self.close_connection = True
                self._send_error(400, b'{"error":"transfer encoding not supported"}')
                return
            length = self.headers.get("Content-Length")
            if length is None or len(length) > 12 or not length.isascii() or not length.isdecimal():
                self.close_connection = True
                self._send_error(400, b'{"error":"invalid content length"}')
                return
            size = int(length)
            maximum = MAX_PATCH_BYTES if method == "PATCH" else MAX_WAV_BYTES + MAX_MULTIPART_OVERHEAD
            if size > maximum:
                self.close_connection = True
                self._send_error(413, b'{"error":"request too large"}')
                return
            body = self.rfile.read(size)
            if len(body) != size:
                self.close_connection = True
                self._send_error(400, b'{"error":"incomplete request body"}')
                return
            self._dispatch(method, body)

        def _send_error(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self, method: str, body: bytes) -> None:
            import types
            headers = {k: v for k, v in self.headers.items()}
            status, response_headers, payload = review.handle(
                method, self.path, body, self.headers.get("Cookie", ""), headers
            )
            is_stream = isinstance(payload, types.GeneratorType)
            self.send_response(status)
            for key, value in response_headers.items():
                self.send_header(key, value)
            if not is_stream:
                self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if is_stream:
                try:
                    for chunk in payload:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    if hasattr(payload, "close"):
                        payload.close()
            else:
                self.wfile.write(payload)


        def log_message(self, fmt: str, *args) -> None:
            return

    return Handler


def serve(store: Store, token: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    import time
    from datetime import datetime, timezone
    from http.server import ThreadingHTTPServer

    from server.jobs import Jobs, run_once
    from server.pass1 import prepare_host, purge_expired
    from server.pipeline.transcriber import IsolatedTranscriber
    from server.settings import SettingsStore
    from server.telemetry import SSEBroker, TelemetryStore

    settings_store = SettingsStore(store.root)
    telemetry_store = TelemetryStore()
    sse_broker = SSEBroker()

    jobs = Jobs(store)
    # WB-023 lane: the model runs in a killable subprocess with a hard
    # timeout, never inside the HTTP server process.
    runner = IsolatedTranscriber()

    Handler = create_handler(
        store, token,
        settings_store=settings_store,
        telemetry_store=telemetry_store,
        sse_broker=sse_broker,
        jobs=jobs,
    )

    prepare_host(store, datetime.now(timezone.utc))

    def _sweep() -> None:
        while True:
            time.sleep(900)
            try:
                purge_expired(store, datetime.now(timezone.utc))
            except Exception as exc:  # noqa: BLE001 - retention loop must survive filesystem errors
                print(f"purge failed {type(exc).__name__}", flush=True)

    threading.Thread(target=_sweep, daemon=True).start()

    def _worker() -> None:
        while True:
            try:
                worked = run_once(store, runner, jobs)
            except Exception as exc:  # noqa: BLE001 - preserve service if a job fails unexpectedly
                print(f"worker failed {type(exc).__name__}", flush=True)
                worked = False
            if not worked:
                time.sleep(1)

    threading.Thread(target=_worker, daemon=True).start()

    ThreadingHTTPServer((host, port), Handler).serve_forever()
