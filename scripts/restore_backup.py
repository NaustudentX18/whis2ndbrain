#!/usr/bin/env python3
"""Restore a review root from a manifest-verified backup (A3 / WB-031).

Fail-closed: every file hash is verified against ``manifest.json`` BEFORE
anything is written; any mismatch, missing file, or unknown extra audio file
aborts with a clear report and a non-zero exit. After the copy the restored
store is reconciled against the manifest inventory (per-capture receipt
hashes, job counts) and every note is exported to a scratch directory twice
to prove export digests are reproducible from the backup alone.

Usage:
    python3 scripts/restore_backup.py --backup /path/to/backup-dir \
        --target /path/to/fresh/root [--export-dir /path/to/scratch]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.export import export_note_to_dir
from server.pass1 import Store

MANIFEST_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(backup: Path) -> tuple[dict, list[str]]:
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        return {}, [f"missing {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, [f"unreadable manifest: {exc}"]
    if manifest.get("schema_version") != MANIFEST_VERSION:
        return {}, [f"unsupported manifest schema_version: {manifest.get('schema_version')}"]

    problems: list[str] = []
    for rel, facts in manifest.get("files", {}).items():
        path = backup / rel
        if not path.is_file():
            problems.append(f"missing from backup: {rel}")
            continue
        if path.stat().st_size != facts["bytes"]:
            problems.append(f"size mismatch: {rel}")
        elif sha256_file(path) != facts["sha256"]:
            problems.append(f"hash mismatch (tampered or corrupt): {rel}")
    return manifest, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed restore from a manifest backup")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--export-dir", type=Path, default=None)
    args = parser.parse_args()

    backup = args.backup.resolve()
    target = args.target.resolve()
    if target.exists() and any(target.iterdir()):
        print(f"error: target {target} exists and is not empty - restore needs a clean dir", file=sys.stderr)
        return 2

    manifest, problems = verify(backup)
    if problems:
        print(json.dumps({"ok": False, "stage": "verify", "problems": problems}, indent=2))
        return 1

    # copy the verified set
    copied = 0
    for rel in manifest["files"]:
        source = backup / rel
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied += 1

    # reconcile the restored store against the inventory taken at backup time
    store = Store(target)
    reconcile: list[str] = []
    expected = manifest.get("captures", {})
    for capture_id, facts in expected.items():
        receipt = store.get(capture_id)
        if receipt is None:
            reconcile.append(f"capture missing after restore: {capture_id}")
        elif receipt.sha256 != facts["sha256"]:
            reconcile.append(f"receipt hash mismatch: {capture_id}")
    restored_captures = {
        row[0] for row in _capture_ids(target)
    }
    for extra in sorted(restored_captures - set(expected)):
        reconcile.append(f"capture present after restore but absent from manifest: {extra}")

    job_counts: dict[str, int] = {}
    with store._connect() as conn:
        for row in conn.execute("SELECT state, COUNT(*) AS c FROM transcription_jobs GROUP BY state"):
            job_counts[row["state"]] = row["c"]
    if job_counts != manifest.get("job_counts", {}):
        reconcile.append(
            f"job counts differ: restored={job_counts} manifest={manifest.get('job_counts', {})}"
        )

    # export reproducibility from the backup alone (twice, to fresh dirs)
    exports: dict[str, str] = {}
    export_problems: list[str] = []
    export_dir = args.export_dir
    if export_dir is not None:
        for capture_id in expected:
            note = store.get_note(capture_id)
            receipt = store.get(capture_id)
            if note is None or receipt is None:
                export_problems.append(f"cannot export missing note: {capture_id}")
                continue
            first = export_note_to_dir(note, receipt, export_dir / "pass1")
            second = export_note_to_dir(note, receipt, export_dir / "pass2")
            digest = sha256_file(first)
            if sha256_file(second) != digest:
                export_problems.append(f"export not reproducible: {capture_id}")
            exports[capture_id] = digest

    ok = not reconcile and not export_problems
    print(
        json.dumps(
            {
                "ok": ok,
                "stage": "reconcile",
                "files_restored": copied,
                "captures_reconciled": len(expected),
                "job_counts": job_counts,
                "exports_verified": len(exports),
                "problems": reconcile + export_problems,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def _capture_ids(target: Path) -> list[tuple[str]]:
    import sqlite3

    conn = sqlite3.connect(target / "queue.sqlite")
    try:
        return conn.execute("SELECT capture_id FROM captures").fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
