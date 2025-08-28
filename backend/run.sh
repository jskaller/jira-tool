#!/usr/bin/env bash
set -euo pipefail

# Choose a Python that is compatible with pydantic-core (avoid 3.13 for now).
choose_python() {
  for c in python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      ver=$($c -c 'import sys;print(".".join(map(str, sys.version_info[:3])))')
      case "$ver" in
        3.13.*) continue ;; # skip 3.13
      esac
      echo "$c"
      return 0
    fi
  done
  return 1
}

if ! PY_BIN=$(choose_python); then
  echo "No suitable Python found."
  echo "Please install Python 3.12 (recommended) or 3.11."
  echo "On macOS (Homebrew):  brew install python@3.12"
  exit 1
fi

echo "[using] $PY_BIN ($($PY_BIN -V))"
$PY_BIN -m venv .venv
source .venv/bin/activate
python -V

pip install -U pip
pip install -r requirements.txt

cp -n .env.example .env || true

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
