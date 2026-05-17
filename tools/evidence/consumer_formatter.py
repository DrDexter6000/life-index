#!/usr/bin/env python3
"""Deterministic evidence consumer formatter.

Pure formatter that renders EvidencePack data into a human-readable
Markdown string.  No LLM, no network, no filesystem reads/writes,
no search calls.
"""

from __future__ import annotations

from tools.evidence.types import (
    EvidenceDiagnostics,
    EvidenceItem,
    EvidencePack,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_entity_annotated(pack: EvidencePack) -> str:
    """Return a deterministic Markdown rendering of *pack*.

    The output includes:
    - A retrieval-quality banner with diagnostics
    - Per-item entity match badges (when present)
    - Pipeline composition label
    """
    lines: list[str] = []

    # Diagnostics banner
    _render_diagnostics(lines, pack.diagnostics)

    # Results section
    lines.append(f"## Evidence Results ({len(pack.items)} items)")
    lines.append("")

    if not pack.items:
        lines.append("_No matching documents found._")
        lines.append("")
    else:
        for idx, item in enumerate(pack.items, start=1):
            _render_item(lines, item, idx)

    # Semantic candidates (when present)
    if pack.semantic_candidates:
        lines.append(f"## Semantic Candidates ({len(pack.semantic_candidates)} items)")
        lines.append("")
        for idx, candidate in enumerate(pack.semantic_candidates, start=1):
            doc = candidate.document
            lines.append(f"{idx}. **{doc.title}** — {doc.date}")
            lines.append(f"   - Similarity: {candidate.similarity:.3f}")
            if candidate.snippet:
                lines.append(f"   - Snippet: {candidate.snippet}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _render_diagnostics(lines: list[str], diagnostics: EvidenceDiagnostics | None) -> None:
    """Append a retrieval-quality banner to *lines*."""
    if diagnostics is None:
        lines.append("## Retrieval Quality")
        lines.append("")
        lines.append("_Diagnostics unavailable._")
        lines.append("")
        return

    outcome = diagnostics.retrieval_outcome
    reason = diagnostics.outcome_reason

    # Map outcome to a human-readable label
    outcome_label = {
        "ok": "✓ Confident results",
        "weak_results": "⚠ Weak results",
        "no_confident_match": "⚠ No confident match",
        "zero_results": "✗ No results",
    }.get(outcome, outcome)

    lines.append("## Retrieval Quality")
    lines.append("")
    lines.append(f"**Outcome:** {outcome_label}")
    if reason:
        lines.append(f"**Reason:** {reason}")

    if diagnostics.pipeline_composition is not None:
        primary = diagnostics.pipeline_composition.primary_pipeline
        lines.append(f"**Pipeline:** {primary}")

    if diagnostics.notes:
        lines.append("")
        lines.append("**Notes:**")
        for note in diagnostics.notes:
            lines.append(f"- {note}")

    if diagnostics.suggestions:
        lines.append("")
        lines.append("**Suggestions:**")
        for suggestion in diagnostics.suggestions:
            lines.append(f"- {suggestion}")

    lines.append("")


def _render_item(lines: list[str], item: EvidenceItem, idx: int) -> None:
    """Append a single evidence item to *lines*."""
    doc = item.document
    lines.append(f"{idx}. **{doc.title}** — {doc.date}")

    if doc.path:
        lines.append(f"   - Path: `{doc.path}`")

    lines.append(f"   - Source: {item.scores.source} | Confidence: {item.scores.confidence}")

    if item.snippet:
        snippet = item.snippet.replace("\n", " ")
        lines.append(f"   - Snippet: {snippet}")

    # Entity match badges
    if item.entity_matches:
        lines.append("   - Entities:")
        for em in item.entity_matches:
            terms = ", ".join(em.matched_terms) if em.matched_terms else "—"
            sources = ", ".join(em.match_sources) if em.match_sources else "—"
            query_term = f" (query: {em.query_matched_term})" if em.query_matched_term else ""
            lines.append(
                f"     - `{em.entity_id}` ({em.entity_type}) — "
                f"matched: {terms}{query_term} | sources: {sources}"
            )

    lines.append("")
