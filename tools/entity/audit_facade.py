"""Read-only Entity Graph audit facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.entity.audit import audit_entity_graph
from tools.entity.check import run_check
from tools.entity.stats import compute_stats


def build_audit_facade(*, graph_path: Path, journals_dir: Path | None = None) -> dict[str, Any]:
    """Combine entity check/audit/stats into one user-facing health payload."""
    check_result = run_check(graph_path=graph_path)
    check_data = check_result.get("data", {}) or {}

    component_errors: dict[str, str] = {}
    try:
        audit_report = audit_entity_graph(graph_path, journals_dir=journals_dir)
    except (OSError, ValueError) as exc:
        audit_report = _empty_audit_report()
        component_errors["audit"] = str(exc)

    try:
        stats_result = compute_stats(graph_path=graph_path)
        stats_data = stats_result.get("data", {}) or {}
    except (OSError, ValueError) as exc:
        stats_data = _empty_stats(check_data)
        component_errors["stats"] = str(exc)

    audit_summary = audit_report.get("summary", {}) or {}

    structural_issue_count = len(check_data.get("issues", []) or [])
    pending_count = _count_pending_review_items(audit_report.get("issues", []) or [])
    quality_issue_count = len(audit_report.get("issues", []) or [])
    duplicate_count = sum(
        1
        for issue in audit_report.get("issues", []) or []
        if issue.get("type") == "possible_duplicate"
    )

    if structural_issue_count or duplicate_count:
        traffic_light = "red"
        next_reason = "structural or duplicate entity issues need review"
    elif pending_count or quality_issue_count:
        traffic_light = "yellow"
        next_reason = "pending entity review items"
    else:
        traffic_light = "green"
        next_reason = "no pending entity review items"

    return {
        "success": True,
        "data": {
            "workflow": "audit",
            "traffic_light": traffic_light,
            "pending_count": pending_count,
            "structural_issue_count": structural_issue_count,
            "quality_issue_count": quality_issue_count,
            "duplicate_count": duplicate_count,
            "next_step": {
                "command": "life-index entity --review",
                "reason": next_reason,
            },
            "components": {
                "check": check_data,
                "audit": {
                    "audit_date": audit_report.get("audit_date"),
                    "summary": audit_summary,
                    "issues": audit_report.get("issues", []),
                    "facts": audit_report.get("facts", {}),
                },
                "stats": stats_data,
            },
            "component_errors": component_errors,
        },
        "error": None,
    }


def _count_pending_review_items(issues: list[dict[str, Any]]) -> int:
    return sum(
        1 for issue in issues if issue.get("type") in {"candidate_entity", "candidate_relationship"}
    )


def _empty_audit_report() -> dict[str, Any]:
    return {
        "audit_date": None,
        "total_entities": 0,
        "issues": [],
        "summary": {"high": 0, "medium": 0, "low": 0},
        "facts": {},
    }


def _empty_stats(check_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_entities": check_data.get("total_entities", 0),
        "by_type": {},
        "total_aliases": 0,
        "total_relationships": 0,
        "top_referenced": [],
        "top_cooccurrence": [],
    }
