#!/usr/bin/env bash
# ==============================================================================
# Initializes and synchronizes Baserow schema for ERA BaseRow Manager
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

PYTHON_BIN="python3"
if [ -f "$BACKEND_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
elif [ -f "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="$BACKEND_DIR/.venv/Scripts/python.exe"
fi

echo "=== ERA BaseRow Manager - Baserow Schema Initializer ==="
cd "$BACKEND_DIR"
"$PYTHON_BIN" -m app.baserow_init
