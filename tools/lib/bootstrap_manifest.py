"""Bootstrap manifest loading for checkout and installed package layouts."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any, cast

REPO_BOOTSTRAP_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "bootstrap-manifest.json"
PACKAGED_BOOTSTRAP_MANIFEST_NAME = "bootstrap-manifest.json"


def _validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("bootstrap-manifest.json must contain a JSON object")
    return cast(dict[str, Any], payload)


def _read_manifest_path(path: Path) -> dict[str, Any]:
    return _validate_manifest(json.loads(path.read_text(encoding="utf-8")))


def _iter_tools_package_dirs() -> list[Path]:
    tools_package = import_module("tools")
    package_paths = getattr(tools_package, "__path__", ())
    return [Path(raw_path) for raw_path in package_paths if Path(raw_path).is_dir()]


def _read_packaged_manifest() -> dict[str, Any]:
    for package_dir in _iter_tools_package_dirs():
        candidate = package_dir / PACKAGED_BOOTSTRAP_MANIFEST_NAME
        try:
            return _read_manifest_path(candidate)
        except OSError:
            continue
    raise FileNotFoundError(f"{PACKAGED_BOOTSTRAP_MANIFEST_NAME} not found in tools package")


def read_bootstrap_manifest(preferred_path: Path | None = None) -> dict[str, Any]:
    """Read bootstrap manifest from checkout root, then package resource fallback."""
    manifest_path = preferred_path or REPO_BOOTSTRAP_MANIFEST_PATH
    try:
        return _read_manifest_path(manifest_path)
    except OSError:
        return _read_packaged_manifest()


def get_manifest_version(preferred_path: Path | None = None) -> str | None:
    """Return repo_version from the bootstrap manifest if available."""
    try:
        payload = read_bootstrap_manifest(preferred_path=preferred_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    version = payload.get("repo_version")
    return version if isinstance(version, str) else None
