"""Test that exception handlers log errors properly."""

import logging
from pathlib import Path


def test_main_py_has_logger():
    """__main__.py 应该有 logger 实例"""
    source = Path("tools/write_journal/__main__.py").read_text(encoding="utf-8")
    assert "logger" in source, "__main__.py 缺少 logger"
    assert "getLogger" in source or "get_logger" in source, (
        "__main__.py 未初始化 logger"
    )


def test_prepare_py_has_logger():
    """prepare.py 应该有 logger 实例"""
    source = Path("tools/write_journal/prepare.py").read_text(encoding="utf-8")
    assert "logger" in source, "prepare.py 缺少 logger"
    assert "getLogger" in source or "get_logger" in source, "prepare.py 未初始化 logger"


def test_main_exception_handler_logs():
    """__main__.py 的 Exception handler 应该调用 logger"""
    source = Path("tools/write_journal/__main__.py").read_text(encoding="utf-8")
    # 检查 except Exception 块附近是否有 logger 调用
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if "except Exception" in line:
            # 检查后续 3 行是否有 logger 调用
            block = "\n".join(lines[i : i + 4])
            assert "logger." in block, (
                f"line {i + 1}: except Exception 块缺少 logger 调用"
            )


def test_prepare_exception_handler_logs():
    """prepare.py 的 LLM exception handler 应该调用 logger"""
    source = Path("tools/write_journal/prepare.py").read_text(encoding="utf-8")
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if "except Exception" in line:
            block = "\n".join(lines[i : i + 6])
            assert "logger." in block, (
                f"line {i + 1}: except Exception 块缺少 logger 调用"
            )
