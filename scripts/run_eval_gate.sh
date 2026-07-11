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
  python -m pytest tests/unit/test_eval_metrics.py tests/eval/test_eval_run.py -v --timeout=120
  echo ""
  echo "✅ Eval infrastructure passed"

  # ── Section 2: Public synthetic Core assertion ──
  echo "=== Section 2: Public synthetic Core assertion ==="
  python .github/scripts/run_public_core_assertions.py
  echo ""
  echo "✅ Public synthetic Core assertion passed"

  # ── Section 3: Provider retirement and eval compatibility ──
  echo "=== Section 3: Provider retirement and eval compatibility ==="
  python -m pytest tests/unit/test_eval_provider_retirement.py tests/eval/test_semantic_report.py -q --timeout=300
  echo ""
  echo "✅ Provider retirement and eval compatibility passed"

  echo ""
  echo "========================================="
  echo "✅ Deterministic eval checks passed"
  echo "========================================="
fi
