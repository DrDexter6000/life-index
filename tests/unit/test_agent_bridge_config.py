import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _clear_env(mp):
    for k in (
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_BRAIN_ENDPOINT",
    ):
        mp.delenv(k, raising=False)


def test_resolve_brain_config_reads_brain_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "endpoint": "http://localhost:8642/v1",
                "transport": "openai",
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.mode == "host_agent"
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.data_exposure_ack is True


def test_brain_falls_back_to_llm_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {"llm": {"api_key": "k", "base_url": "http://localhost:8642/v1", "model": "hermes"}},
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.model == "hermes"


def test_env_overrides_config(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_BRAIN_ENDPOINT", "http://localhost:8642/v1")
    monkeypatch.setenv("LIFE_INDEX_BRAIN_MODE", "host_agent")
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.mode == "host_agent"


def test_ack_required_raises_without_ack(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {"brain": {"mode": "host_agent", "endpoint": "http://x/v1", "data_exposure_ack": False}},
    )
    from tools.agent_bridge.config import resolve_brain_config, require_ack, AckRequiredError

    cfg = resolve_brain_config()
    import pytest

    with pytest.raises(AckRequiredError):
        require_ack(cfg)


# ──────────────────────────────────────────────────────────────────────
# Phase A RED: ACP config field contract tests
# ──────────────────────────────────────────────────────────────────────


def test_acp_config_fields_are_parsed(monkeypatch):
    """Contract: ACP mode parses acp_command, acp_workdir, acp_auth_method,
    acp_env_allowlist from brain config section.

    RED: BrainConfig dataclass does not have ACP fields yet.
    """
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "acp_workdir": "/tmp/acp-workspace",
                "acp_auth_method": "custom",
                "acp_env_allowlist": {"PATH": "/usr/bin", "HOME": "/home/user"},
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.transport == "acp"

    # RED: BrainConfig has no ACP fields — these will raise AttributeError
    assert cfg.acp_command == ["hermes", "acp"]
    assert cfg.acp_workdir == "/tmp/acp-workspace"
    assert cfg.acp_auth_method == "custom"
    assert cfg.acp_env_allowlist == {"PATH": "/usr/bin", "HOME": "/home/user"}


def test_acp_mode_does_not_require_api_key(monkeypatch):
    """Contract: ACP transport mode does not require LIFE_INDEX_LLM_API_KEY
    or a provider key — ACP uses its own auth mechanism.

    GREEN: current resolve_brain_config is agnostic to transport type.
    This test must remain GREEN after ACP config fields are added.
    """
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "acp_workdir": "/tmp/acp",
                "acp_auth_method": "custom",
                "acp_env_allowlist": {},
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.transport == "acp"
    assert cfg.api_key is None, "ACP mode must not require LIFE_INDEX_LLM_API_KEY or provider key"
    assert cfg.mode == "host_agent"


def test_acp_default_auth_method_is_none(monkeypatch):
    """Contract: when acp_auth_method is not specified, it defaults to None.

    RED: BrainConfig has no acp_auth_method field yet.
    """
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "acp_workdir": "/tmp/acp",
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    # RED: acp_auth_method field does not exist on BrainConfig
    assert cfg.acp_auth_method is None


def test_acp_env_allowlist_defaults_to_empty(monkeypatch):
    """Contract: acp_env_allowlist defaults to empty dict when not specified.

    RED: BrainConfig has no acp_env_allowlist field yet.
    """
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "acp_workdir": "/tmp/acp",
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    # RED: acp_env_allowlist field does not exist on BrainConfig
    assert cfg.acp_env_allowlist == {}


# ──────────────────────────────────────────────────────────────────────
# v6-ce-acp-env-allowlist: JSON list allowlist resolution tests
# ──────────────────────────────────────────────────────────────────────


def test_acp_env_allowlist_list_syntax(monkeypatch):
    """Contract: LIFE_INDEX_ACP_ENV_ALLOWLIST as a JSON list resolves keys
    from os.environ into a dict.
    """
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '["DEEPSEEK_API_KEY", "CUSTOM_VAR"]')
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-from-env")
    monkeypatch.setenv("CUSTOM_VAR", "custom-value")

    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()

    assert cfg.acp_env_allowlist == {
        "DEEPSEEK_API_KEY": "sk-deepseek-from-env",
        "CUSTOM_VAR": "custom-value",
    }


def test_acp_env_allowlist_list_skips_missing_keys(monkeypatch):
    """Contract: list keys not in os.environ are silently skipped."""
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '["MISSING_KEY"]')
    monkeypatch.delenv("MISSING_KEY", raising=False)

    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()

    assert cfg.acp_env_allowlist == {}


def test_acp_env_allowlist_list_rejects_non_string_items(monkeypatch):
    """Contract: list items that are not strings raise ACPConfigError."""
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '[123, "VALID_KEY"]')

    import pytest
    from tools.agent_bridge.config import resolve_brain_config, ACPConfigError

    with pytest.raises(ACPConfigError, match=r"(?i)list items must be strings"):
        resolve_brain_config()


def test_acp_env_allowlist_invalid_type_raises(monkeypatch):
    """Contract: non-dict, non-list values raise ACPConfigError."""
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '"just a string"')

    import pytest
    from tools.agent_bridge.config import resolve_brain_config, ACPConfigError

    with pytest.raises(ACPConfigError, match=r"(?i)must be a JSON object or"):
        resolve_brain_config()
