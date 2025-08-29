    #!/usr/bin/env bash
    set -euo pipefail
    export PYTHONUNBUFFERED=1

    # Resolve repo root and cd there
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
    cd "${ROOT_DIR}"

    # Auto-activate local virtualenv if present
    if [ -d ".venv" ]; then
      # shellcheck disable=SC1091
      source ".venv/bin/activate"
    fi

    # Safely load .env
    if [ -f ".env" ]; then
      set -a
      . ./.env
      set +a
    fi

    # Dependency sanity check
    python - <<'PY'
import sys
try:
    import cryptography  # noqa
    import uvicorn  # noqa
except Exception as e:
    print("\n[run.sh] Missing dependency in current interpreter:", sys.executable)
    print("[run.sh] Error:", e)
    print("[run.sh] Try:")
    print("  source .venv/bin/activate && pip install -r requirements.txt")
    sys.exit(1)
PY

    PORT=${PORT:-8000}
    exec python -m uvicorn app.main:app --reload --port "$PORT" --host 0.0.0.0
