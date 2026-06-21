"""Maintenance repair-plan dry-run envelopes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .audit import run_audit

PLAN_SCHEMA_VERSION = "m33.maintenance_plan.v0"


def _issue_paths(issue: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for evidence in issue.get("evidence", []) or []:
        if isinstance(evidence, dict):
            value = evidence.get("path")
            if isinstance(value, str) and value:
                paths.append(value)
    return sorted(set(paths))


def _post_check_command(issue: dict[str, Any]) -> list[str]:
    domain = str(issue.get("domain", ""))
    return ["life-index", "maintenance", "audit", "--domain", domain, "--json"]


def _plan_steps(issue: dict[str, Any]) -> list[dict[str, Any]]:
    domain = issue.get("domain")
    issue_type = issue.get("type")
    if issue.get("repairable") is not True:
        return []
    if domain == "layout" and issue_type == "missing_generated_index":
        return [
            {
                "action": "regenerate_index_markdown",
                "command": ["life-index", "generate-index"],
                "write_class": "derived_artifact",
            }
        ]
    if domain == "search_index" and issue_type == "missing_rebuildable_index":
        return [
            {
                "action": "rebuild_search_index",
                "command": ["life-index", "index", "--rebuild"],
                "write_class": "derived_artifact",
            }
        ]
    if domain == "revisions" and issue_type == "loose_timestamped_journal_copy":
        return [
            {
                "action": "archive_loose_timestamped_journal_copy",
                "command": [
                    "life-index",
                    "maintenance",
                    "repair",
                    "--issue-id",
                    "<issue-id>",
                    "--apply",
                ],
                "write_class": "user_data_archive",
            }
        ]
    if domain == "revisions" and issue_type == "entity_graph_backup_copy":
        return [
            {
                "action": "archive_entity_graph_backup_copy",
                "command": [
                    "life-index",
                    "maintenance",
                    "repair",
                    "--issue-id",
                    "<issue-id>",
                    "--apply",
                ],
                "write_class": "user_data_archive",
            }
        ]
    return []


def build_plan(data_dir: str | Path | None, issue_id: str) -> tuple[dict[str, Any], int]:
    audit = run_audit(data_dir=data_dir)
    issue = next((item for item in audit["issues"] if item.get("issue_id") == issue_id), None)
    if issue is None:
        return (
            {
                "success": False,
                "schema_version": PLAN_SCHEMA_VERSION,
                "command": "maintenance plan",
                "issue_id": issue_id,
                "error": {
                    "code": "MAINTENANCE_ISSUE_NOT_FOUND",
                    "message": "Issue ID is not present in the current maintenance audit.",
                },
            },
            2,
        )

    repairable = bool(issue.get("repairable"))
    paths = _issue_paths(issue)
    plan_steps = _plan_steps(issue)
    payload: dict[str, Any] = {
        "success": True,
        "schema_version": PLAN_SCHEMA_VERSION,
        "command": "maintenance plan",
        "issue_id": issue_id,
        "domain": issue.get("domain"),
        "type": issue.get("type"),
        "risk": issue.get("risk", "medium"),
        "repairable": repairable and bool(plan_steps),
        "repair_class": issue.get("repair_class", "review"),
        "requires_user_ack": True,
        "touched_paths": paths,
        "preconditions": [
            "Issue ID must still be present in a fresh maintenance audit.",
            "Touched paths must remain inside LIFE_INDEX_DATA_DIR.",
            "Archive repairs require the canonical source file to still exist.",
        ],
        "post_check_command": _post_check_command(issue),
        "rollback_story": (
            "Archived files are moved under .trash/maintenance inside LIFE_INDEX_DATA_DIR; "
            "restore by moving the archived copy back to its original relative path."
            if issue.get("domain") == "revisions"
            and issue.get("type") in {"loose_timestamped_journal_copy", "entity_graph_backup_copy"}
            and repairable
            and plan_steps
            else (
                "Derived artifacts can be regenerated from Markdown truth; user source files "
                "must remain unchanged."
                if repairable and plan_steps
                else (
                    "No automatic rollback is defined because this issue requires human or "
                    "L3 proposal review."
                )
            )
        ),
        "plan_steps": plan_steps,
        "non_repairable_reason": None,
        "error": None,
    }
    if not payload["repairable"]:
        payload["non_repairable_reason"] = (
            "This issue requires proposal or human review before durable changes."
        )
    return payload, 0


__all__ = ["PLAN_SCHEMA_VERSION", "build_plan"]
