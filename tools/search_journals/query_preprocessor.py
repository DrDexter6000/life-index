"""Round 11 — Deterministic Query Preprocessor.

Pure-rule query understanding layer that sits between raw user input
and the retrieval pipeline. No LLM, no non-determinism.

Outputs a structured SearchPlan for consumption by the search pipeline
and by callers (Agent, Web, test harness).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from .query_types import DateRange, IntentType, QueryMode, SearchPlan

# Chinese numerals for month parsing
_CN_NUMERALS: dict[str, int] = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}

# ── Time expression patterns (ordered by specificity) ──────────────────

_TIME_PATTERNS: list[re.Pattern[str]] = [
    # Absolute dates (more specific first)
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?"),
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    re.compile(r"(\d{4})年(\d{1,2})月"),
    re.compile(r"(\d{4})-(\d{2})"),
    # 今年X月 (e.g. "今年一月")
    re.compile(r"今年([一二两三四五六七八九十十一十二])月"),
    # 去年X月 (e.g. "去年一月")
    re.compile(r"去年([一二两三四五六七八九十十一十二])月"),
    # Year+season combos (more specific than standalone season)
    re.compile(r"去年(的)?(春天|夏天|秋天|冬天)"),
    # Seasons
    re.compile(r"(春天|夏天|秋天|冬天)"),
    # Chinese month range (e.g. "三月下旬到四月")
    re.compile(r"([一二两三四五六七八九十十一十二])月下旬到([一二两三四五六七八九十十一十二])月"),
    # Chinese month parts (e.g. "三月初", "三月下旬", "三月底")
    re.compile(r"([一二两三四五六七八九十十一十二])月初"),
    re.compile(r"([一二两三四五六七八九十十一十二])月中旬"),
    re.compile(r"([一二两三四五六七八九十十一十二])月下旬"),
    re.compile(r"([一二两三四五六七八九十十一十二])月底"),
    re.compile(r"(\d{1,2})月底"),
    # Year halves
    re.compile(r"(上半年|下半年)"),
    # Week expressions
    re.compile(r"(上周|上个星期|这周|这个星期|本周)"),
    # Month expressions
    re.compile(r"(这个月|本月)"),
    # Month-Day without year (e.g. "3月15日", "三月十五号")
    re.compile(r"(\d{1,2})月(\d{1,2})[日号]?"),
    # Chinese month names (e.g. "三月份", "三月")
    re.compile(r"([一二两三四五六七八九十十一十二])月份?"),
    # Relative expressions
    re.compile(r"过去(\d+)天"),
    re.compile(r"过去(\d+)周"),
    re.compile(r"过去(\d+)个?月"),
    re.compile(r"过去一年"),
    re.compile(r"最近一周"),
    re.compile(r"过去一周"),
    re.compile(r"上个月"),
    re.compile(r"上个?月"),
    re.compile(r"去年这个时候"),
    re.compile(r"去年"),
    re.compile(r"今年"),
    re.compile(r"最近"),
    re.compile(r"(\d{1,2})月份?"),
    re.compile(r"(\d+)天前"),
    re.compile(r"(\d+)周前"),
]

# ── Intent signal words ────────────────────────────────────────────────

_COUNT_SIGNALS = ["多少次", "多久", "几次", "有没有变多", "频率", "多少个"]
_COMPARE_SIGNALS = ["哪个多", "对比", "比较", "vs", "区别", "差异"]
_SUMMARIZE_SIGNALS = ["进展", "总结", "概述", "什么变化", "趋势", "梳理"]
_QUESTION_WORDS = {"什么", "哪些", "怎么", "怎么样", "有没有", "是否", "如何", "多少", "为什么"}
_PRONOUNS = {
    "我",
    "你",
    "他",
    "她",
    "它",
    "我们",
    "你们",
    "他们",
    "的",
    "了",
    "吗",
    "呢",
    "啊",
    "吧",
    "呀",
    "么",
}

# ── Topic keyword mapping ─────────────────────────────────────────────

_TOPIC_KEYWORD_MAP: dict[str, list[str]] = {
    "health": ["健康", "身体", "运动", "锻炼", "睡眠", "饮食", "看病", "医院", "health"],
    "work": ["工作", "职业", "上班", "项目", "任务", "会议", "部署", "团队", "work"],
    "learn": ["学习", "读书", "课程", "培训", "技能", "知识", "learn"],
    "relation": ["家人", "家庭", "父母", "朋友", "关系", "社交", "聚会", "relation"],
    "think": ["思考", "反思", "感悟", "想法", "领悟", "哲学", "think"],
    "create": ["创作", "写作", "编程", "代码", "设计", "音乐", "create"],
    "life": ["生活", "日常", "开心", "焦虑", "快乐", "悲伤", "幸福", "旅行", "life"],
}


def normalize_query(query: str) -> str:
    """Normalize raw query: trim, strip trailing punctuation, convert fullwidth digits."""
    if not query:
        return ""
    result = query.strip()
    # Remove trailing Chinese/English punctuation
    _TRAILING_PUNCT_RE = re.compile(r"[？！。，、；：\u201c\u201d\u2018\u2019）》\s]+$")
    result = _TRAILING_PUNCT_RE.sub("", result)
    result = result.strip()
    # Fullwidth digits to halfwidth
    result = result.translate(
        str.maketrans(
            "０１２３４５６７８９",
            "0123456789",
        )
    )
    return result


def extract_time_expression(query: str) -> str | None:
    """Extract the first matching time expression from a query string.

    Tries existing Arabic digit patterns first, then falls back to
    Chinese time expression normalization (Round 13 Phase 3).
    """
    if not query:
        return None
    for pattern in _TIME_PATTERNS:
        m = pattern.search(query)
        if m:
            return m.group(0)
    # Fallback: Chinese time expression mapping (一个月, 半年, 两周, etc.)
    from .chinese_time_units import normalize_chinese_time

    return normalize_chinese_time(query)


def parse_time_range(  # noqa: C901
    expr: str | None, *, reference_date: date | None = None
) -> DateRange | None:
    """Parse a Chinese time expression into a concrete date range.

    Args:
        expr: Time expression string (e.g. "过去60天", "上个月").
        reference_date: Anchor date for relative calculations. Defaults to today.

    Returns:
        DateRange with since/until/source, or None if expression is not recognized.
    """
    if not expr:
        return None

    ref = reference_date or date.today()

    # ── Absolute date formats (most specific first) ───────────────────────

    # YYYY年MM月DD日 / YYYY年MM月DD号
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})[日号]?", expr)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        since = date(year, month, day)
        return DateRange(
            since=since.isoformat(), until=since.isoformat(), source="absolute_date_parse"
        )

    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", expr)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        since = date(year, month, day)
        return DateRange(
            since=since.isoformat(), until=since.isoformat(), source="absolute_date_parse"
        )

    # YYYY年MM月 (full month)
    m = re.match(r"(\d{4})年(\d{1,2})月$", expr)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        since = date(year, month, 1)
        if month == 12:
            until = date(year, 12, 31)
        else:
            until = date(year, month + 1, 1) - timedelta(days=1)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="absolute_date_parse"
        )

    # YYYY-MM (month shorthand, e.g. "2026-01")
    m = re.match(r"(\d{4})-(\d{2})$", expr)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        since = date(year, month, 1)
        if month == 12:
            until = date(year, 12, 31)
        else:
            until = date(year, month + 1, 1) - timedelta(days=1)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="absolute_date_parse"
        )

    # 今年X月 (e.g. "今年一月")
    m = re.match(r"今年([一二两三四五六七八九十十一十二])月", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 1)
            if cn_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="relative_time_parse",
            )

    # 去年X月 (e.g. "去年一月")
    m = re.match(r"去年([一二两三四五六七八九十十一十二])月", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year - 1
            since = date(year, cn_month, 1)
            if cn_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="relative_time_parse",
            )

    # 去年X季 (e.g. "去年冬天", "去年的冬天")
    m = re.match(r"去年(的)?(春天|夏天|秋天|冬天)", expr)
    if m:
        season = m.group(2)
        season_months = {
            "春天": (3, 5),
            "夏天": (6, 8),
            "秋天": (9, 11),
            "冬天": (12, 2),
        }
        start_month, end_month = season_months[season]
        year = ref.year - 1
        if start_month <= end_month:
            since = date(year, start_month, 1)
            if end_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, end_month + 1, 1) - timedelta(days=1)
        else:
            # Winter spans year boundary (Dec - Feb)
            since = date(year - 1, start_month, 1)
            until = date(year, end_month + 1, 1) - timedelta(days=1)
        return DateRange(
            since=since.isoformat(),
            until=until.isoformat(),
            source="relative_time_parse",
        )

    # Seasons (春天, 夏天, 秋天, 冬天)
    season_months = {
        "春天": (3, 5),
        "夏天": (6, 8),
        "秋天": (9, 11),
        "冬天": (12, 2),
    }
    for season, (start_month, end_month) in season_months.items():
        if season in expr:
            year = ref.year
            if start_month <= end_month:
                since = date(year, start_month, 1)
                if end_month == 12:
                    until = date(year, 12, 31)
                else:
                    until = date(year, end_month + 1, 1) - timedelta(days=1)
            else:
                # Winter spans year boundary (Dec - Feb)
                since = date(year - 1, start_month, 1)
                until = date(year, end_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="relative_time_parse",
            )

    # Chinese month start (e.g. "三月初")
    m = re.match(r"([一二两三四五六七八九十十一十二])月初", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 1)
            until = date(year, cn_month, 10)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Chinese month range (e.g. "三月下旬到四月")
    m = re.match(
        r"([一二两三四五六七八九十十一十二])月下旬到([一二两三四五六七八九十十一十二])月", expr
    )
    if m:
        cn_start_month = _CN_NUMERALS.get(m.group(1))
        cn_end_month = _CN_NUMERALS.get(m.group(2))
        if cn_start_month and cn_end_month:
            year = ref.year
            since = date(year, cn_start_month, 15)
            if cn_end_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_end_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Chinese month mid (e.g. "三月中旬")
    m = re.match(r"([一二两三四五六七八九十十一十二])月中旬", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 11)
            until = date(year, cn_month, 20)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Chinese month late (e.g. "三月下旬")
    m = re.match(r"([一二两三四五六七八九十十一十二])月下旬", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 15)
            if cn_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Chinese month end (e.g. "三月底")
    m = re.match(r"([一二两三四五六七八九十十一十二])月底", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 25)
            if cn_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Arabic month end (e.g. "4月底")
    m = re.match(r"(\d{1,2})月底", expr)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            year = ref.year
            since = date(year, month, 25)
            if month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # Year halves (上半年 / 下半年)
    if expr == "上半年":
        return DateRange(
            since=f"{ref.year}-01-01",
            until=f"{ref.year}-06-30",
            source="relative_time_parse",
        )
    if expr == "下半年":
        return DateRange(
            since=f"{ref.year}-07-01",
            until=f"{ref.year}-12-31",
            source="relative_time_parse",
        )

    # Week expressions (上周 / 这周 / 本周)
    if expr in ("上周", "上个星期"):
        # Previous full week (Mon-Sun)
        this_monday = ref - timedelta(days=ref.weekday())
        since = this_monday - timedelta(weeks=1)
        until = this_monday - timedelta(days=1)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="relative_time_parse"
        )
    if expr in ("这周", "这个星期", "本周"):
        since = ref - timedelta(days=ref.weekday())  # Monday of current week
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # Month expressions (这个月 / 本月)
    if expr in ("这个月", "本月"):
        since = date(ref.year, ref.month, 1)
        if ref.month == 12:
            until = date(ref.year, 12, 31)
        else:
            until = date(ref.year, ref.month + 1, 1) - timedelta(days=1)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="relative_time_parse"
        )

    # Month-Day without year (e.g. "3月15日", "3月15号")
    m = re.match(r"(\d{1,2})月(\d{1,2})[日号]?", expr)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        if not (1 <= month <= 12):
            return None
        year = ref.year
        try:
            target = date(year, month, day)
            if target > ref:
                target = date(year - 1, month, day)
            return DateRange(
                since=target.isoformat(), until=target.isoformat(), source="absolute_date_parse"
            )
        except ValueError:
            return None

    # Chinese month names (e.g. "三月份", "三月")
    m = re.match(r"([一二两三四五六七八九十十一十二])月份?$", expr)
    if m:
        cn_month = _CN_NUMERALS.get(m.group(1))
        if cn_month:
            year = ref.year
            since = date(year, cn_month, 1)
            if cn_month == 12:
                until = date(year, 12, 31)
            else:
                until = date(year, cn_month + 1, 1) - timedelta(days=1)
            return DateRange(
                since=since.isoformat(),
                until=until.isoformat(),
                source="absolute_date_parse",
            )

    # ── Relative expressions ─────────────────────────────────────────────

    # 过去N天
    m = re.match(r"过去(\d+)天", expr)
    if m:
        n = int(m.group(1))
        since = ref - timedelta(days=n)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 过去N周
    m = re.match(r"过去(\d+)周", expr)
    if m:
        n = int(m.group(1))
        since = ref - timedelta(weeks=n)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 过去N.N个月 (fractional months, e.g. from "半个月" → "过去0.5个月")
    m = re.match(r"过去(\d+\.\d+)个?月", expr)
    if m:
        n_months = float(m.group(1))
        since = ref - timedelta(days=int(n_months * 30))
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 过去N个月
    m = re.match(r"过去(\d+)个?月", expr)
    if m:
        n = int(m.group(1))
        since = _subtract_months(ref, n)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 过去一年
    if "过去一年" in expr:
        since = ref - timedelta(days=365)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 最近一周
    if "最近一周" in expr:
        since = ref - timedelta(weeks=1)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 过去一周
    if "过去一周" in expr:
        since = ref - timedelta(weeks=1)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # 上个月
    if "上个" in expr and "月" in expr:
        first_of_this_month = ref.replace(day=1)
        last_of_prev = first_of_this_month - timedelta(days=1)
        first_of_prev = last_of_prev.replace(day=1)
        return DateRange(
            since=first_of_prev.isoformat(),
            until=last_of_prev.isoformat(),
            source="relative_time_parse",
        )

    # 去年这个时候
    if "去年这个时候" in expr:
        # Roughly same period last year: same month ±15 days
        since = ref.replace(year=ref.year - 1) - timedelta(days=15)
        until = ref.replace(year=ref.year - 1) + timedelta(days=15)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="relative_time_parse"
        )

    # 去年
    if expr == "去年" or (expr.startswith("去年") and "这个时候" not in expr):
        return DateRange(
            since=f"{ref.year - 1}-01-01",
            until=f"{ref.year - 1}-12-31",
            source="relative_time_parse",
        )

    # 今年
    if expr == "今年":
        return DateRange(
            since=f"{ref.year}-01-01", until=ref.isoformat(), source="relative_time_parse"
        )

    # 最近
    if expr == "最近":
        since = ref - timedelta(days=30)
        return DateRange(
            since=since.isoformat(), until=ref.isoformat(), source="relative_time_parse"
        )

    # N月份
    m = re.match(r"(\d{1,2})月份?", expr)
    if m:
        month = int(m.group(1))
        if not (1 <= month <= 12):
            return None
        year = ref.year
        # If month > current month, assume last year
        if month > ref.month:
            year -= 1
        since = date(year, month, 1)
        if month == 12:
            until = date(year, 12, 31)
        else:
            until = date(year, month + 1, 1) - timedelta(days=1)
        return DateRange(
            since=since.isoformat(), until=until.isoformat(), source="relative_time_parse"
        )

    # N天前
    m = re.match(r"(\d+)天前", expr)
    if m:
        n = int(m.group(1))
        target = ref - timedelta(days=n)
        return DateRange(
            since=target.isoformat(), until=target.isoformat(), source="relative_time_parse"
        )

    # N周前
    m = re.match(r"(\d+)周前", expr)
    if m:
        n = int(m.group(1))
        target = ref - timedelta(weeks=n)
        return DateRange(
            since=target.isoformat(), until=target.isoformat(), source="relative_time_parse"
        )

    return None


def _subtract_months(d: date, months: int) -> date:
    """Subtract N months from a date, clamping day to max of target month."""
    month = d.month - months
    year = d.year
    while month <= 0:
        month += 12
        year -= 1
    max_day = (date(year, month + 1, 1) - timedelta(days=1)).day if month < 12 else 31
    return date(year, month, min(d.day, max_day))


def classify_intent(query: str) -> IntentType:
    """Classify query intent using signal word matching.

    Priority: count > compare > summarize > recall (default).
    """
    if not query:
        return IntentType.UNKNOWN

    for signal in _COUNT_SIGNALS:
        if signal in query:
            return IntentType.COUNT

    for signal in _COMPARE_SIGNALS:
        if signal in query:
            return IntentType.COMPARE

    for signal in _SUMMARIZE_SIGNALS:
        if signal in query:
            return IntentType.SUMMARIZE

    return IntentType.RECALL


def extract_keywords(query: str, *, time_expr: str | None = None) -> list[str]:
    """Extract meaningful keywords from query, removing time expr and function words."""
    if not query:
        return []

    text = query
    # Remove time expression portion
    if time_expr and time_expr in text:
        text = text.replace(time_expr, "")

    # Remove common question words, pronouns, particles
    # Use simple tokenization by splitting on whitespace or extracting CJK segments
    tokens = _tokenize(text)

    # Filter out stop words (Chinese question words, pronouns, particles)
    filtered = [
        t
        for t in tokens
        if t not in _QUESTION_WORDS
        and t not in _PRONOUNS
        and len(t) >= 1
        and not re.match(r"^[\d]+$", t)  # pure numbers
    ]

    # Phase 4 T4.4: Filter English stopwords from ASCII tokens
    from .stopwords import load_stopwords as _load_sw

    en_stopwords = _load_sw("en")
    if en_stopwords:
        filtered = [t for t in filtered if not (t.isascii() and t.lower() in en_stopwords)]

    # Round 13 Phase 3: Filter Chinese stopwords from CJK tokens
    zh_stopwords = _load_sw("zh")
    if zh_stopwords:
        filtered = [t for t in filtered if t not in zh_stopwords]

    return filtered if filtered else [query.strip()]


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: split on whitespace, and extract CJK character sequences."""
    # First split on whitespace
    parts = text.split()
    if len(parts) > 1:
        return [p for p in parts if p.strip()]

    # Single CJK string: try jieba if available, else character-level extraction
    try:
        import jieba

        return [t for t in jieba.cut(text) if t.strip()]
    except ImportError:
        # Fallback: extract 2+ char CJK segments
        return re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text)


