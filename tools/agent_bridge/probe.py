from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any
from urllib import error, request

from tools.agent_bridge.config import ACPConfigError, BrainConfig, resolve_brain_config
from tools.agent_bridge.resolve import resolve_source
from tools.lib import config as _cfg

SCHEMA_VERSION = "m35.agent_bridge_probe.v0"

# ACP cold-start handshake timeout: covers real ACP process spawn + initialize
# + authenticate + session/new.  Observed real-runtime timings (Hermes 2026-06-12,
# cumulative): initialize=10.9s, authenticate=16.2s, session/new=48.8s total.
# The full handshake completed around 48.8s; 75.0s gives conservative headroom.
# This is NOT the HTTP probe timeout — callers may pass a smaller explicit
# timeout for fast-fail tests.
_ACP_HANDSHAKE_TIMEOUT = 75.0


def _token_source() -> dict[str, Any]:
    user = getattr(_cfg, "USER_CONFIG", {}) or {}
    brain = dict(user.get("brain", {}))
    llm = dict(user.get("llm", {}))
    if os.environ.get("LIFE_INDEX_LLM_API_KEY"):
        return {
            "configured": True,
            "source": "env:LIFE_INDEX_LLM_API_KEY",
            "persisted_in_config": False,
        }
    if brain.get("api_key"):
        return {"configured": True, "source": "config:brain.api_key", "persisted_in_config": True}
    if llm.get("api_key"):
        return {"configured": True, "source": "config:llm.api_key", "persisted_in_config": True}
    return {"configured": False, "source": "absent", "persisted_in_config": False}


def _endpoint_urls(cfg: BrainConfig) -> tuple[str | None, str | None]:
    if not cfg.endpoint:
        return None, None
    endpoint = cfg.endpoint.rstrip("/")
    health_base = endpoint.rsplit("/v1", 1)[0].rstrip("/")
    health_url = f"{health_base}/health" if health_base else None
    models_url = f"{endpoint}/models"
    return health_url, models_url


def _fetch_json(url: str, *, token: str | None, timeout: float) -> tuple[int | None, Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        status = getattr(resp, "status", getattr(resp, "code", None))
        body = resp.read().decode("utf-8")
    if not body:
        return status, None
    return status, json.loads(body)


def _network_checks(cfg: BrainConfig, *, network: bool, timeout: float) -> list[dict[str, Any]]:
    health_url, models_url = _endpoint_urls(cfg)
    if not network:
        return [{"name": "network", "status": "skip", "reason": "--no-network"}]
    if not cfg.endpoint:
        return [{"name": "endpoint", "status": "skip", "reason": "no endpoint configured"}]

    checks: list[dict[str, Any]] = []
    if health_url:
        try:
            status, _payload = _fetch_json(health_url, token=None, timeout=timeout)
            checks.append(
                {"name": "health", "status": "pass", "http_status": status, "url": health_url}
            )
        except (OSError, error.URLError, error.HTTPError, ValueError) as exc:
            checks.append(
                {
                    "name": "health",
                    "status": "fail",
                    "url": health_url,
                    "error": exc.__class__.__name__,
                }
            )

    if not cfg.api_key:
        checks.append({"name": "models", "status": "skip", "reason": "token missing"})
        return checks

    try:
        status, payload = _fetch_json(models_url or "", token=cfg.api_key, timeout=timeout)
        model_ids = []
        if isinstance(payload, dict):
            data = payload.get("data", [])
            if isinstance(data, list):
                model_ids = [
                    item.get("id") for item in data if isinstance(item, dict) and item.get("id")
                ]
        checks.append(
            {
                "name": "models",
                "status": "pass",
                "http_status": status,
                "url": models_url,
                "model_ids": model_ids,
            }
        )
    except (OSError, error.URLError, error.HTTPError, ValueError) as exc:
        checks.append(
            {
                "name": "models",
                "status": "fail",
                "url": models_url,
                "error": exc.__class__.__name__,
            }
        )
    return checks


def _models_check_passed(checks: list[dict[str, Any]]) -> bool:
    return any(check.get("name") == "models" and check.get("status") == "pass" for check in checks)


def _acp_config_checks(cfg: BrainConfig) -> list[dict[str, Any]]:
    """Check ACP configuration readiness without spawning subprocesses."""
    checks: list[dict[str, Any]] = []
    command = cfg.acp_command
    command_configured = bool(command and len(command) > 0)

    if command_configured:
        checks.append(
            {
                "name": "acp_command",
                "status": "pass",
                "reason": f"acp_command configured: {command}",
            }
        )
    else:
        checks.append(
            {
                "name": "acp_command",
                "status": "fail",
                "reason": "acp_command not configured",
            }
        )
        return checks

    assert command is not None and len(command) > 0
    executable = shutil.which(command[0])
    if executable:
        checks.append(
            {
                "name": "acp_executable",
                "status": "pass",
                "executable": executable,
                "reason": f"Found: {executable}",
            }
        )
    else:
        checks.append(
            {
                "name": "acp_executable",
                "status": "fail",
                "executable": None,
                "reason": f"'{command[0]}' not found in PATH",
            }
        )

    return checks


def _acp_live_handshake(cfg: BrainConfig, *, timeout: float, network: bool) -> dict[str, Any]:
    """Run ACP initialize -> authenticate -> session/new and stop there."""
    if not network:
        return {"status": "skip", "reason": "--no-network"}

    if not cfg.acp_command:
        return {
            "status": "fail",
            "steps": {"initialize": "fail", "authenticate": "fail", "session_new": "fail"},
            "error": "acp_command not configured",
            "duration_ms": 0,
        }

    from tools.agent_bridge.acp_client import _ACPConnection

    start = time.monotonic()
    conn = _ACPConnection(cfg, rpc_timeout=timeout, handshake_timeout=timeout)

    try:
        conn.__enter__()
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "status": "pass",
            "steps": dict(conn.handshake_steps),
            "duration_ms": duration_ms,
        }
    except (ACPConfigError, RuntimeError, FileNotFoundError, OSError) as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        steps = dict(conn.handshake_steps)
        if "initialize" not in steps:
            steps["initialize"] = "fail"
        if "authenticate" not in steps:
            steps["authenticate"] = "fail"
        if "session_new" not in steps:
            steps["session_new"] = "fail"
        return {
            "status": "fail",
            "steps": steps,
            "error": str(exc),
            "duration_ms": duration_ms,
        }
    finally:
        try:
            conn.__exit__(None, None, None)
        except Exception:
            pass


