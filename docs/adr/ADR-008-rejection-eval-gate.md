# ADR-008: Rejection Eval Gate as Hard CI Threshold

**Status**: Accepted
**Date**: 2026-04-17
**Round/Phase**: Round 10 Phase 5 Task 5.3
**Decision**: D15 (PRD §9)

## Context

Round 10 introduced search rejection capability — the ability to return zero/low-confidence results for queries unrelated to the user's journal corpus. A golden rejection set of 22 queries (`tests/golden_rejection_queries.yaml`) was created in Phase 2 (T2.3) and validated in Phase 5 (T5.2) with a pass-rate ≥ 90%.

Without a CI gate, regressions in rejection quality (e.g., loosening thresholds, removing noise filters) could pass CI undetected. The golden set provides the regression signal; the gate ensures it's enforced.

## Decision

Integrate the rejection pass-rate into `scripts/run_eval_gate.sh` as a **hard CI threshold**:

- **Threshold**: ≥ 90% pass-rate (D15)
- **Enforcement**: Non-zero exit code on failure — no `continue-on-error`, no retry
- **Test source**: `tests/golden_rejection_queries.yaml` (22 queries)
- **Test runner**: `pytest tests/integration/test_golden_rejection.py`

### Threshold Rationale

90% allows up to 2 failures out of 22 queries. This accounts for edge cases where:
- A query is semantically ambiguous (e.g., "我的朋友小明" — "小明" could match real content)
- A borderline result passes through but with `low` confidence

The 90% floor is intentionally high — the search system should reject clearly unrelated queries with very high reliability.

### Threshold Adjustment Process

If the rejection set needs adjustment (adding/removing queries, changing expectations):
1. Update `tests/golden_rejection_queries.yaml`
2. Run `pytest tests/integration/test_golden_rejection.py -v` to verify new pass-rate
3. Document the change in the commit message
4. Do NOT lower the threshold below 90% — instead, fix the search quality or fix the test expectation

## Consequences

- Any PR that degrades rejection quality will fail CI
- The gate also catches regressions from threshold changes (RRF_MIN_SCORE, SEMANTIC_MIN_SIMILARITY)
- Combined with the ranking quality gate (MRR@5/P@5 baselines), the eval gate provides full-spectrum regression protection

## Related

- D15: Rejection evaluation gate design decision
- T2.3: Golden rejection set creation (22 queries)
- T5.2: Pass-rate validation (≥ 90% confirmed)
- `tests/golden_rejection_queries.yaml`: The golden rejection query set
- `tests/integration/test_golden_rejection.py`: Integration test
