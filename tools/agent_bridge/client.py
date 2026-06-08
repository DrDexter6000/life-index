from __future__ import annotations

from tools.agent_bridge.acp_client import UnsupportedTransportError
from tools.agent_bridge.config import BrainConfig, require_ack


def synthesize(cfg: BrainConfig, system_prompt: str, user_prompt: str) -> str:
    """Send a scaffold prompt to the configured transport; return the text.

    This is the ONLY place agent_bridge performs an LLM call (L3). Requires ack
    for supported transports.

    Transport routing:
    - ``"openai"`` — existing OpenAI-compatible call shape (unchanged).
    - ``"acp"`` — delegates to ``tools.agent_bridge.acp_client.acp_synthesize``.
    - unknown — raises ``UnsupportedTransportError`` immediately (no ack check).
    """
    if cfg.transport == "openai":
        require_ack(cfg)
        from openai import OpenAI  # imported lazily; agent_bridge is L3 so this is allowed

        client = OpenAI(api_key=cfg.api_key, base_url=cfg.endpoint)
        resp = client.chat.completions.create(
            model=cfg.model or "default",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or ""

    if cfg.transport == "acp":
        require_ack(cfg)
        from tools.agent_bridge.acp_client import acp_synthesize

        return acp_synthesize(cfg, system_prompt, user_prompt)

    raise UnsupportedTransportError(f"Unknown transport {cfg.transport!r}. Supported: openai, acp.")
