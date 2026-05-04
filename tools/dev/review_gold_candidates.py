#!/usr/bin/env python3
"""Review and fix generated Gold Set candidates."""

from __future__ import annotations

import yaml
from pathlib import Path
from collections import Counter


def main() -> None:
    d = yaml.safe_load(Path("tools/dev/gold_candidates.yaml").read_text(encoding="utf-8"))
    qs = d["candidates"]

    print(f"Total candidates: {len(qs)}")
    cats = Counter(q["category"] for q in qs)
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")

    # Fix issues
    fixed = 0
    for q in qs:
        titles = q["expected"]["must_contain_title"]
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for t in titles:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        if len(unique) != len(titles):
            q["expected"]["must_contain_title"] = unique
            fixed += 1

        # Ensure at least 1 title
        if not unique:
            print(f"WARNING: {q['id']} has empty must_contain_title")

    print(f"\nFixed {fixed} candidates with duplicate titles")

    # Write back
    d["candidates"] = qs
    d["total"] = len(qs)
    d["by_category"] = dict(cats)
    Path("tools/dev/gold_candidates.yaml").write_text(
        yaml.dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # Summary
    print(f"\nAfter review: {len(qs)} candidates")
    for cat, n in cats.most_common():
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
