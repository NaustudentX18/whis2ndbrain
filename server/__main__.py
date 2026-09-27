"""Local pass-1 commands. Binds nothing and writes no vault notes."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from server.pass1 import (
    Rejected,
    Store,
    export_note,
    load_runner,
    purge_expired,
    transcribe,
)
from server.review import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Whis2ndBrain pass-1 host")
    parser.add_argument("cmd", choices=["ingest", "transcribe", "export", "serve", "purge"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--id")
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--dest", type=Path)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    store = Store(args.root)
    if args.cmd == "serve":
        if args.token_file is None:
            raise SystemExit("--token-file is required")
        serve(store, args.token_file.read_text().strip(), args.host, args.port)
        return
    if args.cmd == "purge":
        purge_expired(store, datetime.now(timezone.utc))
        return
    if args.id is None:
        raise SystemExit("--id is required")
    if args.cmd == "ingest":
        if args.wav is None:
            raise SystemExit("--wav is required")
        receipt = store.accept(args.id, args.wav.read_bytes())
        print(receipt.receipt_id)
        print(receipt.sha256)
        return
    if args.cmd == "transcribe":
        note = transcribe(store, args.id, load_runner())
        print(note.status)
        print(note.transcript or "")
        return
    if args.dest is None:
        raise SystemExit("--dest is required")
    try:
        print(export_note(store, args.id, args.dest))
    except Rejected:
        sys.stderr.write("export refused\n")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
