"""Noise gate — hard-rule query classifier for semantic pipeline bypass.

Round 18 Phase 3 discovery: semantic embedding returns low-confidence matches
for noise queries (e.g. "!!!", "xyz123456789"), destroying noise_rejection.
This gate is a deterministic, rule-based pre-filter that skips the semantic
pipeline when a query is clearly noise.

Round 19 Phase 1 extension: add negation-intent and OOD-topic detection
for queries that trigger semantic over-generalization (GQ74-78, GQ128, GQ130).

Design principle: simple, fast, auditable. No ML. No index lookup.
Feature flag: set LIFE_INDEX_NOISE_GATE=0 to disable.

Coverage on Round 19 corrected baseline noise_rejection + edge_case leaks:
- GQ12 "!!!"              -> pure symbols      (Rule 1) -> caught ✅
- GQ129 "xyz123456789"    -> no-dictionary     (Rule 5) -> caught ✅
- GQ128 "不存在的日志标题"  -> negation intent   (Rule 6) -> caught ✅
- GQ130 "完全不相关的随机内容" -> negation intent (Rule 6) -> caught ✅
- GQ74 "日本旅行攻略"      -> OOD topic         (Rule 7) -> caught ✅
- GQ75 "菜谱推荐"          -> OOD topic         (Rule 7) -> caught ✅
- GQ76 "健身减肥计划"      -> OOD topic         (Rule 7) -> caught ✅
- GQ77 "区块链技术投资"    -> OOD topic         (Rule 7) -> caught ✅
- GQ78 "养猫的经历"        -> OOD topic         (Rule 7) -> caught ✅
- GQ09 "人生碎片"          -> not caught (intentional: possible title match)
- GQ11 "investment strategy" -> not caught (intentional: keyword leakage)
"""

from __future__ import annotations

import os
import re
import unicodedata

# Regex for recognizable English words (≥3 letters)
_ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]{3,}")

# CJK Unified Ideographs range
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# ── Round 19 Phase 1: Intent-based noise detection ─────────────────────

# Negation-intent signals: user explicitly states irrelevance or non-existence.
# These are unambiguous — when a user says "不存在的XX" or "完全不相关",
# they are testing the system's ability to reject, not retrieving content.
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

# ── Round 19 Phase 1-D: typo-near-noise (Rule 8, plan §3.C1a) ──────────
# Mid-similarity matches against canonical typo targets are rejected as
# noise: the query *looks* like a typo of a known target but exceeded the
# correction threshold (0.85) — likely user error past the correction
# budget, not a content query. Length-diff guard avoids gating valid
# queries that contain the canonical as a substring (e.g. "Life Index 2.0").
_TYPO_NEAR_NOISE_CANONICALS: tuple[str, ...] = ("life index",)
_TYPO_NEAR_NOISE_LO: float = 0.65
_TYPO_NEAR_NOISE_HI: float = 0.85  # ≥ this → fuzzy correction handles it
_TYPO_NEAR_NOISE_MAX_LEN_DIFF: int = 2


def is_noise_query(query: str | None) -> tuple[bool, str | None]:
    """Return (is_noise, reason) for a query string.

    If the gate is disabled via LIFE_INDEX_NOISE_GATE=0, always returns
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

    # Rule 8: typo-near-noise — short ASCII query matches a canonical typo
    # target with mid similarity (past correction threshold, not unrelated).
    if not has_cjk and len(stripped) <= 20:
        try:
            from rapidfuzz import distance as _rf_distance

            q_lower = stripped.lower()
            for canonical in _TYPO_NEAR_NOISE_CANONICALS:
                if abs(len(q_lower) - len(canonical)) > _TYPO_NEAR_NOISE_MAX_LEN_DIFF:
                    continue
                sim = _rf_distance.Levenshtein.normalized_similarity(q_lower, canonical)
                if _TYPO_NEAR_NOISE_LO <= sim < _TYPO_NEAR_NOISE_HI:
                    return True, "typo_near_noise"
        except ImportError:
            pass

    return False, None
