"""Compatibility data validation helpers for unit tests and CI collection."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tools.lib.config import ATTACHMENTS_DIR, BY_TOPIC_DIR, JOURNALS_DIR
from tools.lib.frontmatter import parse_journal_file


@dataclass
class ValidationIssue:
    level: str
    category: str
    file: str
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class ValidationResult:
    total_journals: int = 0
    total_indices: int = 0
    total_attachments: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "error")

    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.level == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_journals": self.total_journals,
                "total_indices": self.total_indices,
                "total_attachments": self.total_attachments,
                "errors": self.error_count(),
                "warnings": self.warning_count(),
            },
            "issues": [asdict(issue) for issue in self.issues],
            "stats": self.stats,
        }


class DataValidator:
    REQUIRED_FIELDS = ["title", "date"]
    RECOMMENDED_FIELDS = ["mood", "location"]

    def __init__(self, fix_mode: bool = False):
        self.fix_mode = fix_mode
        self.result = ValidationResult()
        self.journal_files: list[Path] = []
        self.index_files: list[Path] = []
        self.attachment_files: list[Path] = []
        self.journal_entries: dict[str, dict[str, Any]] = {}

    def _add_issue(
        self,
        level: str,
        category: str,
        file: str,
        message: str,
        suggestion: str = "",
        auto_fixable: bool = False,
    ) -> None:
        self.result.issues.append(
            ValidationIssue(
                level=level,
                category=category,
                file=file,
                message=message,
                suggestion=suggestion,
                auto_fixable=auto_fixable,
            )
        )

    def _collect_files(self) -> None:
        self.journal_files = (
            sorted(JOURNALS_DIR.rglob("life-index_*.md")) if JOURNALS_DIR.exists() else []
        )
        self.index_files = sorted(BY_TOPIC_DIR.glob("*.md")) if BY_TOPIC_DIR.exists() else []
        self.attachment_files = (
            sorted(ATTACHMENTS_DIR.rglob("*")) if ATTACHMENTS_DIR.exists() else []
        )
        self.result.total_journals = len(self.journal_files)
        self.result.total_indices = len(self.index_files)
        self.result.total_attachments = len([p for p in self.attachment_files if p.is_file()])

    def _parse_frontmatter(self, file_path: Path) -> dict[str, Any] | None:
        try:
            metadata = parse_journal_file(file_path)
        except Exception as exc:
            self._add_issue("error", "metadata", str(file_path), str(exc))
            return None

        if metadata is None:
            return None
        if "_error" in metadata:
            self._add_issue("error", "metadata", str(file_path), str(metadata["_error"]))
            return None
        return metadata

    def _resolve_link(self, source_file: Path, link: str) -> Path | None:
        if link.startswith(("http://", "https://")):
            return None
        if link.startswith("/"):
            return JOURNALS_DIR.parent / link.lstrip("/")
        return (source_file.parent / link).resolve()

    def _validate_journals(self) -> None:
        sequence_groups: dict[str, list[int]] = {}

        for journal_path in self.journal_files:
            metadata = self._parse_frontmatter(journal_path)
            if metadata is None:
                continue

            rel_path = str(journal_path.relative_to(JOURNALS_DIR.parent)).replace("\\", "/")
            self.journal_entries[rel_path] = metadata

            for field_name in self.REQUIRED_FIELDS:
                if not metadata.get(field_name):
                    self._add_issue(
                        "error",
                        "metadata",
                        rel_path,
                        f"Missing required field: {field_name}",
                    )

            for field_name in self.RECOMMENDED_FIELDS:
                if not metadata.get(field_name):
                    self._add_issue(
                        "warning",
                        "metadata",
                        rel_path,
                        f"Missing recommended field: {field_name}",
                    )

            date_value = metadata.get("date")
            if date_value:
                date_text = str(date_value)
                if not re.match(r"^\d{4}-\d{2}-\d{2}(?:T.*)?(?:Z)?$", date_text):
                    self._add_issue("error", "metadata", rel_path, f"Invalid date: {date_text}")

            match = re.search(r"life-index_(\d{4}-\d{2}-\d{2})_(\d{3})\.md$", journal_path.name)
            if match:
                date_key, seq_text = match.groups()
                sequence_groups.setdefault(date_key, []).append(int(seq_text))

        for date_key, sequences in sequence_groups.items():
            ordered = sorted(sequences)
            if not ordered:
                continue
            for expected in range(ordered[0], ordered[-1] + 1):
                if expected not in ordered:
                    self._add_issue(
                        "warning",
                        "sequence",
                        date_key,
                        f"Missing sequence number {expected} for {date_key}",
                    )
                    break

    def _validate_indices(self) -> None:
        pattern = re.compile(r"\(([^)]+)\)")
        for index_file in self.index_files:
            content = index_file.read_text(encoding="utf-8")
            for link in pattern.findall(content):
                resolved = self._resolve_link(index_file, link)
                if resolved is not None and not resolved.exists():
                    self._add_issue("error", "link", str(index_file), f"Dead link: {link}")

    def _generate_stats(self) -> None:
        stats = {
            "topics": {},
            "projects": {},
            "tags": {},
            "moods": {},
            "monthly_distribution": {},
        }

        def _inc(bucket: dict[str, int], key: str) -> None:
            bucket[key] = bucket.get(key, 0) + 1

        for metadata in self.journal_entries.values():
            topic_value = metadata.get("topic")
            if isinstance(topic_value, list):
                for topic in topic_value:
                    _inc(stats["topics"], str(topic))
            elif isinstance(topic_value, str) and topic_value:
                _inc(stats["topics"], topic_value)

            project = metadata.get("project")
            if project:
                _inc(stats["projects"], str(project))

            tags = metadata.get("tags")
            if isinstance(tags, list):
                for tag in tags:
                    _inc(stats["tags"], str(tag))

            mood_value = metadata.get("mood")
            if isinstance(mood_value, list):
                for mood in mood_value:
                    _inc(stats["moods"], str(mood))
            elif isinstance(mood_value, str) and mood_value:
                _inc(stats["moods"], mood_value)

            if "date" in metadata:
                month_key = str(metadata["date"])[:7]
                if month_key:
                    _inc(stats["monthly_distribution"], month_key)

        self.result.stats = stats

    def _validate_attachments(self) -> None:
        for rel_path, metadata in self.journal_entries.items():
            attachments = metadata.get("attachments")
            if not isinstance(attachments, list):
                continue

            for attachment in attachments:
                attachment_name = str(attachment)
                attachment_path = ATTACHMENTS_DIR / attachment_name
                if not attachment_path.exists():
                    journal_dir = (JOURNALS_DIR.parent / rel_path).parent
                    alternative = journal_dir / attachment_name
                    if not alternative.exists():
                        self._add_issue(
                            "warning",
                            "attachment",
                            rel_path,
                            f"Missing attachment: {attachment_name}",
                        )

    def _validate_cross_references(self) -> None:
        indexed_links: dict[str, set[str]] = {}
        pattern = re.compile(r"\(([^)]+)\)")

        for index_file in self.index_files:
            content = index_file.read_text(encoding="utf-8")
            indexed_links[str(index_file)] = set(pattern.findall(content))

        for rel_path, metadata in self.journal_entries.items():
            topic_value = metadata.get("topic", [])
            topics = topic_value if isinstance(topic_value, list) else [topic_value]
            for topic in topics:
                if not topic:
                    continue

                expected_index = BY_TOPIC_DIR / f"主题_{topic}.md"
                if expected_index not in self.index_files:
                    continue

                expected_link = f"../{rel_path}"
                links = indexed_links.get(str(expected_index), set())
                if expected_link not in links:
                    self._add_issue(
                        "warning",
                        "orphan_index",
                        rel_path,
                        f"Journal missing from topic index: {topic}",
                        suggestion="Rebuild topic indices",
                        auto_fixable=True,
                    )

    def run(self) -> ValidationResult:
        self._collect_files()
        self._validate_journals()
        self._validate_indices()
        self._validate_attachments()
        self._validate_cross_references()
        self._generate_stats()
        return self.result


def print_report(result: ValidationResult, use_json: bool = False) -> None:
    if use_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print("Validation Summary")
    print(f"Journals: {result.total_journals}")
    print(f"Indices: {result.total_indices}")
    print(f"Attachments: {result.total_attachments}")

    if result.stats:
        print("Stats:")
        for section, values in result.stats.items():
            print(f"- {section}: {values}")

    if result.issues:
        print("Issues:")
        for issue in result.issues:
            print(f"- [{issue.level}] {issue.category} {issue.file}: {issue.message}")
            if issue.suggestion:
                print(f"  Suggestion: {issue.suggestion}")
    else:
        print("No issues found")
