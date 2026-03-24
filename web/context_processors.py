"""Template global context helpers."""

from __future__ import annotations

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

from web.runtime import get_runtime_info


def _get_current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_app_version() -> str:
    try:
        return version("life-index")
    except PackageNotFoundError:
        return "dev"


def _get_runtime_banner_data() -> dict[str, object]:
    return get_runtime_info()


def global_context() -> dict[str, object]:
    return {
        "current_date": _get_current_date,
        "app_version": _get_app_version,
        "runtime_banner": _get_runtime_banner_data,
    }
