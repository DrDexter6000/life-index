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
#   bash scripts/run_eval_gate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Run the eval gate tests (isolated data, no LLM, no semantic)
python -m pytest tests/unit/test_eval_gate.py tests/unit/test_eval_runner.py tests/unit/test_eval_llm.py -v --timeout=120

echo ""
echo "✅ Search eval quality gate passed"
