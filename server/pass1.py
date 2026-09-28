"""Pass-1 host slice: durable WAV receipt, local transcript, conflict-safe export."""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

MODEL_ID = "Systran/faster-distil-whisper-medium.en"
MODEL_DIR = Path("/data/models/whis2ndbrain")
MAX_WAV_BYTES = 25 * 1024 * 1024
MAX_WAV_DURATION_SECONDS = 15 * 60
logger = logging.getLogger(__name__)


class Conflict(Exception):
    pass


class Rejected(Exception):
    pass


@dataclass(frozen=True)
class Receipt:
    capture_id: str
    sha256: str
    byte_count: int
    receipt_id: str


@dataclass(frozen=True)
class Note:
    capture_id: str
    status: str
    transcript: str | None
    transcript_source: str | None
    received_at: str | None = None
    audio_purged_at: str | None = None
    category: str | None = None
    urgency: str | None = None
    actionable: bool | None = None


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.audio_dir = self.root / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "queue.sqlite"
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS captures (
                    capture_id TEXT PRIMARY KEY,
                    receipt_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    transcript TEXT,
                    transcript_source TEXT
                )
                """
            )
            self._ensure_columns(conn)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS transcription_jobs (
                    capture_id TEXT PRIMARY KEY REFERENCES captures(capture_id),
                    state TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
                    token TEXT, lease_until REAL, run_after REAL NOT NULL DEFAULT 0,
                    error TEXT
                )"""
            )
            conn.execute(
                """INSERT OR IGNORE INTO transcription_jobs(capture_id, state)
                   SELECT capture_id, 'queued' FROM captures
                   WHERE status IN ('received', 'transcribing')"""
            )
        self._quarantine()

    def accept(
        self,
        capture_id: str,
        wav: bytes,
        after_write: Callable[[], None] | None = None,
        manifest_json: str | None = None,
    ) -> Receipt:
        _check_id(capture_id)
        if len(wav) > MAX_WAV_BYTES:
            raise Rejected("not a wav")
        digest = hashlib.sha256(wav).hexdigest()
        dest = self.audio_path(capture_id)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT receipt_id, sha256, byte_count, manifest_json "
                "FROM captures WHERE capture_id = ?",
                (capture_id,),
            ).fetchone()
            if row is not None:
                if row["sha256"] != digest:
                    raise Conflict(capture_id)
                # Same bytes: replay. A different immutable manifest for the
                # same ID + bytes is a conflict; the original receipt stands.
                stored_manifest = row["manifest_json"]
                if manifest_json is not None and stored_manifest is not None:
                    if stored_manifest != manifest_json:
                        raise Conflict(capture_id)
                elif manifest_json is not None and stored_manifest is None:
                    conn.execute(
                        "UPDATE captures SET manifest_json = ? WHERE capture_id = ?",
                        (manifest_json, capture_id),
                    )
                return Receipt(capture_id, row["sha256"], row["byte_count"], row["receipt_id"])
            if not _is_wav(wav):
                raise Rejected("not a wav")
            _write_durable(dest, wav)
            if after_write is not None:
                after_write()
            receipt_id = str(uuid.uuid4())
            try:
                received_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    """
                    INSERT INTO captures
                        (capture_id, receipt_id, sha256, byte_count, status, received_at,
                         manifest_json)
                    VALUES (?, ?, ?, ?, 'received', ?, ?)
                    """,
                    (capture_id, receipt_id, digest, len(wav), received_at, manifest_json),
                )
                conn.execute(
                    "INSERT INTO transcription_jobs(capture_id, state) VALUES (?, 'queued')",
                    (capture_id,),
                )
            except sqlite3.Error:
                dest.unlink(missing_ok=True)
                raise
        return Receipt(capture_id, digest, len(wav), receipt_id)

    def get_manifest(self, capture_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT manifest_json FROM captures WHERE capture_id = ?", (capture_id,)
            ).fetchone()
        return row["manifest_json"] if row is not None else None

    def get(self, capture_id: str) -> Receipt | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, sha256, byte_count FROM captures WHERE capture_id = ?",
                (capture_id,),
            ).fetchone()
        if row is None:
            return None
        return Receipt(capture_id, row["sha256"], row["byte_count"], row["receipt_id"])

    def get_note(self, capture_id: str) -> Note | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT status, transcript, transcript_source, received_at, audio_purged_at,
                       category, urgency, actionable
                FROM captures WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()
        if row is None:
            return None
        keys = row.keys()
        return Note(
            capture_id,
            row["status"],
            row["transcript"],
            row["transcript_source"],
            row["received_at"],
            row["audio_purged_at"],
            row["category"] if "category" in keys else None,
            row["urgency"] if "urgency" in keys else None,
            bool(row["actionable"]) if "actionable" in keys and row["actionable"] is not None else None,
        )

    def set_transcript(self, capture_id: str, text: str, source: str) -> None:
        if source not in {"model", "owner"}:
            raise Rejected("bad transcript source")
        status = "reviewed" if source == "owner" else "transcribed"
        with self._connect() as conn:
            if source == "model":
                # The owner check must be part of the write predicate: a model
                # finishing concurrently with an edit must never replace it.
                cur = conn.execute(
                    """
                    UPDATE captures
                    SET transcript = ?, transcript_source = ?, status = ?
                    WHERE capture_id = ? AND transcript_source IS NOT 'owner'
                      AND status != 'reviewed'
                    """,
                    (text, source, status, capture_id),
                )
                if cur.rowcount == 0:
                    exists = conn.execute(
                        "SELECT 1 FROM captures WHERE capture_id = ?", (capture_id,)
                    ).fetchone()
                    if exists is None:
                        raise Rejected("unknown capture")
                    return
            else:
                cur = conn.execute(
                    """
                    UPDATE captures
                    SET transcript = ?, transcript_source = ?, status = ?
                    WHERE capture_id = ?
                    """,
                    (text, source, status, capture_id),
                )
            if cur.rowcount != 1:
                raise Rejected("unknown capture")

    def set_suggestions(
        self, capture_id: str, category: str, urgency: str, actionable: bool,
        source: str = "model",
    ) -> None:
        if source not in {"model", "owner"}:
            raise Rejected("bad suggestion source")
        guard = "AND transcript_source IS NOT 'owner' AND annotation_source IS NOT 'owner'" if source == "model" else ""
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE captures
                SET category = ?, urgency = ?, actionable = ?, annotation_source = ?
                WHERE capture_id = ? {guard}
                """,
                (category, urgency, 1 if actionable else 0, source, capture_id),
            )

    def mark_not_transcribed(self, capture_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE captures
                SET status = 'not_transcribed', transcript = NULL, transcript_source = NULL
                WHERE capture_id = ? AND transcript_source IS NOT 'owner'
                  AND status != 'reviewed'
                """,
                (capture_id,),
            )

    def mark_transcribing(self, capture_id: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM captures WHERE capture_id = ?",
                (capture_id,),
            ).fetchone()
            if row is None:
                raise Rejected("unknown capture")
            if row["status"] != "received":
                return
            conn.execute(
                """
                UPDATE captures SET status = 'transcribing'
                WHERE capture_id = ? AND status = 'received'
                """,
                (capture_id,),
            )

    def list_notes(
        self,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("transcript LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT capture_id, status, transcript, transcript_source, received_at, audio_purged_at,
                   category, urgency, actionable
            FROM captures
            {where}
            ORDER BY capture_id
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Note(
                row["capture_id"],
                row["status"],
                row["transcript"],
                row["transcript_source"],
                row["received_at"],
                row["audio_purged_at"],
                row["category"],
                row["urgency"],
                bool(row["actionable"]) if row["actionable"] is not None else None,
            )
            for row in rows
        ]

    def count_notes(self, status: str | None = None, search: str | None = None) -> int:
        clauses = []
        params = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("transcript LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS c FROM captures {where}", params).fetchone()
        return int(row["c"]) if row else 0


    def audio_path(self, capture_id: str) -> Path:
        _check_id(capture_id)
        return self.audio_dir / f"{capture_id}.wav"

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=2000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        have = {row["name"] for row in conn.execute("PRAGMA table_info(captures)")}
        if "received_at" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN received_at TEXT")
        if "audio_purged_at" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN audio_purged_at TEXT")
        if "category" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN category TEXT")
        if "urgency" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN urgency TEXT")
        if "actionable" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN actionable INTEGER")
        if "annotation_source" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN annotation_source TEXT")
        if "manifest_json" not in have:
            conn.execute("ALTER TABLE captures ADD COLUMN manifest_json TEXT")

    def _quarantine(self) -> None:
        orphans = self.root / "orphans"
        orphans.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            known = {row["capture_id"] for row in conn.execute("SELECT capture_id FROM captures")}
        for path in list(self.audio_dir.iterdir()):
            if path.name.endswith(".part") or path.suffix == ".wav" and path.stem not in known:
                dest = orphans / path.name
            else:
                continue
            if dest.exists():
                continue
            os.replace(path, dest)


HOLD = timedelta(hours=168)
STAMP = "%Y-%m-%dT%H:%M:%SZ"


def _parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, STAMP).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(STAMP)


