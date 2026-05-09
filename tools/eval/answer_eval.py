"""Deterministic answer-level evaluation harness for R2-D synthesis.

Classifies answer synthesis output along five failure-mode axes:
  1. supported answer
  2. unsupported / overclaiming answer
  3. invalid citation
  4. no valid citations
  5. transparency quality

No network or LLM credentials required. Operates on pre-computed
orchestrator output dicts (or deterministic fakes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Classification enums


class AnswerVerdict(str, Enum):
    """Top-level answer quality classification."""

    SUPPORTED = "supported"
    OVERCLAIMING = "overclaiming"
    INVALID_CITATION = "invalid_citation"
    NO_CITATIONS = "no_citations"
    EMPTY = "empty"


class TransparencyVerdict(str, Enum):
    """Transparency field quality classification."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


# Data structures


@dataclass(frozen=True)
class CitationCheck:
    """Result of checking a single citation."""

    citation: str
    valid: bool
    reason: str


@dataclass(frozen=True)
class TransparencyCheck:
    """Result of checking transparency fields."""

    confidence_reason_present: bool
    limitations_present: bool
    evidence_summary_present: bool
    limitations_is_list: bool
    verdict: TransparencyVerdict


@dataclass
class AnswerEvalResult:
    """Complete answer evaluation result."""

    verdict: AnswerVerdict
    citation_checks: list[CitationCheck] = field(default_factory=list)
    valid_citation_count: int = 0
    invalid_citation_count: int = 0
    transparency: TransparencyCheck | None = None
    confidence: str = "low"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "verdict": self.verdict.value,
            "valid_citation_count": self.valid_citation_count,
            "invalid_citation_count": self.invalid_citation_count,
            "confidence": self.confidence,
            "notes": self.notes,
            "citation_checks": [
                {
                    "citation": cc.citation,
                    "valid": cc.valid,
                    "reason": cc.reason,
                }
                for cc in self.citation_checks
            ],
        }
        if self.transparency is not None:
            d["transparency"] = {
                "confidence_reason_present": self.transparency.confidence_reason_present,
                "limitations_present": self.transparency.limitations_present,
                "evidence_summary_present": self.transparency.evidence_summary_present,
                "limitations_is_list": self.transparency.limitations_is_list,
                "verdict": self.transparency.verdict.value,
            }
        return d


# Core evaluation function


def evaluate_answer(
    answer: dict[str, Any],
    known_paths: set[str],
    *,
    check_transparency: bool = True,
) -> AnswerEvalResult:
    """Evaluate a single answer dict deterministically.

    Args:
        answer: Dict with keys matching the answer schema:
            answer_text, citations, confidence, confidence_reason,
            limitations, evidence_summary.
        known_paths: Set of known valid relative document paths
            (from filtered_results + evidence_context).
        check_transparency: Whether to evaluate transparency fields.

    Returns:
        AnswerEvalResult with verdict, citation checks, and transparency.
    """
    answer_text = answer.get("answer_text", "")
    raw_citations = answer.get("citations", [])
    confidence = answer.get("confidence", "low")

    # Empty answer still gets a NOT_APPLICABLE transparency verdict.
    if not answer_text:
        empty_transparency = (
            _check_transparency(answer, AnswerVerdict.EMPTY) if check_transparency else None
        )
        return AnswerEvalResult(
            verdict=AnswerVerdict.EMPTY,
            confidence=confidence,
            transparency=empty_transparency,
            notes=["Answer text is empty."],
        )

    # Validate each citation
    citation_checks: list[CitationCheck] = []
    for c in raw_citations:
        if not isinstance(c, str):
            citation_checks.append(
                CitationCheck(citation=str(c), valid=False, reason="not_a_string")
            )
            continue
        if _is_absolute_path(c):
            citation_checks.append(CitationCheck(citation=c, valid=False, reason="absolute_path"))
        elif c in known_paths:
            citation_checks.append(CitationCheck(citation=c, valid=True, reason="known_path"))
        else:
            citation_checks.append(CitationCheck(citation=c, valid=False, reason="unknown_path"))

    valid_count = sum(1 for cc in citation_checks if cc.valid)
    invalid_count = sum(1 for cc in citation_checks if not cc.valid)

    # Determine verdict
    if not raw_citations:
        verdict = AnswerVerdict.NO_CITATIONS
    elif valid_count == 0:
        verdict = AnswerVerdict.INVALID_CITATION
    elif _detect_overclaiming(answer_text, raw_citations, known_paths):
        verdict = AnswerVerdict.OVERCLAIMING
    else:
        verdict = AnswerVerdict.SUPPORTED

    # Transparency check
    transparency_result: TransparencyCheck | None = None
    if check_transparency:
        transparency_result = _check_transparency(answer, verdict)

    notes: list[str] = []
    if invalid_count > 0:
        notes.append(f"{invalid_count} citation(s) failed validation.")
    if confidence not in ("high", "medium", "low"):
        notes.append(f"Unexpected confidence value: {confidence}")

    return AnswerEvalResult(
        verdict=verdict,
        citation_checks=citation_checks,
        valid_citation_count=valid_count,
        invalid_citation_count=invalid_count,
        transparency=transparency_result,
        confidence=confidence if confidence in ("high", "medium", "low") else "low",
        notes=notes,
    )


