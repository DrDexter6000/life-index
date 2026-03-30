"""Test that semantic_pipeline.py does not import unittest.mock."""

import ast
from pathlib import Path


def test_semantic_pipeline_does_not_import_mock():
    """生产代码不得 import unittest.mock"""
    source_file = Path("tools/search_journals/semantic_pipeline.py")
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "unittest.mock", (
                f"生产代码 semantic_pipeline.py line {node.lineno} "
                f"不得 import unittest.mock"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "unittest.mock" not in alias.name, (
                    f"生产代码 semantic_pipeline.py line {node.lineno} "
                    f"不得 import unittest.mock"
                )


def test_no_isinstance_mock_check():
    """生产代码不应使用 isinstance(..., Mock) 检查"""
    source_file = Path("tools/search_journals/semantic_pipeline.py")
    source = source_file.read_text(encoding="utf-8")

    # 检查代码中是否包含 isinstance(*, Mock) 模式
    assert "isinstance" not in source or "Mock" not in source, (
        "生产代码 semantic_pipeline.py 不得使用 isinstance(..., Mock) 检查"
    )
