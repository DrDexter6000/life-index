"""Ranking reason: natural language explanation for search result ranking (D16).

Produces a human-readable string explaining why a result made it into the Top-k.
Output is for `--explain` mode only — not included in normal search output.
"""

from __future__ import annotations

_MAX_LENGTH: int = 120


def compose(result: dict) -> str:
    """Compose a natural-language ranking reason for a single result.

    Priority order: title_promoted → fts_hit → semantic_hit.
    Returns a string of at most 120 characters.
    """
    segments: list[str] = []

    title_promoted = result.get("title_promoted", False)
    fts_score = float(result.get("fts_score", 0))
    semantic_score = float(result.get("semantic_score", 0))

    if title_promoted:
        segments.append("标题命中查询词（+1.5x 置顶）")

    if fts_score > 0:
        segments.append(f"关键词 FTS={fts_score:.2f}")

    if semantic_score > 0:
        sim = semantic_score / 100.0
        segments.append(f"语义相似度 {sim:.2f}")

    if not segments:
        segments.append("元数据匹配（弱信号）")

    reason = "；".join(segments)

    if len(reason) > _MAX_LENGTH:
        reason = reason[: _MAX_LENGTH - 1] + "…"
    return reason
