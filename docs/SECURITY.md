# Security guide — Whis2ndBrain

> This guide covers the security model for the **prototype** phase: one owner, one Pi recorder, one host machine (co-located with the Obsidian vault), Android-only PWA/app.

---

## Threat model (scoped prototype)

| Threat | In scope | Mitigation |
|---|---|---|
| Tailnet neighbour reads owner audio/notes | ✅ | Bearer + session token; all `/api/*` requires auth |
| Stale session replayed after password change | ✅ | Token rotation resets the server token-file; restart required |
| Pi device impersonates owner session | ✅ | Separate device bearer token; cannot escalate to owner cookie |
| Tampered audio file on disk | ✅ | AES-256-GCM at-rest encryption; tag authentication detects tampering |
| Exported Markdown routed into live vault | ✅ | `refuse_vault_destination()` blocks export into vault root |
| Drive backup exposes plaintext audio | ✅ | Encrypt before upload; Drive receives only `.enc` files |
| Plaintext capture in transit (Pi → host) | ✅ | Tailscale WireGuard (recommended) or self-signed TLS |
| Attacker reads `settings.json` (key file path) | ⚠️ | Host filesystem ACLs; key file mode 0o600 enforced by `load_key_file()` |
| Model inference on private speech | ✅ | `local_files_only=True`; no cloud ASR call |
| Cross-site request forgery on review API | ✅ | `SameSite=Strict` cookie; Bearer token on Android |
| Always-listening microphone | ❌ out of scope | Push-to-talk only; no wake word |
| Multi-user access | ❌ out of scope | Single owner; no user table |

---

## Authentication

### Owner session (browser / Flutter Web)

- **Cookie:** `whis_session=<token>; HttpOnly; Secure; SameSite=Strict; Path=/`
- **Token:** single high-entropy string stored in `<root>/token` (owner-readable only, 0o600)
- **Login:** `POST /login` with `token=<value>` form body; success sets the cookie
- **No expiry on the prototype** — token lives until the file is rotated and the server restarted
- **Rotation:** `openssl rand -hex 32 > /data/whis2ndbrain/review/token && systemctl --user restart whis2ndbrain-review`

### Device bearer token (Pi spool uploader)

- Pi sends `Authorization: Bearer <token>` on every upload and heartbeat
- Uses the **same token file** in the prototype; separate device credential is a Phase 2 requirement (WB-022)
- **Never stored in Git, never in `settings.json`**, never logged

### Android app (Flutter)

- Initial auth: user enters host URL + token in Settings screen
- Token stored in `flutter_secure_storage` (Android Keystore-backed)
- All API requests send `Authorization: Bearer <token>`
- Cookie is not used by the native app

---

## TLS / network topology

### Recommended: Tailscale (simplest, no certificate management)

```
Pi ──[Tailscale WireGuard]──→ Host (100.x.x.x:8765)
Android app ──[Tailscale]──→ Host (100.x.x.x:8765)
```

- Install Tailscale on Pi, host, and Android device
- Bind the review server to `0.0.0.0` or the Tailscale IP (not `127.0.0.1`)
- Update `--host` flag in the systemd service to the Tailscale IP
- No certificate configuration needed; WireGuard handles encryption in transit

### Alternative: self-signed CA (for LAN without Tailscale)

```bash
# On host: generate CA and server cert
openssl genrsa -out /data/whis2ndbrain/ca.key 4096
openssl req -new -x509 -days 3650 -key /data/whis2ndbrain/ca.key \
  -out /data/whis2ndbrain/ca.crt -subj "/CN=Whis2ndBrain CA"

openssl genrsa -out /data/whis2ndbrain/server.key 2048
openssl req -new -key /data/whis2ndbrain/server.key \
  -out /data/whis2ndbrain/server.csr -subj "/CN=whis.local"
openssl x509 -req -days 365 -in /data/whis2ndbrain/server.csr \
  -CA /data/whis2ndbrain/ca.crt -CAkey /data/whis2ndbrain/ca.key \
  -CAcreateserial -out /data/whis2ndbrain/server.crt
```

- Install `ca.crt` on Pi and Android as a trusted root CA
- Wrap the Python HTTP server with `ssl.wrap_socket()` (pending WB-011 implementation)
- **Tailscale is strongly preferred** — eliminates cert management and works across networks

---

## At-rest encryption

### Algorithm

- **AES-256-GCM** (authenticated encryption — detects tampering)
- **Key derivation:** PBKDF2-HMAC-SHA256, 100 000 iterations, 16-byte random salt per file
- **Nonce:** 12 random bytes per file — never reused
- **Format:** `WB01` magic + salt + nonce + ciphertext+tag (see `server/crypto.py`)

