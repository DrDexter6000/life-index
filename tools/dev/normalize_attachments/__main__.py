#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

from ...lib.paths import get_journals_dir
from . import AttachmentNormalizer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Attachment Normalization Governance Tool"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()

    result = AttachmentNormalizer(journals_dir=get_journals_dir(), dry_run=True).run()

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"🔍 已扫描 journals: {result.summary['total_journals']}")
    print(f"🔍 migration candidates: {result.summary['migration_candidates']}")
    print(f"🔍 issues: {result.summary['issues']}")

    for issue in result.issues:
        print(f"- [{issue.category}] {issue.file}: {issue.message}")


if __name__ == "__main__":
    main()
