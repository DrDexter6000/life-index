#!/usr/bin/env python3
"""Export adapters for Qrels and Run to standard IR formats (R2-B3d).

Converts Qrels ({query_id: {doc_id: int}}) and Run ({query_id: {doc_id: float}})
to plain dicts and TREC-format strings. No ranx dependency.

This module is independent of run_eval.py. It does not change eval behavior.
"""

from __future__ import annotations

from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Plain dict adapters
# ---------------------------------------------------------------------------


def qrels_to_plain_dict(
    qrels: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    """Deep-copy qrels to plain dict. Ensures output is mutable and serializable."""
    return {qid: dict(inner) for qid, inner in qrels.items()}


def run_to_plain_dict(
    run: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    """Deep-copy run to plain dict. Ensures output is mutable and serializable."""
    return {qid: dict(inner) for qid, inner in run.items()}


# ---------------------------------------------------------------------------
# TREC format
# ---------------------------------------------------------------------------


def qrels_to_trec(qrels: Mapping[str, Mapping[str, int]]) -> str:
    """Export qrels to TREC qrels format.

    Line format: ``<query_id> 0 <doc_id> <relevance>``
    Sorted by query_id asc, doc_id asc.
    Empty input returns ``""``.
    """
    if not qrels:
        return ""

    lines: list[str] = []
    for qid in sorted(qrels):
        inner = qrels[qid]
        for doc_id in sorted(inner):
            lines.append(f"{qid} 0 {doc_id} {inner[doc_id]}")
    return "\n".join(lines) + "\n"


def run_to_trec(
    run: Mapping[str, Mapping[str, float]],
    run_name: str = "life-index",
) -> str:
    """Export run to TREC run format.

    Line format: ``<query_id> Q0 <doc_id> <rank> <score> <run_name>``
    Sorted by query_id asc, then score desc, then doc_id asc.
    Rank starts at 1 per query.
    Empty input returns ``""``.
    """
    if not run:
        return ""

    lines: list[str] = []
    for qid in sorted(run):
        inner = run[qid]
        # Sort by score desc, then doc_id asc for ties
        ranked = sorted(inner.items(), key=lambda x: (-x[1], x[0]))
        for rank, (doc_id, score) in enumerate(ranked, start=1):
            lines.append(f"{qid} Q0 {doc_id} {rank} {score} {run_name}")
    return "\n".join(lines) + "\n"
