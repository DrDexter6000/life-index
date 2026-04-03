#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.lib import content_analysis
from tools.lib.frontmatter import format_frontmatter, parse_frontmatter
from tools.lib.config import resolve_journals_dir


def find_journals_without_sentiment() -> list[Path]:
    pending: list[Path] = []
    for journal in resolve_journals_dir().rglob("*.md"):
        content = journal.read_text(encoding="utf-8")
        metadata, _body = parse_frontmatter(content)
        if "sentiment_score" not in metadata:
            pending.append(journal)
    return pending


def backfill_sentiment(*, dry_run: bool, batch_size: int) -> dict[str, Any]:
    pending = find_journals_without_sentiment()[:batch_size]
    updated = 0

    for journal in pending:
        content = journal.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)
        score = content_analysis.generate_sentiment_score(body)
        if score is None:
            continue
        metadata["sentiment_score"] = score
        if dry_run:
            continue
        new_content = format_frontmatter(metadata) + "\n\n\n" + body
        journal.write_text(new_content, encoding="utf-8")
        updated += 1

    return {
        "success": True,
        "updated": updated,
        "scanned": len(pending),
        "dry_run": dry_run,
    }
