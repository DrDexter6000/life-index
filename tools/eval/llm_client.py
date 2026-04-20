#!/usr/bin/env python3
"""LLM client helpers for eval workflows."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

LLM_TIMEOUT_SECONDS = 30.0


class LLMClient(Protocol):
    def query(
        self,
        prompt: str,
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ) -> str: ...


@dataclass
class MockLLMClient:
    """Deterministic mock client for tests."""

    responses: list[str] = field(default_factory=list)
    default_response: str = '{"score": 0, "reason": "mock default"}'
    prompts: list[str] = field(default_factory=list)

    def query(
        self,
        prompt: str,
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ) -> str:
        self.prompts.append(prompt)
        if self.responses:
            return self.responses.pop(0)
        return self.default_response


def _extract_json_object(raw: str) -> str | None:
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        return match.group(0)
    return None


def parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    candidates = [text]
    extracted = _extract_json_object(text)
    if extracted and extracted != text:
        candidates.append(extracted)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    score_match = re.search(r'"?score"?\s*[:=]\s*(\d+)', text)
    reason_match = re.search(r'"?reason"?\s*[:=]\s*"([^"]+)"', text)
    if score_match:
        fallback: dict[str, Any] = {"score": int(score_match.group(1))}
        if reason_match:
            fallback["reason"] = reason_match.group(1)
        else:
            fallback["reason"] = text
        return fallback

    expected_hits_match = re.search(r'"?expected_hits"?\s*[:=]\s*\[(.*?)\]', text, flags=re.DOTALL)
    if expected_hits_match:
        titles = [
            item.strip().strip('"').strip("'")
            for item in expected_hits_match.group(1).split(",")
            if item.strip()
        ]
        return {"expected_hits": titles, "reason": text}

    return {"raw": text, "reason": text}


def _query_openai(prompt: str, model: str, temperature: float) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=LLM_TIMEOUT_SECONDS)
    response = client.responses.create(
        model=model,
        temperature=temperature,
        input=prompt,
    )
    return str(response.output_text)


def _query_anthropic(prompt: str, model: str, temperature: float) -> str:
    from anthropic import Anthropic

    anthropic_model = model if model.startswith("claude") else "claude-3-5-haiku-latest"
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=LLM_TIMEOUT_SECONDS)
    response = client.messages.create(
        model=anthropic_model,
        max_tokens=512,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [
        text for block in response.content if (text := getattr(block, "text", None)) is not None
    ]
    return "".join(parts)


def query_llm(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return _query_openai(prompt, model=model, temperature=temperature)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _query_anthropic(prompt, model=model, temperature=temperature)
    raise RuntimeError("No LLM provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
