"""Lightweight compatibility facts available before product configuration imports."""

from __future__ import annotations

from typing import Final

LANGUAGE_JUDGE_ERROR: Final = {
    "code": "EVAL_LLM_JUDGE_HOST_AGENT_REQUIRED",
    "message": "Language-assisted evaluation belongs to the Host Agent + Life Index Skill.",
}


def language_judge_requested(argv: list[str], *, command_offset: int) -> bool:
    args = argv[command_offset:]
    return "--judge=llm" in args or any(
        arg == "--judge" and index + 1 < len(args) and args[index + 1] == "llm"
        for index, arg in enumerate(args)
    )
