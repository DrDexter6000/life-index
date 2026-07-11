#!/usr/bin/env bash
# run_eval_gate.sh — Deterministic eval contract gate for CI/local use
#
# Runs deterministic evaluation contract checks:
#   - Eval infrastructure completes without error
#   - Provider retirement and fail-fast compatibility stay enforced
#   - A public synthetic token-match Core assertion executes
#   - Eval result/report compatibility remains stable
#
# Exit codes:
#   0 — all deterministic checks passed
#   1 — a deterministic check failed
#
# Usage:
#   bash scripts/run_eval_gate.sh
#   bash scripts/run_eval_gate.sh --snapshot=phase2
#
# Options:
#   --snapshot=PHASE   Maintenance-only snapshot operation; this does not run
#                      the deterministic gate. Prefer freeze_baseline.py for
#                      new automation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-120}"
EVAL_TEST_TARGETS=(
  tests/unit/test_eval_provider_retirement.py
  tests/unit/test_eval_metrics.py
  tests/integration/test_eval_gate_ci.py
  tests/integration/test_eval_private_inventory.py
  tests/eval/test_semantic_report.py
  tests/eval/test_eval_compare.py
  tests/eval/test_eval_run.py
  tests/eval/test_eval_qrels.py
  tests/eval/test_eval_export.py
  tests/eval/test_eval_serialization.py
)

# Parse --snapshot=PHASE argument
SNAPSHOT_PHASE=""
for arg in "$@"; do
  case "$arg" in
    --snapshot=*)
      SNAPSHOT_PHASE="${arg#--snapshot=}"
      ;;
  esac
done

if [ -n "$SNAPSHOT_PHASE" ]; then
  echo "Freezing baseline snapshot for '$SNAPSHOT_PHASE'..."
  python scripts/freeze_baseline.py --phase "$SNAPSHOT_PHASE"
  echo ""
  echo "✅ Baseline snapshot frozen: .strategy/cli/Round_10_baselines/${SNAPSHOT_PHASE}.json"
else
  echo "=== Section 1: Authoritative deterministic inventory ==="
  echo "=== Section 2: Public synthetic Core assertion ==="
  python .github/scripts/run_public_core_assertions.py
  echo ""
  echo "✅ Public synthetic Core assertion passed"

  echo "=== Section 3: Deterministic eval contracts ==="
  PYTEST_ARGS=(-v "--timeout=$PYTEST_TIMEOUT_SECONDS")
  if [ -n "${EVAL_PYTEST_BASETEMP:-}" ]; then
    PYTEST_ARGS+=("--basetemp=$EVAL_PYTEST_BASETEMP")
  fi
  python -m pytest "${EVAL_TEST_TARGETS[@]}" "${PYTEST_ARGS[@]}"
  echo ""
  echo "✅ Deterministic eval contracts passed"

  echo ""
  echo "========================================="
  echo "✅ Deterministic eval checks passed"
  echo "========================================="
fi
