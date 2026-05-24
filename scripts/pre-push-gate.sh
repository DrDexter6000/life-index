#!/usr/bin/env bash
# Life Index CLI — pre-push gate
#
# Implements L4 from docs/PROJECT_WORKFLOW.md v1.2 §M3 (d) push 前置门
# within-version revision. Runs all CI hard checks listed in
# .agent-governance/CI_HARD_CHECKS.md.
#
# Exit code:
#   0  All checks pass; safe to push.
#   1  At least one check failed; DO NOT push.
#
# Run from any directory; script chdir's to repo root.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BLOCKER_TIMEOUT_SECONDS=900
CONTRACT_TIMEOUT_SECONDS=1200
EVAL_TIMEOUT_SECONDS=600
PYTEST_TIMEOUT_SECONDS=120
NON_TEST_MARGIN_SECONDS=900
RECOMMENDED_WATCHDOG_SECONDS=$((BLOCKER_TIMEOUT_SECONDS + CONTRACT_TIMEOUT_SECONDS + EVAL_TIMEOUT_SECONDS + NON_TEST_MARGIN_SECONDS))

TIMESTAMP=$(date +%s)
LOG_DIR=".agent-reports/pre-push-gate"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run_${TIMESTAMP}.log"
echo "Log: $LOG"
exec > >(tee "$LOG") 2>&1

START_TIME=$(date +%s)
echo "================================================"
echo "Life Index pre-push gate"
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Repo:  $REPO_ROOT"
echo "SSOT:  .agent-governance/CI_HARD_CHECKS.md"
echo "Expected shell: Git Bash (MSYSTEM set, non-WSL)"
echo "Recommended outer watchdog: ${RECOMMENDED_WATCHDOG_SECONDS}s"
echo "================================================"

declare -a FAILED_CHECKS=()
declare -a PASSED_CHECKS=()

gate_fail() {
    local REASON="$1"
    echo ""
    echo "GATE FAIL: $REASON"
    echo "See log: $LOG"
    exit 1
}

check_environment() {
    if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null || [ -n "${WSL_INTEROP:-}" ]; then
        gate_fail "WSL bash detected. Use D:\\Program Files\\Git\\bin\\bash.exe scripts/pre-push-gate.sh from the Windows repo checkout."
    fi

    if [ -z "${MSYSTEM:-}" ] && [ "${ALLOW_NON_GIT_BASH:-0}" != "1" ]; then
        gate_fail "non-Git-Bash shell detected (MSYSTEM is empty). Use D:\\Program Files\\Git\\bin\\bash.exe or set ALLOW_NON_GIT_BASH=1 only in a verified non-WSL environment."
    fi

    if [ -n "${PRE_PUSH_GATE_WATCHDOG_SECONDS:-}" ]; then
        case "$PRE_PUSH_GATE_WATCHDOG_SECONDS" in
            *[!0-9]*)
                gate_fail "PRE_PUSH_GATE_WATCHDOG_SECONDS must be numeric seconds"
                ;;
        esac
        if [ "$PRE_PUSH_GATE_WATCHDOG_SECONDS" -lt "$RECOMMENDED_WATCHDOG_SECONDS" ]; then
            gate_fail "outer watchdog ${PRE_PUSH_GATE_WATCHDOG_SECONDS}s is shorter than recommended ${RECOMMENDED_WATCHDOG_SECONDS}s; timeout would hide the final verdict."
        fi
    fi

    for bin in git python timeout; do
        command -v "$bin" >/dev/null 2>&1 || gate_fail "missing required command: $bin"
    done

    python - <<'PY' || gate_fail "missing required Python dependency for full gate; install the project dev/test environment before running pre-push gate"
import importlib.util
import sys

missing = [
    name
    for name in ("black", "flake8", "bandit", "mypy", "pytest")
    if importlib.util.find_spec(name) is None
]
if missing:
    print("Missing Python modules: " + ", ".join(missing))
    sys.exit(1)
PY
}

if [ "${1:-}" = "--check-env" ]; then
    check_environment
    echo "PRE-PUSH-GATE PREFLIGHT PASS"
    exit 0
fi

run_check() {
    local NAME="$1"
    shift
    local CMD_START
    CMD_START=$(date +%s)
    echo ""
    echo "--- [${NAME}] starting ---"
    if "$@"; then
        local CMD_END
        CMD_END=$(date +%s)
        echo "--- [${NAME}] PASS ($((CMD_END - CMD_START))s) ---"
        PASSED_CHECKS+=("$NAME")
    else
        local EXIT=$?
        local CMD_END
        CMD_END=$(date +%s)
        echo "--- [${NAME}] FAIL exit=$EXIT ($((CMD_END - CMD_START))s) ---"
        FAILED_CHECKS+=("$NAME")
    fi
}

