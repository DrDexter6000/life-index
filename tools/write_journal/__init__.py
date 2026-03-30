#!/usr/bin/env python3
"""
Life Index - Write Journal Tool
写入日志并自动维护索引体系

Usage:
    python -m tools.write_journal --data '{"title": "...", "content": "...", ...}'
    python -m tools.write_journal --data @input.json
    python -m tools.write_journal --dry-run --data '...'

Public API:
    from tools.write_journal import write_journal, prepare_journal_metadata
    result = write_journal(data={"date": "2026-03-14", "content": "..."})
    prepared = prepare_journal_metadata(form_data={...})
"""

# Public API exports
from .core import write_journal
from .prepare import (
    prepare_journal_metadata,
    KNOWN_PROJECT_ALIASES,
)

__all__ = [
    "write_journal",
    "prepare_journal_metadata",
    "KNOWN_PROJECT_ALIASES",
]
