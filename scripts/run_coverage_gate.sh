#!/usr/bin/env bash
# run_coverage_gate.sh — canonical blocker/contract coverage gate for CI and local use
#
# Keeps the existing blocker-or-contract coverage inventory in one place. The
# coverage threshold remains owned by pyproject.toml [tool.coverage.report].

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: bash scripts/run_coverage_gate.sh

Runs the blocker-or-contract coverage gate with an isolated pytest basetemp
and synthetic LIFE_INDEX_DATA_DIR.

Optional environment:
  COVERAGE_GATE_BASETEMP  An isolated child of .pytest_tmp locally or of
                          RUNNER_TEMP in CI. The runner derives its data
                          directory from this path and never falls back to
                          an inherited LIFE_INDEX_DATA_DIR.
EOF
}

gate_fail() {
    echo "COVERAGE GATE FAIL: $1" >&2
    exit 1
}

if [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

if [ "$#" -ne 0 ]; then
    usage >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

command -v python >/dev/null 2>&1 || gate_fail "missing required command: python"

if ! python - <<'PY'
import importlib.util
import sys

missing = [
    name
    for name in ("pytest", "pytest_cov", "pytest_timeout")
    if importlib.util.find_spec(name) is None
]
if missing:
    print("Missing Python modules: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
then
    gate_fail "missing required Python dependencies; install the project dev/test environment"
fi

if [ "${COVERAGE_GATE_BASETEMP+x}" = "x" ] && [ -z "$COVERAGE_GATE_BASETEMP" ]; then
    gate_fail "COVERAGE_GATE_BASETEMP cannot be empty"
fi

TIMESTAMP="$(date +%s)"
DEFAULT_BASETEMP="$REPO_ROOT/.pytest_tmp/coverage_${TIMESTAMP}_$$"
REQUESTED_BASETEMP="${COVERAGE_GATE_BASETEMP:-$DEFAULT_BASETEMP}"

if [[ "$REQUESTED_BASETEMP" = /* ]]; then
    PYTEST_BASETEMP="$REQUESTED_BASETEMP"
else
    PYTEST_BASETEMP="$REPO_ROOT/$REQUESTED_BASETEMP"
fi

if [[ "$PYTEST_BASETEMP" == *".."* ]]; then
    gate_fail "COVERAGE_GATE_BASETEMP cannot contain '..'"
fi

REPO_TEMP_ROOT="$REPO_ROOT/.pytest_tmp"
mkdir -p "$REPO_TEMP_ROOT" || gate_fail "cannot create repository test temp root"
REPO_TEMP_ROOT="$(cd "$REPO_TEMP_ROOT" && pwd -P)"
SAFE_TEMP_ROOTS=("$REPO_TEMP_ROOT")

if [ -n "${RUNNER_TEMP:-}" ]; then
    [ -d "$RUNNER_TEMP" ] || gate_fail "RUNNER_TEMP does not exist or is not a directory"
    SAFE_TEMP_ROOTS+=("$(cd "$RUNNER_TEMP" && pwd -P)")
fi

is_isolated_child() {
    local candidate="$1"
    local root
    for root in "${SAFE_TEMP_ROOTS[@]}"; do
        [[ "$candidate" == "$root"/* ]] && return 0
    done
    return 1
}

if ! is_isolated_child "$PYTEST_BASETEMP"; then
    gate_fail "COVERAGE_GATE_BASETEMP must be an isolated child of .pytest_tmp or RUNNER_TEMP"
fi

if [ -e "$PYTEST_BASETEMP" ] && [ ! -d "$PYTEST_BASETEMP" ]; then
    gate_fail "COVERAGE_GATE_BASETEMP exists but is not a directory"
fi
mkdir -p "$PYTEST_BASETEMP" || gate_fail "cannot create COVERAGE_GATE_BASETEMP"
PYTEST_BASETEMP="$(cd "$PYTEST_BASETEMP" && pwd -P)"

if ! is_isolated_child "$PYTEST_BASETEMP"; then
    gate_fail "COVERAGE_GATE_BASETEMP resolves outside its allowed isolated root"
fi

if [ -n "${LIFE_INDEX_DATA_DIR:-}" ] && [ "$LIFE_INDEX_DATA_DIR" != "$PYTEST_BASETEMP/data" ]; then
    echo "Ignoring inherited LIFE_INDEX_DATA_DIR; using synthetic coverage data root."
fi
export LIFE_INDEX_DATA_DIR="$PYTEST_BASETEMP/data"

if [ -e "$LIFE_INDEX_DATA_DIR" ] && { [ ! -d "$LIFE_INDEX_DATA_DIR" ] || [ -L "$LIFE_INDEX_DATA_DIR" ]; }; then
    gate_fail "synthetic LIFE_INDEX_DATA_DIR must be a non-symlink directory"
fi
mkdir -p "$LIFE_INDEX_DATA_DIR" || gate_fail "cannot create synthetic LIFE_INDEX_DATA_DIR"

export LIFE_INDEX_INDEX_FTS_ONLY="${LIFE_INDEX_INDEX_FTS_ONLY:-1}"

echo "Coverage threshold: pyproject.toml [tool.coverage.report].fail_under"
echo "Using pytest basetemp: $PYTEST_BASETEMP"
echo "Using synthetic LIFE_INDEX_DATA_DIR: $LIFE_INDEX_DATA_DIR"

python -m pytest -m "blocker or contract" -v --timeout=300 \
    --cov=tools --cov-report=term-missing --basetemp="$PYTEST_BASETEMP"