check_environment

# === quality.yml hard checks (tools/ scope) ===
run_check "doc-sync"            python .github/scripts/check_doc_sync.py
run_check "black --check tools/" python -m black --check tools/
run_check "flake8 tools/"        python -m flake8 tools/ --count --max-complexity=40 --max-line-length=100 --show-source --statistics
run_check "bandit tools/"        python -m bandit -r tools/ -ll -c pyproject.toml -q
run_check "mypy tools/"          python -m mypy tools/ --ignore-missing-imports

# === git hygiene ===
run_check "git diff --check"     git diff --check

# === compile sanity ===
run_check "compileall tools tests" python -m compileall -q tools tests

# === L2 pre-Gate state hygiene (must run before pytest) ===
# Clean .pytest_tmp to avoid pollution from previous interrupted runs
rm -rf .pytest_tmp/* .pytest_tmp/.* 2>/dev/null || true
# Use isolated basetemp for this run to avoid contention with concurrent runs
PYTEST_BASETEMP=".pytest_tmp/prepush_${TIMESTAMP}"
mkdir -p "$PYTEST_BASETEMP"
echo "Using pytest basetemp: $PYTEST_BASETEMP"

# Keep every CLI/test subprocess off the real user data directory. Some tests
# invoke the CLI through subprocess boundaries, so the sandbox must be exported.
export LIFE_INDEX_DATA_DIR="$PYTEST_BASETEMP/data"
mkdir -p "$LIFE_INDEX_DATA_DIR"
echo "Using LIFE_INDEX_DATA_DIR: $LIFE_INDEX_DATA_DIR"

# === tests.yml hard checks (with L1 outer timeout) ===
# Timeouts: blocker 900s (typical ~90s, 10× safety margin); contract 1200s; eval 600s
mkdir -p "$PYTEST_BASETEMP/blocker"
run_check "pytest -m blocker"    timeout "$BLOCKER_TIMEOUT_SECONDS" python -m pytest -o addopts="" -ra -q --strict-markers --strict-config -m blocker --timeout="$PYTEST_TIMEOUT_SECONDS" --basetemp="$PYTEST_BASETEMP/blocker"
mkdir -p "$PYTEST_BASETEMP/contract"
run_check "pytest -m contract"   timeout "$CONTRACT_TIMEOUT_SECONDS" python -m pytest -o addopts="" -ra -q --strict-markers --strict-config -m contract --timeout="$PYTEST_TIMEOUT_SECONDS" --basetemp="$PYTEST_BASETEMP/contract"
mkdir -p "$PYTEST_BASETEMP/eval"
run_check "search-eval-gate"     timeout "$EVAL_TIMEOUT_SECONDS" python -m pytest \
    -o addopts="" -ra -q --strict-markers --strict-config \
    tests/unit/test_eval_gate.py \
    tests/unit/test_eval_runner.py \
    tests/unit/test_eval_llm.py \
    tests/eval/test_broad_eval_soft_gate.py \
    tests/eval/test_semantic_report.py \
    tests/eval/test_eval_compare.py \
    tests/eval/test_eval_run.py \
    tests/eval/test_eval_qrels.py \
    tests/eval/test_eval_export.py \
    tests/eval/test_eval_serialization.py \
    --timeout="$PYTEST_TIMEOUT_SECONDS" --basetemp="$PYTEST_BASETEMP/eval"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "================================================"
echo "Pre-push gate summary (${DURATION}s)"
echo "================================================"
echo ""
echo "PASSED (${#PASSED_CHECKS[@]}):"
for check in "${PASSED_CHECKS[@]}"; do
    echo "  + $check"
done
echo ""
echo "FAILED (${#FAILED_CHECKS[@]}):"
for check in "${FAILED_CHECKS[@]}"; do
    echo "  - $check"
done

if [ "${#FAILED_CHECKS[@]}" -eq 0 ]; then
    echo ""
    echo "ALL CHECKS PASS — safe to push"
    exit 0
else
    echo ""
    echo "GATE FAIL: failed checks: ${FAILED_CHECKS[*]}"
    echo "DO NOT PUSH until all failed checks pass."
    echo "See log: $LOG"
    exit 1
fi
