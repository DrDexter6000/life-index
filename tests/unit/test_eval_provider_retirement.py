from __future__ import annotations

import builtins
import json

import pytest


def test_eval_cli_llm_judge_fails_fast_without_loading_provider(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tools.eval import __main__ as eval_main

    provider_import_attempts: list[str] = []

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"tools.eval.llm_client", "openai", "anthropic"}:
            provider_import_attempts.append(name)
            raise AssertionError("provider module must not be imported")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(
        eval_main,
        "run_evaluation",
        lambda **_kwargs: pytest.fail("LLM judge must fail before eval execution"),
    )
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    exit_code = eval_main.main(["--judge", "llm", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code != 0
    assert payload == {
        "success": False,
        "error": {
            "code": "EVAL_LLM_JUDGE_HOST_AGENT_REQUIRED",
            "message": (
                "Language-assisted evaluation belongs to the Host Agent + " "Life Index Skill."
            ),
        },
    }
    assert captured.err == ""
    assert provider_import_attempts == []
