#!/usr/bin/env bash
# Life Index CLI — Tier 1 fast local gate
#
# Fast local feedback for WIP and pre-PR work. This is not the full
# merge/push-batch gate; run scripts/pre-push-gate.sh before merge readiness.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP=$(date +%s)
LOG_DIR=".agent-reports/tier1-gate"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run_${TIMESTAMP}.log"
echo "Log: $LOG"
exec > >(tee "$LOG") 2>&1

START_TIME=$(date +%s)
echo "================================================"
echo "Life Index Tier 1 fast gate"
echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Repo:  $REPO_ROOT"
echo "SSOT:  .agent-governance/CI_HARD_CHECKS.md"
echo "================================================"

declare -a FAILED_CHECKS=()
declare -a PASSED_CHECKS=()

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

export LIFE_INDEX_INDEX_FTS_ONLY="${LIFE_INDEX_INDEX_FTS_ONLY:-1}"

run_check "public-diff-names"    python .github/scripts/check_public_diff_names.py
run_check "doc-sync"             python .github/scripts/check_doc_sync.py
run_check "l2-no-llm"            python .github/scripts/check_l2_no_llm.py
run_check "black --check tools/"  python -m black --check tools/
run_check "flake8 tools/"         python -m flake8 tools/ --count --max-complexity=40 --max-line-length=100 --show-source --statistics
run_check "bandit tools/"         python -m bandit -r tools/ -ll -c pyproject.toml -q
run_check "mypy tools/"           python -m mypy tools/ --ignore-missing-imports
run_check "git diff --check"      git diff --check
run_check "compileall tools tests" python -m compileall -q tools tests

PYTEST_BASETEMP=".pytest_tmp/tier1_${TIMESTAMP}"
mkdir -p "$PYTEST_BASETEMP"
export LIFE_INDEX_DATA_DIR="$PYTEST_BASETEMP/data"
mkdir -p "$LIFE_INDEX_DATA_DIR"
echo "Using pytest basetemp: $PYTEST_BASETEMP"
echo "Using LIFE_INDEX_DATA_DIR: $LIFE_INDEX_DATA_DIR"

run_check "pytest -m blocker" timeout 900 python -m pytest -m blocker -o addopts="" -ra -q --strict-markers --strict-config --timeout=120 --basetemp="$PYTEST_BASETEMP/blocker"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "================================================"
echo "Tier 1 fast gate summary (${DURATION}s)"
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
    echo "TIER 1 FAST GATE PASS — continue local work or prepare PR"
    exit 0
else
    echo ""
    echo "TIER 1 FAST GATE FAIL: failed checks: ${FAILED_CHECKS[*]}"
    echo "Fix before continuing."
    echo "See log: $LOG"
    exit 1
fi
