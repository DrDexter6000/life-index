"""Mood extractor: frontmatter mood list + body emoji/description words."""

from __future__ import annotations

from typing import Any, Dict, List

# Common mood emojis mapped to descriptive labels
_EMOJI_MOOD_MAP = {
    "🎉": "celebratory",
    "😰": "stressed",
    "🚀": "excited",
    "🎄": "festive",
    "😞": "sad",
    "😊": "happy",
    "😢": "sad",
    "😠": "angry",
    "😴": "sleepy",
    "🤔": "pensive",
}

# Body description words that indicate mood (in addition to frontmatter)
_BODY_MOOD_WORDS = {
    "stressed",
    "happy",
    "sad",
    "tired",
    "excited",
    "calm",
    "joyful",
    "melancholy",
    "grateful",
    "neutral",
    "warm",
}


def extract_mood(metadata: Dict[str, Any], body: str) -> List[str]:
    """Return list of mood strings found in metadata or body."""
    values: List[str] = []

    raw = metadata.get("mood")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                values.append(item.strip())
    elif isinstance(raw, str) and raw.strip():
        values.append(raw.strip())

    # Emoji extraction from body
    for emoji, label in _EMOJI_MOOD_MAP.items():
        if emoji in body and label not in values:
            values.append(label)

    # Description word extraction (simple whole-word match)
    body_lower = body.lower()
    for word in _BODY_MOOD_WORDS:
        if word in body_lower and word not in values:
            values.append(word)

    return values