def extract_topic_hints(query: str) -> list[str]:
    """Extract topic hints from query based on keyword matching."""
    if not query:
        return []

    hints: list[str] = []
    seen: set[str] = set()
    for topic, keywords in _TOPIC_KEYWORD_MAP.items():
        for kw in keywords:
            if kw in query and topic not in seen:
                hints.append(topic)
                seen.add(topic)
                break

    return hints


def classify_query_mode(query: str) -> QueryMode:
    """Classify whether the query is keyword-style or natural language."""
    if not query:
        return QueryMode.KEYWORD

    trimmed = query.strip()

    # Short queries with no punctuation → keyword
    if len(trimmed) <= 5 and not re.search(r"[？！。，、？]", trimmed):
        return QueryMode.KEYWORD

    # Space-separated tokens with no CJK → keyword
    parts = trimmed.split()
    if len(parts) >= 2 and all(len(p) <= 10 for p in parts):
        has_cjk = any(re.search(r"[\u4e00-\u9fff]", p) for p in parts)
        if not has_cjk or (len(parts) >= 2 and not re.search(r"[？！。，]", trimmed)):
            return QueryMode.KEYWORD

    # Contains question marks or question words → natural language
    if re.search(r"[？！]", trimmed) or any(qw in trimmed for qw in _QUESTION_WORDS):
        return QueryMode.NATURAL_LANGUAGE

    # Long CJK text without spaces → natural language
    if re.search(r"[\u4e00-\u9fff]", trimmed) and len(trimmed) > 5:
        return QueryMode.NATURAL_LANGUAGE

    return QueryMode.MIXED


