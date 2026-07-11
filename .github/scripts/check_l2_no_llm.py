#!/usr/bin/env python3
"""Fail when deterministic tools import or own in-tool LLM plumbing."""

from __future__ import annotations

import argparse
import ast
import re
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
    "cohere",
    "fireworks",
    "google.genai",
    "google.generativeai",
    "groq",
    "llm_extract",
    "litellm",
    "mistralai",
    "ollama",
    "openai",
    "together",
    "tools._optional.llm_extract",
    "tools.eval.llm_client",
    "tools.lib.llm_extract",
    "vertexai",
}

DISALLOWED_FROM_NAMES = {
    ("tools.lib.config", "get_llm_config"): "tools.lib.config.get_llm_config",
}

SEARCH_OWNERSHIP_ROOTS = {
    ("tools", "search_journals"),
    ("tools", "smart_search"),
}

LEGACY_LLM_OWNERSHIP_NAMES = {
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

PROVIDER_CALL_METHODS = {
    "chat",
    "complete",
    "completion",
    "generate",
    "invoke",
}

PROVIDER_CREATE_CHAINS = {
    ("chat", "completions", "create"),
    ("messages", "create"),
    ("responses", "create"),
}

PROVIDER_CHAIN_OWNER_NAMES = {
    "backend",
    "client",
    "sdk",
}

PROVIDER_IDENTIFIER_TOKENS = {
    "anthropic",
    "cohere",
    "groq",
    "litellm",
    "mistral",
    "mistralai",
    "ollama",
    "openai",
    "provider",
    "vertexai",
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


def _identifier_tokens(name: str) -> tuple[str, ...]:
    """Normalize snake/camel/acronym identifiers into lowercase tokens."""
    tokens: list[str] = []
    for chunk in re.split(r"[^A-Za-z0-9]+", name.strip("_")):
        if not chunk:
            continue
        tokens.extend(
            part.lower()
            for part in re.findall(
                r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+",
                chunk,
            )
        )
    return tuple(tokens)


def _is_provider_ownership_identifier(name: str) -> bool:
    tokens = set(_identifier_tokens(name))
    if not tokens:
        return False
    if "llm" in tokens or "provider" in tokens:
        return True
    if "client" in tokens and "model" in tokens:
        return True
    return bool(tokens & PROVIDER_IDENTIFIER_TOKENS and "client" in tokens)


def _expression_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _expression_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _is_provider_create_call(call_name: str) -> bool:
    """Recognize common provider SDK create chains without banning create()."""
    parts = tuple(part for part in call_name.split(".") if part)
    for chain in PROVIDER_CREATE_CHAINS:
        if len(parts) <= len(chain) or parts[-len(chain) :] != chain:
            continue
        owner = parts[-len(chain) - 1]
        return owner in PROVIDER_CHAIN_OWNER_NAMES or _is_provider_ownership_identifier(owner)
    return False


def _assignment_targets(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.Tuple, ast.List)):
        targets: list[ast.AST] = []
        for item in node.elts:
            targets.extend(_assignment_targets(item))
        return targets
    return [node]


def _scan_search_ownership(tree: ast.AST, rel: str) -> list[Violation]:
    """Scan provider ownership structures in production search packages.

    This is deliberately structural rather than a universal semantic proof. It
    catches common import, declaration, storage, construction, dynamic import,
    and provider-call forms while allowing deterministic query planning names.
    """
    owned: set[tuple[int, str]] = set()
    importlib_aliases = {"importlib"}
    import_module_aliases = {"__import__"}

    def add(node: ast.AST, marker: str) -> None:
        owned.add((getattr(node, "lineno", 0), marker))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
                disallowed = _module_is_disallowed(alias.name)
                if disallowed is not None:
                    add(node, disallowed)
                if alias.asname and _is_provider_ownership_identifier(alias.asname):
                    add(node, alias.asname)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "importlib":
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_aliases.add(alias.asname or alias.name)
            disallowed = _module_is_disallowed(module)
            if disallowed is not None:
                add(node, disallowed)
            for alias in node.names:
                if _is_provider_ownership_identifier(alias.name):
                    add(node, f"{module}.{alias.name}".strip("."))
                if alias.asname and _is_provider_ownership_identifier(alias.asname):
                    add(node, alias.asname)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in LEGACY_LLM_OWNERSHIP_NAMES or _is_provider_ownership_identifier(
                node.name
            ):
                add(node, node.name)
        elif isinstance(node, ast.arg) and _is_provider_ownership_identifier(node.arg):
            add(node, node.arg)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for leaf in _assignment_targets(target):
                    target_name = _expression_name(leaf)
                    if _is_provider_ownership_identifier(target_name.rsplit(".", 1)[-1]):
                        add(leaf, target_name)
        elif isinstance(node, ast.AnnAssign):
            for leaf in _assignment_targets(node.target):
                target_name = _expression_name(leaf)
                if _is_provider_ownership_identifier(target_name.rsplit(".", 1)[-1]):
                    add(leaf, target_name)
        elif isinstance(node, ast.NamedExpr):
            target_name = _expression_name(node.target)
            if _is_provider_ownership_identifier(target_name.rsplit(".", 1)[-1]):
                add(node.target, target_name)
        elif isinstance(node, ast.Attribute) and _is_provider_ownership_identifier(node.attr):
            add(node, _expression_name(node))
        elif isinstance(node, ast.Call):
            call_name = _expression_name(node.func)
            call_leaf = call_name.rsplit(".", 1)[-1]
            if _is_provider_create_call(call_name):
                add(node, call_name)
            elif call_leaf in PROVIDER_CALL_METHODS:
                add(node, call_name)
            elif _is_provider_ownership_identifier(call_leaf):
                add(node, call_name)

            is_dynamic_import = (
                isinstance(node.func, ast.Name) and node.func.id in import_module_aliases
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in importlib_aliases
            )
            if is_dynamic_import and node.args and isinstance(node.args[0], ast.Constant):
                dynamic_module = node.args[0].value
                if isinstance(dynamic_module, str):
                    disallowed = _module_is_disallowed(dynamic_module)
                    if disallowed is not None:
                        add(node, f"dynamic import {dynamic_module}")

    return [Violation(rel, line, marker) for line, marker in sorted(owned)]


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
        violations.extend(_scan_search_ownership(tree, rel))
    return sorted(set(violations), key=lambda item: (item.path, item.line, item.import_name))


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
