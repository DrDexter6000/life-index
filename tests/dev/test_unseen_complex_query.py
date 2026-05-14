"""
Phase 2-B 防过拟合验证：5 条未见 complex_query。

约束要求覆盖：
1. 纯 topic 过滤
2. topic + 时间
3. topic + tag
4. 三元组合 × 2

设计原则（补丁②）：以用户意图为基准、不绑定当前图谱 schema。
断言检查"是否找到符合查询意图的 journal 条目"，而非 entity_expansion 输出。

运行方式: LIFE_INDEX_ENABLE_REALDATA_TESTS=1 python -m pytest tests/dev/test_unseen_complex_query.py -v

This test requires explicit opt-in via LIFE_INDEX_ENABLE_REALDATA_TESTS=1 env var
AND a real Life-Index data directory at ~/Documents/Life-Index. It does NOT write
real user data; it only queries the search engine against the existing index.
"""

import os
from pathlib import Path

import pytest

_REAL_DATA_DIR_STR = str(Path.home() / "Documents" / "Life-Index")
_REAL_DATA_DIR = Path(_REAL_DATA_DIR_STR)


_REALDATA_ENABLED = (
    os.environ.get("LIFE_INDEX_ENABLE_REALDATA_TESTS", "") == "1" and _REAL_DATA_DIR.is_dir()
)

pytestmark = pytest.mark.skipif(
    not _REALDATA_ENABLED,
    reason=(
        "Real-data tests disabled: set LIFE_INDEX_ENABLE_REALDATA_TESTS=1 "
        "and ensure ~/Documents/Life-Index exists"
    ),
)


def _search(query: str, level: int = 3):
    os.environ["LIFE_INDEX_DATA_DIR"] = str(_REAL_DATA_DIR)
    from tools.search_journals.core import hierarchical_search

    return hierarchical_search(query=query, level=level, semantic=False)


def _results(results: dict) -> list[dict]:
    return list(results.get("merged_results", []))


# ── 1. 纯 topic 过滤 ──────────────────────────────────────────────


def test_unseen_complex_topic_filter():
    """work相关的记录 → 应返回 topic=work 的日志"""
    results = _search("work相关的记录")
    items = _results(results)
    assert len(items) > 0, "Expected non-empty results for work topic filter"
    work_items = [r for r in items if "work" in (_to_list(r.get("topic")) or [])]
    assert len(work_items) >= 2, f"Expected >=2 work-topic results, got {len(work_items)}"


# ── 2. topic + 时间 ──────────────────────────────────────────────


def test_unseen_complex_topic_and_time():
    """2026年3月life相关的记录 → 应返回 2026-03 且 topic=life 的日志"""
    results = _search("2026年3月life相关的记录")
    items = _results(results)
    assert len(items) > 0, "Expected non-empty results for life + March 2026"
    march_items = [r for r in items if r.get("date", "").startswith("2026-03")]
    assert len(march_items) >= 2, f"Expected >=2 March 2026 results, got {len(march_items)}"
    life_items = [r for r in items if "life" in (_to_list(r.get("topic")) or [])]
    assert len(life_items) >= 1, f"Expected >=1 life-topic result, got {len(life_items)}"


# ── 3. topic + tag ──────────────────────────────────────────────


def test_unseen_complex_topic_and_tag():
    """带AI标签的创作记录 → 应返回 topic=create 且含 AI tag 的日志"""
    results = _search("带AI标签的创作记录")
    items = _results(results)
    assert len(items) > 0, "Expected non-empty results for create + AI tag"
    create_items = [r for r in items if "create" in (_to_list(r.get("topic")) or [])]
    assert len(create_items) >= 1, f"Expected >=1 create-topic result, got {len(create_items)}"
    ai_items = [
        r for r in items if any("AI" in str(tag) for tag in (_to_list(r.get("tags")) or []))
    ]
    assert len(ai_items) >= 1, f"Expected >=1 result with AI tag, got {len(ai_items)}"


# ── 4. 三元组合 1 ──────────────────────────────────────────────


def test_unseen_complex_triple_combo_1():
    """上半年关于work的记录 → 应返回 2026H1 且 topic=work 的日志"""
    results = _search("上半年关于work的记录")
    items = _results(results)
    assert len(items) > 0, "Expected non-empty results for work + 2026H1"
    h1_items = [
        r
        for r in items
        if r.get("date", "").startswith("2026-01")
        or r.get("date", "").startswith("2026-02")
        or r.get("date", "").startswith("2026-03")
        or r.get("date", "").startswith("2026-04")
        or r.get("date", "").startswith("2026-05")
        or r.get("date", "").startswith("2026-06")
    ]
    assert len(h1_items) >= 2, f"Expected >=2 H1 2026 results, got {len(h1_items)}"
    work_items = [r for r in items if "work" in (_to_list(r.get("topic")) or [])]
    assert len(work_items) >= 2, f"Expected >=2 work-topic results, got {len(work_items)}"


# ── 5. 三元组合 2 ──────────────────────────────────────────────


def test_unseen_complex_triple_combo_2():
    """四月份create相关的记录 → 应返回 2026-04 且 topic=create 的日志"""
    results = _search("四月份create相关的记录")
    items = _results(results)
    assert len(items) > 0, "Expected non-empty results for create + April 2026"
    april_items = [r for r in items if r.get("date", "").startswith("2026-04")]
    assert len(april_items) >= 1, f"Expected >=1 April 2026 result, got {len(april_items)}"
    create_items = [r for r in items if "create" in (_to_list(r.get("topic")) or [])]
    assert len(create_items) >= 1, f"Expected >=1 create-topic result, got {len(create_items)}"


def _to_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []
