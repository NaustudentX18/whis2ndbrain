"""Adversarial integration matrix (Lane C1 / WB-049 prep).

Crash at every durable boundary, hostile uploads, symlink escape and
tombstone replay — through the real HTTP layer or real subprocesses,
synthetic data only. Every test asserts the honest failure mode, never a
convenient one; the suite is red on regression by construction.

Boundaries covered here that earlier suites do not already prove
(test_http_review: manifest lies/duplicates/conflicts; test_process_crash:
kill between audio publish and commit; test_jobs: lease semantics in
process):

  * device replay of an upload whose note the owner has tombstoned
  * worker death while holding a job lease (real SIGKILL, real sqlite)
  * export crash at the atomic-rename boundary (partial file impossibility)
  * oversized / truncated / falsely-labelled media over real HTTP
  * hostile capture ids never touching the filesystem
  * symlinked audio files refused at both serve sites
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request

from server.export import export_note_to_dir
from server.jobs import Jobs
from server.pass1 import MAX_WAV_BYTES, Store
from tests.integration.test_http_review import _manifest_for, _multipart, synthetic_wav

REPO = Path(__file__).resolve().parents[2]


class MatrixHttpTestCase(unittest.TestCase):
    """Same disposable real-loopback harness as test_http_review."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="whis-matrix-")
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "store")
        self.token = "synthetic-test-owner-token"
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), __import__("server.review", fromlist=["create_handler"]).create_handler(
                self.store, self.token, runner=None
            )
        )
        self.addCleanup(self.httpd.server_close)
        import threading

        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (self.httpd.shutdown(), thread.join(timeout=2)))
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.wav = synthetic_wav()

    def request(self, method: str, path: str, body: bytes = b"", *, auth=True, headers=None):
        from urllib.error import HTTPError
        from urllib.request import urlopen

        request_headers = dict(headers or {})
        if auth:
            request_headers["Authorization"] = f"Bearer {self.token}"
        req = Request(
            self.base + path,
            data=body if method in {"POST", "PATCH"} else None,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
        except HTTPError as error:
            with error:
                return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()

    def upload(self, cid: str):
        body, ctype = _multipart(cid, self.wav, _manifest_for(cid, self.wav))
        return self.request("POST", "/api/v1/captures", body, headers={"Content-Type": ctype})

    def note(self, cid: str):
        status, _, payload = self.request("GET", f"/api/v1/notes/{cid}")
        return status, json.loads(payload) if status == 200 else None


class TombstoneReplayTests(MatrixHttpTestCase):
    """A device replay must never resurrect an owner-deleted note."""

    def test_replay_after_owner_delete_keeps_note_tombstoned(self):
        # Break: a device resending the same bytes silently un-deletes the note
        # (or bumps its revision), overriding the owner's delete decision.
        cid = "matrix-tombstone-replay-001"
        status, _, payload = self.upload(cid)
        self.assertEqual(status, 201)
        original_receipt = json.loads(payload)["receipt_id"]

        status, _, _ = self.request("DELETE", f"/api/v1/notes/{cid}")
        self.assertEqual(status, 204)
        _, _, payload = self.request("GET", "/api/v1/notes?include_deleted=1")
        trashed = {n["capture_id"]: n for n in json.loads(payload)["items"]}
        self.assertIn(cid, trashed)
        deleted_at, revision_before = trashed[cid]["deleted_at"], trashed[cid]["revision"]

        # The device retries the exact same upload (lost response, reboot, …).
        status, _, payload = self.upload(cid)
        self.assertEqual(status, 200)
        replay = json.loads(payload)
        self.assertEqual(replay["receipt_id"], original_receipt)  # idempotent receipt

        # …but the owner's decision stands: still tombstoned, nothing bumped.
        _, _, payload = self.request("GET", "/api/v1/notes?limit=100")
        self.assertNotIn(cid, [n["capture_id"] for n in json.loads(payload)["items"]])
        _, _, payload = self.request("GET", "/api/v1/notes?include_deleted=1")
        still = {n["capture_id"]: n for n in json.loads(payload)["items"]}[cid]
        self.assertEqual(still["deleted_at"], deleted_at)
        self.assertEqual(still["revision"], revision_before)
        status, _, _ = self.request("GET", f"/api/v1/notes/{cid}/audio")
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", f"/api/v1/notes/{cid}/markdown")
        self.assertEqual(status, 404)
        status, _, _ = self.request(
            "PATCH", f"/api/v1/notes/{cid}", b'{"transcript":"zombie text"}',
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 409)
        status, _, _ = self.request("POST", f"/api/v1/notes/{cid}/retry")
        self.assertEqual(status, 409)

        # Restore still works and the audio survived the whole cycle.
        status, _, _ = self.request("POST", f"/api/v1/notes/{cid}/restore")
        self.assertEqual(status, 204)
        status, _, _ = self.request("GET", f"/api/v1/notes/{cid}/audio")
        self.assertEqual(status, 200)

    def test_delete_idempotent_and_restore_of_live_note_refused(self):
        cid = "matrix-tombstone-lifecycle-001"
        self.upload(cid)
        self.assertEqual(self.request("DELETE", f"/api/v1/notes/{cid}")[0], 204)
        self.assertEqual(self.request("DELETE", f"/api/v1/notes/{cid}")[0], 204)
        self.assertEqual(self.request("POST", f"/api/v1/notes/{cid}/restore")[0], 204)
        status, _, payload = self.request("POST", f"/api/v1/notes/{cid}/restore")
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(payload)["error"], "note is not deleted")


