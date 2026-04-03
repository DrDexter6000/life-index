import pytest

from web.services.llm_provider import _parse_json_object_from_text


def test_parse_json_object_from_text_handles_markdown_fence() -> None:
    text = '```json\n{"title":"测试","topic":["work"]}\n```'

    parsed = _parse_json_object_from_text(text)

    assert parsed == {"title": "测试", "topic": ["work"]}


def test_parse_json_object_from_text_strips_think_block() -> None:
    text = '<think>internal</think>\n{"title":"测试","topic":["work"]}'

    parsed = _parse_json_object_from_text(text)

    assert parsed == {"title": "测试", "topic": ["work"]}
