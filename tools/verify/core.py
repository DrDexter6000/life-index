#!/usr/bin/env python3
"""Life Index - Verify Command Core Logic."""

from __future__ import annotations

import pickle
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from ..lib.config import ATTACHMENTS_DIR, BY_TOPIC_DIR, JOURNALS_DIR, USER_DATA_DIR
from ..lib.frontmatter import get_required_fields, parse_journal_file


@dataclass
class CheckResult:
    """Result of a single check."""

    name: str
    status: str  # ok, warning, error
    count: int = 0
    issues: List[str] = field(default_factory=list)


ATTACHMENT_REF_PATTERN = re.compile(
    r"!\[[^\]]*\]\((?P<path>[^)]+)\)|(?P<plain>attachments/[\w\-./]+)",
    re.IGNORECASE,
)
TOPIC_LINK_PATTERN = re.compile(r"\((?P<path>Journals/[^)]+\.md)\)")


def _collect_journal_files() -> List[Path]:
    if not JOURNALS_DIR.exists():
        return []
    return [
        f
        for f in JOURNALS_DIR.rglob("life-index_*.md")
        if not f.name.startswith("monthly_") and not f.name.startswith("yearly_")
    ]


def _rel_path(file_path: Path) -> str:
    return str(file_path.relative_to(USER_DATA_DIR)).replace("\\", "/")


def _load_fts_paths() -> set[str]:
    db_path = USER_DATA_DIR / ".index" / "journals_fts.db"
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM journals")
        return {str(row[0]).replace("\\", "/") for row in cursor.fetchall()}
    finally:
        conn.close()


def _load_vector_paths() -> set[str]:
    sqlite_db_path = USER_DATA_DIR / ".index" / "journals_vec.db"
    simple_index_path = USER_DATA_DIR / ".index" / "vectors_simple.pkl"

    if sqlite_db_path.exists():
        db_path = sqlite_db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT path FROM journal_vectors")
            return {str(row[0]).replace("\\", "/") for row in cursor.fetchall()}
        except sqlite3.Error:
            return set()
        finally:
            conn.close()

    if simple_index_path.exists():
        try:
            with simple_index_path.open("rb") as fh:
                payload = pickle.load(fh)
            if isinstance(payload, dict):
                return {str(path).replace("\\", "/") for path in payload.keys()}
        except Exception:
            return set()

    return set()


def _resolve_attachment_path(raw_path: str) -> Path:
    normalized = raw_path.strip().replace("\\", "/")
    if normalized.startswith("attachments/"):
        return USER_DATA_DIR / normalized
    return ATTACHMENTS_DIR / normalized


def _collect_topic_links() -> list[str]:
    if not BY_TOPIC_DIR.exists():
        return []

    links: list[str] = []
    for index_file in BY_TOPIC_DIR.glob("*.md"):
        content = index_file.read_text(encoding="utf-8")
        for match in TOPIC_LINK_PATTERN.finditer(content):
            links.append(match.group("path"))
    return links


