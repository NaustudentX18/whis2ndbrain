#!/usr/bin/env bash
# scripts/drive_backup.sh — Back up encrypted audio and database to Google Drive
#
# Usage:
#   bash scripts/drive_backup.sh --root /data/whis2ndbrain/review [--dry-run]
#
# Requirements:
#   - Python 3.x with google-auth-oauthlib and google-api-python-client
#   - drive-credentials.json and drive-token.json in <root>/
#   - Encryption must be enabled; this script will NOT upload plaintext .wav files
#
# Safety:
#   - Only uploads .enc, queue.sqlite, and settings.json — never token, key files, or .wav
#   - Uploads to Whis2ndBrain/backups/YYYY-MM-DD/ folder only
#   - Verifies upload checksum (MD5) against local file before marking success
#   - Updates drive_last_backup_at in settings.json on success
#
# This script requires owner sign-off before being run with real credentials.
# See docs/SECURITY.md for Drive OAuth2 setup instructions.

set -euo pipefail

ROOT=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  echo "Error: --root is required" >&2
  exit 1
fi

ROOT="$(realpath "$ROOT")"
AUDIO_DIR="$ROOT/audio"
DB_FILE="$ROOT/queue.sqlite"
SETTINGS_FILE="$ROOT/settings.json"
CREDS_FILE="$ROOT/drive-credentials.json"
TOKEN_FILE_OAUTH="$ROOT/drive-token.json"
DATE="$(date -u +%Y-%m-%d)"
BACKUP_FOLDER="Whis2ndBrain/backups/$DATE"

echo "=== Whis2ndBrain Google Drive backup ==="
echo "Root:   $ROOT"
echo "Date:   $DATE"
echo "Target: $BACKUP_FOLDER"
[[ "$DRY_RUN" == "1" ]] && echo "[DRY RUN — no files will be uploaded]"

# Safety check: refuse if credentials are not present
if [[ ! -f "$CREDS_FILE" ]]; then
  echo "Error: $CREDS_FILE not found. See docs/SECURITY.md for Drive OAuth2 setup." >&2
  exit 1
fi
if [[ ! -f "$TOKEN_FILE_OAUTH" ]]; then
  echo "Error: $TOKEN_FILE_OAUTH not found. Run: python -m server drive-auth --root $ROOT" >&2
  exit 1
fi

# Safety check: refuse to upload any .wav file (plaintext audio)
WAV_COUNT=$(find "$AUDIO_DIR" -name "*.wav" 2>/dev/null | wc -l)
if [[ "$WAV_COUNT" -gt 0 ]]; then
  echo "WARNING: Found $WAV_COUNT plaintext .wav file(s) in $AUDIO_DIR" >&2
  echo "Encryption must be enabled before Drive backup. Run:" >&2
  echo "  curl -X PATCH http://localhost:8765/api/v1/settings -H 'Authorization: Bearer <token>' \\" >&2
  echo "    -d '{\"encryption_enabled\": true, \"encryption_key_file\": \"$ROOT/audio.key\"}'" >&2
  exit 2
fi

# Count .enc files to upload
ENC_COUNT=$(find "$AUDIO_DIR" -name "*.enc" 2>/dev/null | wc -l)
echo "Encrypted audio files: $ENC_COUNT"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "[DRY RUN] Would upload:"
  find "$AUDIO_DIR" -name "*.enc" 2>/dev/null | head -10
  [[ -f "$DB_FILE" ]] && echo "  $DB_FILE"
  [[ -f "$SETTINGS_FILE" ]] && echo "  $SETTINGS_FILE"
  echo "[DRY RUN] Done — no files uploaded."
  exit 0
fi

# Delegate to Python for the actual Drive API calls
PYTHONPATH="$(dirname "$0")/.." python3 - <<'PYEOF'
import json
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone

root = Path(os.environ.get("WHIS_ROOT", ""))
audio_dir = root / "audio"
backup_date = os.environ.get("WHIS_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
backup_folder_name = f"Whis2ndBrain/backups/{backup_date}"
settings_path = root / "settings.json"

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("Missing Google client libraries. Install with:", file=sys.stderr)
    print("  uv pip install google-auth-oauthlib google-api-python-client", file=sys.stderr)
    sys.exit(1)

# Load and refresh credentials
creds_path = root / "drive-credentials.json"
token_path = root / "drive-token.json"
creds_data = json.loads(token_path.read_text())
creds = Credentials.from_authorized_user_info(creds_data)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
    token_path.write_text(creds.to_json())

service = build("drive", "v3", credentials=creds, cache_discovery=False)

def get_or_create_folder(name: str, parent_id: str | None = None) -> str:
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    f = service.files().create(body=meta, fields="id").execute()
    return f["id"]

# Create folder hierarchy: Whis2ndBrain/backups/YYYY-MM-DD/audio
root_folder_id = get_or_create_folder("Whis2ndBrain")
backups_folder_id = get_or_create_folder("backups", root_folder_id)
date_folder_id = get_or_create_folder(backup_date, backups_folder_id)
audio_folder_id = get_or_create_folder("audio", date_folder_id)

uploaded = 0
errors = 0

def upload_file(local_path: Path, folder_id: str) -> bool:
    media = MediaFileUpload(str(local_path), resumable=True)
    meta = {"name": local_path.name, "parents": [folder_id]}
    try:
        f = service.files().create(body=meta, media_body=media, fields="id,md5Checksum").execute()
        # Verify checksum
        local_md5 = hashlib.md5(local_path.read_bytes()).hexdigest()
        if f.get("md5Checksum") and f["md5Checksum"] != local_md5:
            print(f"  CHECKSUM MISMATCH: {local_path.name}", file=sys.stderr)
            return False
        print(f"  ✓ {local_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ {local_path.name}: {type(e).__name__}: {e}", file=sys.stderr)
        return False

# Upload .enc files
for enc_file in sorted(audio_dir.glob("*.enc")):
    if upload_file(enc_file, audio_folder_id):
        uploaded += 1
    else:
        errors += 1

# Upload DB and settings
for f in [root / "queue.sqlite", root / "settings.json"]:
    if f.exists():
        if upload_file(f, date_folder_id):
            uploaded += 1
        else:
            errors += 1

print(f"\nUploaded: {uploaded}  Errors: {errors}")

if errors == 0:
    # Update drive_last_backup_at in settings.json
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}
    settings["drive_last_backup_at"] = now_iso
    settings_path.write_text(json.dumps(settings, indent=2))
    print(f"drive_last_backup_at set to {now_iso}")
    sys.exit(0)
else:
    print(f"Backup completed with {errors} error(s)", file=sys.stderr)
    sys.exit(1)
PYEOF

echo "=== Drive backup complete ==="
