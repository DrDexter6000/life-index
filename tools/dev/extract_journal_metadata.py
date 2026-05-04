#!/usr/bin/env python3
"""Extract journal metadata for Gold Set generation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def main() -> None:
    data_dir = Path.home() / "Documents" / "Life-Index" / "Journals"
    files = list(data_dir.rglob("*.md"))

    entries: list[dict] = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("---", 3)
            if end <= 0:
                continue
            meta = yaml.safe_load(content[3:end])
            if not meta or "title" not in meta:
                continue
            entries.append(
                {
                    "file": str(f.relative_to(data_dir)),
                    "title": str(meta.get("title", "")),
                    "date": str(meta.get("date", ""))[:10] if meta.get("date") else "",
                    "location": str(meta.get("location", "")),
                    "topic": (
                        meta.get("topic", [])
                        if isinstance(meta.get("topic"), list)
                        else [str(meta.get("topic", ""))]
                    ),
                    "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
                }
            )
        except Exception:
            continue

    out = Path("tools/dev/journal_metadata.json")
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracted {len(entries)} entries -> {out}")


if __name__ == "__main__":
    main()
