"""Settings route."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from tools.lib.config import (
    get_default_location,
    get_llm_config,
    get_search_mode,
    get_search_weights,
    save_default_location,
    save_llm_config,
    save_search_mode,
    save_search_weights,
)

router = APIRouter()

BASE_URL_PRESETS = [
    ("https://api.openai.com/v1", "OpenAI"),
    ("https://openrouter.ai/api/v1", "OpenRouter"),
    ("custom", "自定义"),
]


def _mask_api_key(api_key: str) -> str:
    value = str(api_key or "").strip()
    if not value:
        return ""
    return f"••••{value[-4:]}" if len(value) >= 4 else "••••"


async def _check_llm_connectivity(
    api_key: str, base_url: str, model: str
) -> tuple[bool, str]:
    if not api_key.strip():
        return False, "API Key 为空，无法验证连接"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return False, f"连接失败：{exc}"

    return True, "连接成功"


def _build_settings_context(
    request: Request,
    *,
    form_data: dict[str, Any] | None = None,
    llm_save_message: str | None = None,
    weight_save_message: str | None = None,
    search_mode_save_message: str | None = None,
    connectivity_ok: bool | None = None,
    connectivity_message: str | None = None,
) -> dict[str, Any]:
    values = form_data or {}
    llm_config = get_llm_config()
    fts_weight, semantic_weight = get_search_weights()

    api_key = str(values.get("api_key", llm_config["api_key"]))
    base_url = str(values.get("base_url", llm_config["base_url"]))
    model = str(values.get("model", llm_config["model"]))
    default_location = str(values.get("default_location", get_default_location()))
    fts_weight = float(values.get("fts_weight", fts_weight))
    semantic_weight = float(values.get("semantic_weight", semantic_weight))
    search_mode = str(values.get("search_mode", get_search_mode()))

    preset_value = next(
        (preset for preset, _label in BASE_URL_PRESETS if preset == base_url),
        "custom",
    )

    return {
        "request": request,
        "current_page": "/settings",
        "api_key": api_key,
        "api_key_masked": _mask_api_key(api_key),
        "base_url": base_url,
        "base_url_preset": values.get("base_url_preset", preset_value),
        "model": model,
        "default_location": default_location,
        "fts_weight": fts_weight,
        "semantic_weight": semantic_weight,
        "search_mode": search_mode,
        "base_url_presets": BASE_URL_PRESETS,
        "llm_save_message": llm_save_message,
        "weight_save_message": weight_save_message,
        "search_mode_save_message": search_mode_save_message,
        "connectivity_ok": connectivity_ok,
        "connectivity_message": connectivity_message,
    }


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        _build_settings_context(request),
    )


@router.post("/settings", response_class=HTMLResponse)
async def submit_settings(
    request: Request,
    api_key: str = Form(""),
    base_url: str = Form(""),
    base_url_preset: str = Form("custom"),
    model: str = Form("gpt-4o-mini"),
    default_location: str = Form(""),
    test_only: str = Form("0"),
) -> HTMLResponse:
    selected_base_url = (
        base_url.strip() if base_url_preset == "custom" else base_url_preset.strip()
    )

    if test_only == "1":
        # Test-only mode: only check connectivity, don't save anything
        connectivity_ok, connectivity_message = await _check_llm_connectivity(
            api_key, selected_base_url, model
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "settings.html",
            _build_settings_context(
                request,
                form_data={
                    "api_key": api_key,
                    "base_url": selected_base_url,
                    "base_url_preset": base_url_preset,
                    "model": model,
                    "default_location": default_location,
                },
                connectivity_ok=connectivity_ok,
                connectivity_message=connectivity_message,
                llm_save_message="测试完成",
            ),
        )

    # Save-only mode
    save_llm_config(
        api_key=api_key,
        base_url=selected_base_url,
        model=model,
    )
    save_default_location(default_location)

    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        _build_settings_context(
            request,
            form_data={
                "api_key": api_key,
                "base_url": selected_base_url,
                "base_url_preset": base_url_preset,
                "model": model,
                "default_location": default_location,
            },
            llm_save_message="配置已保存",
        ),
    )


@router.post("/settings/weights", response_class=HTMLResponse)
async def submit_weights(
    request: Request,
    fts_weight: str = Form(""),
    semantic_weight: str = Form(""),
) -> HTMLResponse:
    try:
        fw = float(fts_weight)
        sw = float(semantic_weight)
        fw = max(0.0, min(1.0, fw))
        sw = max(0.0, min(1.0, sw))
        save_search_weights(fw, sw)
        weight_save_message = "权重已保存"
    except ValueError:
        weight_save_message = "保存失败"

    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        _build_settings_context(
            request,
            form_data={
                "fts_weight": fts_weight,
                "semantic_weight": semantic_weight,
            },
            weight_save_message=weight_save_message,
        ),
    )


@router.post("/settings/search-mode", response_class=HTMLResponse)
async def submit_search_mode(
    request: Request,
    search_mode: str = Form("balanced"),
) -> HTMLResponse:
    """Save search mode preference (strict/balanced/loose)."""
    valid_modes = ["strict", "balanced", "loose"]
    if search_mode not in valid_modes:
        search_mode = "balanced"

    save_search_mode(search_mode)

    return request.app.state.templates.TemplateResponse(
        request,
        "settings.html",
        _build_settings_context(
            request,
            form_data={"search_mode": search_mode},
            search_mode_save_message="搜索模式已保存",
        ),
    )