def build_search_plan(query: str, *, reference_date: date | None = None) -> SearchPlan:
    """Build a complete SearchPlan from a raw query string.

    Orchestrates all sub-functions: normalize → extract time → classify intent
    → extract keywords → extract topic hints → classify mode → assemble.
    """
    if not query or not query.strip():
        return SearchPlan(
            raw_query=query or "",
            normalized_query="",
            intent_type=IntentType.UNKNOWN,
            query_mode=QueryMode.KEYWORD,
            keywords=[],
            expanded_query="",
        )

    normalized = normalize_query(query)
    time_expr = extract_time_expression(query)
    date_range = parse_time_range(time_expr, reference_date=reference_date) if time_expr else None
    intent = classify_intent(query)
    keywords = extract_keywords(query, time_expr=time_expr)
    topic_hints = extract_topic_hints(query)

    # Phase 2-B: For topic-only queries like "work相关的日志", drop generic nouns
    # that are part of the query template rather than content filters.
    original_keywords = keywords[:]
    _GENERIC_NOUNS = {"日志", "记录", "笔记"}
    if topic_hints:
        non_topic_keywords = [kw for kw in keywords if kw not in topic_hints]
        particles = {"相关", "的", "有关", "关于", "年", "月"}
        meaningful = [
            kw for kw in non_topic_keywords if kw not in _GENERIC_NOUNS and kw not in particles
        ]
        if not meaningful:
            keywords = [kw for kw in keywords if kw not in _GENERIC_NOUNS and kw not in particles]

    query_mode = classify_query_mode(query)

    # Only use keyword-joined expanded_query when keywords were actually modified
    if keywords != original_keywords:
        expanded = " ".join(keywords) if keywords else normalized
    else:
        expanded = normalized

    return SearchPlan(
        raw_query=query,
        normalized_query=normalized,
        intent_type=intent,
        query_mode=query_mode,
        keywords=keywords,
        date_range=date_range,
        topic_hints=topic_hints,
        entity_hints_used=[],
        expanded_query=expanded,
        pipelines={"keyword": True, "semantic": True},
    )