class HostileMediaTests(MatrixHttpTestCase):
    """Oversized, truncated and falsely-labelled media never reach the disk."""

    def _tree(self):
        return {str(p) for p in Path(self.temp.name).rglob("*")}

    def test_oversized_upload_is_refused_without_any_disk_write(self):
        # Break: a body larger than MAX_WAV_BYTES lands on disk or in the store.
        blob = synthetic_wav() * (MAX_WAV_BYTES // len(synthetic_wav()) + 2)
        self.assertGreater(len(blob), MAX_WAV_BYTES)
        before = self._tree()
        status, _, _ = self.request(
            "POST", "/api/v1/captures", blob,
            headers={"Content-Type": "audio/wav", "X-Capture-ID": "matrix-oversize-001"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.request("GET", "/api/v1/captures/matrix-oversize-001")[0], 404)
        self.assertEqual(self._tree(), before)

    def test_truncated_and_mislabelled_wav_bodies_are_rejected(self):
        # Break: a RIFF size lie or a cut-off body is stored as if valid.
        before = self._tree()
        riff_lie = bytearray(self.wav)
        riff_lie[4:8] = (len(self.wav) + 4096).to_bytes(4, "little")  # header claims more
        truncated = self.wav[:-100]  # header intact, body short
        for label, body in (
            ("riff-size-lie", bytes(riff_lie)),
            ("truncated", truncated),
            ("not-a-wav", b"just some text pretending to be audio"),
        ):
            cid = f"matrix-hostile-{label}"
            status, _, payload = self.request(
                "POST", "/api/v1/captures", body,
                headers={"Content-Type": "audio/wav", "X-Capture-ID": cid},
            )
            self.assertEqual(status, 400, label)
            self.assertEqual(json.loads(payload)["error"], "rejected", label)
            self.assertEqual(self.request("GET", f"/api/v1/captures/{cid}")[0], 404, label)
        self.assertEqual(self._tree(), before)

    def test_hostile_capture_ids_never_touch_the_filesystem(self):
        # Break: a crafted id escapes the store root or writes anywhere else.
        before = self._tree()
        for bad in ("../../escape", "/tmp/whis-escape", "..", "a/b", "." * 200, "x" * 200):
            status, _, _ = self.request(
                "POST", "/api/v1/captures", self.wav,
                headers={"Content-Type": "audio/wav", "X-Capture-ID": bad},
            )
            self.assertEqual(status, 400, bad)
            status, _, _ = self.request("GET", f"/api/v1/notes/{bad}/audio")
            self.assertIn(status, (400, 404), bad)
        self.assertEqual(self._tree(), before)
        self.assertFalse(Path("/tmp/whis-escape").exists())


class SymlinkEscapeTests(MatrixHttpTestCase):
    """On-disk symlink swaps must not be served through either audio route."""

    def test_audio_routes_refuse_symlinked_audio_file(self):
        # Break: replacing the stored audio with a symlink to an outside file
        # makes the host stream that outside file's bytes.
        cid = "matrix-symlink-audio-001"
        self.upload(cid)
        sentinel = Path(self.temp.name) / "outside-secret.wav"
        sentinel.write_bytes(b"this file is not part of the store")
        audio = self.store.audio_path(cid)
        audio.unlink()
        audio.symlink_to(sentinel)
        for path in (f"/api/v1/notes/{cid}/audio", f"/n/{cid}/audio"):
            status, _, payload = self.request("GET", path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"outside-secret", payload)


class CrashBoundaryTests(unittest.TestCase):
    """Real SIGKILL at the durable boundaries of ingest, jobs and export."""

    def _child(self, code: str, *args: str):
        return subprocess.Popen(
            [sys.executable, "-c", code, *args],
            cwd=REPO, env={**os.environ, "PYTHONPATH": str(REPO)},
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    @staticmethod
    def _await(marker: Path, child: subprocess.Popen, timeout: float = 10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if marker.exists() or child.poll() is not None:
                return marker.exists()
            time.sleep(0.05)
        return marker.exists()

    def test_kill_between_publish_and_commit_then_manifest_replay(self):
        # Extends the proven publish-boundary kill into the manifest era: the
        # orphaned audio must still replay cleanly WITH its manifest envelope.
        with tempfile.TemporaryDirectory(prefix="whis-mx-kill-") as temp:
            root, source, marker = (Path(temp) / p for p in ("store", "synthetic.wav", "m"))
            source.write_bytes(synthetic_wav())
            child = self._child(
                """
import sys, time
from pathlib import Path
from server.pass1 import Store
root, source, marker = map(Path, sys.argv[1:])
def pause():
    marker.write_text('published')
    time.sleep(60)
Store(root).accept('matrix-kill-001', source.read_bytes(), after_write=pause)
""",
                str(root), str(source), str(marker),
            )
            try:
                self.assertTrue(self._await(marker, child), "child never reached the boundary")
            finally:
                child.kill(); child.wait(timeout=5)
                if child.stderr: child.stderr.close()

            restarted = Store(root)
            self.assertIsNone(restarted.get("matrix-kill-001"))
            manifest = _manifest_for("matrix-kill-001", source.read_bytes())
            receipt = restarted.accept("matrix-kill-001", source.read_bytes(), manifest_json=manifest)
            self.assertTrue(receipt.receipt_id)
            self.assertEqual(restarted.get_manifest("matrix-kill-001"), manifest)

    def test_worker_killed_holding_lease_is_reclaimed_not_lost(self):
        # Break: a SIGKILLed worker strands the job in 'running' forever, or
        # its stale token later overwrites a fresher worker's result.
        with tempfile.TemporaryDirectory(prefix="whis-mx-lease-") as temp:
            root, marker = Path(temp) / "store", Path(temp) / "claimed"
            store = Store(root)
            store.accept("matrix-lease-001", synthetic_wav())
            jobs = Jobs(store, max_attempts=3, lease_seconds=900)
            child = self._child(
                """
import sys, time
from pathlib import Path
from server.pass1 import Store
from server.jobs import Jobs
root, marker = map(Path, sys.argv[1:])
job = Jobs(Store(root)).claim()
assert job is not None and job.capture_id == 'matrix-lease-001'
marker.write_text(job.token)
time.sleep(60)
""",
                str(root), str(marker),
            )
            try:
                self.assertTrue(self._await(marker, child), "child never claimed the job")
            finally:
                child.kill(); child.wait(timeout=5)
                if child.stderr: child.stderr.close()

            # Lease expiry passes: the expiry claim requeues the dead lease
            # with backoff (not immediately runnable), then a fresh worker
            # claim runs it — the capture ends transcribed exactly once.
            self.assertIsNone(jobs.claim(now=time.time() + 1000))
            reclaimed = jobs.claim(now=time.time() + 1100)
            self.assertIsNotNone(reclaimed)
            self.assertEqual(reclaimed.capture_id, "matrix-lease-001")
            self.assertEqual(reclaimed.attempt, 2)
            self.assertTrue(jobs.complete(reclaimed, transcript="recovered after worker death"))
            note = store.get_note("matrix-lease-001")
            self.assertEqual(note.transcript, "recovered after worker death")
            self.assertEqual(note.status, "transcribed")
            with store._connect() as conn:
                rows = conn.execute(
                    "SELECT state FROM transcription_jobs WHERE capture_id='matrix-lease-001'"
                ).fetchall()
            self.assertEqual([r["state"] for r in rows], ["done"])

    def test_export_crash_never_leaves_a_partial_final_file(self):
        # Break: a crash mid-export leaves a truncated .md that later reads as
        # an owner hand-edit (permanent Conflict) or as the exported note.
        with tempfile.TemporaryDirectory(prefix="whis-mx-export-") as temp:
            root, dest, marker = (Path(temp) / p for p in ("store", "exported", "m"))
            store = Store(root)
            store.accept("matrix-export-001", synthetic_wav())
            note, receipt = store.get_note("matrix-export-001"), store.get("matrix-export-001")
            child = self._child(
                """
import os, sys, time
from pathlib import Path
from server.pass1 import Store
from server.export import export_note_to_dir
root, dest, marker = map(Path, sys.argv[1:])
store = Store(root)
def freeze_replace(a, b):
    marker.write_text('part-written')
    time.sleep(60)
os.replace = freeze_replace  # crash exactly at the atomic-rename boundary
export_note_to_dir(store.get_note('matrix-export-001'), store.get('matrix-export-001'), dest)
""",
                str(root), str(dest), str(marker),
            )
            try:
                self.assertTrue(self._await(marker, child), "child never wrote the .part file")
            finally:
                child.kill(); child.wait(timeout=5)
                if child.stderr: child.stderr.close()

            final = dest / "matrix-export-001.md"
            self.assertFalse(final.exists(), "final file must not exist before the rename")
            # A clean retry succeeds despite the stale .part, is byte-stable,
            # and a repeat export is idempotent (no conflict with itself).
            first = export_note_to_dir(note, receipt, dest)
            self.assertTrue(first.is_file())
            body = first.read_text(encoding="utf-8")
            self.assertEqual(export_note_to_dir(note, receipt, dest).read_text(encoding="utf-8"), body)


if __name__ == "__main__":
    unittest.main()
