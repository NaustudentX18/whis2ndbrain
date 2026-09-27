"""Formal versioned schemas for device captures, server receipts, notes, and export."""

from __future__ import annotations

import enum
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


class SchemaValidationError(ValueError):
    """Raised when data fails contract validation."""


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _check_id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SchemaValidationError(f"invalid {field}")


def _check_sha256(value: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise SchemaValidationError("sha256 must be a 64-character lowercase hex string")


def _check_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SchemaValidationError(f"invalid {field}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaValidationError(f"invalid {field}") from exc


class NoteStatus(str, enum.Enum):
    RECEIVED = "received"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    NOT_TRANSCRIBED = "not_transcribed"
    REVIEWED = "reviewed"
    PURGED = "purged"
    TRASHED = "trashed"


class TranscriptSource(str, enum.Enum):
    MODEL = "model"
    OWNER = "owner"
    NONE = "none"


class Category(str, enum.Enum):
    THOUGHT = "thought"
    TODO = "todo"
    MEETING = "meeting"
    IDEA = "idea"
    REFERENCE = "reference"
    UNREVIEWED = "unreviewed"


class Urgency(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class AudioMetadata:
    sha256: str
    bytes: int
    format: str = "wav"
    sample_rate_hz: int = 16000
    channels: int = 1
    sample_width_bits: int = 16

    def validate(self) -> None:
        _check_sha256(self.sha256)
        if type(self.bytes) is not int or not 44 <= self.bytes <= 25 * 1024 * 1024:
            raise SchemaValidationError("bytes must be greater than 0")
        if self.format != "wav":
            raise SchemaValidationError("format must be wav")
        if type(self.sample_rate_hz) is not int or self.sample_rate_hz not in (16000, 44100, 48000):
            raise SchemaValidationError(f"unsupported sample rate: {self.sample_rate_hz}")
        if type(self.channels) is not int or self.channels not in (1, 2):
            raise SchemaValidationError("channels must be mono or stereo")
        if type(self.sample_width_bits) is not int or self.sample_width_bits != 16:
            raise SchemaValidationError("sample width must be 16-bit PCM")


@dataclass(frozen=True)
class CaptureManifest:
    device_id: str
    capture_id: str
    sequence: int
    captured_at: str
    duration_ms: int
    audio: AudioMetadata
    schema_version: int = 1
    clock_status: str = "trusted"

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise SchemaValidationError("unsupported schema version")
        _check_id(self.device_id, "device_id")
        _check_id(self.capture_id, "capture_id")
        if type(self.sequence) is not int or self.sequence < 0:
            raise SchemaValidationError("sequence must be non-negative")
        if type(self.duration_ms) is not int or not 0 <= self.duration_ms <= 15 * 60 * 1000:
            raise SchemaValidationError("duration_ms must be non-negative")
        if self.clock_status not in ("trusted", "estimated", "unknown"):
            raise SchemaValidationError("invalid clock_status")
        _check_timestamp(self.captured_at, "captured_at")
        self.audio.validate()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaptureManifest:
        try:
            audio = AudioMetadata(**data["audio"])
            manifest = cls(
                schema_version=data.get("schema_version", 1),
                device_id=data["device_id"],
                capture_id=data["capture_id"],
                sequence=data["sequence"],
                captured_at=data["captured_at"],
                duration_ms=data["duration_ms"],
                clock_status=data.get("clock_status", "trusted"),
                audio=audio,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaValidationError("invalid capture manifest") from exc
        manifest.validate()
        return manifest


@dataclass(frozen=True)
class ReceiptResponse:
    capture_id: str
    receipt_id: str
    sha256: str
    byte_count: int
    received_at: str
    schema_version: int = 1

    def validate(self) -> None:
        if self.schema_version != 1:
            raise SchemaValidationError("unsupported schema version")
        _check_id(self.capture_id, "capture_id")
        if not isinstance(self.receipt_id, str) or not self.receipt_id:
            raise SchemaValidationError("missing receipt_id")
        _check_sha256(self.sha256)
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise SchemaValidationError("byte_count must be positive")
        _check_timestamp(self.received_at, "received_at")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SuggestionPayload:
    category: str = Category.UNREVIEWED.value
    urgency: str = Urgency.NORMAL.value
    actionable: bool = False
    domain: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NotePayload:
    capture_id: str
    status: str
    transcript: str | None = None
    transcript_source: str | None = None
    received_at: str | None = None
    audio_purged_at: str | None = None
    suggestions: SuggestionPayload | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExportFrontmatter:
    capture_id: str
    sha256: str
    transcript_source: str
    review_state: str
    type: str = "permanent-note"
    status: str = "draft"
    category: str | None = None
    urgency: str | None = None
    actionable: bool | None = None
    received_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Filter None values for clean YAML output
        return {k: v for k, v in asdict(self).items() if v is not None}
