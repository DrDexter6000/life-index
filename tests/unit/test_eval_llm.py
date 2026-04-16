#!/usr/bin/env python3

from importlib import import_module


def _load_llm_module():
    return import_module("tools.eval.llm_client")


def _load_prompts_module():
    return import_module("tools.eval.prompts")


def test_precision_prompt_renders_correctly() -> None:
    prompt = _load_prompts_module().PRECISION_JUDGE_PROMPT.format(
        query="想念我的女儿",
        title="想念尿片侠",
        date="2026-03-04",
        abstract="翻看旧照片想起女儿。",
        snippet="那个让我神魂颠倒的尿片侠。",
    )

    assert "想念我的女儿" in prompt
    assert "想念尿片侠" in prompt
    assert '仅返回 JSON: {"score": N, "reason": "一句话说明"}' in prompt


def test_recall_gap_prompt_renders_correctly() -> None:
    prompt = _load_prompts_module().RECALL_GAP_PROMPT.format(
        query="团团",
        all_titles="- 想念我的女儿\n- 重庆过生日\n- 团团不认真吃饭",
    )

    assert "团团" in prompt
    assert "想念我的女儿" in prompt
    assert "重庆过生日" in prompt
    assert '"expected_hits": ["标题1", "标题2"]' in prompt


def test_llm_client_parse_json_response() -> None:
    parsed = _load_llm_module().parse_json_response(
        '{"score": 3, "reason": "直接命中"}'
    )

    assert parsed["score"] == 3
    assert parsed["reason"] == "直接命中"


def test_llm_client_handles_malformed_response() -> None:
    parsed = _load_llm_module().parse_json_response(
        '结果如下：```json\n{"score": 2, "reason": "部分相关"}\n```'
    )

    assert parsed["score"] == 2
    assert parsed["reason"] == "部分相关"


def test_llm_client_mock_mode() -> None:
    client = _load_llm_module().MockLLMClient(
        responses=[
            '{"score": 1, "reason": "间接相关"}',
            '{"expected_hits": ["想念我的女儿"], "reason": "标题明显相关"}',
        ]
    )

    assert client.query("prompt 1") == '{"score": 1, "reason": "间接相关"}'
    assert client.query("prompt 2") == (
        '{"expected_hits": ["想念我的女儿"], "reason": "标题明显相关"}'
    )
