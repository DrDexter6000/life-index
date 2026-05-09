#!/usr/bin/env python3
"""Evidence Pack runtime adapter — wraps builder for two consumption contexts.

Pure extraction/normalization. Does not call search, semantic, LLM, filesystem,
or production data. Does not modify input dicts.
"""

from __future__ import annotations

from typing import Any

from tools.evidence.builder import build_evidence_pack
from tools.evidence.types import EvidencePack

_REQUIRED_KEYS = frozenset({"query_params", "merged_results"})


def extract_evidence_from_search_result(result: dict[str, Any]) -> EvidencePack:
    """Extract EvidencePack from hierarchical_search() output dict.

    Validates required keys, then delegates to build_evidence_pack().
    """
    missing = _REQUIRED_KEYS - set(result.keys())
    if missing:
        raise ValueError(
            f"Evidence adapter requires {sorted(missing)}; got: {sorted(result.keys())}"
        )
    return build_evidence_pack(result)


def extract_evidence_from_orchestrator(
    raw_results: dict[str, Any],
    smart_result: dict[str, Any] | None = None,
) -> EvidencePack:
    """Extract EvidencePack from orchestrator's raw search results.

    Optionally overlays smart-search rewritten_query into pack.extra,
    separate from query_context.expanded_query (reserved for entity expansion).
    """
    missing = _REQUIRED_KEYS - set(raw_results.keys())
    if missing:
        raise ValueError(
            f"Evidence adapter requires {sorted(missing)}; got: {sorted(raw_results.keys())}"
        )

    pack = build_evidence_pack(raw_results)

    if smart_result is not None:
        rq = smart_result.get("rewritten_query")
        if rq and rq != pack.query_context.query:
            new_extra = {**pack.extra, "rewritten_query": rq}
            pack = EvidencePack(
                query_context=pack.query_context,
                items=pack.items,
                semantic_candidates=pack.semantic_candidates,
                total_available=pack.total_available,
                has_more=pack.has_more,
                no_confident_match=pack.no_confident_match,
                extra=new_extra,
            )

    return pack
