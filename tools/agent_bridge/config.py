from __future__ import annotations
import os
from dataclasses import dataclass
from tools.lib import config as _cfg


class AckRequiredError(RuntimeError):
    """Raised when a provider-backed (P1/P2) brain is selected without data_exposure_ack."""


@dataclass(frozen=True)
class BrainConfig:
    mode: str  # auto | in_context | host_agent | byol | deterministic_only
    endpoint: str | None
    transport: str  # openai | acp
    api_key: str | None
    model: str | None
    data_exposure_ack: bool


def resolve_brain_config() -> BrainConfig:
    user = getattr(_cfg, "USER_CONFIG", {}) or {}
    brain = dict(user.get("brain", {}))
    llm = dict(user.get("llm", {}))  # config-compatible fallback (no smart-search refactor)

    endpoint = (
        os.environ.get("LIFE_INDEX_BRAIN_ENDPOINT")
        or brain.get("endpoint")
        or os.environ.get("LIFE_INDEX_LLM_BASE_URL")
        or llm.get("base_url")
    )
    mode = os.environ.get("LIFE_INDEX_BRAIN_MODE") or brain.get("mode") or "auto"
    transport = brain.get("transport", "openai")
    api_key = os.environ.get("LIFE_INDEX_LLM_API_KEY") or brain.get("api_key") or llm.get("api_key")
    model = os.environ.get("LIFE_INDEX_LLM_MODEL") or brain.get("model") or llm.get("model")
    ack = bool(brain.get("data_exposure_ack", False))
    return BrainConfig(
        mode=mode,
        endpoint=endpoint,
        transport=transport,
        api_key=api_key,
        model=model,
        data_exposure_ack=ack,
    )


def require_ack(cfg: BrainConfig) -> None:
    if not cfg.data_exposure_ack:
        raise AckRequiredError(
            "P1/P2 brain requires explicit data_exposure_ack=true before sending journal data."
        )
