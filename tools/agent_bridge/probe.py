from __future__ import annotations

import json
import os
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


def probe_agent_bridge(
    *,
    network: bool = True,
    timeout: float = 1.5,
    in_context_agent: bool = False,
) -> dict[str, Any]:
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)
    token = _token_source()
    checks = _network_checks(cfg, network=network, timeout=timeout)
    ready = source in ("P1", "P2") and bool(cfg.data_exposure_ack) and token["configured"]
    if network:
        ready = ready and _models_check_passed(checks)
    else:
        ready = False

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
        "sends_journal_evidence": False,
        "ready_to_send_evidence": bool(ready),
    }
