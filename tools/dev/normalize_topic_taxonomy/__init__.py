#!/usr/bin/env python3

from __future__ import annotations

import json
import argparse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...lib.frontmatter import format_frontmatter, parse_journal_file

STANDARD_TOPICS = ("work", "learn", "health", "relation", "think", "create", "life")
SAFE_TOPIC_MAPPING = {
    "learning": "learn",
    "ai": "think",
    "general": "life",
    "personal": "life",
}
REBUILD_HINT = "应用 topic 规范化后请执行 `life-index index --rebuild`。"


@dataclass
class TopicTaxonomyIssue:
    level: str
    category: str
    file: str
    original_topic: str
    suggested_topic: str | None
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class TopicTaxonomyResult:
    issues: list[TopicTaxonomyIssue] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {
            "total_journals": 0,
            "journals_with_issues": 0,
            "non_standard_topics": 0,
            "unmapped_topics": 0,
            "fixed_files": 0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "issues": [asdict(issue) for issue in self.issues],
            "changed_files": list(self.changed_files),
            "standard_topics": list(STANDARD_TOPICS),
        }


class TopicTaxonomyNormalizer:
    def __init__(self, *, journals_dir: Path, dry_run: bool = True) -> None:
        self.journals_dir = journals_dir
        self.dry_run = dry_run

    def run(self) -> TopicTaxonomyResult:
        result = TopicTaxonomyResult()
        journal_files = sorted(self.journals_dir.rglob("life-index_*.md"))
        result.summary["total_journals"] = len(journal_files)

        journals_with_issues: set[str] = set()

        for journal_file in journal_files:
            metadata = parse_journal_file(journal_file)
            if metadata.get("_error"):
                continue

            topics = metadata.get("topic", [])
            if isinstance(topics, str):
                topics = [topics]
            if not isinstance(topics, list):
                continue

            normalized_topics: list[str] = []
            changed = False

            for topic in topics:
                topic_text = str(topic).strip()
                if not topic_text:
                    continue

                if topic_text in STANDARD_TOPICS:
                    normalized_topics.append(topic_text)
                    continue

                suggested = SAFE_TOPIC_MAPPING.get(topic_text.lower())
                result.issues.append(
                    TopicTaxonomyIssue(
                        level="warning",
                        category="non_standard_topic",
                        file=str(journal_file),
                        original_topic=topic_text,
                        suggested_topic=suggested,
                        message=f"Non-standard topic '{topic_text}' detected",
                        suggestion=(
                            f"Map to standard topic '{suggested}'"
                            if suggested
                            else "Review manually against standard topic set"
                        ),
                        auto_fixable=suggested is not None,
                    )
                )
                journals_with_issues.add(str(journal_file))

                if suggested is None:
                    result.summary["unmapped_topics"] += 1
                    normalized_topics.append(topic_text)
                    continue

                normalized_topics.append(suggested)
                if suggested != topic_text:
                    changed = True

            deduped_topics: list[str] = []
            for topic in normalized_topics:
                if topic not in deduped_topics:
                    deduped_topics.append(topic)

            if changed and not self.dry_run:
                metadata["topic"] = deduped_topics
                self._rewrite_file(journal_file, metadata)
                result.changed_files.append(str(journal_file))

        result.summary["journals_with_issues"] = len(journals_with_issues)
        result.summary["non_standard_topics"] = len(result.issues)
        result.summary["fixed_files"] = len(result.changed_files)
        return result

    def _rewrite_file(self, journal_file: Path, metadata: dict[str, Any]) -> None:
        body = str(metadata.get("_body", ""))
        frontmatter_data = {k: v for k, v in metadata.items() if not k.startswith("_")}
        frontmatter = format_frontmatter(frontmatter_data)
        journal_file.write_text(f"{frontmatter}\n\n{body}\n", encoding="utf-8")


def print_report(result: TopicTaxonomyResult, *, use_json: bool = False) -> None:
    if use_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("Life Index Topic Taxonomy 治理报告")
    print("=" * 60)
    print(f"标准主题集: {', '.join(STANDARD_TOPICS)}")
    print(f"日志文件: {result.summary['total_journals']}")
    print(f"存在问题的日志: {result.summary['journals_with_issues']}")
    print(f"非标准 topic 数: {result.summary['non_standard_topics']}")
    print(f"未映射 topic 数: {result.summary['unmapped_topics']}")
    if result.summary["fixed_files"]:
        print(f"已修复文件: {result.summary['fixed_files']}")
    print()

    if not result.issues:
        print("[OK] 未发现非标准 topic")
        return

    for issue in result.issues:
        target = issue.suggested_topic or "<manual-review>"
        print(f"[WARN] {issue.original_topic} -> {target}")
        print(f"   文件: {issue.file}")
        print(f"   建议: {issue.suggestion}")
        print()

    print(REBUILD_HINT)


def main() -> None:
    from ...lib.config import JOURNALS_DIR

    parser = argparse.ArgumentParser(description="Life Index Topic Taxonomy 治理工具")
    parser.add_argument("--fix", action="store_true", help="应用安全的标准主题映射")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    result = TopicTaxonomyNormalizer(journals_dir=JOURNALS_DIR, dry_run=not args.fix).run()
    print_report(result, use_json=args.json)


if __name__ == "__main__":
    main()
