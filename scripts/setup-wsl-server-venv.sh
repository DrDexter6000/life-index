#!/usr/bin/env bash
set -euo pipefail

# Build a dedicated WSL/Linux virtual environment for the loopback server.
# This script installs Life Index into its own venv and never relies on
# PYTHONPATH or another runtime's site-packages.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${LIFE_INDEX_WSL_VENV:-"${HOME}/.local/share/life-index/server-venv"}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "error: ${PYTHON_BIN} not found" >&2
  exit 1
fi

if [[ -n "${PYTHONPATH:-}" ]]; then
  echo "warning: ignoring caller PYTHONPATH while building the server venv" >&2
fi

"${PYTHON_BIN}" -m venv "${VENV_PATH}"

env -u PYTHONPATH "${VENV_PATH}/bin/python" -m pip install --upgrade pip
env -u PYTHONPATH "${VENV_PATH}/bin/python" -m pip install -e "${REPO_ROOT}"

env -u PYTHONPATH "${VENV_PATH}/bin/python" - <<'PY'
import importlib.util
import sys

modules = ["yaml", "numpy", "httpx", "jieba", "rapidfuzz", "PIL"]
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(f"missing runtime dependencies: {', '.join(missing)}")

print(f"python={sys.executable}")
print("runtime_dependencies=ok")
PY

cat <<EOF

Life Index WSL server venv is ready.

Venv:
  ${VENV_PATH}

Start the server with:
  unset PYTHONPATH
  export LIFE_INDEX_DATA_DIR=/path/to/sandbox/Life-Index
  export LIFE_INDEX_ACP_COMMAND='["/path/to/acp-runtime", "acp"]'
  ${VENV_PATH}/bin/python -m tools server start --host 127.0.0.1 --port 8765

For smoke tests, set LIFE_INDEX_DATA_DIR to an isolated sandbox before running
any health, server, or query command.

See docs/wsl-server-venv.md for the full runbook.
EOF