### Key file

```bash
# Generate (one-time setup)
python -m server genkey --key-file /data/whis2ndbrain/review/audio.key

# File must be mode 0o600
chmod 600 /data/whis2ndbrain/review/audio.key
```

- Key file path set in `settings.json` → `encryption_key_file`
- `load_key_file()` refuses to load if group/other has any permission bits
- **Key file is never committed to Git, never in `settings.json` itself**
- **Backup the key file separately from the encrypted audio** — loss of key = loss of audio

### Enabling encryption (after setup)

```bash
# Via settings API (owner session required)
curl -X PATCH http://localhost:8765/api/v1/settings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"encryption_enabled": true, "encryption_key_file": "/data/whis2ndbrain/review/audio.key"}'
```

> **Note:** Existing `.wav` files are not automatically re-encrypted. Run a migration script (not yet implemented; tracked as a future task) to encrypt existing audio in place.

---

## Google Drive backup

### Scope

- OAuth2 scope: `https://www.googleapis.com/auth/drive.file`
- This grants access **only to files created by the app** — not your full Drive
- Backups go into a `Whis2ndBrain/` folder auto-created by the app
- **Only encrypted files (`.enc`) and the database are uploaded — never plaintext audio**

### OAuth2 setup (one-time)

1. Create a Google Cloud project (free tier)
2. Enable the Drive API
3. Create an OAuth2 Desktop App credential
4. Download `credentials.json` to `/data/whis2ndbrain/review/drive-credentials.json` (mode 0o600)
5. Run `python -m server drive-auth` (not yet implemented) to complete the Device Flow
6. Refresh token stored in `/data/whis2ndbrain/review/drive-token.json` (mode 0o600)

### What gets backed up

| File | Destination |
|---|---|
| `audio/*.enc` | `Whis2ndBrain/backups/YYYY-MM-DD/audio/` |
| `queue.sqlite` | `Whis2ndBrain/backups/YYYY-MM-DD/` |
| `settings.json` | `Whis2ndBrain/backups/YYYY-MM-DD/` |

**Never uploaded:** `token`, `audio.key`, `drive-credentials.json`, `drive-token.json`, plaintext `.wav` files

---

## Content-security and input validation

- All capture IDs validated against `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` before any filesystem use
- WAV files validated (RIFF header, chunk structure, sample rate, encoding) before storage
- Transcripts HTML-escaped before rendering in classic review page
- Vault export path checked against `VAULT_ROOT` to prevent writes into live vault
- Symlink traversal: `resolve()` used in vault check to follow symlinks
- PATCH body limited to `MAX_PATCH_BYTES` (256 KB); upload limited to `MAX_WAV_BYTES` (25 MB)
- `Transfer-Encoding` requests rejected (no chunked body attacks)
- SSE endpoint only streams; no client body accepted on GET

---

## Secrets never in Git

| Secret | Location | Mode |
|---|---|---|
| Owner token | `/data/whis2ndbrain/review/token` | 0o600 |
| Encryption key | `/data/whis2ndbrain/review/audio.key` | 0o600 |
| Drive credentials | `/data/whis2ndbrain/review/drive-credentials.json` | 0o600 |
| Drive refresh token | `/data/whis2ndbrain/review/drive-token.json` | 0o600 |

The `.gitignore` already excludes `*.key`, `*.token`, `data/`, `*.db`, `*.wav`.

---

## Revocation

| Scenario | Action |
|---|---|
| Owner token compromised | Replace token file, restart service |
| Pi lost | Rotate token (Pi can no longer authenticate), audit recent captures |
| Drive access revoked | Revoke OAuth token in Google Account settings, delete `drive-token.json` |
| Encryption key compromised | Rotate key, re-encrypt all audio (migration script required) |

---

## Open security tasks (pre-pilot)

- [ ] Wrap HTTP server with TLS (Tailscale preferred; self-signed CA as fallback)
- [ ] Separate device bearer token from owner token (WB-022)
- [ ] Implement `drive-auth` command and Drive backup runner
- [ ] Implement encryption migration script for existing `.wav` → `.enc`
- [ ] Add rate limiting on `/login` (brute-force protection)
- [ ] Add `Content-Security-Policy` header to review/PWA responses
- [ ] Audit log (redacted): capture received, exported, token rotated — no transcript content in logs
- [ ] Verify cookie `Secure` flag when running behind Tailscale (HTTPS required for Secure cookies)
- [ ] CSRF token on state-mutating classic HTML forms (`/upload`, `/n/{id}`)

> **Owner sign-off required before** enabling encryption on real audio, connecting Drive, or running a pilot with real speech data.