def evaluate_answer_from_orchestrator_output(
    output: dict[str, Any],
) -> AnswerEvalResult | None:
    """Evaluate answer from a full orchestrator search() output dict.

    Extracts known_paths from filtered_results and evidence_pack, then
    delegates to evaluate_answer().

    Returns None if no answer field is present.
    """
    answer = output.get("answer")
    if answer is None:
        return None

    known_paths: set[str] = set()

    # Collect from filtered_results
    for r in output.get("filtered_results", []):
        rel = r.get("rel_path", "")
        p = r.get("path", "")
        if rel and not _is_absolute_path(rel):
            known_paths.add(rel)
        elif p and not _is_absolute_path(p):
            known_paths.add(p)

    # Collect from evidence_pack items
    ep = output.get("evidence_pack", {})
    if isinstance(ep, dict):
        for item in ep.get("items", []):
            doc = item.get("document", {})
            rel = doc.get("rel_path", "") or doc.get("path", "")
            if rel and not _is_absolute_path(rel):
                known_paths.add(rel)

    return evaluate_answer(answer, known_paths)


# Batch evaluation


@dataclass
class BatchAnswerEvalResult:
    """Aggregated result from evaluating multiple answer outputs."""

    total: int = 0
    by_verdict: dict[str, int] = field(default_factory=dict)
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_verdict": dict(self.by_verdict),
            "details": self.details,
        }


def evaluate_answer_batch(
    cases: list[dict[str, Any]],
) -> BatchAnswerEvalResult:
    """Evaluate a batch of answer dicts with their known_paths.

    Each case dict must have:
      - "answer": the answer dict
      - "known_paths": set of known valid paths

    Returns aggregated BatchAnswerEvalResult.
    """
    result = BatchAnswerEvalResult()
    for case in cases:
        answer = case["answer"]
        known_paths = case["known_paths"]
        eval_result = evaluate_answer(answer, known_paths)
        result.total += 1
        verdict_str = eval_result.verdict.value
        result.by_verdict[verdict_str] = result.by_verdict.get(verdict_str, 0) + 1
        result.details.append(eval_result.to_dict())
    return result


# Internal helpers


def _is_absolute_path(path: str) -> bool:
    """Check if a path looks absolute (Windows or POSIX)."""
    import os

    return os.path.isabs(path) or (len(path) >= 2 and path[1] == ":")


def _detect_overclaiming(
    answer_text: str,
    citations: list[Any],
    known_paths: set[str],
) -> bool:
    """Heuristic overclaiming detection.

    Flags answers that make strong universal claims ("all", "every", "never")
    without supporting evidence from multiple citations, or that claim
    completeness when only one citation is present.

    This is a conservative heuristic: it may produce false negatives but
    aims for zero false positives on well-supported answers.
    """
    if not citations:
        return False

    valid = [c for c in citations if isinstance(c, str) and c in known_paths]
    if not valid:
        return False  # Already classified as invalid_citation

    text_lower = answer_text.lower()
    strong_markers = ("all of", "every single", "never", "none of", "always")
    completeness_markers = ("all entries", "all journals", "complete list", "every entry")

    has_strong = any(m in text_lower for m in strong_markers)
    has_completeness = any(m in text_lower for m in completeness_markers)

    # Single citation claiming completeness is overclaiming
    if has_completeness and len(valid) == 1:
        return True

    # Strong universal claim with minimal support
    if has_strong and len(valid) < 2:
        return True

    return False


def _check_transparency(
    answer: dict[str, Any],
    verdict: AnswerVerdict,
) -> TransparencyCheck:
    """Check transparency field presence and quality."""
    has_confidence_reason = (
        "confidence_reason" in answer
        and isinstance(answer["confidence_reason"], str)
        and len(answer["confidence_reason"]) > 0
    )
    has_limitations = "limitations" in answer
    has_evidence_summary = "evidence_summary" in answer and isinstance(
        answer["evidence_summary"], str
    )
    limitations_is_list = isinstance(answer.get("limitations"), list)

    # Determine verdict
    if verdict == AnswerVerdict.NO_CITATIONS:
        # For no-citation answers, we still expect limitations to say so
        if has_confidence_reason and has_limitations and limitations_is_list:
            tv = TransparencyVerdict.COMPLETE
        elif has_confidence_reason or has_limitations:
            tv = TransparencyVerdict.PARTIAL
        else:
            tv = TransparencyVerdict.MISSING
    elif verdict == AnswerVerdict.EMPTY:
        tv = TransparencyVerdict.NOT_APPLICABLE
    else:
        present = [has_confidence_reason, has_limitations, has_evidence_summary]
        count = sum(present)
        if count == 3 and limitations_is_list:
            tv = TransparencyVerdict.COMPLETE
        elif count >= 1:
            tv = TransparencyVerdict.PARTIAL
        else:
            tv = TransparencyVerdict.MISSING

    return TransparencyCheck(
        confidence_reason_present=has_confidence_reason,
        limitations_present=has_limitations,
        evidence_summary_present=has_evidence_summary,
        limitations_is_list=limitations_is_list,
        verdict=tv,
    )
