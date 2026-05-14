#!/usr/bin/env python3
"""Life Index - Smart Search CLI Entry Point.

Usage:
    life-index smart-search --query "..."
    python -m tools.smart_search --query "..."

Intelligence Layer search with deterministic default behavior.
Pass --use-llm to enable LLM-assisted query rewriting, result filtering,
and summarization. Without --use-llm, it uses pure dual-pipeline mode.
"""

import argparse
import json
import sys
from typing import Any


def _emit_json(payload: dict[str, Any]) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smart search with deterministic default and optional LLM orchestration",
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        required=True,
        help="Natural language search query",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        default=False,
        help="Enable LLM-assisted orchestration (explicit opt-in)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Include agent decisions in output",
    )
    parser.add_argument(
        "--include-evidence",
        action="store_true",
        default=False,
        help="Include evidence pack in output",
    )
    parser.add_argument(
        "--synthesize",
        action="store_true",
        default=False,
        help="Generate citation-backed answer from search evidence (requires LLM)",
    )
    args = parser.parse_args()

    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    llm_client = _try_init_llm() if args.use_llm else None
    orch = SmartSearchOrchestrator(llm_client=llm_client)
    result = orch.search(
        args.query, include_evidence=args.include_evidence, synthesize=args.synthesize
    )

    # Optionally strip agent_decisions for cleaner output
    if not args.explain and "agent_decisions" in result:
        result["agent_decisions_summary"] = f"{len(result['agent_decisions'])} decisions made"
        del result["agent_decisions"]

    _emit_json(result)
    sys.exit(0 if result.get("success") else 1)


def _resolve_llm_config() -> tuple[str | None, str | None, str]:
    """Resolve LLM config with atomic source selection.

    Two mutually exclusive sources:
    1. Legacy env (OPENAI_API_KEY / LLM_API_KEY present):
       Uses only OPENAI_BASE_URL / LLM_BASE_URL and LLM_MODEL env / defaults.
       Never inherits Life Index base_url or model.
    2. Life Index config (LIFE_INDEX_LLM_* env + config.yaml):
       Used only when no legacy API key exists.
    """
    import os

    legacy_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")

    if legacy_api_key:
        legacy_base_url = (
            os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL") or None
        )
        legacy_model = os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        return legacy_api_key, legacy_base_url, legacy_model

    from tools.lib.config import get_llm_config

    cfg = get_llm_config()
    life_index_api_key = cfg.get("api_key") or None
    life_index_base_url = cfg.get("base_url") or None
    life_index_model = cfg.get("model") or "gpt-4o-mini"
    return life_index_api_key, life_index_base_url, life_index_model


def _try_init_llm() -> Any | None:
    """Try to initialize LLM client. Returns None if unavailable."""
    try:
        api_key, base_url, model = _resolve_llm_config()

        if not api_key:
            return None

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
