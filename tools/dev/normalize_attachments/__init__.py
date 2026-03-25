#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...lib.frontmatter import normalize_attachment_entries, parse_journal_file


@dataclass
class NormalizationIssue:
    level: str
    category: str
    file: str
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class NormalizationResult:
    issues: list[NormalizationIssue] = field(default_factory=list)
    previews: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {
            "total_journals": 0,
            "migration_candidates": 0,
            "issues": 0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "issues": [asdict(issue) for issue in self.issues],
            "previews": list(self.previews),
        }


class AttachmentNormalizer:
    def __init__(self, *, journals_dir: Path, dry_run: bool = True) -> None:
        self.journals_dir = journals_dir
        self.dry_run = dry_run

    def run(self) -> NormalizationResult:
        result = NormalizationResult()
        journal_files = sorted(self.journals_dir.rglob("life-index_*.md"))
        result.summary["total_journals"] = len(journal_files)

        for journal_file in journal_files:
            metadata = parse_journal_file(journal_file)
            if metadata.get("_error"):
                continue

            issues = self._scan_file(journal_file, metadata)
            if issues:
                result.summary["migration_candidates"] += 1
                result.issues.extend(issues)
                result.previews.append(self._build_preview(journal_file, metadata))

        result.summary["issues"] = len(result.issues)
        return result

    def _scan_file(
        self, journal_file: Path, metadata: dict[str, Any]
    ) -> list[NormalizationIssue]:
        issues: list[NormalizationIssue] = []
        attachments = metadata.get("attachments", []) or []
        body = str(metadata.get("_body", ""))

        for attachment in attachments:
            if (
                isinstance(attachment, str)
                and "/" not in attachment
                and "\\" not in attachment
            ):
                issues.append(
                    NormalizationIssue(
                        level="warning",
                        category="attachment_bare_filename",
                        file=str(journal_file),
                        message=f"Bare filename attachment: {attachment}",
                        suggestion="Convert to structured attachment object with rel_path",
                        auto_fixable=False,
                    )
                )

        if "## Attachments" in body or "## 附件" in body:
            issues.append(
                NormalizationIssue(
                    level="warning",
                    category="attachment_body_duplication",
                    file=str(journal_file),
                    message="Body attachment section duplicates frontmatter storage",
                    suggestion=(
                        "Keep frontmatter attachments as SSOT "
                        "and remove generated body section"
                    ),
                    auto_fixable=True,
                )
            )

        if any(isinstance(attachment, str) for attachment in attachments):
            issues.append(
                NormalizationIssue(
                    level="info",
                    category="attachment_string_legacy",
                    file=str(journal_file),
                    message="Legacy string attachment entries detected",
                    suggestion="Normalize to structured object entries",
                    auto_fixable=True,
                )
            )

        return issues

    def _build_preview(
        self, journal_file: Path, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        normalized_attachments: list[dict[str, Any]] = []
        for entry in normalize_attachment_entries(
            metadata.get("attachments", []), mode="stored_metadata"
        ):
            normalized_attachments.append(
                {
                    "filename": entry["name"],
                    "rel_path": entry["path"],
                    "description": entry.get("description", ""),
                    "source_url": entry.get("source_url"),
                    "content_type": entry.get("content_type"),
                    "size": entry.get("size"),
                }
            )

        return {
            "file": str(journal_file),
            "normalized_attachments": normalized_attachments,
        }
