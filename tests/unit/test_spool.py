"""Unit tests for device durable spool and crash recovery. Each test names the break it catches."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from contracts.schemas import CaptureManifest
from device.src.spool import (
    DeviceSpool,
    InvalidWavError,
    ReceiptVerificationError,
    SpoolError,
    SpoolUploader,
)


def make_wav_bytes(duration_frames: int = 160) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(16000)
        h.writeframes(b"\x00\x01" * duration_frames)
    return buf.getvalue()


class DeviceSpoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-spool-test-"))
        self.spool = DeviceSpool(self.tmp)
        self.valid_wav = make_wav_bytes()

    def test_start_and_finalize_valid_capture(self):
        # Break: finalize does not produce durable pending file or records incorrect hash.
        cap_id = "cap-spool-001"
        part_path = self.spool.start_capture(cap_id)
        self.assertTrue(part_path.is_file())
        self.assertEqual(part_path.parent, self.spool.partial_dir)

        record = self.spool.finalize_capture(cap_id, self.valid_wav)
        self.assertEqual(record.capture_id, cap_id)
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.byte_count, len(self.valid_wav))

        # Part file is gone, pending file exists
        self.assertFalse(part_path.exists())
        pending_file = self.spool.pending_dir / f"{cap_id}.wav"
        self.assertTrue(pending_file.is_file())
        self.assertEqual(pending_file.read_bytes(), self.valid_wav)

        # Listed in pending queue
        pending_list = self.spool.list_pending()
        self.assertEqual(len(pending_list), 1)
        self.assertEqual(pending_list[0].capture_id, cap_id)

    def test_finalize_invalid_wav_moves_to_quarantine(self):
        # Break: corrupted non-WAV data is spooled to pending or dropped silently.
        cap_id = "cap-corrupt-001"
        self.spool.start_capture(cap_id)
        with self.assertRaises(InvalidWavError):
            self.spool.finalize_capture(cap_id, b"NOT_A_VALID_RIFF_HEADER_123456789")

        # Pending should be empty
        self.assertFalse((self.spool.pending_dir / f"{cap_id}.wav").exists())
        self.assertEqual(len(self.spool.list_pending()), 0)

        # File is preserved in quarantine
        quarantine_file = self.spool.quarantine_dir / f"{cap_id}.corrupt.part"
        self.assertTrue(quarantine_file.is_file())

    def test_header_only_wav_is_not_reported_saved(self):
        cap_id = "cap-fake-riff"
        self.spool.start_capture(cap_id)
        fake = b"RIFF" + (4).to_bytes(4, "little") + b"WAVE"
        with self.assertRaises(InvalidWavError):
            self.spool.finalize_capture(cap_id, fake)
        self.assertTrue((self.spool.quarantine_dir / f"{cap_id}.corrupt.part").is_file())
        self.assertIsNone(self.spool.get_record(cap_id))

    def test_reconcile_on_boot_quarantines_interrupted_partials(self):
        # Break: power cut mid-write silently deletes or leaves unmanaged partial files.
        cap_id = "cap-partial-crash"
        part_file = self.spool.partial_dir / f"{cap_id}.part"
        part_file.write_bytes(b"unfinished recording bytes")

        result = self.spool.reconcile_on_boot()
        self.assertEqual(result["quarantined_partials"], 1)
        self.assertFalse(part_file.exists())

        quarantined = self.spool.quarantine_dir / f"{cap_id}.interrupted.part"
        self.assertTrue(quarantined.is_file())
        self.assertEqual(quarantined.read_bytes(), b"unfinished recording bytes")

    def test_reconcile_on_boot_recovers_unindexed_pending(self):
        # Break: power cut after atomic rename but before DB insert loses queue record.
        cap_id = "cap-unindexed-pending"
        dest_file = self.spool.pending_dir / f"{cap_id}.wav"
        dest_file.write_bytes(self.valid_wav)

        result = self.spool.reconcile_on_boot()
        self.assertEqual(result["recovered_pending"], 1)

        record = self.spool.get_record(cap_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.byte_count, len(self.valid_wav))
        self.assertEqual(record.sha256, hashlib.sha256(self.valid_wav).hexdigest())

    def test_reconcile_recovers_ack_rename_before_journal_update(self):
        # Break: a reboot between pending->synced rename and SQLite ACK leaves a capture stranded.
        cap_id = "cap-ack-rename-crash"
        self.spool.start_capture(cap_id)
        self.spool.finalize_capture(cap_id, self.valid_wav)
        with self.spool._connect() as conn:
            conn.execute("UPDATE spool_queue SET status = 'ack_persisting', receipt_id = ? WHERE capture_id = ?",
                         ("receipt-before-rename", cap_id))
        (self.spool.pending_dir / f"{cap_id}.wav").replace(self.spool.synced_dir / f"{cap_id}.wav")

        self.spool.reconcile_on_boot()

        recovered = self.spool.get_record(cap_id)
        self.assertEqual(recovered.status, "acknowledged")
        self.assertEqual(recovered.receipt_id, "receipt-before-rename")
        self.assertEqual((self.spool.synced_dir / f"{cap_id}.wav").read_bytes(), self.valid_wav)

    def test_reconcile_quarantines_synced_file_that_disagrees_with_journal(self):
        # Break: recovery marks corrupted audio acknowledged based only on file presence.
        cap_id = "cap-ack-mismatch"
        self.spool.start_capture(cap_id)
        self.spool.finalize_capture(cap_id, self.valid_wav)
        with self.spool._connect() as conn:
            conn.execute("UPDATE spool_queue SET status = 'ack_persisting', receipt_id = ? WHERE capture_id = ?",
                         ("receipt-before-rename", cap_id))
        (self.spool.pending_dir / f"{cap_id}.wav").replace(self.spool.synced_dir / f"{cap_id}.wav")
        (self.spool.synced_dir / f"{cap_id}.wav").write_bytes(b"tampered")

        self.spool.reconcile_on_boot()

        self.assertEqual(self.spool.get_record(cap_id).status, "quarantined")
        self.assertTrue((self.spool.quarantine_dir / f"{cap_id}.bad_synced.wav").is_file())

    def test_finalize_rejects_capture_id_reuse_without_replacing_saved_audio(self):
        # Break: retrying finalize overwrites an existing capture and changes its journaled identity.
        cap_id = "cap-duplicate-finalize"
        original = self.spool.finalize_capture(cap_id, self.valid_wav)
        with self.assertRaises(SpoolError):
            self.spool.start_capture(cap_id)

        self.assertEqual((self.spool.pending_dir / f"{cap_id}.wav").read_bytes(), self.valid_wav)
        self.assertEqual(self.spool.get_record(cap_id).sha256, original.sha256)

    def test_reconcile_on_boot_resets_in_flight_to_pending(self):
        # Break: reboot during network upload leaves capture permanently stuck in in_flight.
        cap_id = "cap-stuck-flight"
        self.spool.start_capture(cap_id)
        self.spool.finalize_capture(cap_id, self.valid_wav)
        self.spool.mark_in_flight(cap_id)

        self.assertEqual(self.spool.get_record(cap_id).status, "in_flight")
        result = self.spool.reconcile_on_boot()
        self.assertEqual(result["reset_in_flight"], 1)
        self.assertEqual(self.spool.get_record(cap_id).status, "pending")

    def test_mark_acknowledged_moves_file_to_synced(self):
        # Break: acknowledgement leaves file in pending, causing duplicate sync loops.
        cap_id = "cap-ack-test"
        self.spool.start_capture(cap_id)
        record = self.spool.finalize_capture(cap_id, self.valid_wav)

        self.spool.mark_acknowledged(
            cap_id,
            receipt_id="rcpt-12345",
            sha256=record.sha256,
            byte_count=record.byte_count,
        )

        self.assertFalse((self.spool.pending_dir / f"{cap_id}.wav").exists())
        synced_file = self.spool.synced_dir / f"{cap_id}.wav"
        self.assertTrue(synced_file.is_file())
        self.assertEqual(synced_file.read_bytes(), self.valid_wav)

        updated = self.spool.get_record(cap_id)
        self.assertEqual(updated.status, "acknowledged")
        self.assertEqual(updated.receipt_id, "rcpt-12345")

    def test_mark_acknowledged_refuses_mismatched_receipt(self):
        # Break: fake/corrupt server receipt is accepted and moves bad audio to synced.
        cap_id = "cap-bad-hash"
        self.spool.start_capture(cap_id)
        record = self.spool.finalize_capture(cap_id, self.valid_wav)

        with self.assertRaises(ReceiptVerificationError):
            self.spool.mark_acknowledged(
                cap_id,
                receipt_id="rcpt-bogus",
                sha256="wrong-sha256-hash-value-0000000000000000000000000000000000000000",
                byte_count=record.byte_count,
            )

        self.assertFalse((self.spool.synced_dir / f"{cap_id}.wav").exists())
        self.assertFalse((self.spool.pending_dir / f"{cap_id}.wav").exists())
        # Audio moved to quarantine for investigation
        self.assertTrue((self.spool.quarantine_dir / f"{cap_id}.receipt_mismatch.wav").exists())
        self.assertEqual(self.spool.get_record(cap_id).status, "quarantined")


class SpoolUploaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-uploader-test-"))
        self.spool = DeviceSpool(self.tmp)
        self.valid_wav = make_wav_bytes()
        self.uploader = SpoolUploader(
            self.spool, "http://127.0.0.1:9999", token="test-token", allow_insecure_loopback=True,
        )

    def test_plaintext_transport_is_rejected_except_explicit_loopback(self):
        with self.assertRaises(ValueError):
            SpoolUploader(self.spool, "http://127.0.0.1:9999", token="test-token")
        with self.assertRaises(ValueError):
            SpoolUploader(
                self.spool, "http://192.0.2.10:9999", token="test-token",
                allow_insecure_loopback=True,
            )

    @patch("device.src.spool._open_request")
    def test_upload_success_acknowledges_and_syncs(self, mock_urlopen):
        # Break: uploader does not parse receipt or leaves pending status unchanged.
        cap_id = "cap-upload-ok"
        self.spool.start_capture(cap_id)
        record = self.spool.finalize_capture(cap_id, self.valid_wav)

        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = json.dumps(
            {
                "capture_id": cap_id,
                "receipt_id": "receipt-uuid-abc",
                "sha256": record.sha256,
                "byte_count": record.byte_count,
                "received_at": "2026-09-26T12:00:00Z",
            }
        ).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.uploader.upload_one(record)
        self.assertEqual(res["status"], "acknowledged")
        self.assertEqual(self.spool.get_record(cap_id).status, "acknowledged")
        self.assertTrue((self.spool.synced_dir / f"{cap_id}.wav").exists())

    @patch("device.src.spool._open_request")
    def test_wrong_capture_receipt_keeps_original_pending(self, mock_urlopen):
        cap_id = "cap-wrong-receipt"
        record = self.spool.finalize_capture(cap_id, self.valid_wav)
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = json.dumps({
            "capture_id": "some-other-capture",
            "receipt_id": "receipt-other",
            "sha256": record.sha256,
            "byte_count": record.byte_count,
            "received_at": "2026-09-26T12:00:00Z",
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        self.assertEqual(self.uploader.upload_one(record)["status"], "invalid_receipt")
        self.assertEqual(self.spool.get_record(cap_id).status, "pending")
        self.assertTrue((self.spool.pending_dir / f"{cap_id}.wav").is_file())

    @patch("device.src.spool._open_request")
    def test_upload_network_error_leaves_capture_in_pending(self, mock_urlopen):
        # Break: network timeout discards local capture or leaves capture stuck in in_flight.
        cap_id = "cap-upload-retry"
        self.spool.start_capture(cap_id)
        record = self.spool.finalize_capture(cap_id, self.valid_wav)

        mock_urlopen.side_effect = TimeoutError("connection timed out")

        res = self.uploader.upload_one(record)
        self.assertEqual(res["status"], "network_error")

        rec = self.spool.get_record(cap_id)
        self.assertEqual(rec.status, "pending")
        self.assertEqual(rec.attempts, 1)
        self.assertTrue((self.spool.pending_dir / f"{cap_id}.wav").exists())


if __name__ == "__main__":
    unittest.main()


class ManifestEnvelopeTests(unittest.TestCase):
    """Provisional v1 capture manifest (docs/CONTRACT-NOTES.md), synthetic data."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="whis-manifest-test-"))
        self.spool = DeviceSpool(self.tmp, device_id="dev-test-1")
        self.valid_wav = make_wav_bytes()
        self.uploader = SpoolUploader(
            self.spool, "http://127.0.0.1:9999", token="test-token", allow_insecure_loopback=True,
        )

    def _record(self, cap_id):
        self.spool.start_capture(cap_id)
        return self.spool.finalize_capture(cap_id, self.valid_wav)

    def test_finalize_builds_unknown_clock_manifest(self):
        record = self._record("cap-manifest-1")
        self.assertIsNotNone(record.manifest_json)
        m = CaptureManifest.from_dict(json.loads(record.manifest_json))
        self.assertEqual(m.device_id, "dev-test-1")
        self.assertEqual(m.capture_id, "cap-manifest-1")
        self.assertEqual(m.clock_status, "unknown")
        self.assertEqual(m.captured_at, "")
        self.assertEqual(m.audio.sha256, record.sha256)
        self.assertEqual(m.audio.bytes, record.byte_count)
        self.assertEqual(m.audio.sample_rate_hz, 16000)
        self.assertEqual(m.audio.channels, 1)
        self.assertEqual(m.audio.sample_width_bits, 16)
        self.assertEqual(m.sequence, 0)

    def test_sequence_is_monotonic_per_device(self):
        first = self._record("cap-seq-a")
        second = self._record("cap-seq-b")
        self.assertEqual(second.sequence, first.sequence + 1)

    @patch("device.src.spool._open_request")
    def test_upload_sends_manifest_multipart_envelope(self, mock_urlopen):
        cap_id = "cap-manifest-upload"
        record = self._record(cap_id)
        seen_request = {}

        def capture_request(req, timeout=None):
            seen_request["body"] = req.data
            seen_request["content_type"] = req.headers.get("Content-type")
            mock_resp = MagicMock()
            mock_resp.status = 201
            mock_resp.read.return_value = json.dumps({
                "capture_id": cap_id,
                "receipt_id": "receipt-m1",
                "sha256": record.sha256,
                "byte_count": record.byte_count,
                "received_at": "2026-09-28T00:00:00Z",
            }).encode()
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        mock_urlopen.side_effect = capture_request
        res = self.uploader.upload_one(record)
        self.assertEqual(res["status"], "acknowledged")
        body = seen_request["body"]
        self.assertIn(b'form-data; name="metadata"', body)
        self.assertIn(b'filename="cap-manifest-upload.wav"', body)
        self.assertIn(b'"clock_status": "unknown"', body)
        # The uploaded bytes themselves are intact inside the multipart body.
        self.assertIn(self.valid_wav, body)

    @patch("device.src.spool._open_request")
    def test_manifest_audio_mismatch_never_uploaded(self, mock_urlopen):
        cap_id = "cap-manifest-tamper"
        record = self._record(cap_id)
        tampered = json.loads(record.manifest_json)
        tampered["audio"]["sha256"] = "b" * 64
        with self.spool._connect() as conn:
            conn.execute(
                "UPDATE spool_queue SET manifest_json = ? WHERE capture_id = ?",
                (json.dumps(tampered), cap_id),
            )
        record = self.spool.get_record(cap_id)
        res = self.uploader.upload_one(record)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "manifest does not match audio")
        mock_urlopen.assert_not_called()
        self.assertNotEqual(self.spool.get_record(cap_id).status, "acknowledged")
