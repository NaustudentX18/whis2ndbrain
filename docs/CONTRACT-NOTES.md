# Provisional capture-manifest contract notes (schema_version = 1)

**Status:** provisional software contract, tested with synthetic data only.
**Not** a frozen project-wide v1 API and not WB-007/WB-016/WB-018/WB-020/021 acceptance.
These decisions were recorded before interface edits, per the 2026-09-27 push plan.

## Provisional decisions

1. **Wire shape.** The uploader sends `multipart/form-data` with:
   - `file`: the raw WAV bytes (`audio/wav`, filename `<capture_id>.wav`), and
   - `metadata`: a UTF-8 JSON `CaptureManifest` (`schema_version=1`), and
   - `capture_id`: plain text field matching `metadata.capture_id`.
   The legacy raw-`audio/wav` body route remains compatibility-only and is
   still covered by regression tests. Legacy uploads carry no manifest and are
   never described as validated envelopes.

2. **Byte truth over metadata.** The host validates every immutable manifest
   fact against the received bytes before issuing a receipt:
   `capture_id` matches, `audio.sha256` matches the SHA-256 of the WAV,
   `audio.bytes` matches the received length, `audio.format/sample_rate_hz/
   channels/sample_width_bits` match the parsed WAV header, and
   `duration_ms` matches the WAV frame count within 100 ms. Any mismatch is a
   `400 rejected`; metadata is never trusted over bytes.

3. **Clock-null rule.** An unknown device clock is `clock_status="unknown"`
   with `captured_at=""`. A timestamp is present only when the clock status is
   `trusted` or `estimated`. The host's `received_at` remains the separate,
   authoritative receipt timestamp. No default ever upgrades an unknown clock
   to trusted.

4. **Replay/conflict semantics.** Same `capture_id` + same bytes + same
   manifest → the original receipt (idempotent replay, HTTP 200). Same ID with
   different bytes → `409 conflict` (existing behavior). Same ID + same bytes
   but a *different immutable manifest* → `409 conflict`. The accepted
   manifest is persisted in the same SQLite transaction as the receipt row, so
   a repeated response returns the original facts.

5. **Bounds.** Manifest JSON ≤ 16 KiB; WAV bounds are unchanged
   (`MAX_WAV_BYTES`). IDs use the existing `_check_id` rules. Malformed JSON,
   unsupported `schema_version`, missing required fields and out-of-range
   values are all `400 rejected` without altering the stored file, DB row or
   job.

## Explicitly out of scope here

Pairing/auth lifecycle, TLS trust, worker isolation, physical capture,
retention policy changes, and cross-team contract freeze. All WB acceptance
checks remain open.
