"""Six maintenance checks — each returns a status and structured details.

All checks that invoke existing CLI commands do so via subprocess.run().
The orphan_related_entries check performs read-only file inspection.
Zero production data writes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "m16.maintenance.v0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_result(
    category: str,
    status: str,
    details: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a structured check result."""
    return {
        "category": category,
        "status": status,
        "details": details,
        "timestamp": timestamp or _now_iso(),
    }


def _run_subprocess(
    args: list[str],
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> tuple[int, str, str, str | None]:
    """Run a subprocess and return (returncode, stdout, stderr, timeout_error).

    Returns timeout_error=None on success, or timeout error string on timeout.
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env or os.environ.copy(),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip(), None
    except subprocess.TimeoutExpired as e:
        return -1, "", str(e), f"subprocess timed out after {timeout}s"


def _resolve_data_dir(data_dir: str | None = None) -> str:
    """Resolve the data directory, preferring env var or explicit path."""
    if data_dir:
        return data_dir
    return os.environ.get("LIFE_INDEX_DATA_DIR", str(Path.home() / "Documents" / "Life-Index"))


# ── Check 1: Index freshness ───────────────────────────────────────


def check_index_freshness(data_dir: str | None = None) -> dict[str, Any]:
    """Check FTS/vector index health via subprocess to build_index --check.

    Invokes: python -m tools index --check --json
    """
    env = os.environ.copy()
    if data_dir:
        env["LIFE_INDEX_DATA_DIR"] = data_dir

    rc, stdout, stderr, timeout_err = _run_subprocess(
        [sys.executable, "-m", "tools", "index", "--check", "--json"],
        env=env,
    )

    if timeout_err:
        return _check_result(
            "index_freshness",
            "fail",
            {"error": timeout_err},
        )

    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return _check_result(
            "index_freshness",
            "fail",
            {
                "error": "index check output not valid JSON",
                "stderr": stderr,
                "raw_stdout": stdout[:500],
            },
        )

    healthy = result.get("healthy", False)
    issues = result.get("issues", [])
    fts_count = result.get("fts_count", 0)
    vector_count = result.get("vector_count", 0)
    file_count = result.get("file_count", 0)

    if healthy and not issues:
        return _check_result(
            "index_freshness",
            "pass",
            {
                "fts_count": fts_count,
                "vector_count": vector_count,
                "file_count": file_count,
                "healthy": True,
            },
        )
    elif issues:
        return _check_result(
            "index_freshness",
            "fail",
            {
                "fts_count": fts_count,
                "vector_count": vector_count,
                "file_count": file_count,
                "healthy": False,
                "issues": issues,
            },
        )
    else:
        return _check_result(
            "index_freshness",
            "needs-user-action",
            {
                "fts_count": fts_count,
                "vector_count": vector_count,
                "file_count": file_count,
                "healthy": False,
                "message": "Index not built — run 'life-index index'",
            },
        )


# ── Check 2: Entity audit ──────────────────────────────────────────


def check_entity_audit(data_dir: str | None = None) -> dict[str, Any]:
    """Run entity graph quality audit via subprocess.

    Invokes: python -m tools entity --audit
    """
    env = os.environ.copy()
    if data_dir:
        env["LIFE_INDEX_DATA_DIR"] = data_dir

    rc, stdout, stderr, timeout_err = _run_subprocess(
        [sys.executable, "-m", "tools", "entity", "--audit"],
        env=env,
    )

    if timeout_err:
        return _check_result(
            "entity_audit",
            "fail",
            {"error": timeout_err},
        )

    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return _check_result(
            "entity_audit",
            "fail",
            {
                "error": "entity audit output not valid JSON",
                "stderr": stderr,
                "raw_stdout": stdout[:500],
            },
        )

    if not result.get("success"):
        return _check_result(
            "entity_audit",
            "fail",
            {"error": result.get("error", "entity audit failed"), "result": result},
        )

    data = result.get("data", {})
    summary = data.get("summary", {})
    total_issues = sum(summary.get(k, 0) for k in ("high", "medium", "low"))

    if total_issues == 0:
        return _check_result(
            "entity_audit",
            "pass",
            {
                "total_entities": data.get("total_entities", 0),
                "issues_found": 0,
                "summary": summary,
                "audit_date": data.get("audit_date"),
            },
        )
    else:
        high_count = summary.get("high", 0)
        if high_count > 0:
            return _check_result(
                "entity_audit",
                "fail",
                {
                    "total_entities": data.get("total_entities", 0),
                    "issues_found": total_issues,
                    "high_severity": high_count,
                    "summary": summary,
                    "message": f"{total_issues} issues found ({high_count} high severity)",
                },
            )
        else:
            return _check_result(
                "entity_audit",
                "needs-user-action",
                {
                    "total_entities": data.get("total_entities", 0),
                    "issues_found": total_issues,
                    "summary": summary,
                    "message": f"{total_issues} low/medium issues — review recommended",
                },
            )


# ── Check 3: Orphan related_entries ─────────────────────────────────


def check_orphan_related_entries(data_dir: str | None = None) -> dict[str, Any]:
    """Scan journal frontmatter for related_entries not matching any entity.

    This is a read-only inspection. It does NOT import tools.entity internals.
    It reads entity_graph.yaml and journal files directly.
    """
    ddir = Path(_resolve_data_dir(data_dir))
    graph_path = ddir / "entity_graph.yaml"
    journals_dir = ddir / "Journals"

    # Load entity names from entity_graph.yaml
    known_entities: set[str] = set()
    if graph_path.exists():
        try:
            import yaml

            with graph_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entity in data.get("entities", []):
                primary = entity.get("primary_name", "")
                if primary:
                    known_entities.add(primary.lower())
                for alias in entity.get("aliases", []):
                    if alias:
                        known_entities.add(alias.lower())
        except Exception as e:
            return _check_result(
                "orphan_related_entries",
                "fail",
                {"error": f"Failed to parse entity_graph.yaml: {e}"},
            )

    if not known_entities:
        return _check_result(
            "orphan_related_entries",
            "needs-user-action",
            {
                "message": "No entities in entity_graph.yaml — seed the graph first",
                "entity_count": 0,
            },
        )

    # Scan journal files for related_entries
    orphan_refs: list[dict[str, Any]] = []
    journal_count = 0

    if journals_dir.exists():
        for md_file in journals_dir.rglob("*.md"):
            # Skip index and by-topic files
            fname = md_file.name.lower()
            if fname.startswith("index_") or "索引_" in fname:
                continue
            if any(fname.startswith(p) for p in ("主题_", "项目_", "标签_")):
                continue

            journal_count += 1
            try:
                import yaml

                with md_file.open("r", encoding="utf-8") as f:
                    content = f.read()

                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                        related = frontmatter.get("related_entries", [])
                        if isinstance(related, list):
                            for ref in related:
                                ref_str = str(ref).strip()
                                if ref_str and ref_str.lower() not in known_entities:
                                    orphan_refs.append(
                                        {
                                            "entry": ref_str,
                                            "source_file": md_file.relative_to(
                                                journals_dir
                                            ).as_posix(),
                                        }
                                    )
            except Exception:
                continue  # Skip files that can't be parsed

    if not orphan_refs:
        return _check_result(
            "orphan_related_entries",
            "pass",
            {
                "journals_scanned": journal_count,
                "orphans_found": 0,
                "known_entities": len(known_entities),
            },
        )

    return _check_result(
        "orphan_related_entries",
        "needs-user-action",
        {
            "journals_scanned": journal_count,
            "orphans_found": len(orphan_refs),
            "known_entities": len(known_entities),
            "orphans": orphan_refs[:50],  # Limit to 50 to avoid huge output
            "message": f"{len(orphan_refs)} related_entries reference unknown entities",
        },
    )


# ── Check 4: Search eval smoke ──────────────────────────────────────


def check_search_eval_smoke(data_dir: str | None = None) -> dict[str, Any]:
    """Run a minimal ablation eval smoke test via subprocess.

    Invokes: python -m tools entity-graph-eval --queries <fixture>
    Uses the existing ablation_queries.json fixture from Phase A.
    Gracefully degrades to needs-user-action if data directory is empty.
    """
    env = os.environ.copy()
    if data_dir:
        env["LIFE_INDEX_DATA_DIR"] = data_dir

    # Use the Phase A fixture path relative to repo root
    repo_root = Path(__file__).resolve().parents[2]
    fixture = repo_root / "tests" / "fixtures" / "eval" / "ablation_queries.json"

    if not fixture.exists():
        return _check_result(
            "search_eval_smoke",
            "needs-user-action",
            {"message": f"Ablation fixture not found: {fixture}"},
        )

    # Only run first 3 queries for smoke test
    try:
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        smoke_queries = raw[:3] if isinstance(raw, list) else []
    except Exception:
        smoke_queries = []

    if not smoke_queries:
        return _check_result(
            "search_eval_smoke",
            "needs-user-action",
            {"message": "No queries in ablation fixture"},
        )

    # Write a temporary fixture with just 3 queries
    import tempfile

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(smoke_queries, tmp)
        tmp_path = tmp.name
        tmp.close()

        rc, stdout, stderr, timeout_err = _run_subprocess(
            [sys.executable, "-m", "tools", "entity-graph-eval", "--queries", tmp_path],
            env=env,
            timeout=30,  # Short timeout for smoke test
        )

        if timeout_err:
            return _check_result(
                "search_eval_smoke",
                "needs-user-action",
                {"message": f"Eval smoke timed out: {timeout_err}"},
            )

        try:
            result = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            return _check_result(
                "search_eval_smoke",
                "fail",
                {
                    "error": "eval output not valid JSON",
                    "stderr": stderr,
                    "raw_stdout": stdout[:500],
                },
            )

        if result.get("success"):
            combinations = result.get("combinations", [])
            combination_count = len(combinations)
            return _check_result(
                "search_eval_smoke",
                "pass",
                {
                    "query_count": len(smoke_queries),
                    "combinations_run": combination_count,
                    "message": (
                        f"Smoke eval passed: {combination_count} pipeline "
                        f"variants on {len(smoke_queries)} queries"
                    ),
                },
            )
        else:
            return _check_result(
                "search_eval_smoke",
                "fail",
                {"error": result.get("error", "eval smoke failed"), "result": result},
            )
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


# ── Check 5: Backup verification ────────────────────────────────────


def check_backup_verification(data_dir: str | None = None) -> dict[str, Any]:
    """Verify backup accessibility by listing backups.

    Because there is no dedicated --verify command, we use --list
    to confirm the backup infrastructure is reachable. If no --dest
    is configured, reports needs-user-action.
    """
    env = os.environ.copy()
    if data_dir:
        env["LIFE_INDEX_DATA_DIR"] = data_dir

    # Check for a configured backup destination
    backup_dest = os.environ.get("LIFE_INDEX_BACKUP_DEST")

    if not backup_dest:
        # Try default backup location
        default_dest = Path.home() / "Backups" / "Life-Index"
        if default_dest.exists():
            backup_dest = str(default_dest)
        else:
            return _check_result(
                "backup_verification",
                "needs-user-action",
                {
                    "message": "No backup destination configured. "
                    "Set LIFE_INDEX_BACKUP_DEST env var or run 'life-index backup --dest <path>'.",
                    "suggested_action": "Configure backup destination and re-run maintenance.",
                },
            )

    rc, stdout, stderr, timeout_err = _run_subprocess(
        [
            sys.executable,
            "-m",
            "tools",
            "backup",
            "--list",
            "--dest",
            backup_dest,
        ],
        env=env,
    )

    if timeout_err:
        return _check_result(
            "backup_verification",
            "fail",
            {"error": timeout_err, "backup_dest": backup_dest},
        )

    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return _check_result(
            "backup_verification",
            "fail",
            {
                "error": "backup list output not valid JSON",
                "stderr": stderr,
                "raw_stdout": stdout[:500],
            },
        )

    if result.get("success"):
        backups = result.get("backups", [])
        return _check_result(
            "backup_verification",
            "pass",
            {
                "backup_dest": backup_dest,
                "backup_count": len(backups),
                "message": f"{len(backups)} backup(s) found",
            },
        )
    else:
        return _check_result(
            "backup_verification",
            "fail",
            {"error": result.get("error", "backup list failed"), "backup_dest": backup_dest},
        )


# ── Check 6: Candidate edges count ──────────────────────────────────


def check_candidate_edges_count(data_dir: str | None = None) -> dict[str, Any]:
    """Count candidate edges via subprocess to entity --candidate-edges.

    Invokes: python -m tools entity --candidate-edges
    """
    env = os.environ.copy()
    if data_dir:
        env["LIFE_INDEX_DATA_DIR"] = data_dir

    rc, stdout, stderr, timeout_err = _run_subprocess(
        [sys.executable, "-m", "tools", "entity", "--candidate-edges"],
        env=env,
    )

    if timeout_err:
        return _check_result(
            "candidate_edges",
            "fail",
            {"error": timeout_err},
        )

    try:
        result = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return _check_result(
            "candidate_edges",
            "fail",
            {
                "error": "candidate-edges output not valid JSON",
                "stderr": stderr,
                "raw_stdout": stdout[:500],
            },
        )

    if not result.get("success"):
        return _check_result(
            "candidate_edges",
            "fail",
            {"error": result.get("error", "candidate edges check failed")},
        )

    candidates = result.get("candidates", [])
    total = result.get("total", len(candidates))

    if total == 0:
        return _check_result(
            "candidate_edges",
            "pass",
            {
                "candidate_count": 0,
                "message": "No candidate edges found — entity graph is current",
            },
        )

    # Count high-confidence candidates
    high_conf = sum(1 for c in candidates if c.get("confidence", 0) >= 0.8)
    medium_conf = sum(1 for c in candidates if 0.4 <= c.get("confidence", 0) < 0.8)
    low_conf = sum(1 for c in candidates if c.get("confidence", 0) < 0.4)

    return _check_result(
        "candidate_edges",
        "needs-user-action",
        {
            "candidate_count": total,
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf,
            "message": f"{total} candidate edges found — review recommended",
        },
    )


# ── All checks ──────────────────────────────────────────────────────


def run_all_checks(data_dir: str | None = None) -> list[dict[str, Any]]:
    """Run all six maintenance checks and return results."""
    return [
        check_index_freshness(data_dir=data_dir),
        check_entity_audit(data_dir=data_dir),
        check_orphan_related_entries(data_dir=data_dir),
        check_search_eval_smoke(data_dir=data_dir),
        check_backup_verification(data_dir=data_dir),
        check_candidate_edges_count(data_dir=data_dir),
    ]


__all__ = [
    "run_all_checks",
    "check_index_freshness",
    "check_entity_audit",
    "check_orphan_related_entries",
    "check_search_eval_smoke",
    "check_backup_verification",
    "check_candidate_edges_count",
]
