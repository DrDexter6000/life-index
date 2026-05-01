#!/usr/bin/env python3
"""Life Index - Smart Search CLI Entry Point.

Usage:
    life-index smart-search --query "..."
    python -m tools.smart_search --query "..."

Intelligence Layer search with LLM-assisted query rewriting,
result filtering, and summarization. Falls back to pure dual-pipeline
when LLM is unavailable.
"""

import argparse
import json
import sys
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smart search with LLM-assisted orchestration",
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="Natural language search query",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="Force degradation mode (no LLM, pure dual-pipeline)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Include agent decisions in output",
    )
    args = parser.parse_args()

    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm_client = None if args.no_llm else _try_init_llm()
    orch = SmartSearchOrchestrator(llm_client=llm_client)
    result = orch.search(args.query)

    # Optionally strip agent_decisions for cleaner output
    if not args.explain and "agent_decisions" in result:
        result["agent_decisions_summary"] = f"{len(result['agent_decisions'])} decisions made"
        del result["agent_decisions"]

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if result.get("success") else 1)


def _try_init_llm() -> Any | None:
    """Try to initialize LLM client. Returns None if unavailable."""
    try:
        import os

        # Support OpenAI-compatible API via environment variables
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL")
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

        if not api_key:
            return None

        # Lazy import to avoid hard dependency
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)

        class OpenAIClient:
            def __init__(self, client: Any, model: str) -> None:
                self._client = client
                self._model = model

            def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 2000) -> str:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                content = response.choices[0].message.content
                return str(content) if content is not None else ""

        return OpenAIClient(client, model)
    except Exception as e:
        import logging

        logging.getLogger(__name__).info(
            f"[SmartSearch] LLM init failed: {e}. Using degradation mode."
        )
        return None


if __name__ == "__main__":
    main()
