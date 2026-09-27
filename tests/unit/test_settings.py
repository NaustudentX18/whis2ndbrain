"""Unit tests for server.settings — Settings storage."""

import json
import tempfile
import unittest
from pathlib import Path

from server.settings import Settings, SettingsStore


class SettingsDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = SettingsStore(Path(self.tmp))

    def test_load_returns_defaults_when_no_file(self):
        s = self.store.load()
        self.assertIsNone(s.vault_export_path)
        self.assertEqual(s.retention_hours, 168)
        self.assertFalse(s.encryption_enabled)
        self.assertFalse(s.drive_enabled)
        self.assertTrue(s.transcription_enabled)

    def test_save_and_reload(self):
        s = self.store.load()
        s = Settings(
            vault_export_path="/tmp/inbox",
            retention_hours=72,
            encryption_enabled=True,
            drive_enabled=False,
            transcription_enabled=True,
        )
        self.store.save(s)
        loaded = self.store.load()
        self.assertEqual(loaded.vault_export_path, "/tmp/inbox")
        self.assertEqual(loaded.retention_hours, 72)
        self.assertTrue(loaded.encryption_enabled)

    def test_save_writes_json_file(self):
        self.store.save(Settings())
        p = Path(self.tmp) / "settings.json"
        self.assertTrue(p.exists())
        data = json.loads(p.read_text())
        self.assertIn("retention_hours", data)

    def test_save_atomic_no_part_file_remains(self):
        self.store.save(Settings())
        part = Path(self.tmp) / "settings.json.part"
        self.assertFalse(part.exists())


class SettingsPatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = SettingsStore(Path(self.tmp))

    def test_patch_single_field(self):
        result = self.store.patch({"retention_hours": 48})
        self.assertEqual(result.retention_hours, 48)

    def test_patch_persists_to_disk(self):
        self.store.patch({"vault_export_path": "/tmp/vault-inbox"})
        loaded = self.store.load()
        self.assertEqual(loaded.vault_export_path, "/tmp/vault-inbox")

    def test_patch_unknown_field_raises(self):
        with self.assertRaises(ValueError):
            self.store.patch({"nonexistent_key": True})

    def test_patch_invalid_retention_raises(self):
        with self.assertRaises(ValueError):
            self.store.patch({"retention_hours": 0})

    def test_patch_relative_vault_path_raises(self):
        with self.assertRaises(ValueError):
            self.store.patch({"vault_export_path": "relative/path"})

    def test_patch_preserves_unpatched_fields(self):
        self.store.patch({"retention_hours": 24})
        self.store.patch({"encryption_enabled": True})
        final = self.store.load()
        self.assertEqual(final.retention_hours, 24)
        self.assertTrue(final.encryption_enabled)

    def test_unknown_keys_round_trip(self):
        """Future keys written by a newer version must survive a read-write cycle."""
        p = Path(self.tmp) / "settings.json"
        p.write_text(json.dumps({"retention_hours": 96, "future_feature": "beta"}))
        loaded = self.store.load()
        self.store.save(loaded)
        data = json.loads(p.read_text())
        self.assertIn("future_feature", data)
        self.assertEqual(data["future_feature"], "beta")


class SettingsValidationTests(unittest.TestCase):
    def test_retention_bounds(self):
        for bad in (0, -1, 9000):
            with self.assertRaises(ValueError):
                Settings(retention_hours=bad).validate()
        Settings(retention_hours=1).validate()
        Settings(retention_hours=8760).validate()

    def test_vault_path_must_be_absolute(self):
        with self.assertRaises(ValueError):
            Settings(vault_export_path="relative").validate()
        Settings(vault_export_path="/absolute/path").validate()
