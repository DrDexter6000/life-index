#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...lib.frontmatter import format_frontmatter, parse_journal_file

LIST_FIELDS = ("topic", "tags", "mood", "people")
REBUILD_HINT = (
    "修复后请执行 `life-index index --rebuild` 以重建 metadata cache 和搜索索引。"
)


@dataclass
class MetadataAuditIssue:
    level: str
    category: str
    file: str
    field: str
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class MetadataAuditResult:
    issues: list[MetadataAuditIssue] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {
            "total_journals": 0,
            "journals_with_issues": 0,
            "issues": 0,
            "scalar_list_fields": 0,
            "fixed_files": 0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "issues": [asdict(issue) for issue in self.issues],
            "changed_files": list(self.changed_files),
        }


class JournalMetadataAuditor:
    def __init__(self, *, journals_dir: Path, dry_run: bool = True) -> None:
        self.journals_dir = journals_dir
        self.dry_run = dry_run

    def run(self) -> MetadataAuditResult:
        result = MetadataAuditResult()
        journal_files = sorted(self.journals_dir.rglob("life-index_*.md"))
        result.summary["total_journals"] = len(journal_files)

        journals_with_issues: set[str] = set()

        for journal_file in journal_files:
            metadata = parse_journal_file(journal_file)
            if metadata.get("_error"):
                continue

            fixed = False

            for field_name in LIST_FIELDS:
                value = metadata.get(field_name)
                if isinstance(value, str) and value.strip():
                    result.issues.append(
                        MetadataAuditIssue(
                            level="warning",
                            category="scalar_list_field",
                            file=str(journal_file),
                            field=field_name,
                            message=f"Field '{field_name}' is stored as scalar string",
                            suggestion=(
                                "Rewrite "
                                f"{field_name} as JSON/YAML list, "
                                f'e.g. {field_name}: ["{value.strip()}"]'
                            ),
                            auto_fixable=False,
                        )
                    )
                    journals_with_issues.add(str(journal_file))
                    if not self.dry_run:
                        metadata[field_name] = [value.strip()]
                        fixed = True

            if fixed:
                self._rewrite_file(journal_file, metadata)
                result.changed_files.append(str(journal_file))

        result.summary["journals_with_issues"] = len(journals_with_issues)
        result.summary["issues"] = len(result.issues)
        result.summary["scalar_list_fields"] = len(result.issues)
        result.summary["fixed_files"] = len(result.changed_files)
        return result

    def _rewrite_file(self, journal_file: Path, metadata: dict[str, Any]) -> None:
        body = str(metadata.get("_body", ""))
        frontmatter_data = {k: v for k, v in metadata.items() if not k.startswith("_")}
        frontmatter = format_frontmatter(frontmatter_data)
        new_content = f"{frontmatter}\n\n{body}\n"
        journal_file.write_text(new_content, encoding="utf-8")


def print_report(result: MetadataAuditResult, *, use_json: bool = False) -> None:
    if use_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("Life Index 元数据审计报告")
    print("=" * 60)
    print(f"日志文件: {result.summary['total_journals']}")
    print(f"存在问题的日志: {result.summary['journals_with_issues']}")
    print(f"标量列表字段问题: {result.summary['scalar_list_fields']}")
    if result.summary["fixed_files"]:
        print(f"已修复文件: {result.summary['fixed_files']}")
    print()

    if not result.issues:
        print("[OK] 未发现 legacy scalar list 字段")
        return

    for issue in result.issues:
        print(f"[WARN] [{issue.field}] {issue.message}")
        print(f"   文件: {issue.file}")
        if issue.suggestion:
            print(f"   建议: {issue.suggestion}")
        print()

    print(REBUILD_HINT)


def main() -> None:
    from ...lib.config import JOURNALS_DIR

    auditor = JournalMetadataAuditor(journals_dir=JOURNALS_DIR, dry_run=True)
    result = auditor.run()
    print_report(result, use_json=False)


if __name__ == "__main__":
    main()
