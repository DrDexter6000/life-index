# WSL Server Virtual Environment Runbook

This runbook describes the dedicated WSL/Linux virtual environment for
`life-index server`. The server process must run from this environment instead
of borrowing dependencies through `PYTHONPATH`.

## Scope

The runbook covers only runtime packaging and launch commands for the loopback
server. It does not change query behavior, ACP handshake behavior, evidence
retrieval, data schemas, or public CLI contracts.

## Create Or Refresh The Venv

Run from the Life Index checkout in WSL:

```bash
bash scripts/setup-wsl-server-venv.sh
```

By default the script creates:

```text
$HOME/.local/share/life-index/server-venv/
```

To use a different path:

```bash
LIFE_INDEX_WSL_VENV="$HOME/.local/share/life-index/server-venv" \
  bash scripts/setup-wsl-server-venv.sh
```

The script runs:

```bash
python3 -m venv "$LIFE_INDEX_WSL_VENV"
"$LIFE_INDEX_WSL_VENV/bin/python" -m pip install -e .
```

It then verifies the core runtime imports used by the server path:

```text
pyyaml, numpy, httpx, jieba, rapidfuzz, Pillow
```

## Smoke Test Data Boundary

All smoke tests must run against an isolated sandbox data directory. Set
`LIFE_INDEX_DATA_DIR` before any `health`, `server`, or `query` command:

```bash
export LIFE_INDEX_DATA_DIR="/path/to/sandbox/Life-Index"
test -n "$LIFE_INDEX_DATA_DIR"
test "$LIFE_INDEX_DATA_DIR" != "$HOME/Documents/Life-Index"
```

Do not run smoke tests against the default user data directory.

## Launch The Server

Use the venv Python directly. Do not activate or compose `PYTHONPATH` from
another runtime. Set `LIFE_INDEX_WSL_VENV` in the shell examples below if you
used a custom path.

```bash
cd /path/to/life-index
unset PYTHONPATH

export LIFE_INDEX_DATA_DIR="/path/to/sandbox/Life-Index"
export LIFE_INDEX_ACP_COMMAND='["/path/to/acp-runtime", "acp"]'

"$HOME/.local/share/life-index/server-venv/bin/python" -m tools server start \
  --host 127.0.0.1 \
  --port 8765
```

Recommended for repeatable smoke tests:

```bash
test -n "$LIFE_INDEX_DATA_DIR"
test "$LIFE_INDEX_DATA_DIR" != "$HOME/Documents/Life-Index"
export LIFE_INDEX_SERVER_STATE_FILE="$PWD/.life-index-smoke/server.json"
```

Use a non-default port for smoke tests when another server may already be
running:

```bash
"$HOME/.local/share/life-index/server-venv/bin/python" -m tools server start \
  --host 127.0.0.1 \
  --port 18765 \
  --state-file "$LIFE_INDEX_SERVER_STATE_FILE"
```

## Verify Health

```bash
test -n "$LIFE_INDEX_DATA_DIR"
curl -sS http://127.0.0.1:18765/healthz

"$HOME/.local/share/life-index/server-venv/bin/python" -m tools server status \
  --host 127.0.0.1 \
  --port 18765 \
  --state-file "$LIFE_INDEX_SERVER_STATE_FILE"

"$HOME/.local/share/life-index/server-venv/bin/python" -m tools health
```

Expected healthy status:

```json
{
  "running": true,
  "state": "warm",
  "degraded": false
}
```

## Verify A Grounded Query In A Sandbox

Point `LIFE_INDEX_DATA_DIR` at a sandbox, not a real user data directory. Then
POST a query to the server:

```bash
test -n "$LIFE_INDEX_DATA_DIR"
curl -sS \
  -H 'Content-Type: application/json' \
  -d '{"query":"SANDBOX_MARKER_QUERY"}' \
  http://127.0.0.1:18765/query
```

Expected result:

- `mode` is `GROUNDED`
- `answer.mode` is `GROUNDED`
- `evidence[0].id` matches the sandbox evidence id

## Environment Guard

Before launch, verify no dependency borrowing is active:

```bash
test -n "$LIFE_INDEX_DATA_DIR"
env | grep -E '^(PYTHONPATH|LIFE_INDEX_DATA_DIR|LIFE_INDEX_ACP_COMMAND)='

"$HOME/.local/share/life-index/server-venv/bin/python" - <<'PY'
import json
import sys
from pathlib import Path

venv = Path(sys.prefix).resolve()

print(json.dumps({
    "executable": sys.executable,
    "borrowed_site_packages": [
        p for p in sys.path
        if "site-packages" in p and venv not in Path(p).resolve().parents
    ],
}, indent=2))
PY
```

`PYTHONPATH` should be absent, and `borrowed_site_packages` should be empty.

## Stop The Smoke Server

```bash
"$HOME/.local/share/life-index/server-venv/bin/python" -m tools server stop \
  --host 127.0.0.1 \
  --port 18765 \
  --state-file "$LIFE_INDEX_SERVER_STATE_FILE"
```

Do not stop a default-port server that belongs to another validation run.
