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
            f"whis_session={self.token}",
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Whis2ndBrain Review", body)
        self.assertIn(b"editModal", body)


if __name__ == "__main__":
    unittest.main()
