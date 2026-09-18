#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
"$PY" -m pip install --upgrade pip >/dev/null
"$PY" -m pip install -r requirements.txt >/dev/null

"$PY" -m PyInstaller \
  --clean \
  --onefile \
  --windowed \
  --name InsomniaLauncher \
  --icon ui/assets/icon.png \
  --add-data "ui/assets/icon.png:ui/assets" \
  main.py

echo ""
echo "Built: $(pwd)/dist/InsomniaLauncher"
echo "Run it with: ./dist/InsomniaLauncher"