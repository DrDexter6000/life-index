#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime
from typing import Any


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _date_distance_days(left: str, right: str) -> int | None:
    try:
        left_dt = datetime.fromisoformat(left[:10])
        right_dt = datetime.fromisoformat(right[:10])
    except (TypeError, ValueError):
        return None
    return abs((left_dt - right_dt).days)


def suggest_related_entries(
    current_entry: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    max_candidates: int = 5,
) -> list[dict[str, Any]]:
    current_rel_path = str(current_entry.get("rel_path") or current_entry.get("path") or "").strip()
    existing_relations = set(_to_list(current_entry.get("related_entries")))
    current_people = set(_to_list(current_entry.get("people")))
    current_topics = set(_to_list(current_entry.get("topic")))
    current_tags = set(_to_list(current_entry.get("tags")))
    current_project = str(current_entry.get("project") or "").strip()
    current_date = str(current_entry.get("date") or "").strip()

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for entry in entries:
        rel_path = str(entry.get("rel_path") or entry.get("path") or "").strip()
        if not rel_path:
            continue
        if rel_path == current_rel_path:
            continue
        if rel_path in existing_relations:
            continue

        score = 0
        reasons: list[str] = []
        structured_reasons: list[dict[str, Any]] = []
        score_breakdown: list[dict[str, Any]] = []

        people_overlap = current_people & set(_to_list(entry.get("people")))
        if people_overlap:
            score += 40
            reasons.append("same people")
            structured_reasons.append(
                {
                    "type": "same_people",
                    "label": "same people",
                    "value": sorted(people_overlap),
                }
            )
            score_breakdown.append({"type": "same_people", "score": 40})

        entry_project = str(entry.get("project") or "").strip()
        if current_project and entry_project and current_project == entry_project:
            score += 30
            reasons.append("same project")
            structured_reasons.append(
                {
                    "type": "same_project",
                    "label": "same project",
                    "value": entry_project,
                }
            )
            score_breakdown.append({"type": "same_project", "score": 30})

        topic_overlap = current_topics & set(_to_list(entry.get("topic")))
        if topic_overlap:
            score += 20
            reasons.append("same topic")
            structured_reasons.append(
                {
                    "type": "same_topic",
                    "label": "same topic",
                    "value": sorted(topic_overlap),
                }
            )
            score_breakdown.append({"type": "same_topic", "score": 20})

        tag_overlap = current_tags & set(_to_list(entry.get("tags")))
        if len(tag_overlap) >= 2:
            score += 15
            reasons.append("tag overlap")
            structured_reasons.append(
                {
                    "type": "tag_overlap",
                    "label": "tag overlap",
                    "value": sorted(tag_overlap),
                }
            )
            score_breakdown.append({"type": "tag_overlap", "score": 15})

        distance_days = _date_distance_days(current_date, str(entry.get("date") or ""))
        if distance_days is not None and distance_days <= 30:
            time_score = max(1, 10 - min(distance_days, 9))
            score += time_score
            reasons.append("close in time")
            structured_reasons.append(
                {
                    "type": "close_in_time",
                    "label": "close in time",
                    "value": distance_days,
                }
            )
            score_breakdown.append({"type": "close_in_time", "score": time_score})

        if score <= 0:
            continue

        scored.append(
            (
                score,
                -(distance_days if distance_days is not None else 9999),
                {
                    "rel_path": rel_path,
                    "title": str(entry.get("title") or "无标题"),
                    "date": str(entry.get("date") or ""),
                    "abstract": str(entry.get("abstract") or ""),
                    "score": score,
                    "match_reason": ", ".join(reasons),
                    "reasons": structured_reasons,
                    "score_breakdown": score_breakdown,
                },
            )
        )

    scored.sort(key=lambda item: (item[0], item[1], item[2]["rel_path"]), reverse=True)

    candidates = [item[2] for item in scored[:max_candidates]]
    for index, candidate in enumerate(candidates, start=1):
        candidate["candidate_id"] = index

    return candidates
