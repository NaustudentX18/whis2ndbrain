"""Unit tests for server.crypto — AES-256-GCM at-rest encryption."""

import os
import tempfile
import unittest
from pathlib import Path

from server.crypto import (
    EncryptionError,
    decrypt_bytes,
    decrypt_file,
    enc_path,
    encrypt_bytes,
    encrypt_file,
    generate_key_file,
    load_key_file,
)

PASSPHRASE = "test-passphrase-do-not-use-in-prod"
SAMPLE = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 20  # fake WAV header


class EncryptDecryptTests(unittest.TestCase):
    def test_roundtrip_bytes(self):
        blob = encrypt_bytes(SAMPLE, PASSPHRASE)
        self.assertEqual(decrypt_bytes(blob, PASSPHRASE), SAMPLE)

    def test_magic_header_present(self):
        blob = encrypt_bytes(b"hello", PASSPHRASE)
        self.assertTrue(blob[:4] == b"WB01")

    def test_each_encrypt_produces_different_ciphertext(self):
        a = encrypt_bytes(b"same data", PASSPHRASE)
        b = encrypt_bytes(b"same data", PASSPHRASE)
        self.assertNotEqual(a, b)  # different salt + nonce each time

    def test_wrong_passphrase_raises(self):
        blob = encrypt_bytes(b"secret", PASSPHRASE)
        with self.assertRaises(EncryptionError):
            decrypt_bytes(blob, "wrong-passphrase")

    def test_tampered_ciphertext_raises(self):
        blob = bytearray(encrypt_bytes(b"secret", PASSPHRASE))
        blob[-1] ^= 0xFF  # flip last byte
        with self.assertRaises(EncryptionError):
            decrypt_bytes(bytes(blob), PASSPHRASE)

    def test_truncated_blob_raises(self):
        with self.assertRaises(EncryptionError):
            decrypt_bytes(b"WB01" + b"\x00" * 10, PASSPHRASE)

    def test_wrong_magic_raises(self):
        with self.assertRaises(EncryptionError):
            decrypt_bytes(b"XXXX" + b"\x00" * 40, PASSPHRASE)

    def test_empty_plaintext_roundtrip(self):
        blob = encrypt_bytes(b"", PASSPHRASE)
        self.assertEqual(decrypt_bytes(blob, PASSPHRASE), b"")


class FileEncryptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_encrypt_and_decrypt_file(self):
        src = Path(self.tmp) / "audio.wav"
        src.write_bytes(SAMPLE)
        enc = Path(self.tmp) / "audio.enc"
        encrypt_file(src, enc, PASSPHRASE)
        self.assertTrue(enc.exists())
        result = decrypt_file(enc, PASSPHRASE)
        self.assertEqual(result, SAMPLE)

    def test_enc_path_returns_enc_suffix(self):
        p = Path("/tmp/test.wav")
        self.assertEqual(enc_path(p), Path("/tmp/test.enc"))

    def test_encrypt_writes_atomically_via_part_file(self):
        """The .part file should not exist after a successful encrypt."""
        src = Path(self.tmp) / "in.wav"
        src.write_bytes(b"X" * 100)
        dest = Path(self.tmp) / "out.enc"
        encrypt_file(src, dest, PASSPHRASE)
        part = dest.with_name(dest.name + ".part")
        self.assertFalse(part.exists())


class KeyFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_generate_and_load_key_file(self):
        p = Path(self.tmp) / "key.txt"
        key = generate_key_file(p)
        self.assertEqual(len(key), 64)  # 32 bytes as hex
        loaded = load_key_file(p)
        self.assertEqual(loaded, key)

    def test_generate_sets_mode_600(self):
        p = Path(self.tmp) / "key.txt"
        generate_key_file(p)
        mode = p.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_load_key_file_rejects_group_readable(self):
        p = Path(self.tmp) / "badkey.txt"
        p.write_text("abc123\n")
        os.chmod(p, 0o640)
        with self.assertRaises(PermissionError):
            load_key_file(p)

    def test_generate_fails_if_file_exists(self):
        p = Path(self.tmp) / "existing.txt"
        p.write_text("already here\n")
        with self.assertRaises(FileExistsError):
            generate_key_file(p)
