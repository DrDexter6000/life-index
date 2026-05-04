#!/usr/bin/env python3
"""Merge reviewed candidates into golden_queries.yaml."""

from __future__ import annotations

import yaml
from pathlib import Path
from collections import Counter


def main() -> None:
    # Load existing
    gold_path = Path("tools/eval/golden_queries.yaml")
    gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    existing = gold.get("queries", [])
    existing_queries = {q["query"] for q in existing}

    # Load candidates
    cand = yaml.safe_load(Path("tools/dev/gold_candidates.yaml").read_text(encoding="utf-8"))
    candidates = cand.get("candidates", [])

    # Filter out duplicates
    added = []
    for c in candidates:
        if c["query"] not in existing_queries:
            added.append(c)
            existing_queries.add(c["query"])

    # Merge
    merged = existing + added

    # Write back
    gold["queries"] = merged
    gold_path.write_text(yaml.dump(gold, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # Report
    print(f"Existing: {len(existing)}")
    print(f"Added: {len(added)}")
    print(f"Total: {len(merged)}")

    cats = Counter(q["category"] for q in merged)
    print("\nCategory distribution:")
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
