"""Unit tests for Phase 3 (Server, Classifier, Export) and Phase 4 (PWA).

Each test names the break it catches.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from contracts.schemas import Category, Urgency
from server.export import (
    export_note_to_dir,
)
from server.pass1 import Conflict, Rejected, Store
from server.pipeline.classify import classify_transcript
from server.review import Review


def make_test_wav() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


class ClassifierTests(unittest.TestCase):
    def test_classify_todo_actionable(self):
        # Break: actionable todo phrases are not recognized or marked non-actionable.
        res = classify_transcript("Remember to buy more AA batteries for the recorder")
        self.assertEqual(res.category, Category.TODO.value)
        self.assertTrue(res.actionable)

    def test_classify_high_urgency(self):
        # Break: critical keywords fail to elevate note urgency.
        res = classify_transcript("This is critical and urgent, fix the network connection ASAP")
        self.assertEqual(res.urgency, Urgency.HIGH.value)

    def test_classify_meeting(self):
        # Break: sync / meeting notes misclassified as random thoughts.
        res = classify_transcript("Had a productive standup and meeting with the engineering team")
        self.assertEqual(res.category, Category.MEETING.value)

    def test_classify_ambiguous_short_text_fails_closed(self):
        # Break: very short ambiguous fragments hallucinate specific categories.
        res = classify_transcript("hello world")
        self.assertEqual(res.category, Category.UNREVIEWED.value)
        self.assertFalse(res.actionable)


class ExportHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-export-test-"))
        self.vault_mock = self.tmp / "Vault"
        self.vault_mock.mkdir()
        self.export_dir = self.tmp / "exports"
        self.store = Store(self.tmp / "store")
        self.wav = make_test_wav()
        self.store.accept("note-exp-1", self.wav)
        self.store.set_transcript("note-exp-1", "A great test idea", source="owner")

    def test_export_refuses_live_vault(self):
        # Break: exporter writes directly into forbidden vault path.
        note = self.store.get_note("note-exp-1")
        receipt = self.store.get("note-exp-1")
        with self.assertRaises(Rejected):
            export_note_to_dir(note, receipt, self.vault_mock, forbidden=self.vault_mock)

        # Refuses subfolder inside vault
        sub_vault = self.vault_mock / "Inbox"
        with self.assertRaises(Rejected):
            export_note_to_dir(note, receipt, sub_vault, forbidden=self.vault_mock)

    def test_export_creates_valid_markdown_and_detects_conflict(self):
        # Break: export does not create atomic file or overwrites modified target.
        note = self.store.get_note("note-exp-1")
        receipt = self.store.get("note-exp-1")
        out_path = export_note_to_dir(note, receipt, self.export_dir, forbidden=self.vault_mock)
        self.assertTrue(out_path.is_file())
        content = out_path.read_text()
        self.assertIn("type: permanent-note", content)
        self.assertIn("A great test idea", content)

        # Second export with identical content succeeds idempotently
        out_path2 = export_note_to_dir(note, receipt, self.export_dir, forbidden=self.vault_mock)
        self.assertEqual(out_path, out_path2)

        # External modification causes Conflict error
        out_path.write_text("tampered external content")
        with self.assertRaises(Conflict):
            export_note_to_dir(note, receipt, self.export_dir, forbidden=self.vault_mock)


class NotesApiAndPwaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-api-test-"))
        self.store = Store(self.tmp)
        self.wav = make_test_wav()
        self.token = "test-owner-token"
        self.review = Review(self.store, self.token)
        self.auth_headers = {"authorization": f"Bearer {self.token}"}
        _sid, self.csrf = self.review.auth.open_session()[:2]
        self.sid = _sid

        # Seed 3 notes
        for i in range(3):
            cid = f"test-note-{i}"
            self.store.accept(cid, self.wav)
            self.store.set_transcript(cid, f"Transcript sample number {i} with key term", source="model")

    def test_notes_list_pagination_and_search(self):
        # Break: notes API pagination or search returns wrong subsets or counts.
        status, _, body = self.review.handle(
            "GET",
            "/api/v1/notes?limit=2&offset=0",
            b"",
            "",
            headers=self.auth_headers,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["total"], 3)

        # Search filter
        status, _, body = self.review.handle(
            "GET",
            "/api/v1/notes?search=number+1",
            b"",
            "",
            headers=self.auth_headers,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["capture_id"], "test-note-1")

    def test_notes_list_rejects_unbounded_or_invalid_limit(self):
        for query in ("limit=-1", "limit=0", "limit=101", "limit=oops", "offset=-1"):
            with self.subTest(query=query):
                status, _, _ = self.review.handle(
                    "GET", f"/api/v1/notes?{query}", b"", "", headers=self.auth_headers,
                )
                self.assertEqual(status, 400)

    def test_note_patch_correction(self):
        # Break: PATCH API fails to record owner transcript correction or taxonomy.
        patch_body = json.dumps({"transcript": "Updated by owner", "category": "idea"}).encode()
        status, _, body = self.review.handle(
            "PATCH",
            "/api/v1/notes/test-note-0",
            patch_body,
            "",
            headers=self.auth_headers,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertEqual(data["transcript"], "Updated by owner")
        self.assertEqual(data["transcript_source"], "owner")
        self.assertEqual(data["category"], "idea")

        # Verified in database
        note = self.store.get_note("test-note-0")
        self.assertEqual(note.transcript, "Updated by owner")
        self.assertEqual(note.transcript_source, "owner")

    def test_note_markdown_download_route(self):
        # Break: markdown endpoint does not return text/markdown with YAML frontmatter.
        status, headers, body = self.review.handle(
            "GET",
            "/api/v1/notes/test-note-1/markdown",
            b"",
            "",
            headers=self.auth_headers,
        )
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers["content-type"])
        self.assertIn(b"type: permanent-note", body)
        self.assertIn(b"Transcript sample number 1", body)

    def test_pwa_shell_and_manifest_routes(self):
        # Break: PWA shell or manifest route fails or requires authentication.
        status, headers, body = self.review.handle("GET", "/manifest.json", b"", "")
        self.assertEqual(status, 200)
        self.assertIn("application/manifest+json", headers["content-type"])
        manifest = json.loads(body.decode())
        self.assertEqual(manifest["short_name"], "Whis2ndBrain")

        status, headers, body = self.review.handle("GET", "/sw.js", b"", "")
        self.assertEqual(status, 200)
        self.assertIn("application/javascript", headers["content-type"])

        # PWA requires auth
        status, _, _ = self.review.handle("GET", "/pwa", b"", "")
        self.assertEqual(status, 200)  # Shows login form for unauthenticated GET

        status, headers, body = self.review.handle(
            "GET",
            "/pwa",
            b"",
            f"whis_session={self.sid}",
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Whis2ndBrain Review", body)
        self.assertIn(b"editModal", body)


class TombstoneRevisionCursorRangeTests(unittest.TestCase):
    """BP1 item 4: tombstones, revisions/If-Match, cursor pagination, byte ranges."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-api4-test-"))
        self.store = Store(self.tmp)
        self.wav = make_test_wav()
        self.token = "test-owner-token"
        self.review = Review(self.store, self.token)
        self.auth_headers = {"authorization": f"Bearer {self.token}"}
        for i in range(3):
            cid = f"test-note-{i}"
            self.store.accept(cid, self.wav)
            self.store.set_transcript(cid, f"Transcript sample number {i}", source="model")



    def _req(self, method, path, body=b"", headers=None):
        return self.review.handle(method, path, body, "", headers=headers or self.auth_headers)



    def test_delete_tombstones_note_and_hides_everywhere(self):
        # Break: DELETE leaves the note visible, playable, editable or exportable.
        status, _, _ = self._req("DELETE", "/api/v1/notes/test-note-1")
        self.assertEqual(status, 204)

        status, _, body = self._req("GET", "/api/v1/notes")
        data = json.loads(body.decode())
        self.assertEqual([i["capture_id"] for i in data["items"]], ["test-note-0", "test-note-2"])
        self.assertEqual(data["total"], 2)

        # Tombstoned note is inspectable as the owner but inert.
        status, _, body = self._req("GET", "/api/v1/notes/test-note-1")
        self.assertEqual(status, 200)
        self.assertIsNotNone(json.loads(body.decode())["deleted_at"])

        # Idempotent at the HTTP level.
        status, _, _ = self._req("DELETE", "/api/v1/notes/test-note-1")
        self.assertEqual(status, 204)

        self.assertEqual(self._req("GET", "/api/v1/notes/test-note-1/audio")[0], 404)
        self.assertEqual(self._req("GET", "/n/test-note-1/audio")[0], 404)
        self.assertEqual(self._req("GET", "/api/v1/notes/test-note-1/markdown")[0], 404)
        patch = json.dumps({"transcript": "zombie edit"}).encode()
        self.assertEqual(self._req("PATCH", "/api/v1/notes/test-note-1", patch)[0], 409)
        self.assertEqual(self._req("POST", "/api/v1/notes/test-note-1/retry")[0], 409)

        status, _, _ = self._req("DELETE", "/api/v1/notes/does-not-exist")
        self.assertEqual(status, 404)



    def test_restore_returns_note_and_rejects_bad_states(self):
        # Break: restore un-deletes nothing, or accepts a non-deleted note.
        self.assertEqual(self._req("POST", "/api/v1/notes/test-note-0/restore")[0], 409)
        self.assertEqual(self._req("POST", "/api/v1/notes/missing/restore")[0], 404)
        self.assertEqual(self._req("GET", "/api/v1/notes/test-note-0/restore")[0], 405)

        self.assertEqual(self._req("DELETE", "/api/v1/notes/test-note-0")[0], 204)
        self.assertEqual(self._req("POST", "/api/v1/notes/test-note-0/restore")[0], 204)

        _, _, body = self._req("GET", "/api/v1/notes")
        data = json.loads(body.decode())
        self.assertEqual([i["capture_id"] for i in data["items"]], ["test-note-0", "test-note-1", "test-note-2"])
        self.assertEqual(self._req("POST", "/api/v1/notes/test-note-0/restore")[0], 409)



    def test_include_deleted_lists_tombstones(self):
        # Break: include_deleted hides tombstones or accepts garbage values.
        self._req("DELETE", "/api/v1/notes/test-note-2")

        status, _, body = self._req("GET", "/api/v1/notes?include_deleted=1")
        self.assertEqual(status, 200)
        data = json.loads(body.decode())
        self.assertEqual(data["total"], 3)
        by_id = {i["capture_id"]: i for i in data["items"]}
        self.assertIsNotNone(by_id["test-note-2"]["deleted_at"])

        self.assertEqual(self._req("GET", "/api/v1/notes?include_deleted=true")[0], 200)
        self.assertEqual(self._req("GET", "/api/v1/notes?include_deleted=bogus")[0], 400)



    def test_revision_in_payloads_and_bumped_by_patch(self):
        # Break: revision is absent, stale, or does not move on owner edits.
        status, headers, body = self._req("GET", "/api/v1/notes/test-note-0")
        data = json.loads(body.decode())
        self.assertEqual(data["revision"], 1)  # accept + model transcript
        self.assertEqual(headers["etag"], '"rev-1"')

        patch = json.dumps({"transcript": "owner edit"}).encode()
        status, _, body = self._req("PATCH", "/api/v1/notes/test-note-0", patch)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode())["revision"], 2)

        _, _, body = self._req("GET", "/api/v1/notes")
        by_id = {i["capture_id"]: i for i in json.loads(body.decode())["items"]}
        self.assertEqual(by_id["test-note-0"]["revision"], 2)



    def test_if_match_conflict_semantics(self):
        # Break: stale If-Match overwrites a newer edit; garbage is accepted.
        _, headers, _ = self._req("GET", "/api/v1/notes/test-note-0")
        etag = headers["etag"]

        patch = json.dumps({"transcript": "first writer"}).encode()
        status, _, body = self._req(
            "PATCH", "/api/v1/notes/test-note-0", patch, headers={**self.auth_headers, "if-match": etag}
        )
        self.assertEqual(status, 200)

        stale_patch = json.dumps({"transcript": "stale writer"}).encode()
        status, _, body = self._req(
            "PATCH", "/api/v1/notes/test-note-0", stale_patch, headers={**self.auth_headers, "if-match": etag}
        )
        self.assertEqual(status, 412)
        conflict = json.loads(body.decode())
        self.assertEqual(conflict["current_revision"], 2)

        # The stale write must not have landed.
        self.assertEqual(self.store.get_note("test-note-0").transcript, "first writer")

        self.assertEqual(
            self._req(
                "PATCH", "/api/v1/notes/test-note-0", stale_patch,
                headers={**self.auth_headers, "if-match": "garbage"},
            )[0],
            400,
        )
        self.assertEqual(
            self._req(
                "PATCH", "/api/v1/notes/test-note-0", stale_patch,
                headers={**self.auth_headers, "if-match": "*"},
            )[0],
            200,
        )



    def test_cursor_pagination_stable_under_new_inserts(self):
        # Break: offset drift under inserts; cursor pages duplicate or miss rows.
        _, _, body = self._req("GET", "/api/v1/notes?limit=2")
        page1 = json.loads(body.decode())
        self.assertEqual([i["capture_id"] for i in page1["items"]], ["test-note-0", "test-note-1"])
        self.assertEqual(page1["next_cursor"], "test-note-1")

        # An insert lands between the two pages.
        self.store.accept("test-note-9", self.wav)
        self.store.set_transcript("test-note-9", "late arrival", source="model")

        _, _, body = self._req("GET", "/api/v1/notes?limit=2&after=test-note-1")
        page2 = json.loads(body.decode())
        self.assertEqual([i["capture_id"] for i in page2["items"]], ["test-note-2", "test-note-9"])
        self.assertEqual(page2["total"], 4)

        _, _, body = self._req("GET", "/api/v1/notes?limit=2&after=test-note-9")
        page3 = json.loads(body.decode())
        self.assertEqual(page3["items"], [])
        self.assertIsNone(page3["next_cursor"])

        self.assertEqual(self._req("GET", "/api/v1/notes?after=" + "x" * 129)[0], 400)



    def test_audio_byte_range_partial_serving(self):
        # Break: ranges return wrong slices, codes, or lose Content-Range.
        full = self.wav
        size = len(full)

        status, headers, body = self._req("GET", "/api/v1/notes/test-note-0/audio")
        self.assertEqual(status, 200)
        self.assertEqual(headers["accept-ranges"], "bytes")
        self.assertEqual(body, full)

        status, headers, body = self._req(
            "GET", "/api/v1/notes/test-note-0/audio", headers={**self.auth_headers, "range": "bytes=0-99"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, full[:100])
        self.assertEqual(headers["content-range"], f"bytes 0-99/{size}")
        self.assertEqual(headers["content-length"], "100")

        status, _, body = self._req(
            "GET", "/api/v1/notes/test-note-0/audio", headers={**self.auth_headers, "range": f"bytes={size - 10}-"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, full[-10:])

        status, _, body = self._req(
            "GET", "/api/v1/notes/test-note-0/audio", headers={**self.auth_headers, "range": "bytes=-50"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, full[-50:])

        status, headers, _ = self._req(
            "GET", "/api/v1/notes/test-note-0/audio", headers={**self.auth_headers, "range": f"bytes={size}-"}
        )
        self.assertEqual(status, 416)
        self.assertEqual(headers["content-range"], f"bytes */{size}")

        # Malformed, inverted and multi-range are ignored: full 200 body.
        for bad in ("bytes=5-2", "bytes=0-1,3-4", "bytes=", "chunks=0-4"):
            with self.subTest(bad=bad):
                status, _, body = self._req(
                    "GET", "/api/v1/notes/test-note-0/audio", headers={**self.auth_headers, "range": bad}
                )
                self.assertEqual(status, 200)
                self.assertEqual(body, full)

        # The HTML-served audio route honours ranges too.
        status, _, body = self._req(
            "GET", "/n/test-note-0/audio", headers={**self.auth_headers, "range": "bytes=0-9"}
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, full[:10])




if __name__ == "__main__":
    unittest.main()
