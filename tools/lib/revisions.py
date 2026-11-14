#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _revision_dir_for(journal_path: Path) -> Path:
    return journal_path.parent / ".revisions"


def save_revision_bytes(original_path: Path, content: bytes) -> Path:
    """Store the original file's exact bytes as a revision copy.

    The revision is byte-identical to the file it preserves: mixed line
    endings and any other byte-level detail survive. A rewriter calls this
    with the bytes it read inside the journals lock, before replacing the
    journal; if this raises, the journal is not replaced.
    """
    revision_dir = _revision_dir_for(original_path)
    revision_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    revision_path = revision_dir / f"{original_path.stem}_{timestamp}.md"
    collision_index = 1
    while revision_path.exists():
        revision_path = revision_dir / f"{original_path.stem}_{timestamp}_{collision_index}.md"
        collision_index += 1
    revision_path.write_bytes(content)
    return revision_path


def list_revisions(journal_path: Path) -> list[Path]:
    revision_dir = _revision_dir_for(journal_path)
    if not revision_dir.exists():
        return []
    return sorted(revision_dir.glob(f"{journal_path.stem}_*.md"))
