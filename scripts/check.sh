#!/usr/bin/env bash
set -euo pipefail

echo "=== Whis2ndBrain local check: syntax, unit, integration (not browser/model/hardware proof) ==="
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export PYTHONPATH="$PROJECT_DIR"

echo "-> Running Python syntax check..."
python3 -m py_compile server/*.py device/src/*.py contracts/*.py tests/unit/*.py tests/integration/*.py

echo "-> Running Unit Test Suite..."
.venv/bin/python -m unittest discover -s tests/unit -v

echo "-> Running Integration Test Suite..."
.venv/bin/python -m unittest discover -s tests/integration -v

echo "=== Local syntax/unit/integration checks passed; ruff, browser, model, and hardware gates remain separate ==="
