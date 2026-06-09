from __future__ import annotations

import json
import os
import shutil
from typing import Any
from urllib import error, request

from tools.agent_bridge.config import BrainConfig, resolve_brain_config
from tools.agent_bridge.resolve import resolve_source
from tools.lib import config as _cfg

SCHEMA_VERSION = "m35.agent_bridge_probe.v0"


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
    """Check ACP configuration readiness without spawning subprocesses.

    Only uses ``shutil.which`` to check if the launcher executable is in PATH.
    Never calls ``subprocess.Popen``/``run``/``call``.
    """
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

    # mypy: we only reach here when command_configured is True,
    # so command is guaranteed non-None and non-empty.
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


def probe_agent_bridge(
    *,
    network: bool = True,
    timeout: float = 1.5,
    in_context_agent: bool = False,
) -> dict[str, Any]:
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)
    token = _token_source()

    # ── transport routing ──────────────────────────────────────────────
    if cfg.transport == "acp":
        checks = _acp_config_checks(cfg)
        # For ACP, re-derive source since resolve_source is endpoint-centric
        acp_usable = bool(cfg.acp_command and cfg.data_exposure_ack)
        if source == "deterministic_only" and acp_usable:
            source = "P2" if cfg.mode == "byol" else "P1"
        # ready_to_send_evidence for ACP: source must be P1/P2 + ack +
        # command_configured + executable_resolved
        acp_cmd_ok = bool(cfg.acp_command and len(cfg.acp_command) > 0)
        acp_exe_ok = bool(
            any(c.get("name") == "acp_executable" and c.get("status") == "pass" for c in checks)
        )
        ready = source in ("P1", "P2") and bool(cfg.data_exposure_ack) and acp_cmd_ok and acp_exe_ok
    else:
        checks = _network_checks(cfg, network=network, timeout=timeout)
        ready = source in ("P1", "P2") and bool(cfg.data_exposure_ack) and token["configured"]
        if network:
            ready = ready and _models_check_passed(checks)
        else:
            ready = False

    # ── build ACP info (always present) ─────────────────────────────────
    acp_cmd = cfg.acp_command
    acp_executable_resolved = None
    if acp_cmd and len(acp_cmd) > 0:
        acp_executable_resolved = shutil.which(acp_cmd[0])

    acp_info: dict[str, Any] = {
        "command_configured": bool(acp_cmd and len(acp_cmd) > 0),
        "command": acp_cmd if acp_cmd else None,
        "workdir": cfg.acp_workdir,
        "auth_method": cfg.acp_auth_method,
        "executable_resolved": acp_executable_resolved,
        "live_handshake": {
            "status": "not_checked",
            "reason": "deferred to Phase C-2",
        },
    }

    return {
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
        "acp": acp_info,
        "sends_journal_evidence": False,
        "ready_to_send_evidence": bool(ready),
    }
