"""A1 / WB-030 export hardening: hostile matrix against server/export.py.

Covers: path traversal and YAML-breaking capture ids (defended independently
of store-level validation), symlink file/dir attacks, vault-destination
refusal, repeat-export idempotency, digest stability, hand-edit conflict
preservation, hostile-Unicode transcripts, unicode/space destination dirs.
"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

import yaml

from server.export import build_markdown_body, export_note_to_dir
from server.pass1 import Conflict, Note, Receipt, Rejected, Store

HOSTILE_TRANSCRIPT = (
    "---\ntype: daily\nstatus: active\n---\n"
    "not real frontmatter 🎙️ مرحبا 日本語 \u200b\n"
    "quotes: 'single' \"double\" \\backslash\\\n"
    "yaml: [a, {b: 1}]\n"
    "ends with newline\n"
)


def make_wav() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * 160)
    return buf.getvalue()


def make_receipt(capture_id: str) -> Receipt:
    return Receipt(
        capture_id=capture_id,
        sha256=hashlib.sha256(b"stub").hexdigest(),
        byte_count=5,
        receipt_id="r-" + capture_id,
    )


class HostileCaptureIdTests(unittest.TestCase):
    """The exporter defends itself; it never trusts store-level validation."""

    def setUp(self):
        self.dest = Path(tempfile.mkdtemp(prefix="whis-exp-hard-"))

    def _note(self, capture_id: str) -> Note:
        return Note(capture_id, "reviewed", "text", "owner")

    def test_traversal_and_absolute_ids_are_rejected(self):
        for bad in ("../escape", "..", "../../etc", "/abs/path", "a/b", "a//b", ".hidden", "", "x" * 200):
            with self.assertRaises(Rejected, msg=bad):
                export_note_to_dir(self._note(bad), make_receipt("x"), self.dest)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_yaml_breaking_ids_are_rejected(self):
        for bad in ("---", "x: 1", "- item", "#comment", "'quoted'", '"dq"', "a\nid", "id with space"):
            with self.assertRaises(Rejected, msg=bad):
                export_note_to_dir(self._note(bad), make_receipt("x"), self.dest)
        self.assertEqual(list(self.dest.iterdir()), [])


class SymlinkAttackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-exp-sym-"))
        self.dest = self.tmp / "exports"
        self.dest.mkdir()
        self.victim = self.tmp / "victim.txt"
        self.victim.write_text("do not touch\n")
        self.note = Note("cap-1", "reviewed", "text", "owner")
        self.receipt = make_receipt("cap-1")

    def test_file_symlink_is_refused_and_never_written_through(self):
        (self.dest / "cap-1.md").symlink_to(self.victim)
        with self.assertRaises(Rejected):
            export_note_to_dir(self.note, self.receipt, self.dest)
        self.assertEqual(self.victim.read_text(), "do not touch\n")

    def test_symlinked_dest_dir_into_forbidden_tree_is_refused(self):
        vault_like = self.tmp / "Vault"
        vault_like.mkdir()
        sneaky = self.tmp / "sneaky"
        sneaky.symlink_to(vault_like, target_is_directory=True)
        with self.assertRaises(Rejected):
            export_note_to_dir(self.note, self.receipt, sneaky, forbidden=vault_like)

    def test_dest_inside_forbidden_tree_is_refused(self):
        vault_like = self.tmp / "Vault"
        (vault_like / "exports").mkdir(parents=True)
        with self.assertRaises(Rejected):
            export_note_to_dir(self.note, self.receipt, vault_like / "exports", forbidden=vault_like)


class IdempotencyAndConflictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-exp-idem-"))
        self.dest = self.tmp / "exports"
        self.root = self.tmp / "store"
        self.store = Store(self.root)
        self.store.accept("cap-1", make_wav())
        self.store.set_transcript("cap-1", HOSTILE_TRANSCRIPT, source="owner")
        self.note = self.store.get_note("cap-1")
        self.receipt = self.store.get("cap-1")

    def test_repeat_export_is_idempotent_with_stable_digest(self):
        first = export_note_to_dir(self.note, self.receipt, self.dest)
        digest_one = hashlib.sha256(first.read_bytes()).hexdigest()
        second = export_note_to_dir(self.note, self.receipt, self.dest)
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(second.read_bytes()).hexdigest(), digest_one)

    def test_digest_is_stable_across_fresh_directories_and_reloads(self):
        one = export_note_to_dir(self.note, self.receipt, self.dest / "a")
        # reload the note from a fresh Store instance over the same root
        fresh_store = Store(self.root)
        fresh_note = fresh_store.get_note("cap-1")
        two = export_note_to_dir(fresh_note, fresh_store.get("cap-1"), self.dest / "b")
        self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_hand_edit_conflict_is_preserved_not_overwritten(self):
        path = export_note_to_dir(self.note, self.receipt, self.dest)
        path.write_text(path.read_text(encoding="utf-8") + "\nOWNER HAND EDIT\n", encoding="utf-8")
        with self.assertRaises(Conflict):
            export_note_to_dir(self.note, self.receipt, self.dest)
        self.assertIn("OWNER HAND EDIT", path.read_text(encoding="utf-8"))

    def test_changed_note_conflicts_with_older_export(self):
        export_note_to_dir(self.note, self.receipt, self.dest)
        self.store.set_transcript("cap-1", "changed text", source="owner")
        with self.assertRaises(Conflict):
            export_note_to_dir(self.store.get_note("cap-1"), self.receipt, self.dest)


class HostileTranscriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-exp-uni-"))
        self.root = self.tmp / "store"
        self.store = Store(self.root)
        self.store.accept("cap-1", make_wav())
        self.store.set_transcript("cap-1", HOSTILE_TRANSCRIPT, source="owner")

    def test_transcript_round_trips_verbatim_and_stays_out_of_frontmatter(self):
        note = self.store.get_note("cap-1")
        receipt = self.store.get("cap-1")
        body = build_markdown_body(note, receipt)
        # frontmatter block parses as YAML with exactly the controlled keys
        blocks = body.split("---\n")
        fm = yaml.safe_load(blocks[1])
        self.assertEqual(
            set(fm),
            {"capture_id", "sha256", "transcript_source", "review_state", "type", "status", "received_at"},
        )
        # the hostile transcript appears verbatim in the body, never in YAML
        self.assertNotIn(HOSTILE_TRANSCRIPT.split("---\n")[-1], yaml.safe_dump(fm))
        self.assertIn("not real frontmatter 🎙️ مرحبا 日本語", body)
        self.assertIn("yaml: [a, {b: 1}]", body)

    def test_exported_file_reparses_with_our_frontmatter_intact(self):
        note = self.store.get_note("cap-1")
        receipt = self.store.get("cap-1")
        path = export_note_to_dir(note, receipt, self.tmp / "exports")
        text = path.read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---\n")[1])
        self.assertEqual(fm["capture_id"], "cap-1")
        self.assertEqual(fm["type"], "permanent-note")
        # transcript's fake frontmatter survives as inert body text after our
        # real block - a consumer parsing only the first block sees ours.
        # index 0: before our opener; 1: our fm; 2: blank line; 3: fake block
        self.assertTrue(text.split("---\n")[3].startswith("type: daily"))

    def test_unicode_and_space_destination_directory_works(self):
        note = self.store.get_note("cap-1")
        receipt = self.store.get("cap-1")
        dest = self.tmp / "étude 日本" / "exports dir"
        path = export_note_to_dir(note, receipt, dest)
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