def run_verify() -> Dict[str, Any]:
    """
    Run data integrity verification.

    Returns:
        {
            "success": bool,
            "total_journals": int,
            "checks": [CheckResult],
            "issues_count": int,
            "suggestion": str
        }
    """
    result: Dict[str, Any] = {
        "success": True,
        "total_journals": 0,
        "checks": [],
        "issues_count": 0,
        "suggestion": "",
    }

    journal_files = _collect_journal_files()
    journal_rel_paths = {_rel_path(file_path) for file_path in journal_files}

    result["total_journals"] = len(journal_files)

    # Check 1: Frontmatter validity
    frontmatter_check = CheckResult(name="frontmatter_valid", status="ok", count=0)
    required_fields = get_required_fields()

    for journal_file in journal_files:
        try:
            metadata = parse_journal_file(journal_file)
            if "_error" in metadata:
                frontmatter_check.status = "error"
                frontmatter_check.issues.append(
                    f"{journal_file.name}: {metadata['_error']}"
                )
            else:
                frontmatter_check.count += 1
                # Check required fields
                for req_field in required_fields:
                    if req_field not in metadata or not metadata[req_field]:
                        frontmatter_check.status = "warning"
                        frontmatter_check.issues.append(
                            f"{journal_file.name}: missing {req_field}"
                        )
        except Exception as e:
            frontmatter_check.status = "error"
            frontmatter_check.issues.append(f"{journal_file.name}: {e}")

    result["checks"].append(asdict(frontmatter_check))

    # Check 1b: Required fields completeness (kept separate for six-check contract)
    required_check = CheckResult(name="required_fields", status="ok", count=0)
    for journal_file in journal_files:
        try:
            metadata = parse_journal_file(journal_file)
            if "_error" in metadata:
                continue
            required_check.count += 1
            for req_field in required_fields:
                if req_field not in metadata or not metadata[req_field]:
                    required_check.status = "warning"
                    required_check.issues.append(
                        f"{journal_file.name}: missing {req_field}"
                    )
        except Exception:
            continue

    result["checks"].append(asdict(required_check))

    # Check 2: FTS index consistency
    fts_check = CheckResult(
        name="fts_consistency", status="ok", count=len(journal_files)
    )
    fts_paths = _load_fts_paths()
    if not fts_paths and journal_rel_paths:
        fts_check.status = "warning"
        fts_check.issues.append(
            f"missing: {len(journal_rel_paths)} journals not indexed"
        )
    else:
        missing_fts = sorted(journal_rel_paths - fts_paths)
        orphan_fts = sorted(fts_paths - journal_rel_paths)
        if missing_fts or orphan_fts:
            fts_check.status = "warning"
        for path in missing_fts:
            fts_check.issues.append(f"missing: {path}")
        for path in orphan_fts:
            fts_check.issues.append(f"orphan: {path}")

    result["checks"].append(asdict(fts_check))

    # Check 3: Vector index consistency
    vector_check = CheckResult(
        name="vector_consistency", status="ok", count=len(journal_files)
    )
    vector_paths = _load_vector_paths()
    missing_vectors = sorted(journal_rel_paths - vector_paths)
    orphan_vectors = sorted(vector_paths - journal_rel_paths)
    if missing_vectors or orphan_vectors:
        vector_check.status = "warning"
    for path in missing_vectors:
        vector_check.issues.append(f"missing: {path}")
    for path in orphan_vectors:
        vector_check.issues.append(f"orphan: {path}")

    result["checks"].append(asdict(vector_check))

    # Check 4: Attachment references in body
    attachment_check = CheckResult(name="attachment_refs", status="ok", count=0)

    for journal_file in journal_files:
        try:
            metadata = parse_journal_file(journal_file)
            body = str(metadata.get("_body", ""))
            for match in ATTACHMENT_REF_PATTERN.finditer(body):
                raw_path = match.group("path") or match.group("plain") or ""
                if not raw_path:
                    continue
                attachment_check.count += 1
                resolved = _resolve_attachment_path(raw_path)
                if not resolved.exists():
                    attachment_check.status = "warning"
                    attachment_check.issues.append(
                        f"{journal_file.name}: missing attachment {resolved.name}"
                    )
        except Exception:
            pass

    result["checks"].append(asdict(attachment_check))

    # Check 5: by-topic index consistency
    topic_check = CheckResult(name="topic_consistency", status="ok", count=0)
    topic_links = _collect_topic_links()
    topic_check.count = len(topic_links)
    for rel_path in topic_links:
        if rel_path not in journal_rel_paths:
            topic_check.status = "warning"
            topic_check.issues.append(f"orphan: {rel_path}")

    result["checks"].append(asdict(topic_check))

    # Count total issues
    total_issues = sum(len(c.get("issues", [])) for c in result["checks"])
    result["issues_count"] = total_issues

    # Set success
    result["success"] = total_issues == 0

    # Suggestion
    if total_issues > 0:
        result["suggestion"] = (
            "Run 'life-index index --rebuild' to fix index inconsistencies."
        )

    return result
