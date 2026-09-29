#!/usr/bin/env python3
"""Pair a device with a Whis2ndBrain host (BP1 item 2).

Run this on the device (or any machine that can reach the host). It redeems
a single-use pairing code the owner generated in the review UI and writes
the resulting device credentials to a JSON file with owner-only permissions.

Usage:
    python3 scripts/pair_device.py --server https://host:8765 \
        --code ABCDEF1234 --name "bench pi" --out device-creds.json

The token is shown/written exactly once; the host stores only a digest.
"""

from __future__ import annotations

import argparse
import json
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Pair a device with a Whis2ndBrain host")
    parser.add_argument("--server", required=True, help="Host base URL (HTTPS)")
    parser.add_argument("--code", required=True, help="Pairing code from the review UI")
    parser.add_argument("--name", default="unnamed device", help="Human-readable device name")
    parser.add_argument("--out", type=Path, default=Path("device-creds.json"))
    parser.add_argument(
        "--allow-insecure-loopback",
        action="store_true",
        help="Permit plaintext http for loopback test hosts only",
    )
    args = parser.parse_args()

    parsed = urllib.parse.urlsplit(args.server)
    loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not (
        args.allow_insecure_loopback and parsed.scheme == "http" and loopback
    ):
        print("error: server URL must use HTTPS (loopback http needs --allow-insecure-loopback)")
        return 2

    body = json.dumps({"code": args.code.strip(), "device_name": args.name}).encode()
    req = urllib.request.Request(
        f"{args.server.rstrip('/')}/api/v1/pair",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 201:
                print(f"error: unexpected status {resp.status}")
                return 1
            cred = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        print(f"error: HTTP {exc.code}: {detail}")
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {type(exc).__name__}: {exc}")
        return 1

    args.out.write_text(
        json.dumps(
            {
                "server": args.server.rstrip("/"),
                "device_id": cred["device_id"],
                "token": cred["token"],
            },
            indent=2,
        )
        + "\n"
    )
    args.out.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(f"paired: device_id={cred['device_id']}")
    print(f"credentials written to {args.out} (mode 600) - token shown/written once")
    return 0


if __name__ == "__main__":
    sys.exit(main())
