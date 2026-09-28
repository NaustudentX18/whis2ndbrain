"""Unit tests for system contracts and schemas. Each test names the break it catches."""

from __future__ import annotations

import unittest

from contracts.schemas import (
    AudioMetadata,
    CaptureManifest,
    ExportFrontmatter,
    ReceiptResponse,
    SchemaValidationError,
)
from tests.fixtures import sample_manifest_dict


class ContractTests(unittest.TestCase):
    def test_valid_manifest_roundtrip(self):
        # Break: valid manifest fails schema validation or does not roundtrip.
        raw = sample_manifest_dict("cap-contract-01")
        manifest = CaptureManifest.from_dict(raw)
        self.assertEqual(manifest.capture_id, "cap-contract-01")
        self.assertEqual(manifest.audio.format, "wav")
        dumped = manifest.to_dict()
        self.assertEqual(dumped["capture_id"], "cap-contract-01")

    def test_invalid_sha256_raises_validation_error(self):
        # Break: malformed hex hash is accepted by AudioMetadata.
        audio = AudioMetadata(sha256="not-a-valid-sha256", bytes=100)
        with self.assertRaises(SchemaValidationError):
            audio.validate()

    def test_non_hex_sha256_rejected_even_at_valid_length(self):
        # Break: an arbitrary 64-character string is trusted as a content digest.
        with self.assertRaises(SchemaValidationError):
            AudioMetadata(sha256="g" * 64, bytes=100).validate()

    def test_capture_id_rejects_path_and_markup_characters(self):
        # Break: IDs containing separators or HTML syntax escape their storage/rendering boundary.
        for bad_id in ("../capture", "folder\\capture", 'capture" onclick="x'):
            with self.subTest(capture_id=bad_id):
                raw = sample_manifest_dict(bad_id)
                with self.assertRaises(SchemaValidationError):
                    CaptureManifest.from_dict(raw)

    def test_audio_channel_and_sample_width_values_are_validated(self):
        # Break: metadata advertises audio layout the implementation cannot safely consume.
        for field, value in (("channels", 0), ("channels", 3), ("sample_width_bits", 8),
                             ("sample_width_bits", 24)):
            with self.subTest(field=field, value=value):
                audio = AudioMetadata(sha256="a" * 64, bytes=100, **{field: value})
                with self.assertRaises(SchemaValidationError):
                    audio.validate()

    def test_schema_version_timestamp_and_numeric_types_are_validated(self):
        # Break: malformed versions/timestamps or stringified numbers pass as a valid v1 manifest.
        cases = (
            ("schema_version", 2),
            ("captured_at", "yesterday-ish"),
            ("sequence", "1"),
            ("duration_ms", "200"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                raw = sample_manifest_dict("cap-contract-types")
                raw[field] = value
                with self.assertRaises(SchemaValidationError):
                    CaptureManifest.from_dict(raw)

    def test_invalid_clock_status_raises_validation_error(self):
        # Break: arbitrary clock status strings bypass manifest validation.
        raw = sample_manifest_dict("cap-contract-02")
        raw["clock_status"] = "super-accurate"
        with self.assertRaises(SchemaValidationError):
            CaptureManifest.from_dict(raw)

    def test_receipt_response_validation(self):
        # Break: receipt response accepts negative bytes or empty IDs.
        receipt = ReceiptResponse(
            capture_id="cap-1",
            receipt_id="rcpt-1",
            sha256="a" * 64,
            byte_count=1024,
            received_at="2026-09-26T12:00:00Z",
        )
        receipt.validate()
        self.assertEqual(receipt.to_dict()["byte_count"], 1024)

        bad_receipt = ReceiptResponse(
            capture_id="cap-1",
            receipt_id="",
            sha256="a" * 64,
            byte_count=1024,
            received_at="2026-09-26T12:00:00Z",
        )
        with self.assertRaises(SchemaValidationError):
            bad_receipt.validate()

    def test_export_frontmatter_filtering(self):
        # Break: None fields pollute YAML frontmatter dictionary.
        frontmatter = ExportFrontmatter(
            capture_id="cap-1",
            sha256="a" * 64,
            transcript_source="model",
            review_state="reviewed",
            category="thought",
            urgency=None,
        )
        d = frontmatter.to_dict()
        self.assertIn("category", d)
        self.assertNotIn("urgency", d)
        self.assertEqual(d["type"], "permanent-note")


if __name__ == "__main__":
    unittest.main()

class CaptureManifestClockRuleTests(unittest.TestCase):
    """Provisional clock rule: unknown clock = empty captured_at, never trusted."""

    @staticmethod
    def _manifest(**overrides):
        from contracts.schemas import AudioMetadata, CaptureManifest

        base = {
            "device_id": "dev-1",
            "capture_id": "cap-1",
            "sequence": 0,
            "captured_at": "",
            "duration_ms": 10,
            "audio": AudioMetadata(
                sha256="a" * 64, bytes=336, sample_rate_hz=16000, channels=1,
                sample_width_bits=16,
            ),
        }
        base.update(overrides)
        return CaptureManifest(**base)

    def test_unknown_clock_with_empty_timestamp_is_valid(self):
        m = self._manifest(clock_status="unknown", captured_at="")
        m.validate()  # must not raise

    def test_unknown_clock_with_timestamp_is_rejected(self):
        m = self._manifest(clock_status="unknown", captured_at="2026-09-28T00:00:00Z")
        with self.assertRaises(SchemaValidationError):
            m.validate()

    def test_missing_clock_fields_default_to_unknown(self):
        data = self._manifest().to_dict()
        data.pop("clock_status")
        data.pop("captured_at")
        m = CaptureManifest.from_dict(data)
        self.assertEqual(m.clock_status, "unknown")
        self.assertEqual(m.captured_at, "")

    def test_estimated_clock_requires_timestamp(self):
        m = self._manifest(clock_status="estimated", captured_at="")
        with self.assertRaises(SchemaValidationError):
            m.validate()
        m2 = self._manifest(clock_status="estimated", captured_at="2026-09-28T00:00:00Z")
        m2.validate()  # must not raise
