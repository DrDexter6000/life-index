from __future__ import annotations

import pytest

from tools.eval.run_eval import _compute_ndcg_at_5


@pytest.mark.parametrize(
    ("scores", "expected"),
    (
        ([3, 2, 1, 0, 0], 1.0),
        ([], 0.0),
        ([0, 0, 0, 0, 0], 0.0),
    ),
)
def test_compute_ndcg_at_5_deterministic_cases(
    scores: list[int],
    expected: float,
) -> None:
    assert _compute_ndcg_at_5(scores) == expected


def test_compute_ndcg_at_5_disordered_scores_are_bounded() -> None:
    value = _compute_ndcg_at_5([1, 3, 2, 0, 0])

    assert 0.0 < value < 1.0