def _acp_config_ready(cfg: BrainConfig, source: str, checks: list[dict[str, Any]]) -> bool:
    command_ok = bool(cfg.acp_command and len(cfg.acp_command) > 0)
    executable_ok = any(
        check.get("name") == "acp_executable" and check.get("status") == "pass" for check in checks
    )
    return source in ("P1", "P2") and bool(cfg.data_exposure_ack) and command_ok and executable_ok


def _acp_info(cfg: BrainConfig, live_handshake: dict[str, Any]) -> dict[str, Any]:
    acp_cmd = cfg.acp_command
    executable = shutil.which(acp_cmd[0]) if acp_cmd and len(acp_cmd) > 0 else None
    return {
        "command_configured": bool(acp_cmd and len(acp_cmd) > 0),
        "command": acp_cmd if acp_cmd else None,
        "workdir": cfg.acp_workdir,
        "auth_method": cfg.acp_auth_method,
        "executable_resolved": executable,
        "live_handshake": live_handshake,
    }


def probe_agent_bridge(
    *,
    network: bool = True,
    timeout: float = 1.5,
    in_context_agent: bool = False,
) -> dict[str, Any]:
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)
    token = _token_source()

    if cfg.transport == "acp":
        checks = _acp_config_checks(cfg)
        config_ready = _acp_config_ready(cfg, source, checks)
    else:
        checks = _network_checks(cfg, network=network, timeout=timeout)
        config_ready = (
            source in ("P1", "P2") and bool(cfg.data_exposure_ack) and token["configured"]
        )
        if network:
            config_ready = config_ready and _models_check_passed(checks)
        else:
            config_ready = False

    result: dict[str, Any] = {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "command": "agent-bridge probe",
        "source": source,
        "mode": cfg.mode,
        "transport": cfg.transport,
        "endpoint": {"configured": bool(cfg.endpoint), "url": cfg.endpoint},
        "model": {"configured": bool(cfg.model), "name": cfg.model},
        "ack": {"data_exposure_ack": bool(cfg.data_exposure_ack), "required_for": ["P1", "P2"]},
        "token": token,
        "checks": checks,
        "sends_journal_evidence": False,
    }

    if cfg.transport == "acp":
        handshake = _acp_live_handshake(cfg, timeout=_ACP_HANDSHAKE_TIMEOUT, network=network)
        result["live_handshake"] = handshake
        result["acp"] = _acp_info(cfg, handshake)
        if network:
            result["ready_to_send_evidence"] = (
                bool(config_ready) and handshake.get("status") == "pass"
            )
        else:
            result["ready_to_send_evidence"] = bool(config_ready)
    else:
        result["ready_to_send_evidence"] = bool(config_ready)

    return result
