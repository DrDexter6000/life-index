"""Maintenance cycle core — aggregates six checks and formats output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .checks import run_all_checks

SCHEMA_VERSION = "m16.maintenance.v0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary counts from check results."""
    pass_count = sum(1 for c in checks if c["status"] == "pass")
    fail_count = sum(1 for c in checks if c["status"] == "fail")
    needs_user_action_count = sum(1 for c in checks if c["status"] == "needs-user-action")
    return {
        "pass_count": pass_count,
        "fail_count": fail_count,
        "needs_user_action_count": needs_user_action_count,
        "overall_healthy": fail_count == 0,
    }


def run_maintenance(data_dir: str | None = None) -> dict[str, Any]:
    """Run all six maintenance checks and return structured result.

    This is a pure dry-run / report-only operation. Zero production writes.

    Returns:
        Dict with schema_version, checks, summary, timestamp.
    """
    checks = run_all_checks(data_dir=data_dir)
    summary = _compute_summary(checks)
    return {
        "success": True,
        "command": "maintenance",
        "schema_version": SCHEMA_VERSION,
        "checks": checks,
        "summary": summary,
        "timestamp": _now_iso(),
        "error": None,
    }


def format_text_report(result: dict[str, Any]) -> str:
    """Format the maintenance result as a human-readable text report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  Life Index - Maintenance Report")
    lines.append("=" * 60)
    lines.append(f"  Timestamp: {result.get('timestamp', 'N/A')}")
    lines.append(f"  Schema:    {result.get('schema_version', 'N/A')}")
    lines.append("")

    summary = result.get("summary", {})
    lines.append(f"  Pass:              {summary.get('pass_count', 0)}")
    lines.append(f"  Fail:              {summary.get('fail_count', 0)}")
    lines.append(f"  Needs User Action: {summary.get('needs_user_action_count', 0)}")
    lines.append("")
    lines.append("-" * 60)

    STATUS_ICONS = {"pass": "[PASS]", "fail": "[FAIL]", "needs-user-action": "[ACTN]"}

    for check in result.get("checks", []):
        icon = STATUS_ICONS.get(check["status"], "[???]")
        lines.append(f"  {icon} {check['category']}")
        lines.append(f"        Status: {check['status']}")
        details = check.get("details", {})
        # Show key detail fields
        for key, value in details.items():
            if key in ("error", "message"):
                lines.append(f"        {key}: {value}")
            elif key == "issues" and isinstance(value, list):
                lines.append(f"        issues ({len(value)}):")
                for issue in value[:5]:
                    lines.append(f"          - {issue}")
                if len(value) > 5:
                    lines.append(f"          ... and {len(value) - 5} more")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def to_json(result: dict[str, Any]) -> str:
    """Serialize result to JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2)


__all__ = ["run_maintenance", "format_text_report", "to_json"]
