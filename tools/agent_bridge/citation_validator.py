"""Hard citation gate for Agent Bridge query answers.

This module validates the citation boundary after an ACP agent returns an
``m35.agent_bridge_query.v0`` envelope.  It is intentionally independent from
the prompt: prompt instructions are advisory, this gate is the deterministic
output authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from tools.lib.paths import get_user_data_dir

_JOURNAL_REF_RE = re.compile(
    r"(?:(?:Journals[/\\])?\d{4}[/\\]\d{2}[/\\][^\s\]\"'`,;:)}]+(?:\.md)?)"
)
_SHORT_REF_RE_TEMPLATE = r"(?<![A-Za-z0-9_-]){ref}(?![A-Za-z0-9_-])"
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CHINESE_DATE_RE = re.compile(r"\d{1,2}月\d{1,2}日")
_NUMBER_FACT_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:days?|entries|logs?|times?)\b|"
    r"\d+(?:\.\d+)?\s*(?:天|次|篇|条|个))",
    re.IGNORECASE,
)
_AGGREGATE_FACT_RE = re.compile(
    r"\b(?:total|count|aggregate|sum)\b|(?:总共|一共|共计|合计)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CitationGateResult:
    ok: bool
    error: str | None
    evidence_refs: list[str]
    trace_checked: bool = False
    trace_missing: tuple[str, ...] = ()


def normalize_journal_ref(ref: str) -> str | None:
    """Normalize a journal reference to ``Journals/YYYY/MM/name.md``.

    Accepts canonical ``Journals/...`` refs, slash-form ``YYYY/MM/name`` refs,
    and absolute paths containing a ``Journals/`` suffix.  Returns ``None`` for
    non-journal IDs or unsafe paths.
    """
    norm = ref.replace("\\", "/").strip().strip("[](){}'\".,;:")
    if not norm:
        return None

    idx = norm.find("Journals/")
    if idx != -1:
        norm = norm[idx:]
    elif re.match(r"^\d{4}/\d{2}/", norm):
        norm = f"Journals/{norm}"
    else:
        return None

    if not norm.endswith(".md"):
        norm = f"{norm}.md"

    posix = PurePosixPath(norm)
    parts = posix.parts
    if len(parts) != 4 or parts[0] != "Journals":
        return None
    if any(part in (".", "..") for part in parts):
        return None
    filename = parts[-1]
    if filename in ("", ".md") or "*" in filename:
        return None
    return "/".join(parts)


def _journal_path(ref: str) -> Path:
    data_dir = get_user_data_dir().expanduser().resolve(strict=False)
    candidate = (data_dir / ref).expanduser().resolve(strict=False)
    try:
        candidate.relative_to(data_dir)
    except ValueError as exc:
        raise ValueError(f"journal ref escapes data directory: {ref}") from exc
    return candidate


def journal_ref_exists(ref: str) -> bool:
    """Return True when *ref* exists as a file in the active data directory."""
    return _journal_path(ref).is_file()


def extract_journal_refs_from_text(text: str) -> list[str]:
    """Extract normalized journal refs from free text, preserving first-seen order."""
    refs: list[str] = []
    seen: set[str] = set()
    for match in _JOURNAL_REF_RE.finditer(text):
        normalized = normalize_journal_ref(match.group(0))
        if normalized and normalized not in seen:
            seen.add(normalized)
            refs.append(normalized)
    return refs


def extract_tool_trace_journal_refs(messages: list[dict[str, Any]]) -> list[str]:
    """Extract journal refs from non-message ACP session updates.

    ``agent_message_chunk`` contains the final model answer, so including it
    would make a read-trace check tautological.  Tool/read/runtime updates are
    not standardized across ACP runtimes yet; this helper therefore scans any
    non-message update payload generically.
    """
    refs: list[str] = []
    seen: set[str] = set()
    for msg in messages:
        try:
            update = msg.get("params", {}).get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                continue
            payload = json.dumps(update, ensure_ascii=False)
        except (AttributeError, TypeError, ValueError):
            continue
        for ref in extract_journal_refs_from_text(payload):
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _iter_raw_refs(envelope: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    top_refs = envelope.get("evidence_refs")
    if isinstance(top_refs, list):
        refs.extend(ref for ref in top_refs if isinstance(ref, str))

    insights = envelope.get("insights")
    if isinstance(insights, list):
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            insight_refs = insight.get("evidence_refs")
            if isinstance(insight_refs, list):
                refs.extend(ref for ref in insight_refs if isinstance(ref, str))
    return refs


def _canonicalize_ref(ref: str, short_id_mapping: dict[str, str]) -> str | None:
    mapped = short_id_mapping.get(ref, ref)
    return normalize_journal_ref(mapped)


def _canonical_refs(
    envelope: dict[str, Any],
    short_id_mapping: dict[str, str],
) -> tuple[list[str], str | None]:
    refs: list[str] = []
    seen: set[str] = set()
    for raw_ref in _iter_raw_refs(envelope):
        canonical = _canonicalize_ref(raw_ref, short_id_mapping)
        if canonical is None:
            return [], f"Evidence ref is not a journal id: {raw_ref}"
        if canonical not in seen:
            seen.add(canonical)
            refs.append(canonical)
    return refs, None


def _claim_segments(answer: str) -> list[str]:
    lines: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if stripped:
            lines.extend(part.strip() for part in re.split(r"(?<=[。！？.!?])\s*", stripped))
    return [line for line in lines if _is_substantive_claim(line)]


def _is_substantive_claim(segment: str) -> bool:
    stripped = segment.strip()
    if stripped.startswith("#") or stripped.endswith((":", "：")):
        return False
    compact = re.sub(r"\s+", "", segment)
    if len(compact) < 6:
        return False
    lowered = segment.lower()
    if lowered.startswith(("gap:", "note:", "insufficient evidence")):
        return False
    return True


def _segment_has_ref_marker(
    segment: str,
    canonical_refs: list[str],
    short_id_mapping: dict[str, str],
) -> bool:
    segment_norm = segment.replace("\\", "/")
    for ref in canonical_refs:
        gui_ref = ref[len("Journals/") : -3] if ref.startswith("Journals/") else ref
        if ref in segment_norm or gui_ref in segment_norm:
            return True
    for short_ref in short_id_mapping:
        pattern = _SHORT_REF_RE_TEMPLATE.format(ref=re.escape(short_ref))
        if re.search(pattern, segment):
            return True
    return False


def _map_refs_in_place(envelope: dict[str, Any], short_id_mapping: dict[str, str]) -> None:
    top_refs = envelope.get("evidence_refs")
    if isinstance(top_refs, list):
        envelope["evidence_refs"] = [
            _canonicalize_ref(ref, short_id_mapping) or ref
            for ref in top_refs
            if isinstance(ref, str)
        ]

    insights = envelope.get("insights")
    if isinstance(insights, list):
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            refs = insight.get("evidence_refs")
            if isinstance(refs, list):
                insight["evidence_refs"] = [
                    _canonicalize_ref(ref, short_id_mapping) or ref
                    for ref in refs
                    if isinstance(ref, str)
                ]


def _is_structured_magazine_insight(insight: dict[str, Any]) -> bool:
    return isinstance(insight.get("quote"), str) or isinstance(insight.get("interpretation"), str)


def _has_structured_magazine_insights(envelope: dict[str, Any]) -> bool:
    insights = envelope.get("insights")
    if not isinstance(insights, list):
        return False
    return any(isinstance(ins, dict) and _is_structured_magazine_insight(ins) for ins in insights)


def _validate_insight_refs(
    envelope: dict[str, Any],
    short_id_mapping: dict[str, str],
) -> str | None:
    insights = envelope.get("insights")
    if not isinstance(insights, list):
        return "insights must be a list"
    if envelope.get("status") == "GROUNDED" and not insights:
        return "GROUNDED status requires at least one cited insight"
    for idx, insight in enumerate(insights):
        if not isinstance(insight, dict):
            return f"insights[{idx}] must be an object"
        refs = insight.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            return f"insights[{idx}].evidence_refs must contain at least one journal id"
        for raw_ref in refs:
            if not isinstance(raw_ref, str):
                return f"insights[{idx}].evidence_refs must contain only strings"
            if _canonicalize_ref(raw_ref, short_id_mapping) is None:
                return f"Evidence ref is not a journal id: {raw_ref}"
    return None


def _insight_support_text(envelope: dict[str, Any], canonical_refs: list[str]) -> str:
    parts: list[str] = []
    insights = envelope.get("insights")
    if isinstance(insights, list):
        for insight in insights:
            if not isinstance(insight, dict):
                continue
            for key in ("quote", "interpretation", "text", "theme", "date"):
                val = insight.get(key)
                if isinstance(val, str):
                    parts.append(val)
    for ref in canonical_refs:
        match = re.search(r"Journals/(\d{4})/(\d{2})/life-index_(\d{4}-\d{2}-\d{2})_", ref)
        if match:
            _, _, iso_date = match.groups()
            _year, month, day = iso_date.split("-")
            parts.extend([iso_date, f"{int(month)}月{int(day)}日", f"{month}月{day}日"])
            parts.append(ref)
    return "\n".join(parts)


def _summary_fact_markers(summary: str) -> list[str]:
    markers: list[str] = []
    seen: set[str] = set()
    for pattern in (_ISO_DATE_RE, _CHINESE_DATE_RE, _NUMBER_FACT_RE, _AGGREGATE_FACT_RE):
        for match in pattern.finditer(summary):
            token = match.group(0).strip()
            if token and token not in seen:
                seen.add(token)
                markers.append(token)
    return markers


def _validate_summary_covered_by_insights(
    answer: Any,
    envelope: dict[str, Any],
    canonical_refs: list[str],
) -> str | None:
    if not isinstance(answer, str) or not answer.strip():
        return None
    support_text = _insight_support_text(envelope, canonical_refs)
    support_compact = re.sub(r"\s+", "", support_text)
    for marker in _summary_fact_markers(answer):
        marker_compact = re.sub(r"\s+", "", marker)
        if marker_compact and marker_compact not in support_compact:
            return (
                "Summary fact not covered by cited insights; answer claim lacks an "
                f"evidence id: {marker}"
            )
    return None


def validate_citation_gate(
    envelope: dict[str, Any],
    *,
    short_id_mapping: dict[str, str] | None = None,
    tool_trace_refs: list[str] | None = None,
    require_answer_citations: bool = True,
    apply_mapping: bool = True,
) -> CitationGateResult:
    """Validate and optionally canonicalize citations in an ACP answer envelope."""
    mapping = short_id_mapping or {}
    status = envelope.get("status")
    answer = envelope.get("answer")
    if status == "UNGROUNDED":
        return CitationGateResult(ok=True, error=None, evidence_refs=[])

    if status not in ("GROUNDED", "PARTIAL"):
        return CitationGateResult(ok=False, error=f"Unsupported status: {status}", evidence_refs=[])

    canonical_refs, ref_error = _canonical_refs(envelope, mapping)
    if ref_error:
        return CitationGateResult(ok=False, error=ref_error, evidence_refs=[])

    if not canonical_refs:
        return CitationGateResult(
            ok=False,
            error=f"{status} status requires at least one journal evidence ref",
            evidence_refs=[],
        )

    for ref in canonical_refs:
        if not journal_ref_exists(ref):
            return CitationGateResult(
                ok=False,
                error=f"Cited journal evidence does not exist: {ref}",
                evidence_refs=canonical_refs,
            )

    insight_error = _validate_insight_refs(envelope, mapping)
    if insight_error:
        return CitationGateResult(
            ok=False,
            error=insight_error,
            evidence_refs=canonical_refs,
        )

    structured_magazine = _has_structured_magazine_insights(envelope)
    if structured_magazine:
        summary_error = _validate_summary_covered_by_insights(answer, envelope, canonical_refs)
        if summary_error:
            return CitationGateResult(
                ok=False,
                error=summary_error,
                evidence_refs=canonical_refs,
            )
    elif require_answer_citations and isinstance(answer, str) and answer.strip():
        for segment in _claim_segments(answer):
            if not _segment_has_ref_marker(segment, canonical_refs, mapping):
                return CitationGateResult(
                    ok=False,
                    error=f"Answer claim lacks an evidence id: {segment[:120]}",
                    evidence_refs=canonical_refs,
                )

    trace_checked = bool(tool_trace_refs)
    trace_missing: tuple[str, ...] = ()
    if tool_trace_refs:
        trace_set = set(tool_trace_refs)
        trace_missing = tuple(ref for ref in canonical_refs if ref not in trace_set)
        if trace_missing:
            return CitationGateResult(
                ok=False,
                error="Cited journal evidence was not observed in ACP read/tool trace: "
                + ", ".join(trace_missing),
                evidence_refs=canonical_refs,
                trace_checked=True,
                trace_missing=trace_missing,
            )

    if apply_mapping:
        _map_refs_in_place(envelope, mapping)
        envelope["evidence_refs"] = canonical_refs

    return CitationGateResult(
        ok=True,
        error=None,
        evidence_refs=canonical_refs,
        trace_checked=trace_checked,
        trace_missing=trace_missing,
    )
