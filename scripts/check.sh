#!/usr/bin/env bash
set -euo pipefail

echo "=== Whis2ndBrain local syntax/unit check (not browser, model, or hardware proof) ==="
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR"

echo "-> Running Python syntax check..."
python3 -m py_compile server/*.py device/src/*.py contracts/*.py tests/unit/*.py

echo "-> Running Unit Test Suite..."
.venv/bin/python -m unittest discover -s tests/unit -v

echo "=== Local syntax/unit checks passed; integration, browser, model, and hardware gates remain separate ==="
