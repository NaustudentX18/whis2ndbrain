"""At-rest encryption for Whis2ndBrain audio files.

Strategy: AES-256-GCM using a 32-byte key derived from an owner-supplied
passphrase via PBKDF2-HMAC-SHA256 (100 000 iterations, 16-byte random salt).

File format (.enc):
    [4 bytes]  magic b"WB01"
    [16 bytes] KDF salt
    [12 bytes] GCM nonce
    [N bytes]  GCM ciphertext + 16-byte authentication tag

The 16-byte tag is appended by the library inside the ciphertext blob.
No passphrase or key is ever stored on disk; the caller must supply it.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"WB01"
MAGIC_LEN = 4
SALT_LEN = 16
NONCE_LEN = 12
HEADER_LEN = MAGIC_LEN + SALT_LEN + NONCE_LEN  # 32 bytes
TAG_LEN = 16  # appended by AESGCM inside ciphertext

_KDF_ITERATIONS = 100_000


class EncryptionError(Exception):
    """Raised when a ciphertext cannot be authenticated or is malformed."""


def derive_key(passphrase: str | bytes, salt: bytes) -> bytes:
    """Derive a 32-byte AES-256 key from *passphrase* using PBKDF2-HMAC-SHA256."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, _KDF_ITERATIONS, dklen=32)


def encrypt_bytes(plaintext: bytes, passphrase: str | bytes) -> bytes:
    """Encrypt *plaintext* and return the complete .enc blob."""
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return MAGIC + salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, passphrase: str | bytes) -> bytes:
    """Decrypt a blob produced by :func:`encrypt_bytes`.

    Raises :class:`EncryptionError` if the magic is wrong, the blob is
    truncated, or GCM authentication fails (wrong key or tampered data).
    """
    if len(blob) < HEADER_LEN + TAG_LEN:
        raise EncryptionError("blob too short to be a valid WB01 file")
    if blob[:MAGIC_LEN] != MAGIC:
        raise EncryptionError("not a WB01 encrypted file")
    salt = blob[MAGIC_LEN : MAGIC_LEN + SALT_LEN]
    nonce = blob[MAGIC_LEN + SALT_LEN : HEADER_LEN]
    ciphertext = blob[HEADER_LEN:]
    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise EncryptionError("decryption failed — wrong key or tampered data") from exc


# ── File helpers ──────────────────────────────────────────────────────────────


def encrypt_file(src: Path, dest: Path, passphrase: str | bytes) -> None:
    """Encrypt *src* and write the result durably to *dest*.

    *dest* is written atomically via a .part file so a crash mid-write
    leaves *src* intact and *dest* either complete or absent.
    """
    plaintext = src.read_bytes()
    blob = encrypt_bytes(plaintext, passphrase)
    _write_durable(dest, blob)


def decrypt_file(src: Path, passphrase: str | bytes) -> bytes:
    """Read and decrypt *src*, returning the plaintext bytes."""
    blob = src.read_bytes()
    return decrypt_bytes(blob, passphrase)


def enc_path(wav_path: Path) -> Path:
    """Return the .enc counterpart of a .wav path."""
    return wav_path.with_suffix(".enc")


# ── Passphrase key file ───────────────────────────────────────────────────────


def load_key_file(path: Path) -> str:
    """Read a single-line key file; strip whitespace.

    The key file must be owner-readable only (mode 0o600). If the file has
    broader permissions this function raises :class:`PermissionError` so the
    operator notices the misconfiguration early.
    """
    stat = path.stat()
    # Check that group and others have no read/write/execute bits
    if stat.st_mode & 0o077:
        raise PermissionError(
            f"key file {path} has unsafe permissions "
            f"({oct(stat.st_mode & 0o777)}); expected 0o600"
        )
    return path.read_text(encoding="utf-8").strip()


def generate_key_file(path: Path) -> str:
    """Generate a random 32-byte hex passphrase and write it to *path* (0o600)."""
    key = os.urandom(32).hex()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (key + "\n").encode())
    finally:
        os.close(fd)
    return key


# ── Internal ──────────────────────────────────────────────────────────────────


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
