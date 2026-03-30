"""Test that production code uses modern typing (Python 3.11+)."""

import ast
from pathlib import Path


PRODUCTION_FILES = [
    "tools/search_journals/keyword_pipeline.py",
    "tools/lib/schema.py",
]

OLD_TYPING_NAMES = {"Dict", "List", "Tuple", "Optional", "Set", "FrozenSet"}


def test_keyword_pipeline_no_old_style_typing():
    """keyword_pipeline.py 不应 import typing 模块的旧式泛型"""
    source = Path("tools/search_journals/keyword_pipeline.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            imported_names = {alias.name for alias in node.names}
            old_names_found = imported_names & OLD_TYPING_NAMES
            assert not old_names_found, (
                f"tools/search_journals/keyword_pipeline.py:{node.lineno} imports old-style typing: "
                f"{old_names_found}. Use built-in generics instead."
            )


def test_schema_no_old_style_typing():
    """schema.py 不应 import typing 模块的旧式泛型"""
    source = Path("tools/lib/schema.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            imported_names = {alias.name for alias in node.names}
            old_names_found = imported_names & OLD_TYPING_NAMES
            assert not old_names_found, (
                f"tools/lib/schema.py:{node.lineno} imports old-style typing: "
                f"{old_names_found}. Use built-in generics instead."
            )


def test_schema_public_functions_have_return_types():
    """schema.py 的所有公开函数必须有返回类型注解"""
    import inspect
    from tools.lib import schema

    for name, func in inspect.getmembers(schema, inspect.isfunction):
        if name.startswith("_"):
            continue
        hints = func.__annotations__
        assert "return" in hints, f"schema.{name}() 缺少返回类型注解"
