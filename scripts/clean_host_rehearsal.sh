#!/usr/bin/env bash
# Clean-host install rehearsal (Lane D4 / WB-055 prep).
#
# Proves the documented install path works from the repository alone on a
# disposable directory: export the committed tree, build a fresh virtual
# environment from requirements.txt, run the unit suite, start the review
# service exactly as docs/DEPLOYMENT.md describes, and verify the live
# surface (health, upload with receipt, capture readback, metrics) with a
# synthetic capture. Nothing touches prod, the dev checkout state, or any
# real data; everything lands under a temporary directory that is removed
# on exit.
#
# Usage:
#   bash scripts/clean_host_rehearsal.sh [--keep] [python]
#
#   --keep    keep the disposable directory for inspection (path printed)
#   python    interpreter to use for the fresh venv (default: python3)
#
# Exit codes: 0 = rehearsal passed, 1 = a documented step failed.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEEP=0
PYTHON=python3
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
    *) PYTHON="$arg" ;;
  esac
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/whis-rehearsal-XXXXXX")"
cleanup() {
  if [ "$KEEP" = "1" ]; then
    echo "rehearsal dir kept: $WORK"
  else
    rm -rf "$WORK"
  fi
}
trap cleanup EXIT

step() { printf '\n== %s ==\n' "$1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

step "export committed tree (git archive HEAD — no uncommitted files)"
mkdir -p "$WORK/src"
git -C "$HERE" archive HEAD | tar -x -C "$WORK/src"
[ -f "$WORK/src/requirements.txt" ] || fail "exported tree has no requirements.txt"

step "fresh virtualenv from requirements.txt ($PYTHON)"
"$PYTHON" -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --quiet --upgrade pip
"$WORK/venv/bin/python" -m pip install --quiet -r "$WORK/src/requirements.txt"

step "unit suite from the exported tree"
( cd "$WORK/src" && "$WORK/venv/bin/python" -m unittest discover -s tests/unit -q ) \
  || fail "unit suite failed in the clean tree"

step "start review service exactly per docs/DEPLOYMENT.md"
ROOT="$WORK/review"
mkdir -p "$ROOT"
TOKEN_FILE="$WORK/token"
"$PYTHON" - "$TOKEN_FILE" <<'PYEOF'
import secrets, sys
from pathlib import Path
Path(sys.argv[1]).write_text(secrets.token_urlsafe(24))
PYEOF
PORT=18765
( cd "$WORK/src" && PYTHONPATH="$WORK/src" "$WORK/venv/bin/python" -m server serve \
    --root "$ROOT" --token-file "$TOKEN_FILE" --host 127.0.0.1 --port "$PORT" \
    >"$WORK/server.log" 2>&1 ) &
SERVER_PID=$!
for _ in $(seq 1 50); do
  if curl -sf "http://127.0.0.1:$PORT/api/v1/health/live" >/dev/null; then break; fi
  sleep 0.2
done
curl -sf "http://127.0.0.1:$PORT/api/v1/health/live" >/dev/null || { cat "$WORK/server.log"; fail "service never became live"; }
curl -sf "http://127.0.0.1:$PORT/api/v1/health/ready" >/dev/null || fail "service never became ready"

step "synthetic capture through the documented raw ingest route"
CID="rehearsal-$(date +%s)"
WAV="$WORK/synthetic.wav"
"$WORK/venv/bin/python" - "$WAV" <<'PYEOF'
import sys, wave
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x00" * 160)
PYEOF
TOKEN="$(cat "$TOKEN_FILE")"
CODE="$(curl -s -o "$WORK/upload.json" -w '%{http_code}' -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: audio/wav" \
  -H "X-Capture-ID: $CID" --data-binary "@$WAV" \
  "http://127.0.0.1:$PORT/api/v1/captures")"
[ "$CODE" = "201" ] || fail "upload returned $CODE (want 201)"
grep -q '"receipt_id"' "$WORK/upload.json" || fail "no receipt in upload response"

step "capture readback + owner metrics"
CODE="$(curl -s -o "$WORK/get.json" -w '%{http_code}' \
  -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/v1/captures/$CID")"
[ "$CODE" = "200" ] || fail "capture readback returned $CODE (want 200)"
CODE="$(curl -s -o "$WORK/metrics.json" -w '%{http_code}' \
  -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:$PORT/api/v1/metrics")"
[ "$CODE" = "200" ] || fail "metrics returned $CODE (want 200)"

step "anonymous access is refused"
CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/v1/captures/$CID")"
[ "$CODE" = "401" ] || fail "anonymous readback returned $CODE (want 401)"

kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true

printf '\nPASS: clean-host rehearsal complete (upload receipt, readback, metrics, auth fence)\n'
