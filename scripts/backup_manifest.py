#!/usr/bin/env python3
"""Build a manifest-verified local backup of a review root (A3 / WB-031).

Copies the backup set (database + audio + settings) into a destination
directory and writes ``manifest.json`` with a SHA-256 for every file plus a
capture/job inventory captured BEFORE the copy, so the restore side can prove
the backup is complete and untampered.

The Google-Drive uploader (``scripts/drive_backup.sh``) keeps its own role;
this helper backs it with the same file set so a rehearsal can run without
Drive credentials. The owner token and key files are never part of the set.

Usage:
    python3 scripts/backup_manifest.py --root /data/whis2ndbrain/review \
        --out /path/to/backup-dir
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

MANIFEST_VERSION = 1
# Never backed up, never restored: credentials live outside the backup set.
EXCLUDED_NAMES = {"token", "token.key", "encryption.key", "drive-credentials.json", "drive-token.json"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> tuple[dict, dict]:
    captures: dict = {}
    jobs: dict = {}
    db = root / "queue.sqlite"
    if db.is_file():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(
                "SELECT capture_id, sha256, byte_count, status FROM captures"
            ):
                captures[row["capture_id"]] = {
                    "sha256": row["sha256"],
                    "byte_count": row["byte_count"],
                    "status": row["status"],
                }
            for row in conn.execute(
                "SELECT state, COUNT(*) AS c FROM transcription_jobs GROUP BY state"
            ):
                jobs[row["state"]] = row["c"]
        finally:
            conn.close()
    return captures, jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifest-verified local backup of a review root")
    parser.add_argument("--root", type=Path, required=True, help="Review root to back up")
    parser.add_argument("--out", type=Path, required=True, help="Backup destination directory")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    captures, jobs = inventory(root)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    files: dict[str, dict] = {}
    copied = 0
    for source in sorted(root.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(root).as_posix()
        if source.name in EXCLUDED_NAMES or any(part in EXCLUDED_NAMES for part in rel.split("/")):
            continue
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files[rel] = {"sha256": sha256_file(target), "bytes": target.stat().st_size}
        copied += 1

    manifest = {
        "schema_version": MANIFEST_VERSION,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "whis2ndbrain backup_manifest v1",
        "files": files,
        "captures": captures,
        "job_counts": jobs,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "backup_dir": str(out),
                "files_copied": copied,
                "captures": len(captures),
                "manifest": str(manifest_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
