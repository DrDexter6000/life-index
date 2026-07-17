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

PRODUCT_OWNERSHIP_ROOTS = {
    ("tools", "eval"),
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


def _is_provider_specific_call(call_name: str) -> bool:
    """Recognize provider-specific SDK suffixes regardless of owner name."""
    parts = tuple(part for part in call_name.split(".") if part)
    return any(
        len(parts) > len(chain) and parts[-len(chain) :] == chain
        for chain in PROVIDER_CREATE_CHAINS
    )


def _assignment_targets(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.Tuple, ast.List)):
        targets: list[ast.AST] = []
        for item in node.elts:
            targets.extend(_assignment_targets(item))
        return targets
    return [node]


def _constant_dynamic_module_name(node: ast.Call) -> str | None:
    """Read a constant module name from positional or ``name=`` syntax."""
    candidate: ast.AST | None = node.args[0] if node.args else None
    if candidate is None:
        candidate = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "name"),
            None,
        )
    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
        return candidate.value
    return None


class _NoLlmVisitor(ast.NodeVisitor):
    """Single-pass import and provider-ownership policy visitor."""

    def __init__(self, rel: str, *, search_scope: bool) -> None:
        self.rel = rel
        self.search_scope = search_scope
        self.violations: set[Violation] = set()
        self.provider_bindings: set[str] = set()
        self.importlib_aliases = {"importlib"}
        self.import_module_aliases = {"__import__"}

    def _add(self, node: ast.AST, marker: str) -> None:
        self.violations.add(Violation(self.rel, getattr(node, "lineno", 0), marker))

    def _has_provider_provenance(self, node: ast.AST | None) -> bool:
        if node is None:
            return False
        if isinstance(node, ast.Call):
            return self._has_provider_provenance(node.func)
        name = _expression_name(node)
        if not name:
            return False
        leaf = name.rsplit(".", 1)[-1]
        return name in self.provider_bindings or _is_provider_ownership_identifier(leaf)

    def _record_targets(self, target: ast.AST, value: ast.AST | None) -> None:
        value_is_provider = self._has_provider_provenance(value)
        for leaf in _assignment_targets(target):
            target_name = _expression_name(leaf)
            if not target_name:
                continue
            target_is_provider = _is_provider_ownership_identifier(target_name.rsplit(".", 1)[-1])
            if target_is_provider or value_is_provider:
                self.provider_bindings.add(target_name)
                self._add(leaf, target_name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", 1)[0]
            if alias.name == "importlib":
                self.importlib_aliases.add(local_name)
            disallowed = _module_is_disallowed(alias.name)
            if disallowed is not None:
                self._add(node, disallowed)
                if self.search_scope:
                    self.provider_bindings.add(local_name)
            if (
                self.search_scope
                and alias.asname
                and _is_provider_ownership_identifier(alias.asname)
            ):
                self.provider_bindings.add(alias.asname)
                self._add(node, alias.asname)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        disallowed = _module_is_disallowed(module)
        if disallowed is not None:
            self._add(node, disallowed)
        for alias in node.names:
            local_name = alias.asname or alias.name
            explicit = DISALLOWED_FROM_NAMES.get((module, alias.name))
            if explicit is not None:
                self._add(node, explicit)
            if module == "importlib" and alias.name == "import_module":
                self.import_module_aliases.add(local_name)
            if not self.search_scope:
                continue
            provider_named = _is_provider_ownership_identifier(alias.name) or (
                alias.asname is not None and _is_provider_ownership_identifier(alias.asname)
            )
            if disallowed is not None or provider_named:
                self.provider_bindings.add(local_name)
            if provider_named:
                self._add(node, f"{module}.{alias.name}".strip("."))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self.search_scope and (
            node.name in LEGACY_LLM_OWNERSHIP_NAMES or _is_provider_ownership_identifier(node.name)
        ):
            self._add(node, node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.search_scope and (
            node.name in LEGACY_LLM_OWNERSHIP_NAMES or _is_provider_ownership_identifier(node.name)
        ):
            self._add(node, node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self.search_scope and (
            node.name in LEGACY_LLM_OWNERSHIP_NAMES or _is_provider_ownership_identifier(node.name)
        ):
            self._add(node, node.name)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if self.search_scope and _is_provider_ownership_identifier(node.arg):
            self.provider_bindings.add(node.arg)
            self._add(node, node.arg)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.search_scope:
            for target in node.targets:
                self._record_targets(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self.search_scope:
            self._record_targets(node.target, node.value)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        if self.search_scope:
            self._record_targets(node.target, node.value)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.search_scope and _is_provider_ownership_identifier(node.attr):
            self._add(node, _expression_name(node))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not self.search_scope:
            self.generic_visit(node)
            return

        call_name = _expression_name(node.func)
        call_leaf = call_name.rsplit(".", 1)[-1]
        owner_name = call_name.rsplit(".", 1)[0] if "." in call_name else ""
        owner_leaf = owner_name.rsplit(".", 1)[-1]
        owner_is_provider = owner_name in self.provider_bindings or (
            bool(owner_leaf) and _is_provider_ownership_identifier(owner_leaf)
        )
        if _is_provider_specific_call(call_name):
            self._add(node, call_name)
        elif call_leaf in PROVIDER_CALL_METHODS and owner_is_provider:
            self._add(node, call_name)
        elif _is_provider_ownership_identifier(call_leaf) or (call_name in self.provider_bindings):
            self._add(node, call_name)

        is_dynamic_import = (
            isinstance(node.func, ast.Name) and node.func.id in self.import_module_aliases
        ) or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in self.importlib_aliases
        )
        if is_dynamic_import:
            dynamic_module = _constant_dynamic_module_name(node)
            if dynamic_module is not None:
                disallowed = _module_is_disallowed(dynamic_module)
                if disallowed is not None:
                    self._add(node, f"dynamic import {dynamic_module}")
        self.generic_visit(node)


def _scan_file(path: Path, root: Path) -> list[Violation]:
    rel = path.relative_to(root).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    rel_parts = path.relative_to(root).parts
    visitor = _NoLlmVisitor(
        rel,
        search_scope=tuple(rel_parts[:2]) in PRODUCT_OWNERSHIP_ROOTS,
    )
    visitor.visit(tree)
    return sorted(
        visitor.violations,
        key=lambda item: (item.path, item.line, item.import_name),
    )


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
