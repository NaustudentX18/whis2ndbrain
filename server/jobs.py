"""Small durable, single-worker queue for capture transcription."""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    capture_id: str
    token: str
    attempt: int


class Jobs:
    """SQLite jobs stored beside captures. Each operation opens a short DB connection."""

    def __init__(self, store, *, max_attempts: int = 3, lease_seconds: int = 900):
        self.store = store
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        with store._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS transcription_jobs (
                    capture_id TEXT PRIMARY KEY REFERENCES captures(capture_id),
                    state TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    token TEXT,
                    lease_until REAL,
                    run_after REAL NOT NULL DEFAULT 0,
                    error TEXT
                )"""
            )
            # Old captures accepted before jobs existed (or interrupted while
            # transitioning) remain eligible. Deliberately excludes terminal notes.
            conn.execute(
                """INSERT OR IGNORE INTO transcription_jobs(capture_id, state)
                   SELECT capture_id, 'queued' FROM captures
                   WHERE status IN ('received', 'transcribing')"""
            )

    def enqueue(self, conn: sqlite3.Connection, capture_id: str) -> None:
        """Insert into the caller's transaction, atomically with capture receipt."""
        conn.execute(
            "INSERT OR IGNORE INTO transcription_jobs(capture_id, state) VALUES (?, 'queued')",
            (capture_id,),
        )

    def claim(self, *, now: float | None = None) -> Job | None:
        now = time.time() if now is None else now
        token = uuid.uuid4().hex
        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # A legacy/manual transcription may have completed before its job
            # was claimed; never rerun a terminal or owner-reviewed capture.
            conn.execute(
                """UPDATE transcription_jobs SET state='done', token=NULL, lease_until=NULL
                   WHERE state='queued' AND capture_id IN
                     (SELECT capture_id FROM captures WHERE status IN ('transcribed', 'reviewed')
                       OR transcript_source='owner')"""
            )
            # A worker that died while holding a lease gets a bounded retry.
            expired = conn.execute(
                "SELECT capture_id, attempt FROM transcription_jobs WHERE state='running' AND lease_until <= ?",
                (now,),
            ).fetchall()
            for row in expired:
                if row["attempt"] >= self.max_attempts:
                    self._fail_capture(conn, row["capture_id"], "worker lease expired")
                else:
                    conn.execute(
                        "UPDATE transcription_jobs SET state='queued', token=NULL, lease_until=NULL, run_after=? WHERE capture_id=?",
                        (now + self._backoff(row["attempt"]), row["capture_id"]),
                    )
            row = conn.execute(
                "SELECT capture_id, attempt FROM transcription_jobs WHERE state='queued' AND run_after <= ? ORDER BY rowid LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                return None
            attempt = row["attempt"] + 1
            conn.execute(
                "UPDATE transcription_jobs SET state='running', attempt=?, token=?, lease_until=?, error=NULL WHERE capture_id=? AND state='queued'",
                (attempt, token, now + self.lease_seconds, row["capture_id"]),
            )
            conn.execute(
                "UPDATE captures SET status='transcribing' WHERE capture_id=? AND status='received'",
                (row["capture_id"],),
            )
            return Job(row["capture_id"], token, attempt)

    def complete(self, job: Job, transcript: str | None = None, suggestions=None, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            owned = conn.execute(
                "SELECT 1 FROM transcription_jobs WHERE capture_id=? AND state='running' AND token=? AND lease_until > ?",
                (job.capture_id, job.token, now),
            ).fetchone()
            if owned is None:
                return False
            if transcript is not None:
                conn.execute(
                    """UPDATE captures SET transcript=?, transcript_source='model', status='transcribed'
                       WHERE capture_id=? AND transcript_source IS NOT 'owner' AND status != 'reviewed'""",
                    (transcript, job.capture_id),
                )
                if suggestions is not None:
                    category, urgency, actionable = suggestions
                    conn.execute(
                        """UPDATE captures SET category=?, urgency=?, actionable=?, annotation_source='model'
                           WHERE capture_id=? AND transcript_source IS NOT 'owner'
                             AND annotation_source IS NOT 'owner'""",
                        (category, urgency, int(actionable), job.capture_id),
                    )
            conn.execute(
                "UPDATE transcription_jobs SET state='done', token=NULL, lease_until=NULL WHERE capture_id=? AND state='running' AND token=?",
                (job.capture_id, job.token),
            )
            return True

    def fail(self, job: Job, error: Exception | str, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        # Exception text can contain private model paths or transcript content.
        message = type(error).__name__ if isinstance(error, Exception) else "JobError"
        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT attempt FROM transcription_jobs WHERE capture_id=? AND state='running' AND token=? AND lease_until > ?",
                (job.capture_id, job.token, now),
            ).fetchone()
            if row is None:
                return False
            result_exists = conn.execute(
                "SELECT 1 FROM captures WHERE capture_id=? AND transcript_source='model' AND status='transcribed'",
                (job.capture_id,),
            ).fetchone()
            if result_exists is not None:
                conn.execute(
                    "UPDATE transcription_jobs SET state='done', token=NULL, lease_until=NULL WHERE capture_id=?",
                    (job.capture_id,),
                )
                return True
            if row["attempt"] >= self.max_attempts:
                self._fail_capture(conn, job.capture_id, message)
            else:
                conn.execute(
                    "UPDATE transcription_jobs SET state='queued', token=NULL, lease_until=NULL, run_after=?, error=? WHERE capture_id=?",
                    (now + self._backoff(row["attempt"]), message, job.capture_id),
                )
            return True

    def _backoff(self, attempt: int) -> int:
        return min(300, 2 ** max(0, attempt - 1))

    @staticmethod
    def _fail_capture(conn, capture_id: str, error: str) -> None:
        conn.execute(
            "UPDATE transcription_jobs SET state='failed', token=NULL, lease_until=NULL, error=? WHERE capture_id=?",
            (error[:500], capture_id),
        )
        conn.execute(
            "UPDATE captures SET status='not_transcribed' WHERE capture_id=? AND transcript_source IS NOT 'owner' AND status != 'reviewed'",
            (capture_id,),
        )


def run_once(store, runner, jobs: Jobs | None = None) -> bool:
    """Process at most one job; returns whether a job was claimed."""
    jobs = jobs or Jobs(store)
    job = jobs.claim()
    if job is None:
        return False
    try:
        if store.get(job.capture_id) is None:
            raise ValueError("unknown capture")
        transcript = runner(store.audio_path(job.capture_id))
        if not isinstance(transcript, str) or len(transcript) > 100_000:
            raise ValueError("invalid model transcript")
    except Exception as exc:  # noqa: BLE001 - persist all runner failures for retry
        jobs.fail(job, exc)
    else:
        suggestions = None
        try:
            from server.pipeline.classify import classify_transcript

            result = classify_transcript(transcript)
            suggestions = (result.category, result.urgency, result.actionable)
        except Exception as exc:  # noqa: BLE001 - optional suggestions must not erase ASR text
            logger.warning("suggestion generation failed: %s", type(exc).__name__)
        jobs.complete(job, transcript, suggestions)
    return True