def purge_expired(store: Store, now: datetime) -> None:
    if now.tzinfo is None:
        raise Rejected("purge clock must be timezone-aware")
    moment = now.astimezone(timezone.utc)
    with store._connect() as conn:
        rows = conn.execute(
            "SELECT capture_id, received_at, audio_purged_at FROM captures"
        ).fetchall()
    for row in rows:
        path = store.audio_path(row["capture_id"])
        if row["audio_purged_at"]:
            path.unlink(missing_ok=True)
            continue
        received = _parse_stamp(row["received_at"])
        if received is None or moment < received + HOLD:
            continue
        path.unlink(missing_ok=True)
        with store._connect() as conn:
            conn.execute(
                """
                UPDATE captures SET audio_purged_at = ?
                WHERE capture_id = ? AND audio_purged_at IS NULL
                """,
                (_stamp(moment), row["capture_id"]),
            )


def abandon_inflight(store: Store) -> None:
    with store._connect() as conn:
        conn.execute(
            "UPDATE captures SET status = 'not_transcribed' WHERE status = 'transcribing'"
        )


def prepare_host(store: Store, now: datetime) -> None:
    abandon_inflight(store)
    purge_expired(store, now)


VAULT_ROOT = Path.home() / "Documents" / "Vault"


def _refuse_vault(dest: Path, forbidden: Path) -> None:
    root = forbidden.resolve()
    target = dest.resolve()
    if target == root or root in target.parents:
        raise Rejected("export destination is inside the vault")


