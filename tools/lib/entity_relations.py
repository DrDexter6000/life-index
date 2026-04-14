#!/usr/bin/env python3
"""
Entity relation vocabulary normalization — Round 7 Phase 3 Task 10.

Provides canonical relation mapping and alias normalization for entity relationships.

Used by:
- Search phrase registry (entity_runtime.py)
- Entity review/merge operations
- Integrity check (entity check)

Design principle: This is a helper, not a migration tool. Old YAML content is not
forcibly updated. The helper + check work together to gently encourage normalization.
"""

from __future__ import annotations

from typing import Any

# Canonical relation → list of known aliases (Chinese + English)
CANONICAL_RELATIONS: dict[str, list[str]] = {
    "spouse_of": ["wife", "husband", "老婆", "丈夫", "妻子", "老公", "配偶", "爱人"],
    "parent_of": [
        "mom",
        "mother",
        "dad",
        "father",
        "妈妈",
        "母亲",
        "爸爸",
        "父亲",
        "老爸",
        "老妈",
        "家长",
    ],
    "child_of": ["daughter", "son", "女儿", "儿子", "孩子", "小孩"],
    "sibling_of": ["sister", "brother", "姐妹", "兄弟", "哥哥", "弟弟", "姐姐", "妹妹"],
    "colleague_of": ["colleague", "coworker", "同事", "搭档", "合作者"],
    "friend_of": ["friend", "buddy", "朋友", "好友", "哥们"],
    "lives_in": ["resides", "居住", "住在", "生活在"],
    "works_at": ["employed_at", "工作于", "就职于", "任职"],
    "member_of": ["belongs_to", "属于", "成员"],
}

# Build reverse lookup: alias (lowered) → canonical relation
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in CANONICAL_RELATIONS.items():
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


def normalize_relation(label: str) -> str:
    """Normalize a relation label to its canonical form.

    If the label is already canonical, returns it as-is.
    If it's a known alias, returns the canonical form.
    If unknown, returns the label unchanged (no error).

    Case-insensitive for English labels.

    Args:
        label: A relation string (e.g., "wife", "同事", "spouse_of").

    Returns:
        Canonical relation string (e.g., "spouse_of", "colleague_of").
    """
    # Direct canonical match
    if label in CANONICAL_RELATIONS:
        return label

    # Alias lookup (case-insensitive)
    return _ALIAS_TO_CANONICAL.get(label.lower(), label)


def relation_aliases(canonical: str) -> list[str]:
    """Get all known aliases for a canonical relation.

    Args:
        canonical: A canonical relation string (e.g., "spouse_of").

    Returns:
        List of alias strings, or empty list if unknown canonical.
    """
    return list(CANONICAL_RELATIONS.get(canonical, []))
