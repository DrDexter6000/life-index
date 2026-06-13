from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, cast

from tools.agent_bridge.config import resolve_brain_config
from tools.agent_bridge.resolve import resolve_source


def _cli_smart_search(query: str) -> dict[str, Any]:
    """Subprocess the L2 CLI for a deterministic scaffold. No L2 internals imported."""
    out = subprocess.run(
        [sys.executable, "-m", "tools", "smart-search", "--query", query, "--include-evidence"],
        capture_output=True,
        text=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(out.stdout))


def _build_prompts(scaffold: dict[str, Any]) -> tuple[str, str]:
    instr = scaffold.get("agent_instructions", {})
    system = "You are the user's trusted assistant. " + " ".join(instr.get("steps", []))
    user = json.dumps(
        {
            "query": scaffold.get("query"),
            "filtered_results": scaffold.get("filtered_results", []),
            "evidence_pack": scaffold.get("evidence_pack", {}),
            "answer_scaffold": scaffold.get("answer_scaffold", {}),
        },
        ensure_ascii=False,
    )
    return system, user


def handoff_search(query: str, *, in_context_agent: bool = False) -> dict[str, Any]:
    """Run smart-search scaffold -> resolve brain -> (maybe) synthesize.

    Returns a proposal envelope with keys: source, query, scaffold, synthesis
    (or the m35.agent_bridge_query.v0 envelope when routed through ACP).
    """
    scaffold = _cli_smart_search(query)
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)

    # ACP query path: route through dedicated ACP query adapter.
    # This path does NOT call client.synthesize (no OpenAI-compatible fallback).
    if source in ("P1", "P2") and cfg.transport == "acp" and cfg.data_exposure_ack:
        from tools.agent_bridge.acp_query import acp_query_adapter

        try:
            result = acp_query_adapter(query, scaffold, cfg)
            return result  # Already m35.agent_bridge_query.v0 envelope
        except Exception:
            # ACP setup failed — degrade deterministically through adapter
            from tools.agent_bridge.acp_query import build_degraded_result, build_provenance

            return build_degraded_result(
                "UNGROUNDED",
                f"ACP query adapter failed for query: {query}",
                build_provenance(cfg, degraded=True),
            )

    # Legacy P1/P2 path (OpenAI-compatible)
    envelope: dict[str, Any] = {
        "source": source,
        "query": query,
        "scaffold": scaffold,
        "synthesis": None,
    }
    if source in ("P1", "P2"):
        # Lazy import: client.py imports openai inside synthesize(),
        # but we guard here so the degrade path never touches the SDK.
        from tools.agent_bridge import client

        system, user = _build_prompts(scaffold)
        envelope["synthesis"] = client.synthesize(cfg, system, user)
    return envelope
