"""Compatibility query classifier that emits advisory retrieval metadata.

The public ``is_noise_query`` name and reason values remain for compatibility.
Classification is deterministic and advisory only: callers may expose the
reason as metadata, but classification never authorizes retrieval bypass or
result deletion.

Round 19 Phase 1 extension: add negation-intent and OOD-topic detection
for compatibility with existing diagnostic categories.

Design principle: simple, fast, auditable. No ML. No index lookup.
Legacy compatibility flag: set LIFE_INDEX_NOISE_GATE=0 to disable classification.

Compatibility examples:
- "!!!" and "xyz123456789" -> syntactic advisory reasons
- "不存在的日志标题" -> ``negation_intent``
- "菜谱推荐" -> ``ood_topic``
- "life indxxx" -> ``typo_near_noise``
"""

from __future__ import annotations

import importlib
import os
import re
import unicodedata
from typing import Any

from tools.lib.search_constants import (
    FUZZY_TYPO_CANONICALS,
    FUZZY_TYPO_LEN_DIFF_MAX,
    FUZZY_TYPO_RATIO_THRESHOLD,
    NOISE_GATE_TYPO_NEAR_LOW,
)


def _levenshtein() -> Any:
    return importlib.import_module("rapidfuzz.distance").Levenshtein


# Regex for recognizable English words (≥3 letters)
_ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]{3,}")

# CJK Unified Ideographs range
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# ── Round 19 Phase 1: Intent-based noise detection ─────────────────────

# Negation-intent signals: user explicitly states irrelevance or non-existence.
# These phrases retain their existing advisory reason for compatibility; they
# do not determine whether matching content may be retrieved.
_NEGATION_INTENT_SIGNALS: list[str] = [
    "不存在",
    "不相关",
    "完全不相关",
    "随机内容",
    "无关内容",
]

# OOD (Out-of-Distribution) topic signals: domains not covered by user journals.
# Conservative list based on Round 19 edge_case failures (GQ74-78).
# Only matches explicit multi-character phrases to avoid false positives.
# NOTE: "投资" is intentionally excluded because investment-related content
# exists in the corpus (e.g. "AI算力国资股长线投资研究").
_OOD_TOPIC_SIGNALS: list[str] = [
    # Cooking / recipes (GQ75)
    "菜谱",
    # Fitness / weight loss (GQ76)
    "健身",
    "减肥",
    # Blockchain / crypto (GQ77)
    "区块链",
    # Pets (GQ78)
    "养猫",
    "养狗",
    "宠物",
    # Travel guides (GQ74)
    "旅行攻略",
    "旅游攻略",
]


def is_noise_query(query: str | None) -> tuple[bool, str | None]:
    """Return the compatibility ``(is_advisory, reason)`` classification.

    If classification is disabled via LIFE_INDEX_NOISE_GATE=0, always returns
    (False, None).
    """
    if os.environ.get("LIFE_INDEX_NOISE_GATE", "1") == "0":
        return False, None

    if not query:
        return True, "empty_query"

    stripped = query.strip()
    if not stripped:
        return True, "empty_query"

    # Rule 1: pure punctuation / symbols
    if all(unicodedata.category(c).startswith("P") or c.isspace() for c in stripped):
        return True, "pure_symbols"

    # Rule 2: pure digits
    if stripped.isdigit():
        return True, "pure_digits"

    # Rule 3: all same character (repetition)
    if len(set(stripped)) == 1:
        return True, "repeated_char"

    # Rule 4: effective length < 3 after stripping spaces & punctuation
    effective = "".join(
        c for c in stripped if not c.isspace() and not unicodedata.category(c).startswith("P")
    )
    if len(effective) < 3:
        return True, "too_short"

    # Rule 5: no CJK characters AND (high digit ratio OR no recognizable words)
    # Covers random alphanumeric strings like "xyz123456789"
    has_cjk = bool(_CJK_RE.search(stripped))
    if not has_cjk:
        non_space = stripped.replace(" ", "")
        if non_space.isalnum() and len(non_space) > 0:
            digit_ratio = sum(1 for c in non_space if c.isdigit()) / len(non_space)
            if digit_ratio >= 0.5:
                return True, "alphanumeric_noise"
        words = _ENGLISH_WORD_RE.findall(stripped)
        if not words:
            return True, "no_dictionary_words"

    # Rule 6: negation intent — user explicitly states irrelevance or non-existence
    for signal in _NEGATION_INTENT_SIGNALS:
        if signal in stripped:
            return True, "negation_intent"

    # Rule 7: OOD topic — query about domains not covered by user data
    for signal in _OOD_TOPIC_SIGNALS:
        if signal in stripped:
            return True, "ood_topic"

    # Rule 8: typo_near_noise — mid-similarity to canonical terms but below
    # fuzzy correction threshold. Retains a diagnostic category for near-typo
    # queries (e.g. "life indxxx", "lyf index") without filtering results.
    # Only for ASCII queries with len-diff <= max against known canonicals.
    if stripped.isascii():
        q = stripped.lower()
        for canonical in FUZZY_TYPO_CANONICALS:
            if abs(len(q) - len(canonical)) > FUZZY_TYPO_LEN_DIFF_MAX:
                continue

            Levenshtein = _levenshtein()
            sim = Levenshtein.normalized_similarity(q, canonical)
            if sim is not None and NOISE_GATE_TYPO_NEAR_LOW <= sim < FUZZY_TYPO_RATIO_THRESHOLD:
                return True, "typo_near_noise"

    return False, None
