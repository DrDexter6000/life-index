"""Data Doctor maintenance audit envelope.

This module implements the m33 read-only audit surface. It intentionally keeps
detectors small and deterministic; repair and proposal validation live in later
steps.
"""

from __future__ import annotations

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

AUDIT_SCHEMA_VERSION = "m33.maintenance_audit.v0"

AUDIT_DOMAINS: tuple[str, ...] = (
    "layout",
    "search_index",
    "frontmatter",
    "text_encoding",
    "links",
    "attachments",
    "revisions",
    "entity_nodes",
    "entity_relations",
    "import_jobs",
    "migration",
    "backup",
    "config",
    "path_portability",
    "privacy",
)

Issue = dict[str, Any]
Detector = Callable[[Path], list[Issue]]

_TIMESTAMPED_JOURNAL_COPY_RE = re.compile(
    r"^(life-index_\d{4}-\d{2}-\d{2}_\d+)_\d{8}_\d{6}_\d{6}(?:_\d+)?\.md$"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_data_dir() -> Path:
    override = os.environ.get("LIFE_INDEX_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / "Documents" / "Life-Index"


def _rel_path(data_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(data_dir).as_posix()
    except ValueError:
        return path.name


def _issue(
    *,
    domain: str,
    issue_type: str,
    evidence_path: str,
    message: str,
    evidence_kind: str = "issue",
    risk: str = "low",
    repair_class: str = "derived",
    repairable: bool = True,
) -> Issue:
    return {
        "issue_id": f"{domain}.{issue_type}:{evidence_path}",
        "domain": domain,
        "type": issue_type,
        "severity": "warning",
        "risk": risk,
        "repair_class": repair_class,
        "repairable": repairable,
        "message": message,
        "evidence": [{"path": evidence_path, "kind": evidence_kind}],
    }


def _detect_layout(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []

    root_index = data_dir / "INDEX.md"
    if not root_index.exists():
        issues.append(
            _issue(
                domain="layout",
                issue_type="missing_generated_index",
                evidence_path="INDEX.md",
                evidence_kind="missing",
                message="Generated root index is missing.",
            )
        )

    journals_root = data_dir / "Journals"
    for year_dir in sorted(p for p in journals_root.glob("[0-9][0-9][0-9][0-9]") if p.is_dir()):
        year_index = year_dir / f"index_{year_dir.name}.md"
        if not year_index.exists():
            rel = _rel_path(data_dir, year_index)
            issues.append(
                _issue(
                    domain="layout",
                    issue_type="missing_generated_index",
                    evidence_path=rel,
                    evidence_kind="missing",
                    message="Generated year index is missing.",
                )
            )

        for month_dir in sorted(p for p in year_dir.glob("[0-9][0-9]") if p.is_dir()):
            has_journal = any(month_dir.glob("*.md"))
            month_index = month_dir / f"index_{year_dir.name}-{month_dir.name}.md"
            if has_journal and not month_index.exists():
                rel = _rel_path(data_dir, month_index)
                issues.append(
                    _issue(
                        domain="layout",
                        issue_type="missing_generated_index",
                        evidence_path=rel,
                        evidence_kind="missing",
                        message="Generated month index is missing.",
                    )
                )

    return issues


def _iter_files(data_dir: Path, pattern: str) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(p for p in data_dir.rglob(pattern) if p.is_file())


def _iter_markdown(data_dir: Path) -> list[Path]:
    return _iter_files(data_dir, "*.md")


def _read_utf8(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _parse_frontmatter(text: str) -> dict[str, Any] | None:
    if not text.startswith("---\n"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    payload = yaml.safe_load(parts[1]) or {}
    return payload if isinstance(payload, dict) else None


def _detect_search_index(data_dir: Path) -> list[Issue]:
    index_dir = data_dir / ".index"
    if index_dir.exists():
        return []
    return [
        _issue(
            domain="search_index",
            issue_type="missing_rebuildable_index",
            evidence_path=".index",
            evidence_kind="missing",
            message="Search index directory is missing and can be rebuilt.",
        )
    ]


def _detect_frontmatter(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_files(data_dir / "Journals", "*.md"):
        text = _read_utf8(path)
        if text is None:
            continue
        rel = _rel_path(data_dir, path)
        try:
            metadata = _parse_frontmatter(text)
        except yaml.YAMLError:
            issues.append(
                _issue(
                    domain="frontmatter",
                    issue_type="invalid_yaml",
                    evidence_path=rel,
                    evidence_kind="invalid",
                    message="Journal frontmatter is not valid YAML.",
                    risk="medium",
                    repair_class="proposal",
                    repairable=False,
                )
            )
            continue
        if metadata is None:
            issues.append(
                _issue(
                    domain="frontmatter",
                    issue_type="missing_frontmatter",
                    evidence_path=rel,
                    evidence_kind="missing",
                    message="Journal frontmatter block is missing or malformed.",
                    risk="medium",
                    repair_class="proposal",
                    repairable=False,
                )
            )
            continue
        for field in ("title", "date", "topic"):
            if field not in metadata:
                issues.append(
                    _issue(
                        domain="frontmatter",
                        issue_type=f"missing_{field}",
                        evidence_path=rel,
                        evidence_kind="missing",
                        message=f"Journal frontmatter is missing required field {field}.",
                        risk="medium",
                        repair_class="proposal",
                        repairable=False,
                    )
                )
    return issues


def _detect_text_encoding(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_markdown(data_dir):
        rel = _rel_path(data_dir, path)
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(
                _issue(
                    domain="text_encoding",
                    issue_type="utf8_bom",
                    evidence_path=rel,
                    evidence_kind="encoding",
                    message="Markdown file starts with a UTF-8 BOM.",
                    risk="medium",
                    repair_class="proposal",
                    repairable=False,
                )
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            issues.append(
                _issue(
                    domain="text_encoding",
                    issue_type="invalid_utf8",
                    evidence_path=rel,
                    evidence_kind="encoding",
                    message="Markdown file is not valid UTF-8.",
                    risk="high",
                    repair_class="proposal",
                    repairable=False,
                )
            )
            continue
        if "\ufffd" in text or "Ã" in text:
            issues.append(
                _issue(
                    domain="text_encoding",
                    issue_type="mojibake_indicator",
                    evidence_path=rel,
                    evidence_kind="encoding",
                    message="Markdown file contains mojibake indicators.",
                    risk="medium",
                    repair_class="proposal",
                    repairable=False,
                )
            )
    return issues


_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _is_external_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("#")
    )


def _clean_link_target(target: str) -> str:
    return target.split("#", 1)[0].split("?", 1)[0].strip()


def _detect_links(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_markdown(data_dir):
        text = _read_utf8(path)
        if text is None:
            continue
        rel = _rel_path(data_dir, path)
        for match in _MARKDOWN_LINK_RE.finditer(text):
            raw_target = _clean_link_target(match.group(1))
            if (
                not raw_target
                or _is_external_link(raw_target)
                or raw_target.startswith("../../../attachments/")
            ):
                continue
            target_path = (path.parent / raw_target).resolve()
            try:
                target_path.relative_to(data_dir.resolve())
            except ValueError:
                continue
            if not target_path.exists():
                issues.append(
                    _issue(
                        domain="links",
                        issue_type="missing_markdown_target",
                        evidence_path=rel,
                        evidence_kind="broken_link",
                        message="Markdown link target is missing.",
                        risk="medium",
                        repair_class="plan",
                        repairable=False,
                    )
                )
    return issues


def _attachment_refs(data_dir: Path) -> set[str]:
    refs: set[str] = set()
    for path in _iter_markdown(data_dir):
        text = _read_utf8(path)
        if text is None:
            continue
        for match in _MARKDOWN_LINK_RE.finditer(text):
            full = match.group(0)
            target = _clean_link_target(match.group(1))
            if not full.startswith("!") or _is_external_link(target):
                continue
            resolved = (path.parent / target).resolve()
            try:
                refs.add(resolved.relative_to(data_dir.resolve()).as_posix())
            except ValueError:
                continue
    return refs


def _detect_attachments(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    refs = _attachment_refs(data_dir)
    for ref in sorted(refs):
        if ref.startswith("attachments/") and not (data_dir / ref).exists():
            issues.append(
                _issue(
                    domain="attachments",
                    issue_type="missing_attachment",
                    evidence_path=ref,
                    evidence_kind="missing",
                    message="Referenced attachment is missing.",
                    risk="medium",
                    repair_class="review",
                    repairable=False,
                )
            )
    attachments_root = data_dir / "attachments"
    if attachments_root.exists():
        for path in sorted(p for p in attachments_root.rglob("*") if p.is_file()):
            rel = _rel_path(data_dir, path)
            if rel not in refs:
                issues.append(
                    _issue(
                        domain="attachments",
                        issue_type="orphan_attachment_candidate",
                        evidence_path=rel,
                        evidence_kind="orphan_candidate",
                        message="Attachment is not referenced by Markdown fixtures.",
                        risk="medium",
                        repair_class="review",
                        repairable=False,
                    )
                )
    return issues


def _detect_revisions(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    journals_root = data_dir / "Journals"
    if journals_root.exists():
        for path in sorted(p for p in journals_root.rglob("life-index_*.md") if p.is_file()):
            if ".revisions" in path.parts:
                continue
            match = _TIMESTAMPED_JOURNAL_COPY_RE.match(path.name)
            if not match:
                continue

            canonical = path.with_name(f"{match.group(1)}.md")
            rel = _rel_path(data_dir, path)
            canonical_rel = _rel_path(data_dir, canonical)
            repairable = canonical.exists() and canonical.is_file()
            issues.append(
                {
                    "issue_id": f"revisions.loose_timestamped_journal_copy:{rel}",
                    "domain": "revisions",
                    "type": "loose_timestamped_journal_copy",
                    "severity": "warning",
                    "risk": "low" if repairable else "medium",
                    "repair_class": "archive" if repairable else "review",
                    "repairable": repairable,
                    "message": (
                        "Timestamped journal copy is loose in Journals; archive it "
                        "outside the canonical journal tree."
                        if repairable
                        else (
                            "Timestamped journal copy is loose in Journals but no "
                            "canonical original exists."
                        )
                    ),
                    "evidence": [
                        {"path": rel, "kind": "duplicate"},
                        {"path": canonical_rel, "kind": "canonical"},
                    ],
                }
            )

    revisions_root = data_dir / ".revisions"
    if not revisions_root.exists():
        return issues
    issues.extend(
        [
            _issue(
                domain="revisions",
                issue_type="loose_revision_candidate",
                evidence_path=_rel_path(data_dir, path),
                evidence_kind="orphan_candidate",
                message="Revision sidecar needs review before any pruning.",
                risk="medium",
                repair_class="review",
                repairable=False,
            )
            for path in sorted(p for p in revisions_root.rglob("*") if p.is_file())
        ]
    )
    return issues


def _load_entity_payload(data_dir: Path) -> dict[str, Any]:
    graph_path = data_dir / "entity_graph.yaml"
    if not graph_path.exists():
        return {"entities": []}
    payload = yaml.safe_load(graph_path.read_text(encoding="utf-8")) or {"entities": []}
    if not isinstance(payload, dict):
        raise ValueError("entity_graph.yaml must contain a mapping")
    entities = payload.get("entities", [])
    if not isinstance(entities, list):
        raise ValueError("entities must be a list")
    return payload


def _entity_label_values(entity: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    primary = entity.get("primary_name")
    if isinstance(primary, str) and primary:
        labels.append(primary)
    aliases = entity.get("aliases", []) or []
    if isinstance(aliases, list):
        labels.extend(alias for alias in aliases if isinstance(alias, str) and alias)
    return labels


def _detect_entity_nodes(data_dir: Path) -> list[Issue]:
    payload = _load_entity_payload(data_dir)
    entities = payload.get("entities", []) or []
    seen: dict[str, str] = {}
    issues: list[Issue] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_id = str(entity.get("id", "unknown"))
        for label in _entity_label_values(entity):
            key = label.casefold()
            if key in seen and seen[key] != entity_id:
                issues.append(
                    _issue(
                        domain="entity_nodes",
                        issue_type="duplicate_alias",
                        evidence_path="entity_graph.yaml",
                        evidence_kind="duplicate",
                        message="Entity alias or primary name resolves to multiple entities.",
                        risk="high",
                        repair_class="proposal",
                        repairable=False,
                    )
                )
            else:
                seen[key] = entity_id
    return issues


def _detect_entity_relations(data_dir: Path) -> list[Issue]:
    payload = _load_entity_payload(data_dir)
    entities = payload.get("entities", []) or []
    entity_ids = {str(entity.get("id")) for entity in entities if isinstance(entity, dict)}
    issues: list[Issue] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        for relationship in entity.get("relationships", []) or []:
            if not isinstance(relationship, dict):
                continue
            target = str(relationship.get("target", ""))
            if target and target not in entity_ids:
                issues.append(
                    _issue(
                        domain="entity_relations",
                        issue_type="dangling_relation_target",
                        evidence_path="entity_graph.yaml",
                        evidence_kind="dangling",
                        message="Entity relationship references a missing target.",
                        risk="high",
                        repair_class="proposal",
                        repairable=False,
                    )
                )
    return issues


def _detect_import_jobs(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    imports_root = data_dir / ".life-index" / "imports"
    if not imports_root.exists():
        return issues
    for ledger in sorted(imports_root.rglob("ledger.json")):
        rel = _rel_path(data_dir, ledger)
        try:
            payload = json.loads(ledger.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(
                _issue(
                    domain="import_jobs",
                    issue_type="invalid_ledger_json",
                    evidence_path=rel,
                    evidence_kind="invalid",
                    message="Import job ledger is not valid JSON.",
                    risk="medium",
                    repair_class="plan",
                    repairable=False,
                )
            )
            continue
        if payload.get("status") not in {"completed", "rolled_back"}:
            issues.append(
                _issue(
                    domain="import_jobs",
                    issue_type="unfinished_import_job",
                    evidence_path=rel,
                    evidence_kind="state",
                    message="Import job is not in a terminal state.",
                    risk="medium",
                    repair_class="plan",
                    repairable=False,
                )
            )
        manifest_rel = payload.get("rollback_manifest_rel_path")
        if (
            isinstance(manifest_rel, str)
            and manifest_rel
            and not (data_dir / manifest_rel).exists()
        ):
            issues.append(
                _issue(
                    domain="import_jobs",
                    issue_type="missing_rollback_manifest",
                    evidence_path=rel,
                    evidence_kind="missing",
                    message="Import job references a missing rollback manifest.",
                    risk="high",
                    repair_class="plan",
                    repairable=False,
                )
            )
    return issues


def _detect_migration(data_dir: Path) -> list[Issue]:
    marker = data_dir / ".life-index" / "migration_required.marker"
    if not marker.exists():
        return []
    return [
        _issue(
            domain="migration",
            issue_type="migration_dry_run_required",
            evidence_path=_rel_path(data_dir, marker),
            evidence_kind="state",
            message="Migration marker indicates migrate --dry-run should be reviewed.",
            risk="medium",
            repair_class="plan",
            repairable=False,
        )
    ]


def _detect_backup(data_dir: Path) -> list[Issue]:
    manifest = data_dir / ".life-index" / "backup_manifest.json"
    if manifest.exists():
        return []
    return [
        _issue(
            domain="backup",
            issue_type="backup_manifest_missing",
            evidence_path=".life-index/backup_manifest.json",
            evidence_kind="missing",
            message="Backup readiness manifest is missing.",
            risk="medium",
            repair_class="diagnostic",
            repairable=False,
        )
    ]


_SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password)", re.IGNORECASE)


def _detect_config(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    config_root = data_dir / ".life-index"
    for path in sorted(config_root.glob("config.*")) if config_root.exists() else []:
        text = _read_utf8(path)
        if text is None:
            continue
        if _SECRET_KEY_RE.search(text):
            issues.append(
                _issue(
                    domain="config",
                    issue_type="secret_key_present_redacted",
                    evidence_path=_rel_path(data_dir, path),
                    evidence_kind="redacted",
                    message="Config contains secret-like key names; values are redacted.",
                    risk="high",
                    repair_class="review",
                    repairable=False,
                )
            )
    return issues


_ABSOLUTE_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s]+|/home/[^\s]+|/Users/[^\s]+|/mnt/[a-z]/[^\s]+)")


def _detect_path_portability(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_markdown(data_dir):
        text = _read_utf8(path)
        if text is None:
            continue
        if _ABSOLUTE_PATH_RE.search(text):
            issues.append(
                _issue(
                    domain="path_portability",
                    issue_type="absolute_path_reference",
                    evidence_path=_rel_path(data_dir, path),
                    evidence_kind="portability",
                    message="Markdown contains an absolute local path reference.",
                    risk="medium",
                    repair_class="proposal",
                    repairable=False,
                )
            )
    return issues


_TOKEN_RE = re.compile(r"(ghp_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,})")


def _detect_privacy(data_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    for path in _iter_markdown(data_dir):
        text = _read_utf8(path)
        if text is None:
            continue
        if _TOKEN_RE.search(text):
            issues.append(
                _issue(
                    domain="privacy",
                    issue_type="secret_like_token_redacted",
                    evidence_path=_rel_path(data_dir, path),
                    evidence_kind="redacted",
                    message="Markdown contains a secret-like token pattern; value is redacted.",
                    risk="high",
                    repair_class="review",
                    repairable=False,
                )
            )
    return issues


def _empty_detector(data_dir: Path) -> list[Issue]:
    _ = data_dir
    return []


DETECTORS: dict[str, Detector] = {
    "layout": _detect_layout,
    "search_index": _detect_search_index,
    "frontmatter": _detect_frontmatter,
    "text_encoding": _detect_text_encoding,
    "links": _detect_links,
    "attachments": _detect_attachments,
    "revisions": _detect_revisions,
    "entity_nodes": _detect_entity_nodes,
    "entity_relations": _detect_entity_relations,
    "import_jobs": _detect_import_jobs,
    "migration": _detect_migration,
    "backup": _detect_backup,
    "config": _detect_config,
    "path_portability": _detect_path_portability,
    "privacy": _detect_privacy,
}


def parse_domains(raw_domains: str | None) -> list[str]:
    if not raw_domains:
        return list(AUDIT_DOMAINS)
    domains = [part.strip() for part in raw_domains.split(",") if part.strip()]
    unknown = sorted(set(domains) - set(AUDIT_DOMAINS))
    if unknown:
        raise ValueError(f"Unknown maintenance audit domain(s): {', '.join(unknown)}")
    return domains


def run_audit(
    data_dir: str | Path | None = None, domains: list[str] | None = None
) -> dict[str, Any]:
    root = Path(data_dir) if data_dir is not None else _default_data_dir()
    selected_domains = domains or list(AUDIT_DOMAINS)

    issues: list[Issue] = []
    detector_rows: list[dict[str, Any]] = []
    detector_status: dict[str, str] = {}
    domain_counts: dict[str, int] = {}

    for domain in selected_domains:
        detector = DETECTORS[domain]
        status = "ok"
        domain_issues: list[Issue] = []
        error: str | None = None
        try:
            domain_issues = detector(root)
        except Exception as exc:  # pragma: no cover - defensive envelope guard
            status = "error"
            error = exc.__class__.__name__

        issues.extend(domain_issues)
        detector_status[domain] = status
        domain_counts[domain] = len(domain_issues)

        row: dict[str, Any] = {
            "domain": domain,
            "status": status,
            "issue_count": len(domain_issues),
        }
        if error is not None:
            row["error"] = error
        detector_rows.append(row)

    total_issues = len(issues)
    return {
        "success": True,
        "schema_version": AUDIT_SCHEMA_VERSION,
        "command": "maintenance audit",
        "generated_at": _now_iso(),
        "summary": {
            "total_issues": total_issues,
            "domain_counts": domain_counts,
            "detector_status": detector_status,
            "truncated": False,
            "limit": None,
            "offset": 0,
            "has_more": False,
        },
        "detectors": detector_rows,
        "issues": issues,
        "error": None,
    }


__all__ = ["AUDIT_DOMAINS", "AUDIT_SCHEMA_VERSION", "parse_domains", "run_audit"]
