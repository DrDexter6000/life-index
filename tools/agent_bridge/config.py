from __future__ import annotations
import json
import os
import shlex
from dataclasses import dataclass, field
from typing import Any
from tools.lib import config as _cfg


class AckRequiredError(RuntimeError):
    """Raised when a provider-backed (P1/P2) brain is selected without data_exposure_ack."""


class ACPConfigError(RuntimeError):
    """Raised when ACP transport is selected but required config is missing."""


@dataclass(frozen=True)
class BrainConfig:
    mode: str  # auto | in_context | host_agent | byol | deterministic_only
    endpoint: str | None
    transport: str  # openai | acp
    api_key: str | None
    model: str | None
    data_exposure_ack: bool
    acp_command: list[str] | None = None
    acp_workdir: str | None = None
    acp_auth_method: str | None = None
    acp_env_allowlist: dict[str, str] = field(default_factory=dict)


def _parse_json_env(key: str) -> Any | None:
    """Parse a JSON-encoded environment variable, returning None if unset.

    Returns None when the env var is absent. Only used for env vars that
    MUST be valid JSON (e.g. ``LIFE_INDEX_ACP_ENV_ALLOWLIST``).
    """
    raw = os.environ.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ACPConfigError(f"Environment variable {key} must be valid JSON: {exc}") from exc


def _parse_acp_command_env() -> list[str] | None:
    """Parse ``LIFE_INDEX_ACP_COMMAND``, accepting JSON list or shell string.

    Priority:
    1. Valid JSON list (e.g. ``["acp-runtime", "serve"]``)
    2. Shell-like string, split deterministically via ``shlex.split()``

    Returns None when the env var is absent.
    Raises ``ACPConfigError`` when the value exists but cannot be parsed.
    """
    raw = os.environ.get("LIFE_INDEX_ACP_COMMAND")
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        raise ACPConfigError("LIFE_INDEX_ACP_COMMAND is set but empty.")

    # 1. Try JSON list first
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return parsed
        # JSON parsed but not a string list — fall through to raise
    except json.JSONDecodeError:
        pass

    # 2. Deterministic shell-like split fallback
    try:
        parts = shlex.split(stripped)
        if parts:
            return parts
    except ValueError:
        pass

    raise ACPConfigError(
        f"LIFE_INDEX_ACP_COMMAND must be a JSON list or shell-like command string: {raw!r}"
    )


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

    # --- ACP config resolution (env overrides config) ---
    acp_command = _parse_acp_command_env() or brain.get("acp_command")
    acp_workdir = os.environ.get("LIFE_INDEX_ACP_WORKDIR") or brain.get("acp_workdir")
    acp_auth_method = os.environ.get("LIFE_INDEX_ACP_AUTH_METHOD") or brain.get("acp_auth_method")
    acp_env_allowlist = _parse_json_env("LIFE_INDEX_ACP_ENV_ALLOWLIST") or brain.get(
        "acp_env_allowlist"
    )
    if acp_env_allowlist is None:
        acp_env_allowlist = {}

    # Validate: ACP transport requires acp_command
    if transport == "acp" and not acp_command:
        raise ACPConfigError(
            "ACP transport selected but no acp_command configured. "
            "Set acp_command in brain config or LIFE_INDEX_ACP_COMMAND env var."
        )

    return BrainConfig(
        mode=mode,
        endpoint=endpoint,
        transport=transport,
        api_key=api_key,
        model=model,
        data_exposure_ack=ack,
        acp_command=acp_command,
        acp_workdir=acp_workdir,
        acp_auth_method=acp_auth_method,
        acp_env_allowlist=acp_env_allowlist,
    )


def require_ack(cfg: BrainConfig) -> None:
    if not cfg.data_exposure_ack:
        raise AckRequiredError(
            "P1/P2 brain requires explicit data_exposure_ack=true before sending journal data."
        )
