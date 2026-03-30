"""Test that FTS modules use logger instead of print for error handling.

This test provides regression protection for Task 1-3 of POST_AUDIT_TDD_PLAN.
Ensures fts_search.py and fts_update.py use logger for error reporting,
not print() which is unobservable in production.
"""

from pathlib import Path


def test_fts_search_has_logger_instance():
    """fts_search.py 应该有 logger 实例"""
    source = Path("tools/lib/fts_search.py").read_text(encoding="utf-8")
    assert "logger" in source, "fts_search.py 缺少 logger"
    assert "getLogger" in source, "fts_search.py 未初始化 logger"


def test_fts_update_has_logger_instance():
    """fts_update.py 应该有 logger 实例"""
    source = Path("tools/lib/fts_update.py").read_text(encoding="utf-8")
    assert "logger" in source, "fts_update.py 缺少 logger"
    assert "getLogger" in source, "fts_update.py 未初始化 logger"


def test_fts_search_no_print_in_error_handling():
    """fts_search.py 的异常处理不应使用 print()"""
    source = Path("tools/lib/fts_search.py").read_text(encoding="utf-8")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        if "except" in line and ":" in line:
            # 检查 except 块后续 5 行是否有 print(
            block = "\n".join(lines[i : i + 6])
            assert "print(" not in block, (
                f"fts_search.py line {i + 1}: except 块使用了 print()，应使用 logger"
            )


def test_fts_update_no_print_in_error_handling():
    """fts_update.py 的异常处理不应使用 print()"""
    source = Path("tools/lib/fts_update.py").read_text(encoding="utf-8")
    lines = source.split("\n")

    for i, line in enumerate(lines):
        if "except" in line and ":" in line:
            block = "\n".join(lines[i : i + 6])
            assert "print(" not in block, (
                f"fts_update.py line {i + 1}: except 块使用了 print()，应使用 logger"
            )


def test_fts_search_exception_handler_calls_logger():
    """fts_search.py 的异常处理应调用 logger"""
    source = Path("tools/lib/fts_search.py").read_text(encoding="utf-8")
    lines = source.split("\n")

    found_logger_call = False
    for i, line in enumerate(lines):
        if "except" in line and ":" in line:
            block = "\n".join(lines[i : i + 6])
            if "logger." in block:
                found_logger_call = True
                break

    assert found_logger_call, (
        "fts_search.py 的 except 块未调用 logger（应为 logger.error 或 logger.warning）"
    )


def test_fts_update_exception_handler_calls_logger():
    """fts_update.py 的异常处理应调用 logger"""
    source = Path("tools/lib/fts_update.py").read_text(encoding="utf-8")
    lines = source.split("\n")

    found_logger_call = False
    for i, line in enumerate(lines):
        if "except" in line and ":" in line:
            block = "\n".join(lines[i : i + 6])
            if "logger." in block:
                found_logger_call = True
                break

    assert found_logger_call, (
        "fts_update.py 的 except 块未调用 logger（应为 logger.error 或 logger.warning）"
    )
