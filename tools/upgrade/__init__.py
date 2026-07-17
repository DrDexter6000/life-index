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
from .install_integrity import inventory_life_index_distributions
from .install_integrity import recover_install

__all__ = [
    "CommandResult",
    "GitState",
    "InstallContext",
    "ReleaseInfo",
    "apply_upgrade",
    "build_upgrade_plan",
    "detect_install_context",
    "inventory_life_index_distributions",
    "recover_install",
]
