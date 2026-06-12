from __future__ import annotations
from tools.agent_bridge.config import BrainConfig


def resolve_source(cfg: BrainConfig, *, in_context_agent: bool) -> str:
    """Deterministic resolution. Returns one of: P0, P1, P2, deterministic_only.

    Order: explicit mode override -> P0 (in-context) -> P1/P2 (endpoint+ack
    or ACP+ack) -> degrade.  P1 vs P2 is an intent label: mode='byol' marks
    P2; otherwise a usable transport is P1.
    """
    if cfg.mode == "in_context":
        return "P0"
    if cfg.mode == "deterministic_only":
        return "deterministic_only"
    if in_context_agent and cfg.mode in ("auto", "host_agent"):
        return "P0"
    usable_endpoint = bool(cfg.endpoint and cfg.api_key and cfg.data_exposure_ack)
    usable_acp = bool(cfg.transport == "acp" and cfg.acp_command and cfg.data_exposure_ack)
    if usable_endpoint or usable_acp:
        return "P2" if cfg.mode == "byol" else "P1"
    return "deterministic_only"
