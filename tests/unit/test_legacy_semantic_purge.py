"""Successor tests for semantic/vector runtime removal."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_RUNTIME_FILES = {
    "tools/lib/vector_index_simple.py",
    "tools/lib/semantic_search.py",
    "tools/lib/embedding_backends.py",
    "tools/lib/semantic_baseline.py",
    "tools/lib/semantic_status.py",
    "tools/search_journals/semantic.py",
    "tools/search_journals/semantic_pipeline.py",
}

LEGACY_RUNTIME_MODULES = {
    "tools.lib.vector_index_simple",
    "tools.lib.semantic_search",
    "tools.lib.embedding_backends",
    "tools.lib.semantic_baseline",
    "tools.lib.semantic_status",
    "tools.search_journals.semantic",
    "tools.search_journals.semantic_pipeline",
}

REMOVED_HYBRID_RANKING_SYMBOLS = {
    "reciprocal_rank_fusion",
    "merge_and_rank_results_hybrid",
    "_hybrid_priority",
    "_hybrid_backfill_score",
}

REMOVED_HYBRID_ONLY_CONSTANT_IMPORTS = {
    "FTS_WEIGHT_DEFAULT",
    "SEMANTIC_WEIGHT_DEFAULT",
}


def _module_is_blocked(module: str) -> bool:
    return module in LEGACY_RUNTIME_MODULES or any(
        module.endswith("." + blocked.rsplit(".", 1)[-1]) for blocked in LEGACY_RUNTIME_MODULES
    )


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import_from(path: Path, module: str | None, level: int) -> str | None:
    if level == 0:
        return module

    package_parts = _module_name_for_path(path).split(".")[:-1]
    if level > len(package_parts):
        return module
    base = package_parts[: len(package_parts) - level + 1]
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve_import_from(path, node.module, node.level)
            if resolved:
                modules.add(resolved)
    return modules


def _parsed_module(relative_path: str) -> ast.Module:
    path = REPO_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def test_legacy_semantic_runtime_files_are_removed() -> None:
    existing = [path for path in LEGACY_RUNTIME_FILES if (REPO_ROOT / path).exists()]

    assert existing == []


def test_core_dependencies_do_not_include_numpy() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dependencies = pyproject["project"]["dependencies"]
    assert not any(dep.lower().startswith("numpy") for dep in dependencies)

    mypy_overrides = pyproject["tool"]["mypy"].get("overrides", [])
    override_modules = {
        module
        for override in mypy_overrides
        for module in (
            override.get("module")
            if isinstance(override.get("module"), list)
            else [override.get("module")]
        )
        if isinstance(module, str)
    }
    assert "numpy" not in override_modules
    assert "numpy.*" not in override_modules

    coverage_omit = pyproject["tool"]["coverage"]["run"].get("omit", [])
    assert "tools/lib/vector_index_simple.py" not in coverage_omit


def test_active_tools_code_does_not_import_removed_runtime_modules() -> None:
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "tools").rglob("*.py")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in LEGACY_RUNTIME_FILES:
            continue
        blocked = sorted(module for module in _imported_modules(path) if _module_is_blocked(module))
        if blocked:
            offenders.append(f"{relative}: {', '.join(blocked)}")

    assert offenders == []


def test_ranking_module_does_not_expose_legacy_hybrid_fusion_engine() -> None:
    tree = _parsed_module("tools/search_journals/ranking.py")
    function_names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert function_names.isdisjoint(REMOVED_HYBRID_RANKING_SYMBOLS)


def test_ranking_module_does_not_import_hybrid_only_weight_defaults() -> None:
    tree = _parsed_module("tools/search_journals/ranking.py")
    imported_names: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 2
            and node.module == "lib.search_constants"
        ):
            imported_names.update(alias.name for alias in node.names)

    assert imported_names.isdisjoint(REMOVED_HYBRID_ONLY_CONSTANT_IMPORTS)


def test_active_search_tools_do_not_use_removed_hybrid_priority_field() -> None:
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "tools" / "search_journals").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "_hybrid_priority" in text:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []
