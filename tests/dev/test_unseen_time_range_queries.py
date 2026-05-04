"""
Round 18 Phase 2-A — 5 条未见 time_range query 防过拟合验证.

这些 query 使用的时间表达未在原始 _TIME_PATTERNS 中覆盖，
用于验证 query_preprocessor 的修复是 generalized 而非 memorized.
"""

import pytest
from pathlib import Path

UNSEEN_QUERIES = [
    # (query, expected_expr_substring, min_results_found)
    ("二月底的日志", "二月底", 1),
    ("上半年的记录", "上半年", 1),
    ("3月14日的记录", "3月14日", 1),
    ("4月底的睡觉", "4月底", 1),
    ("上周的行程", "上周", 1),
]


def test_all_unseen_queries_pass() -> None:
    import os
    import sys

    DATA_DIR = Path(r"C:\Users\17865\Documents\Life-Index")
    if not DATA_DIR.exists():
        pytest.skip("Real user data dir not available")

    # Ensure fresh imports inside test body to avoid polluting sys.modules
    # during pytest collection for other test files.
    for m in list(sys.modules):
        if "tools" in m:
            del sys.modules[m]

    os.environ["LIFE_INDEX_DATA_DIR"] = str(DATA_DIR)

    from tools.search_journals.query_preprocessor import (
        extract_time_expression,
        parse_time_range,
    )
    from tools.search_journals.core import hierarchical_search

    failures = []
    for query, expected_expr, min_found in UNSEEN_QUERIES:
        expr = extract_time_expression(query)
        dr = parse_time_range(expr)
        sr = hierarchical_search(query=query, semantic=False)
        found = sr["total_found"]

        ok = expr is not None and expected_expr in expr and dr is not None and found >= min_found
        if not ok:
            failures.append(f"  {query}: expr={expr!r}, range={dr}, found={found}")

    if failures:
        raise AssertionError(
            f"{len(failures)} / {len(UNSEEN_QUERIES)} unseen queries failed:\n"
            + "\n".join(failures)
        )


if __name__ == "__main__":
    test_all_unseen_queries_pass()
    print(f"All {len(UNSEEN_QUERIES)} unseen time_range queries passed.")
