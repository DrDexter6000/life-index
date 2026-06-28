#!/usr/bin/env python3
"""Fail when PR-added public lines mention private/local project names."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PUBLIC_GUI_REPO_TERM = "life-index" + "-gui"
PUBLIC_GUI_REPO_URL = "github.com/DrDexter6000/" + PUBLIC_GUI_REPO_TERM
_PUBLIC_GUI_URL_RE = re.compile(re.escape(PUBLIC_GUI_REPO_URL) + r"(?!-workshop)")
_PUBLIC_GUI_MARKDOWN_RE = re.compile(
    r"\[`?"
    + re.escape(PUBLIC_GUI_REPO_TERM)
    + r"`?\]\(https://"
    + re.escape(PUBLIC_GUI_REPO_URL)
    + r"(?!-workshop)[^)\s]*\)"
)


def _forbidden_terms() -> tuple[str, ...]:
    lower_legacy_orchestrator = "ma" + "estro"
    return (
        "." + "agent" + "-reports",
        "." + "dev" + "/",
        "life-index" + "_gui",
        PUBLIC_GUI_REPO_TERM,
        "host" + "-bridge" + "-sandbox",
        "/" + "home" + "/" + "dexter",
        "Los" + "ter",
        lower_legacy_orchestrator,
        lower_legacy_orchestrator[:1].upper() + lower_legacy_orchestrator[1:],
    )


FORBIDDEN_TERMS = _forbidden_terms()
RETIRED_FLAG_TERMS = ("--use" + "-llm",)
RETIRED_FLAG_ALLOWED_CONTEXT = (
    "retired",
    "rejected",
    "rejects",
    "no longer accepts",
    "not accepted",
    "已退役",
    "拒绝",
)
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    term: str
    text: str


def _path_from_diff_header(line: str) -> str:
    raw = line[4:].strip()
    if raw == "/dev/null":
        return ""
    if raw.startswith("b/"):
        return raw[2:]
    return raw


def _public_gui_allowed_spans(text: str) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    for pattern in (_PUBLIC_GUI_MARKDOWN_RE, _PUBLIC_GUI_URL_RE):
        spans.extend(match.span() for match in pattern.finditer(text))
    return tuple(spans)


def _is_within_spans(start: int, end: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(span_start <= start and end <= span_end for span_start, span_end in spans)


def _has_forbidden_term(term: str, text: str) -> bool:
    if term != PUBLIC_GUI_REPO_TERM:
        return term in text

    allowed_spans = _public_gui_allowed_spans(text)
    for match in re.finditer(re.escape(term), text):
        if not _is_within_spans(match.start(), match.end(), allowed_spans):
            return True
    return False


def scan_diff_text(diff_text: str) -> list[Violation]:
    violations: list[Violation] = []
    current_path = ""
    new_line = 0

    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current_path = _path_from_diff_header(line)
            continue

        hunk = _HUNK_RE.match(line)
        if hunk:
            new_line = int(hunk.group(1)) - 1
            continue

        if line.startswith("+"):
            new_line += 1
            added_text = line[1:]
            for term in FORBIDDEN_TERMS:
                if _has_forbidden_term(term, added_text):
                    violations.append(
                        Violation(
                            path=current_path or "<unknown>",
                            line=new_line,
                            term=term,
                            text=added_text,
                        )
                    )
            lower_added_text = added_text.casefold()
            for term in RETIRED_FLAG_TERMS:
                if term in added_text and not any(
                    context in lower_added_text for context in RETIRED_FLAG_ALLOWED_CONTEXT
                ):
                    violations.append(
                        Violation(
                            path=current_path or "<unknown>",
                            line=new_line,
                            term=term,
                            text=added_text,
                        )
                    )
            continue

        if line.startswith(" "):
            new_line += 1

    return violations


def _default_base() -> str:
    if os.environ.get("PUBLIC_DIFF_BASE"):
        return os.environ["PUBLIC_DIFF_BASE"]
    if os.environ.get("GITHUB_BASE_REF"):
        return f"origin/{os.environ['GITHUB_BASE_REF']}"
    return "origin/main"


def _git_diff(base: str, head: str) -> str:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--unified=0",
            "--diff-filter=ACMRT",
            f"{base}...{head}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout


def _print_violations(violations: list[Violation]) -> None:
    print("Public diff private-name check failed.")
    print("Forbidden terms were found in added lines:")
    for item in violations:
        print(f"- {item.path}:{item.line}: {item.term}")
        print(f"  {item.text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="Base ref for git diff; default origin/main")
    parser.add_argument("--head", default="HEAD", help="Head ref for git diff; default HEAD")
    parser.add_argument("--diff-file", help="Read unified diff text from this file instead of git")
    args = parser.parse_args(argv)

    if args.diff_file:
        diff_text = Path(args.diff_file).read_text(encoding="utf-8")
    else:
        diff_text = _git_diff(args.base or _default_base(), args.head)

    violations = scan_diff_text(diff_text)
    if violations:
        _print_violations(violations)
        return 1

    print("Public diff private-name check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
