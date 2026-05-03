"""Sanity test: Round 18 closure M-metrics bind directly to PRD hard metrics.

Task 2.2 (Phase 4): M-metrics must reference PRD §5 hard metric text,
not implementation-level signals like "subcommand registered successfully".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CLOSURE_PATH = Path(".strategy/cli/round-18-plan/phase-7-closure.md")
PRD_PATH = Path(".strategy/cli/round-18-prd.md")
SEMANTIC_BASELINE = Path("tests/eval/baselines/round-18-semantic-baseline.json")
KEYWORD_BASELINE = Path("tests/eval/baselines/round-18-keyword-baseline.json")


class TestClosureBindsToPRD:
    """M5: closure M-metrics must reference PRD hard metric text."""

    @pytest.fixture(scope="class")
    def closure_text(self) -> str:
        if not CLOSURE_PATH.exists():
            pytest.fail(f"Closure doc not found: {CLOSURE_PATH}")
        return CLOSURE_PATH.read_text(encoding="utf-8")

    @pytest.fixture(scope="class")
    def prd_text(self) -> str:
        if not PRD_PATH.exists():
            pytest.fail(f"PRD not found: {PRD_PATH}")
        return PRD_PATH.read_text(encoding="utf-8")

    def test_closure_doc_exists(self, closure_text: str) -> None:
        assert len(closure_text) > 0

    def test_m1_gold_set_150_in_closure(self, closure_text: str) -> None:
        assert "Gold Set >= 150" in closure_text or "Gold Set ≥ 150" in closure_text

    def test_m2_recall_at_5_in_closure(self, closure_text: str) -> None:
        assert "Recall@5 >= 0.45" in closure_text or "Recall@5 ≥ 0.45" in closure_text

    def test_m2_time_range_threshold_in_closure(self, closure_text: str) -> None:
        assert "time_range" in closure_text and "35%" in closure_text

    def test_m2_complex_query_threshold_in_closure(self, closure_text: str) -> None:
        assert "complex_query" in closure_text and "35%" in closure_text

    def test_m3_semantic_baseline_in_closure(self, closure_text: str) -> None:
        assert "semantic-baseline" in closure_text or "semantic baseline" in closure_text

    def test_m7_entity_expansion_in_closure(self, closure_text: str) -> None:
        assert "entity_expansion" in closure_text and "25%" in closure_text

    def test_no_implementation_smoke_signals(self, closure_text: str) -> None:
        """M5 negative: closure must NOT use implementation-level smoke signals."""
        forbidden = [
            "子命令注册成功",
            "subcommand registered",
            "cli registered",
            "module loaded",
            "import successful",
        ]
        for phrase in forbidden:
            assert phrase not in closure_text, (
                f"Closure contains implementation smoke signal: '{phrase}'. "
                "M-metrics must bind to PRD hard metrics, not implementation signals."
            )


class TestBaselineArtifactsExist:
    """M3: semantic baseline must exist with 5 metrics."""

    def test_semantic_baseline_exists(self) -> None:
        assert SEMANTIC_BASELINE.exists(), f"Missing: {SEMANTIC_BASELINE}"

    def test_semantic_baseline_has_5_metrics(self) -> None:
        data = json.loads(SEMANTIC_BASELINE.read_text(encoding="utf-8"))
        metrics = data["data"]["metrics"]
        required = {"mrr_at_5", "recall_at_5", "recall_at_10", "precision_at_5", "ndcg_at_5"}
        assert required.issubset(
            set(metrics.keys())
        ), f"Missing metrics: {required - set(metrics.keys())}"

    def test_semantic_baseline_flag(self) -> None:
        data = json.loads(SEMANTIC_BASELINE.read_text(encoding="utf-8"))
        assert data["data"]["semantic_enabled"] is True

    def test_keyword_baseline_exists(self) -> None:
        assert KEYWORD_BASELINE.exists(), f"Missing: {KEYWORD_BASELINE}"

    def test_keyword_baseline_has_core_metrics(self) -> None:
        data = json.loads(KEYWORD_BASELINE.read_text(encoding="utf-8"))
        metrics = data["data"]["metrics"]
        required = {"mrr_at_5", "recall_at_5", "precision_at_5", "ndcg_at_5"}
        assert required.issubset(set(metrics.keys()))


class TestPRDHardMetricsAreStable:
    """Verify PRD §5 text hasn't drifted since this test was written."""

    @pytest.fixture(scope="class")
    def prd_text(self) -> str:
        return PRD_PATH.read_text(encoding="utf-8")

    def test_prd_m1_text(self, prd_text: str) -> None:
        assert "Gold Set >= 150" in prd_text or "Gold Set ≥ 150" in prd_text

    def test_prd_m2a_text(self, prd_text: str) -> None:
        assert "Recall@5 >= 0.45" in prd_text or "Recall@5 ≥ 0.45" in prd_text

    def test_prd_m7_text(self, prd_text: str) -> None:
        assert "entity_expansion" in prd_text and "25%" in prd_text
