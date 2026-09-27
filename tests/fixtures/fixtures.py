"""Synthetic test fixtures for Whis2ndBrain testing."""

from __future__ import annotations

import hashlib
import io
import math
import struct
import wave


def generate_synthetic_wav(
    duration_s: float = 0.5,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    amplitude: float = 0.25,
) -> bytes:
    """Generate a clean synthetic sine wave in 16-bit mono PCM."""
    buf = io.BytesIO()
    total_samples = int(duration_s * sample_rate)
    with wave.open(buf, "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total_samples):
            val = int(amplitude * 32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        h.writeframes(frames)
    return buf.getvalue()


def sample_manifest_dict(capture_id: str = "fixture-cap-001") -> dict:
    wav = generate_synthetic_wav(duration_s=0.2)
    digest = hashlib.sha256(wav).hexdigest()
    return {
        "schema_version": 1,
        "device_id": "test-device-uuid",
        "capture_id": capture_id,
        "sequence": 1,
        "captured_at": "2026-09-26T12:00:00Z",
        "clock_status": "trusted",
        "duration_ms": 200,
        "audio": {
            "sha256": digest,
            "bytes": len(wav),
            "format": "wav",
            "sample_rate_hz": 16000,
            "channels": 1,
            "sample_width_bits": 16,
        },
    }
