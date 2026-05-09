"""Deterministic tests for answer-level evaluation harness.

No network or LLM credentials required. Uses fake inputs to validate
the classification logic in tools.eval.answer_eval.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.eval.answer_eval import (  # noqa: E402
    AnswerEvalResult,
    AnswerVerdict,
    BatchAnswerEvalResult,
    CitationCheck,
    TransparencyCheck,
    TransparencyVerdict,
    _check_transparency,
    _detect_overclaiming,
    _is_absolute_path,
    evaluate_answer,
    evaluate_answer_batch,
    evaluate_answer_from_orchestrator_output,
)


def _make_answer(
    answer_text="Test answer.",
    citations=None,
    confidence="medium",
    confidence_reason="",
    limitations=None,
    evidence_summary="",
):
    d = {
        "answer_text": answer_text,
        "citations": citations or [],
        "confidence": confidence,
    }
    if confidence_reason:
        d["confidence_reason"] = confidence_reason
    if limitations is not None:
        d["limitations"] = limitations
    if evidence_summary:
        d["evidence_summary"] = evidence_summary
    return d


KNOWN_PATHS = {
    "Journals/2026/03/life-index_2026-03-01_001.md",
    "Journals/2026/03/life-index_2026-03-02_001.md",
    "Journals/2026/03/life-index_2026-03-03_001.md",
}


def test_empty_answer_text():
    answer = _make_answer(answer_text="")
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.EMPTY
    assert result.valid_citation_count == 0
    assert any("empty" in n.lower() for n in result.notes)


def test_no_citations():
    answer = _make_answer(answer_text="Some answer.", citations=[])
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.NO_CITATIONS
    assert result.valid_citation_count == 0


def test_all_citations_valid():
    answer = _make_answer(
        answer_text="Based on evidence.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.SUPPORTED
    assert result.valid_citation_count == 1
    assert result.invalid_citation_count == 0
    assert result.citation_checks[0].valid is True


def test_all_citations_invalid():
    answer = _make_answer(
        answer_text="Answer with bad refs.",
        citations=["Journals/2026/03/FAKE_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.INVALID_CITATION
    assert result.valid_citation_count == 0
    assert result.invalid_citation_count == 1
    assert result.citation_checks[0].valid is False
    assert result.citation_checks[0].reason == "unknown_path"


def test_mixed_citations():
    answer = _make_answer(
        answer_text="Partially supported.",
        citations=[
            "Journals/2026/03/life-index_2026-03-01_001.md",
            "Journals/2026/03/FAKE_001.md",
        ],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.SUPPORTED
    assert result.valid_citation_count == 1
    assert result.invalid_citation_count == 1
    assert any("failed validation" in n for n in result.notes)


def test_absolute_path_citation_rejected():
    answer = _make_answer(
        answer_text="Leaked path.",
        citations=["C:/Users/secret/Documents/Life-Index/Journals/2026/03/test.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.citation_checks[0].valid is False
    assert result.citation_checks[0].reason == "absolute_path"


def test_non_string_citation_rejected():
    answer = _make_answer(answer_text="Bad type.", citations=[123])
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.citation_checks[0].valid is False
    assert result.citation_checks[0].reason == "not_a_string"


def test_confidence_out_of_range_normalized():
    answer = _make_answer(answer_text="Test.", confidence="extreme")
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.confidence == "low"
    assert any("extreme" in n for n in result.notes)


def test_overclaiming_completeness_single_citation():
    answer = _make_answer(
        answer_text="These are all entries from that month.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.OVERCLAIMING


def test_overclaiming_strong_universal_single():
    answer = _make_answer(
        answer_text="I never went to Beijing.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.OVERCLAIMING


def test_no_overclaiming_with_multiple_citations():
    answer = _make_answer(
        answer_text="I never went to Beijing.",
        citations=[
            "Journals/2026/03/life-index_2026-03-01_001.md",
            "Journals/2026/03/life-index_2026-03-02_001.md",
        ],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.SUPPORTED


def test_no_overclaiming_moderate_text():
    answer = _make_answer(
        answer_text="I had some family time.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.SUPPORTED


def test_overclaiming_all_of_single():
    answer = _make_answer(
        answer_text="All of my work was done remotely.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.OVERCLAIMING


def test_transparency_complete():
    answer = _make_answer(
        answer_text="Good answer.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
        confidence_reason="Supported.",
        limitations=[],
        evidence_summary="Entry 1; source: fts; confidence: high",
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.transparency is not None
    assert result.transparency.verdict == TransparencyVerdict.COMPLETE
    assert result.transparency.confidence_reason_present is True
    assert result.transparency.limitations_present is True
    assert result.transparency.evidence_summary_present is True
    assert result.transparency.limitations_is_list is True


def test_transparency_partial():
    answer = _make_answer(
        answer_text="Partial.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
        confidence_reason="Supported.",
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.transparency.verdict == TransparencyVerdict.PARTIAL


def test_transparency_missing():
    answer = _make_answer(
        answer_text="Bare.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.transparency.verdict == TransparencyVerdict.MISSING


def test_transparency_no_citations_complete():
    answer = _make_answer(
        answer_text="No evidence.",
        citations=[],
        confidence_reason="No evidence found.",
        limitations=["No validated citations support this answer."],
    )
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.verdict == AnswerVerdict.NO_CITATIONS
    assert result.transparency.verdict == TransparencyVerdict.COMPLETE


def test_transparency_empty_not_applicable():
    answer = _make_answer(answer_text="")
    result = evaluate_answer(answer, KNOWN_PATHS)
    assert result.transparency.verdict == TransparencyVerdict.NOT_APPLICABLE


def test_transparency_disabled():
    answer = _make_answer(
        answer_text="Test.",
        citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
    )
    result = evaluate_answer(answer, KNOWN_PATHS, check_transparency=False)
    assert result.transparency is None


def test_from_orchestrator_output_no_answer():
    output = {"success": True, "filtered_results": []}
    assert evaluate_answer_from_orchestrator_output(output) is None


def test_from_orchestrator_extracts_known_paths():
    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "evidence_pack": {
            "items": [{"document": {"path": "Journals/2026/03/life-index_2026-03-02_001.md"}}]
        },
        "answer": {
            "answer_text": "Good.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "high",
        },
    }
    result = evaluate_answer_from_orchestrator_output(output)
    assert result is not None
    assert result.verdict == AnswerVerdict.SUPPORTED
    assert result.valid_citation_count == 1


def test_from_orchestrator_skips_absolute_paths():
    output = {
        "success": True,
        "filtered_results": [
            {"rel_path": "C:/Users/secret/test.md"},
            {"rel_path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "Test.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "medium",
        },
    }
    result = evaluate_answer_from_orchestrator_output(output)
    assert result is not None
    assert result.valid_citation_count == 1


def test_from_orchestrator_missing_evidence_pack():
    output = {
        "success": True,
        "filtered_results": [
            {"path": "Journals/2026/03/life-index_2026-03-01_001.md"},
        ],
        "answer": {
            "answer_text": "Works.",
            "citations": ["Journals/2026/03/life-index_2026-03-01_001.md"],
            "confidence": "medium",
        },
    }
    result = evaluate_answer_from_orchestrator_output(output)
    assert result is not None
    assert result.verdict == AnswerVerdict.SUPPORTED


def test_batch_evaluation():
    cases = [
        {
            "answer": _make_answer(
                answer_text="Supported.",
                citations=["Journals/2026/03/life-index_2026-03-01_001.md"],
            ),
            "known_paths": KNOWN_PATHS,
        },
        {
            "answer": _make_answer(answer_text="Empty.", citations=[]),
            "known_paths": KNOWN_PATHS,
        },
        {
            "answer": _make_answer(
                answer_text="Invalid.",
                citations=["FAKE.md"],
            ),
            "known_paths": KNOWN_PATHS,
        },
    ]
    result = evaluate_answer_batch(cases)
    assert result.total == 3
    assert result.by_verdict.get("supported") == 1
    assert result.by_verdict.get("no_citations") == 1
    assert result.by_verdict.get("invalid_citation") == 1
    assert len(result.details) == 3


def test_batch_empty():
    result = evaluate_answer_batch([])
    assert result.total == 0
    assert result.by_verdict == {}
    assert result.details == []


def test_is_absolute_path_windows():
    assert _is_absolute_path("C:/Users/test.md") is True
    assert _is_absolute_path("C:\\Users\\test.md") is True


def test_is_absolute_path_posix():
    assert _is_absolute_path("/home/user/test.md") is True


def test_is_absolute_path_relative():
    assert _is_absolute_path("Journals/2026/03/test.md") is False
    assert _is_absolute_path("test.md") is False


def test_detect_overclaiming_no_citations():
    assert _detect_overclaiming("All entries.", [], KNOWN_PATHS) is False


def test_detect_overclaiming_all_entries_single():
    assert (
        _detect_overclaiming(
            "These are all entries.",
            ["Journals/2026/03/life-index_2026-03-01_001.md"],
            KNOWN_PATHS,
        )
        is True
    )


def test_detect_overclaiming_all_entries_multi():
    assert (
        _detect_overclaiming(
            "These are all entries.",
            [
                "Journals/2026/03/life-index_2026-03-01_001.md",
                "Journals/2026/03/life-index_2026-03-02_001.md",
            ],
            KNOWN_PATHS,
        )
        is False
    )


def test_detect_overclaiming_never_single():
    assert (
        _detect_overclaiming(
            "I never did that.",
            ["Journals/2026/03/life-index_2026-03-01_001.md"],
            KNOWN_PATHS,
        )
        is True
    )


def test_detect_overclaiming_never_multi():
    assert (
        _detect_overclaiming(
            "I never did that.",
            [
                "Journals/2026/03/life-index_2026-03-01_001.md",
                "Journals/2026/03/life-index_2026-03-02_001.md",
            ],
            KNOWN_PATHS,
        )
        is False
    )


def test_detect_overclaiming_invalid_only():
    assert _detect_overclaiming("All entries.", ["FAKE.md"], KNOWN_PATHS) is False


def test_check_transparency_all_present():
    answer = {
        "confidence_reason": "High confidence.",
        "limitations": [],
        "evidence_summary": "Summary.",
    }
    tc = _check_transparency(answer, AnswerVerdict.SUPPORTED)
    assert tc.verdict == TransparencyVerdict.COMPLETE
    assert tc.confidence_reason_present is True
    assert tc.limitations_present is True
    assert tc.evidence_summary_present is True
    assert tc.limitations_is_list is True


def test_check_transparency_missing_fields():
    answer = {"answer_text": "Bare."}
    tc = _check_transparency(answer, AnswerVerdict.SUPPORTED)
    assert tc.verdict == TransparencyVerdict.MISSING
    assert tc.confidence_reason_present is False
    assert tc.limitations_present is False
    assert tc.evidence_summary_present is False


def test_check_transparency_no_citations_complete():
    answer = {
        "confidence_reason": "No evidence.",
        "limitations": ["No validated citations."],
    }
    tc = _check_transparency(answer, AnswerVerdict.NO_CITATIONS)
    assert tc.verdict == TransparencyVerdict.COMPLETE


def test_check_transparency_limitations_not_list():
    answer = {
        "confidence_reason": "Reason.",
        "limitations": "not a list",
        "evidence_summary": "Summary.",
    }
    tc = _check_transparency(answer, AnswerVerdict.SUPPORTED)
    assert tc.limitations_is_list is False
    assert tc.verdict == TransparencyVerdict.PARTIAL


def test_result_to_dict():
    result = AnswerEvalResult(
        verdict=AnswerVerdict.SUPPORTED,
        citation_checks=[CitationCheck("a.md", True, "known_path")],
        valid_citation_count=1,
        invalid_citation_count=0,
        transparency=TransparencyCheck(
            confidence_reason_present=True,
            limitations_present=True,
            evidence_summary_present=True,
            limitations_is_list=True,
            verdict=TransparencyVerdict.COMPLETE,
        ),
        confidence="high",
        notes=["ok"],
    )
    d = result.to_dict()
    assert d["verdict"] == "supported"
    assert d["valid_citation_count"] == 1
    assert d["transparency"]["verdict"] == "complete"
    assert d["citation_checks"][0]["citation"] == "a.md"


def test_result_to_dict_no_transparency():
    result = AnswerEvalResult(
        verdict=AnswerVerdict.EMPTY,
        confidence="low",
        notes=["empty"],
    )
    d = result.to_dict()
    assert "transparency" not in d
    assert d["verdict"] == "empty"


def test_batch_result_to_dict():
    result = BatchAnswerEvalResult(
        total=2, by_verdict={"supported": 2}, details=[{"verdict": "supported"}]
    )
    d = result.to_dict()
    assert d["total"] == 2
    assert d["by_verdict"]["supported"] == 2
