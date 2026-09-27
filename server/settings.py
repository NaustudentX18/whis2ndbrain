"""Settings storage for Whis2ndBrain host.

Settings are kept in a JSON file at <root>/settings.json.
They are never stored in the SQLite DB so they remain human-editable
and survice a DB wipe/migrate without data loss.

All fields have safe defaults; unknown keys are preserved on round-trip
so future versions can add fields without breaking older readers.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTINGS_FILE = "settings.json"

# Sentinel used when a setting has not been explicitly set
_UNSET = object()


@dataclass
class Settings:
    # ── Export ─────────────────────────────────────────────────────────────
    vault_export_path: str | None = None
    """Absolute path to the Obsidian inbox folder for Markdown exports."""

    # ── Retention ──────────────────────────────────────────────────────────
    retention_hours: int = 168
    """How long (hours) to keep audio on the host before purging. Default 7 days."""

    # ── Encryption ─────────────────────────────────────────────────────────
    encryption_enabled: bool = False
    """Whether new audio files are encrypted at rest with AES-256-GCM."""

    encryption_key_file: str | None = None
    """Path to the key file used for at-rest encryption (mode 0o600)."""

    # ── Google Drive ───────────────────────────────────────────────────────
    drive_enabled: bool = False
    """Whether Google Drive backup is configured."""

    drive_folder_id: str | None = None
    """ID of the Drive folder used for backups (Whis2ndBrain/)."""

    drive_last_backup_at: str | None = None
    """ISO-8601 UTC timestamp of the last successful Drive backup."""

    # ── Transcription ──────────────────────────────────────────────────────
    transcription_enabled: bool = True
    """Whether the background worker should transcribe received notes."""

    suggestion_categories_enabled: bool = True
    """Whether the classifier should produce category/urgency suggestions."""

    # ── Device ─────────────────────────────────────────────────────────────
    device_id: str | None = None
    """Paired device identifier (set during first sync)."""

    # ── Extra ──────────────────────────────────────────────────────────────
    _extra: dict = field(default_factory=dict, repr=False, compare=False)
    """Unrecognised keys preserved on round-trip."""

    # ── Validation ─────────────────────────────────────────────────────────
    def validate(self) -> None:
        if not isinstance(self.retention_hours, int) or not 1 <= self.retention_hours <= 8760:
            raise ValueError("retention_hours must be 1–8760")
        if self.vault_export_path is not None:
            p = Path(self.vault_export_path)
            # Must be absolute; existence is not required (it may not exist yet)
            if not p.is_absolute():
                raise ValueError("vault_export_path must be an absolute path")

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        d.update(self._extra)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in cls.__dataclass_fields__.values()
                 if not f.name.startswith("_")}
        extra = {k: v for k, v in data.items() if k not in known}
        kwargs = {k: v for k, v in data.items() if k in known}
        obj = cls(**kwargs)
        object.__setattr__(obj, "_extra", extra)
        return obj

    # ── Permitted PATCH fields ─────────────────────────────────────────────
    PATCHABLE = frozenset({
        "vault_export_path",
        "retention_hours",
        "encryption_enabled",
        "encryption_key_file",
        "drive_enabled",
        "drive_folder_id",
        "drive_last_backup_at",
        "transcription_enabled",
        "suggestion_categories_enabled",
        "device_id",
    })


class SettingsStore:
    def __init__(self, root: Path):
        self._path = Path(root) / SETTINGS_FILE

    def load(self) -> Settings:
        if not self._path.exists():
            return Settings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return Settings()
            return Settings.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return Settings()

    def save(self, settings: Settings) -> None:
        settings.validate()
        data = json.dumps(settings.to_dict(), indent=2, ensure_ascii=False)
        _write_durable(self._path, (data + "\n").encode("utf-8"))

    def patch(self, updates: dict) -> Settings:
        """Apply *updates* (validated subset of patchable fields) and persist."""
        unknown = set(updates) - Settings.PATCHABLE
        if unknown:
            raise ValueError(f"unknown settings fields: {unknown}")
        settings = self.load()
        for key, value in updates.items():
            object.__setattr__(settings, key, value)
        settings.validate()
        self.save(settings)
        return settings


def _write_durable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with part.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(part, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