def export_note(
    store: Store, capture_id: str, dest: Path, forbidden: Path = VAULT_ROOT
) -> Path:
    note = store.get_note(capture_id)
    receipt = store.get(capture_id)
    if note is None or receipt is None:
        raise Rejected("unknown capture")
    dest = Path(dest)
    _refuse_vault(dest, forbidden)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{capture_id}.md"
    body = _markdown(note, receipt)
    if path.exists():
        if path.read_text() == body:
            return path
        raise Conflict(capture_id)
    _write_durable(path, body.encode())
    return path


def transcribe(store: Store, capture_id: str, runner, *, propagate_errors: bool = False) -> Note:
    if store.get(capture_id) is None:
        raise Rejected("unknown capture")
    try:
        text = runner(store.audio_path(capture_id))
    except Exception:
        if propagate_errors:
            raise
        store.mark_not_transcribed(capture_id)
        note = store.get_note(capture_id)
        assert note is not None
        return note
    store.set_transcript(capture_id, text, source="model")
    try:
        from server.pipeline.classify import classify_transcript

        sugg = classify_transcript(text)
        store.set_suggestions(capture_id, sugg.category, sugg.urgency, sugg.actionable)
    except Exception as exc:  # noqa: BLE001 - optional suggestions must not erase ASR text
        logger.warning("suggestion generation failed: %s", type(exc).__name__)
    note = store.get_note(capture_id)
    assert note is not None
    return note


def render_note(note: Note) -> str:
    body = html.escape(note.transcript or "", quote=True)
    return f"<article><p>{body}</p></article>"


def load_runner(model_dir: Path = MODEL_DIR):
    """Load the pinned English model from local storage only."""
    from faster_whisper import WhisperModel

    model = WhisperModel(
        MODEL_ID,
        device="cpu",
        compute_type="int8",
        download_root=str(model_dir),
        local_files_only=True,
    )

    def run(path: Path) -> str:
        segments, _info = model.transcribe(str(path), language="en", vad_filter=True)
        return "".join(segment.text for segment in segments).strip()

    return run


def _markdown(note: Note, receipt: Receipt) -> str:
    header = yaml.safe_dump(
        {
            "type": "permanent-note",
            "status": "draft",
            "capture_id": note.capture_id,
            "sha256": receipt.sha256,
            "transcript_source": note.transcript_source or "none",
            "review_state": note.status,
        },
        sort_keys=False,
    ).strip()
    return f"---\n{header}\n---\n\n{note.transcript or ''}\n"


def _check_id(capture_id: str) -> None:
    if not isinstance(capture_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", capture_id) is None:
        raise Rejected("bad capture id")


def _is_wav(data: bytes) -> bool:
    if len(data) < 44 or len(data) > MAX_WAV_BYTES or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return False
    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size != len(data) - 8:
        return False
    riff_end = riff_size + 8
    offset, fmt, data_size = 12, None, None
    while offset + 8 <= riff_end:
        chunk_id = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        start, end = offset + 8, offset + 8 + size
        if end > riff_end:
            return False
        if chunk_id == b"fmt ":
            if size < 16:
                return False
            fmt = (
                int.from_bytes(data[start : start + 2], "little"),
                int.from_bytes(data[start + 2 : start + 4], "little"),
                int.from_bytes(data[start + 4 : start + 8], "little"),
                int.from_bytes(data[start + 8 : start + 12], "little"),
                int.from_bytes(data[start + 12 : start + 14], "little"),
                int.from_bytes(data[start + 14 : start + 16], "little"),
            )
        elif chunk_id == b"data":
            data_size = size
        offset = end + (size & 1)
    if offset != riff_end or fmt is None or data_size is None:
        return False
    encoding, channels, rate, byte_rate, align, bits = fmt
    if encoding != 1 or channels != 1 or rate not in (16000, 44100, 48000) or bits != 16:
        return False
    if align != channels * bits // 8 or byte_rate != rate * align or data_size % align:
        return False
    return data_size <= rate * align * MAX_WAV_DURATION_SECONDS


def _write_durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
