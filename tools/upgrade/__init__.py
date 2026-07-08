"""Deterministic host-agent upgrade planning and apply helpers."""

from __future__ import annotations

from .core import (
    CommandResult,
    GitState,
    InstallContext,
    ReleaseInfo,
    apply_upgrade,
    build_upgrade_plan,
    detect_install_context,
)

__all__ = [
    "CommandResult",
    "GitState",
    "InstallContext",
    "ReleaseInfo",
    "apply_upgrade",
    "build_upgrade_plan",
    "detect_install_context",
]
