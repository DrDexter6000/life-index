"""
Life Index - Text Normalization Utilities
=========================================
Shared helpers for normalizing text list fields (tags, mood, people, topic).

SSOT: This module is the single source of truth for text list normalization.
Both CLI tools and Web services must use this, never duplicate logic.
"""

from typing import Any


def normalize_text_list(value: Any) -> list[str]:
    """Normalize a value to a list of strings.

    Handles:
    - None → []
    - Already a list → strip each item, handle comma-separated within items
    - Comma-separated string → split and strip each item
    - Single string → wrap in list

    This ensures "tag1, tag2" becomes ["tag1", "tag2"] not ["tag1, tag2"].
    Also normalizes full-width commas (，) to half-width commas.

    Args:
        value: Input value (None, str, or list)

    Returns:
        List of stripped, non-empty strings

    Example:
        >>> normalize_text_list("tag1, tag2")
        ['tag1', 'tag2']
        >>> normalize_text_list(["tag1", "tag2, tag3"])
        ['tag1', 'tag2', 'tag3']
        >>> normalize_text_list(None)
        []
    """
    if value is None:
        return []
    if isinstance(value, list):
        # Already a list - but items might be comma-separated strings
        result: list[str] = []
        for item in value:
            item_str = str(item).strip()
            if not item_str:
                continue
            # Normalize full-width commas to half-width, then split
            normalized = item_str.replace("，", ",")
            if "," in normalized:
                result.extend(
                    [part.strip() for part in normalized.split(",") if part.strip()]
                )
            else:
                result.append(item_str)
        return result
    if isinstance(value, str) and value.strip():
        # Normalize full-width commas to half-width, then split
        normalized = value.replace("，", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]
    return []


__all__ = ["normalize_text_list"]
