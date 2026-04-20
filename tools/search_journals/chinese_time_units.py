"""Chinese time expression normalization — pure rule-based, no LLM.

Round 13 Phase 3 T3.1: Maps Chinese time expressions like "一个月", "半年",
"两周" to normalized forms parseable by parse_time_range() in query_preprocessor.

Order of _TIME_EXPR_MAP matters: more specific patterns must come before
less specific ones. "两个月" must match before "一个月" catches it.
"""

from __future__ import annotations

import re

# ── Chinese numeral mapping ──────────────────────────────────────────

_DIGIT_MAP: dict[str, int] = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "贰": 2,
    "两": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}

# ── Public API ───────────────────────────────────────────────────────


def chinese_numeral_to_int(text: str) -> int | None:
    """Convert a Chinese numeral string to an integer.

    Handles:
      - Single chars: "一" → 1, "两" → 2, "十" → 10
      - Compound: "十二" → 12, "二十" → 20, "三十一" → 31

    Returns None if input is not a recognized Chinese numeral.
    """
    if not text:
        return None

    # Single character lookup
    if text in _DIGIT_MAP:
        return _DIGIT_MAP[text]

    # "十" → 10
    if text == "十":
        return 10

    # Compound numbers with 十/拾: e.g. "十二"=12, "二十"=20, "三十一"=31
    if "十" in text or "拾" in text:
        parts = re.split(r"[十拾]", text, maxsplit=1)
        tens_str = parts[0]
        ones_str = parts[1] if len(parts) > 1 else ""

        tens = _DIGIT_MAP.get(tens_str, 1) if tens_str else 1  # "十二" → 10+2
        ones = _DIGIT_MAP.get(ones_str, 0) if ones_str else 0
        return tens * 10 + ones

    # Fallback: try each character as a digit (e.g. "三五" → 35)
    total = 0
    for ch in text:
        if ch in _DIGIT_MAP:
            total = total * 10 + _DIGIT_MAP[ch]
        else:
            return None
    return total if total > 0 else None


# ── Time expression patterns (ordered by specificity) ────────────────
# CRITICAL: More specific patterns must come BEFORE less specific ones.
# "两个月" must be checked before "一个月". "两周" before "一周".

_TIME_EXPR_MAP: list[tuple[re.Pattern[str], str]] = [
    # Fractional months (most specific — must come before bare 月)
    (re.compile(r"大半个?月"), "过去0.7个月"),
    (re.compile(r"半个?月"), "过去0.5个月"),
    # Half year
    (re.compile(r"半年"), "过去6个月"),
    # Months with explicit numerals (两 > 三 > 一, to prevent "一个月" eating "两个月")
    (re.compile(r"两个?月"), "过去2个月"),
    (re.compile(r"三个?月"), "过去3个月"),
    (re.compile(r"一个?月"), "过去1个月"),
    # Weeks — numeral required to avoid matching bare 周/天/年 in random text
    (re.compile(r"两周"), "过去2周"),
    (re.compile(r"一周"), "过去1周"),
    # Years
    (re.compile(r"两年"), "过去2年"),
    (re.compile(r"一年"), "过去1年"),
    # Days
    (re.compile(r"两天"), "过去2天"),
    (re.compile(r"一天"), "过去1天"),
]


def normalize_chinese_time(text: str) -> str | None:
    """Try to find and normalize a Chinese time expression in text.

    Returns a normalized string like "过去1个月" that parse_time_range()
    can handle, or None if no time expression is found.
    """
    if not text:
        return None
    for pattern, replacement in _TIME_EXPR_MAP:
        if pattern.search(text):
            return replacement
    return None
