#!/usr/bin/env python3
"""Tests for eval_export adapters (R2-B3d).

Covers:
  - qrels_to_plain_dict: deep copy, plain dict output
  - run_to_plain_dict: deep copy, plain dict output
  - qrels_to_trec: format, sorting, empty
  - run_to_trec: format, sorting, rank, run_name, empty
  - No leakage of title/query/absolute path
  - Input not mutated
  - Scores as readable float strings
"""

from __future__ import annotations

from types import MappingProxyType

from tools.eval.eval_export import (
    qrels_to_plain_dict,
    qrels_to_trec,
    run_to_plain_dict,
    run_to_trec,
)

# ---------------------------------------------------------------------------
# qrels_to_plain_dict
# ---------------------------------------------------------------------------


class TestQrelsToPlainDict:
    def test_deep_copy(self) -> None:
        original = {"Q1": {"d1": 1, "d2": 0}}
        result = qrels_to_plain_dict(original)
        assert result == original
        result["Q1"]["d1"] = 99
        assert original["Q1"]["d1"] == 1

    def test_immutable_input_accepted(self) -> None:
        frozen = {"Q1": MappingProxyType({"d1": 1})}
        result = qrels_to_plain_dict(frozen)
        assert isinstance(result["Q1"], dict)
        assert result["Q1"]["d1"] == 1

    def test_empty(self) -> None:
        assert qrels_to_plain_dict({}) == {}


# ---------------------------------------------------------------------------
# run_to_plain_dict
# ---------------------------------------------------------------------------


class TestRunToPlainDict:
    def test_deep_copy(self) -> None:
        original = {"Q1": {"d1": 1.0, "d2": 0.5}}
        result = run_to_plain_dict(original)
        assert result == original
        result["Q1"]["d1"] = 99.0
        assert original["Q1"]["d1"] == 1.0

    def test_immutable_input_accepted(self) -> None:
        frozen = {"Q1": MappingProxyType({"d1": 0.5})}
        result = run_to_plain_dict(frozen)
        assert isinstance(result["Q1"], dict)

    def test_empty(self) -> None:
        assert run_to_plain_dict({}) == {}


# ---------------------------------------------------------------------------
# qrels_to_trec
# ---------------------------------------------------------------------------


class TestQrelsToTrec:
    def test_basic_format(self) -> None:
        qrels = {"Q1": {"d1": 1, "d2": 0}}
        result = qrels_to_trec(qrels)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        parts = lines[0].split()
        assert parts[0] == "Q1"
        assert parts[1] == "0"
        assert parts[2] == "d1"
        assert parts[3] == "1"

    def test_sorted_by_query_then_doc(self) -> None:
        qrels = {"Q2": {"b": 1}, "Q1": {"a": 1, "b": 0}}
        result = qrels_to_trec(qrels)
        lines = result.strip().split("\n")
        assert lines[0].startswith("Q1")
        assert lines[1].startswith("Q1")
        assert lines[2].startswith("Q2")
        # Q1 docs sorted: a before b
        assert lines[0].split()[2] == "a"
        assert lines[1].split()[2] == "b"

    def test_empty_returns_empty_string(self) -> None:
        assert qrels_to_trec({}) == ""

    def test_trailing_newline(self) -> None:
        result = qrels_to_trec({"Q1": {"d1": 1}})
        assert result.endswith("\n")
        assert result.count("\n") == 1


# ---------------------------------------------------------------------------
# run_to_trec
# ---------------------------------------------------------------------------


class TestRunToTrec:
    def test_basic_format(self) -> None:
        run = {"Q1": {"d1": 1.0, "d2": 0.5}}
        result = run_to_trec(run)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        parts = lines[0].split()
        assert parts[0] == "Q1"
        assert parts[1] == "Q0"
        assert parts[2] == "d1"
        assert parts[3] == "1"  # rank
        assert parts[4] == "1.0"
        assert parts[5] == "life-index"

    def test_sorted_score_desc(self) -> None:
        run = {"Q1": {"b": 0.5, "a": 1.0}}
        lines = run_to_trec(run).strip().split("\n")
        assert lines[0].split()[2] == "a"  # score 1.0 first
        assert lines[0].split()[3] == "1"  # rank 1
        assert lines[1].split()[2] == "b"  # score 0.5 second
        assert lines[1].split()[3] == "2"  # rank 2

    def test_tie_broken_by_doc_id_asc(self) -> None:
        run = {"Q1": {"b": 1.0, "a": 1.0}}
        lines = run_to_trec(run).strip().split("\n")
        assert lines[0].split()[2] == "a"  # doc_id asc for tie
        assert lines[1].split()[2] == "b"

    def test_rank_starts_at_one(self) -> None:
        run = {"Q1": {"d": 0.5}}
        line = run_to_trec(run).strip()
        assert line.split()[3] == "1"

    def test_empty_returns_empty_string(self) -> None:
        assert run_to_trec({}) == ""

    def test_trailing_newline(self) -> None:
        result = run_to_trec({"Q1": {"d": 1.0}})
        assert result.endswith("\n")

    def test_custom_run_name(self) -> None:
        run = {"Q1": {"d": 1.0}}
        result = run_to_trec(run, run_name="test-run")
        assert result.strip().endswith("test-run")

    def test_sorted_by_query_id(self) -> None:
        run = {"Q2": {"d": 1.0}, "Q1": {"d": 0.5}}
        lines = run_to_trec(run).strip().split("\n")
        assert lines[0].startswith("Q1")
        assert lines[1].startswith("Q2")

    def test_score_as_readable_float(self) -> None:
        run = {"Q1": {"d": 0.3333333333333333}}
        line = run_to_trec(run).strip()
        score_str = line.split()[4]
        assert float(score_str) == 0.3333333333333333


# ---------------------------------------------------------------------------
# No leakage / mutation
# ---------------------------------------------------------------------------


class TestSafety:
    def test_no_title_in_trec_output(self) -> None:
        run = {"Q1": {"d1": 1.0}}
        qrels = {"Q1": {"d1": 1}}
        assert "Secret Title" not in run_to_trec(run)
        assert "Secret Title" not in qrels_to_trec(qrels)

    def test_no_query_text_in_trec_output(self) -> None:
        run = {"Q1": {"d1": 1.0}}
        assert "what is life" not in run_to_trec(run)

    def test_no_path_beyond_doc_id(self) -> None:
        run = {"Q1": {"2026/03/file.md": 1.0}}
        output = run_to_trec(run)
        lines = output.strip().split("\n")
        parts = lines[0].split()
        # Only doc_id column has path; no extra columns contain paths
        assert parts[2] == "2026/03/file.md"
        # run_name, query_id, Q0, rank, score have no path separators
        for i in [0, 1, 3, 4, 5]:
            assert "/" not in parts[i]

    def test_input_not_mutated_qrels(self) -> None:
        original = {"Q1": {"d1": 1}}
        frozen_inner = MappingProxyType(original["Q1"])
        original["Q1"] = dict(frozen_inner)
        _ = qrels_to_trec(original)
        assert original["Q1"]["d1"] == 1

    def test_input_not_mutated_run(self) -> None:
        original = {"Q1": {"d1": 1.0}}
        _ = run_to_trec(original)
        assert original["Q1"]["d1"] == 1.0
