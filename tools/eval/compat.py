"""Lightweight compatibility facts available before product configuration imports."""

from __future__ import annotations

from typing import Final

LANGUAGE_JUDGE_ERROR: Final = {
    "code": "EVAL_LLM_JUDGE_HOST_AGENT_REQUIRED",
    "message": "Language-assisted evaluation belongs to the Host Agent + Life Index Skill.",
}


def final_judge(argv: list[str], *, command_offset: int) -> str:
    """Return argparse-compatible last-occurrence judge semantics."""
    judge = "keyword"
    args = argv[command_offset:]
    for index, arg in enumerate(args):
        if arg.startswith("--judge="):
            judge = arg.split("=", 1)[1]
        elif arg == "--judge" and index + 1 < len(args):
            judge = args[index + 1]
    return judge


def language_judge_requested(argv: list[str], *, command_offset: int) -> bool:
    return final_judge(argv, command_offset=command_offset) == "llm"
