#!/usr/bin/env bash
# run_eval_gate.sh — Search eval quality gate for CI/local use
#
# Runs the search evaluation against isolated fixture data and checks
# results against quality gate criteria:
#   - Eval infrastructure completes without error
#   - All required golden query categories are covered
#   - Noise queries return zero results
#   - Positive queries return at least one result
#   - Baseline comparison infrastructure works
#
# Exit codes:
#   0 — all quality gates passed
#   1 — quality gate failed
#
# Usage:
#   bash scripts/run_eval_gate.sh [--snapshot=phase2]
#
# Options:
#   --snapshot=PHASE   Freeze eval metrics as baseline snapshot
#                      (e.g. --snapshot=phase2 writes .strategy/cli/Round_10_baselines/phase2.json)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

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
  # ── Section 1: Eval infrastructure tests ──
  echo "=== Section 1: Eval infrastructure ==="
  python -m pytest tests/unit/test_eval_gate.py tests/unit/test_eval_runner.py tests/unit/test_eval_llm.py -v --timeout=120
  echo ""
  echo "✅ Eval infrastructure passed"

  # ── Section 2: Rejection gate (D15, ≥90% pass-rate) ──
  echo "=== Section 2: Rejection quality gate (≥90% pass-rate) ==="
  python -m pytest tests/integration/test_golden_rejection.py -v --timeout=120
  echo ""
  echo "✅ Rejection quality gate passed"

  # ── Section 3: Full unit regression ──
  echo "=== Section 3: Full unit regression ==="
  python -m pytest tests/unit/ -q --timeout=300
  echo ""
  echo "✅ Full unit regression passed"

  echo ""
  echo "========================================="
  echo "✅ All search eval quality gates passed"
  echo "========================================="
fi
