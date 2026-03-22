"""Compatibility rebuild helpers for index maintenance tests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.lib.config import BY_TOPIC_DIR, JOURNALS_DIR, ensure_dirs
from tools.lib.frontmatter import parse_journal_file


class IndexRebuilder:
    """Minimal index rebuilder used by the unit test suite."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.journals: list[Path] = []
        self.journal_metadata: dict[str, dict[str, Any]] = {}
        self.dead_links_found = 0
        self.indices_updated = 0

    def _collect_journals(self) -> None:
        if not JOURNALS_DIR.exists():
            self.journals = []
            return

        self.journals = sorted(JOURNALS_DIR.rglob("life-index_*.md"))

    def _parse_frontmatter(self, file_path: Path) -> dict[str, Any]:
        try:
            return parse_journal_file(file_path)
        except Exception:
            return {}

    def _resolve_link(self, source_file: Path, link: str) -> Path | None:
        if link.startswith(("http://", "https://")):
            return None
        if link.startswith("/"):
            return JOURNALS_DIR.parent / link.lstrip("/")
        return (source_file.parent / link).resolve()

    def _clean_dead_links(self) -> None:
        if not BY_TOPIC_DIR.exists():
            return

        pattern = re.compile(r"\(([^)]+)\)")
        for index_file in BY_TOPIC_DIR.glob("*.md"):
            content = index_file.read_text(encoding="utf-8")
            for link in pattern.findall(content):
                resolved = self._resolve_link(index_file, link)
                if resolved is not None and not resolved.exists():
                    self.dead_links_found += 1

    def _write_index(
        self,
        filename: str,
        header: str,
        entries: list[tuple[str, dict[str, Any]]],
    ) -> None:
        if self.dry_run:
            return

        lines = [f"# {header}", ""]
        for rel_path, metadata in entries:
            title = str(
                metadata.get("_title") or metadata.get("title") or Path(rel_path).stem
            )
            lines.append(f"- [{title}](../{rel_path})")

        output_path = BY_TOPIC_DIR / filename
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.indices_updated += 1

    def _rebuild_topic_indices(self) -> None:
        buckets: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for rel_path, metadata in self.journal_metadata.items():
            topic_value = metadata.get("topic", [])
            topics = topic_value if isinstance(topic_value, list) else [topic_value]
            for topic in topics:
                if topic:
                    buckets.setdefault(str(topic), []).append((rel_path, metadata))

        for topic, entries in buckets.items():
            self._write_index(f"主题_{topic}.md", f"主题: {topic}", entries)

    def _rebuild_project_indices(self) -> None:
        buckets: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for rel_path, metadata in self.journal_metadata.items():
            project = metadata.get("project")
            if project:
                buckets.setdefault(str(project), []).append((rel_path, metadata))

        for project, entries in buckets.items():
            self._write_index(f"项目_{project}.md", f"项目: {project}", entries)

    def _rebuild_tag_indices(self) -> None:
        buckets: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for rel_path, metadata in self.journal_metadata.items():
            tag_value = metadata.get("tags", [])
            tags = tag_value if isinstance(tag_value, list) else [tag_value]
            for tag in tags:
                if tag:
                    buckets.setdefault(str(tag), []).append((rel_path, metadata))

        for tag, entries in buckets.items():
            self._write_index(f"标签_{tag}.md", f"标签: {tag}", entries)

    def run(self) -> None:
        ensure_dirs()
        self._collect_journals()
        self.journal_metadata = {}
        for journal_path in self.journals:
            metadata = self._parse_frontmatter(journal_path)
            rel_path = str(journal_path.relative_to(JOURNALS_DIR.parent)).replace(
                "\\", "/"
            )
            self.journal_metadata[rel_path] = metadata

        self._clean_dead_links()
        self._rebuild_topic_indices()
        self._rebuild_project_indices()
        self._rebuild_tag_indices()
