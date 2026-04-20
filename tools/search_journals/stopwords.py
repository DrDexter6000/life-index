"""Stopword loading and filtering utilities for search query processing."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Iterable

_STOPWORDS_DIR = Path(__file__).parent


@functools.lru_cache(maxsize=4)
def load_stopwords(lang: str = "zh") -> frozenset[str]:
    """Load stopword set from file. Results are cached (singleton per lang).

    Args:
        lang: Language code ("zh" for Chinese, "en" for English).

    Returns:
        Frozen set of stopword strings.
    """
    if lang == "zh":
        path = _STOPWORDS_DIR / "stopwords_zh.txt"
    elif lang == "en":
        path = _STOPWORDS_DIR / "stopwords_en.txt"
    else:
        return frozenset()

    if not path.exists():
        return frozenset()

    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            words.add(stripped)

    return frozenset(words)


def is_stopword(token: str, lang: str = "zh") -> bool:
    """Check if a single token is a stopword.

    Args:
        token: The token to check.
        lang: Language code.

    Returns:
        True if the token is in the stopword list.
    """
    if lang == "en":
        return token.lower() in load_stopwords("en")
    return token in load_stopwords(lang)


def filter_stopwords(tokens: Iterable[str], lang: str = "zh") -> list[str]:
    """Remove stopwords from a token sequence, preserving order.

    Args:
        tokens: Iterable of tokens.
        lang: Language code.

    Returns:
        List of non-stopword tokens in original order.
    """
    if lang == "en":
        sw = load_stopwords("en")
        return [t for t in tokens if t.lower() not in sw]
    sw = load_stopwords(lang)
    return [t for t in tokens if t not in sw]
