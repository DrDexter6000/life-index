#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "Advisory only: inspect life-index eval --judge keyword evidence with the Host Agent."

python -m pytest \
  tests/unit/test_eval_advisory.py \
  tests/unit/test_eval_runner.py \
  tests/eval/test_broad_eval_soft_gate.py \
  -v --timeout=120
