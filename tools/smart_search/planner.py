#!/usr/bin/env python3
"""Additive Planner Recorder — M06 Option A (CHARTER §1.4, §1.5, §1.9).

Backward-compatible re-export shim.  The canonical implementations now live in
``tools.lib.planner_types`` (L2 shared library) so that L2 modules can import
them without creating an upward dependency on this L3 package.

All existing imports ``from tools.smart_search.planner import ...`` continue to
work unchanged.
"""

from __future__ import annotations

# Re-export all public symbols from the canonical L2 location.
from tools.lib.planner_types import (  # noqa: F401
    PlannerRecord,
    StageRecord,
    build_planner_record_from_stages,
    merge_planner_into_search_plan,
)

__all__ = [
    "StageRecord",
    "PlannerRecord",
    "build_planner_record_from_stages",
    "merge_planner_into_search_plan",
]
