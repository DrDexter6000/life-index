#!/usr/bin/env python3
"""Fail when deterministic tools import or own in-tool LLM plumbing."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDED_TOOL_DIRS = {
    "_optional",
    "dev",
    "eval",
}

DISALLOWED_MODULES = {
    "anthropic",
    "llm_extract",
    "openai",
    "tools._optional.llm_extract",
    "tools.lib.llm_extract",
}

DISALLOWED_FROM_NAMES = {
    ("tools.lib.config", "get_llm_config"): "tools.lib.config.get_llm_config",
}

SEARCH_OWNERSHIP_ROOTS = {
    ("tools", "search_journals"),
    ("tools", "smart_search"),
}

FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS = {
    "LLMClient",
    "llm_client",
    "_llm",
    "_call_llm",
    "post_filter_and_summarize",
    "synthesize_answer",
    "_build_synthesis_prompt",
    "_evidence_to_synthesis_context",
    "_parse_synthesis_response",
    "_apply_trust_gate",
    "_compute_transparency",
    "_build_rewrite_prompt",
    "_parse_rewrite_response",
    "_build_filter_prompt",
    "_parse_filter_response",
    "_citation_matches_query",
    "_normalized_tokens",
}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    import_name: str


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    parts = rel.parts
    return len(parts) >= 2 and parts[0] == "tools" and parts[1] in DEFAULT_EXCLUDED_TOOL_DIRS


def _iter_tool_files(root: Path) -> Iterable[Path]:
    tools_root = root / "tools"
    if not tools_root.exists():
        return []
    return (
        path
        for path in sorted(tools_root.rglob("*.py"))
        if "__pycache__" not in path.parts and not _is_excluded(path, root)
    )


def _module_is_disallowed(module: str) -> str | None:
    for disallowed in DISALLOWED_MODULES:
        if module == disallowed or module.startswith(f"{disallowed}."):
            return disallowed
    return None


def _scan_file(path: Path, root: Path) -> list[Violation]:
    rel = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                disallowed = _module_is_disallowed(alias.name)
                if disallowed is not None:
                    violations.append(Violation(rel, node.lineno, disallowed))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            disallowed = _module_is_disallowed(module)
            if disallowed is not None:
                violations.append(Violation(rel, node.lineno, disallowed))
            for alias in node.names:
                explicit = DISALLOWED_FROM_NAMES.get((module, alias.name))
                if explicit is not None:
                    violations.append(Violation(rel, node.lineno, explicit))
    rel_parts = path.relative_to(root).parts
    if tuple(rel_parts[:2]) in SEARCH_OWNERSHIP_ROOTS:
        owned: set[tuple[int, str]] = set()
        for node in ast.walk(tree):
            symbol: str | None = None
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = node.name
            elif isinstance(node, ast.arg):
                symbol = node.arg
            elif isinstance(node, ast.Name):
                symbol = node.id
            elif isinstance(node, ast.Attribute):
                symbol = node.attr
            if symbol in FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS:
                owned.add((getattr(node, "lineno", 0), symbol))
        violations.extend(Violation(rel, line, symbol) for line, symbol in sorted(owned))
    return violations


def scan_tree(root: Path | str) -> list[Violation]:
    resolved_root = Path(root).resolve()
    violations: list[Violation] = []
    for path in _iter_tool_files(resolved_root):
        violations.extend(_scan_file(path, resolved_root))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check deterministic tools for disallowed LLM imports and ownership."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root to scan.",
    )
    args = parser.parse_args()

    violations = scan_tree(args.root)
    if violations:
        print("L2 no-LLM check failed:")
        for violation in violations:
            print(f"{violation.path}:{violation.line}: {violation.import_name}")
        return 1
    print("L2 no-LLM check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
