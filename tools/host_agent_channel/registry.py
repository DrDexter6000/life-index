"""Single authority for the approved Host Agent capability surface.

This registry is intentionally closed.  Transports may project these methods,
but cannot add methods, schemas, or side-effect authority of their own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Literal, TypeAlias


class OperationClass(str, Enum):
    """The only operation class admitted for this initial channel."""

    READ = "read"


class DerivedStateEffect(str, Enum):
    """Explicitly bounded derived-state effects of a capability."""

    NONE = "none"
    INDEX_REFRESH = "index_refresh"


@dataclass(frozen=True)
class HealthParams:
    """The canonical health operation has no channel parameters."""


@dataclass(frozen=True)
class JournalGetParams:
    """One canonical journal selector; the current v0 id is its relative path."""

    path: str | None = field(
        default=None,
        metadata={"description": "Canonical journal relative path under Journals/."},
    )
    id: str | None = field(
        default=None,
        metadata={"description": "Current v0 journal id (equal to the relative path)."},
    )


@dataclass(frozen=True)
class SearchParams:
    """Typed, deterministic query inputs accepted by the channel search method."""

    query: str | None = field(default=None, metadata={"description": "Search query."})
    topic: str | None = field(default=None, metadata={"description": "Topic filter."})
    project: str | None = field(default=None, metadata={"description": "Project filter."})
    tags: tuple[str, ...] | None = field(
        default=None,
        metadata={"description": "Tag filters."},
    )
    mood: tuple[str, ...] | None = field(
        default=None,
        metadata={"description": "Mood filters."},
    )
    people: tuple[str, ...] | None = field(
        default=None,
        metadata={"description": "People filters."},
    )
    date_from: str | None = field(
        default=None,
        metadata={"description": "Inclusive YYYY-MM-DD start."},
    )
    date_to: str | None = field(default=None, metadata={"description": "Inclusive YYYY-MM-DD end."})
    location: str | None = field(default=None, metadata={"description": "Location filter."})
    weather: str | None = field(default=None, metadata={"description": "Weather filter."})
    year: int | None = field(default=None, metadata={"description": "L0 year prefilter."})
    month: int | None = field(default=None, metadata={"description": "L0 month prefilter."})
    level: Literal[1, 2, 3] = field(default=3, metadata={"description": "Search level."})
    use_index: bool = field(
        default=True,
        metadata={"description": "Use the FTS index when available."},
    )
    semantic: bool = field(
        default=False,
        metadata={"description": "Deprecated compatibility no-op."},
    )
    semantic_weight: float = field(
        default=1.0,
        metadata={"description": "Deprecated compatibility no-op."},
    )
    fts_weight: float = field(
        default=1.0,
        metadata={"description": "Deprecated compatibility no-op."},
    )
    explain: bool = field(
        default=False,
        metadata={"description": "Include deterministic diagnostics."},
    )
    semantic_policy: Literal["fallback", "hybrid"] = field(
        default="fallback",
        metadata={"description": "Deprecated compatibility no-op policy."},
    )
    enable_source_tier: bool = field(
        default=False,
        metadata={"description": "Enable the existing deterministic source-tier boost."},
    )
    limit: int = field(
        default=20,
        metadata={"description": "Page size; zero returns all matches."},
    )
    offset: int = field(default=0, metadata={"description": "Zero-based result offset."})


CapabilityParams: TypeAlias = HealthParams | JournalGetParams | SearchParams


@dataclass(frozen=True)
class CapabilityDefinition:
    """A transport-neutral capability description owned by this registry."""

    method_id: str
    description: str
    params_type: type[CapabilityParams]
    operation_class: OperationClass
    derived_state_effect: DerivedStateEffect
    derived_state_paths: tuple[str, ...] = ()
    derived_state_rebuildable: bool = False
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False


def projection_annotations(capability: CapabilityDefinition) -> dict[str, bool]:
    """Derive transport hints from registry-owned logical and physical effect facts."""
    return {
        "readOnlyHint": (
            capability.operation_class is OperationClass.READ
            and capability.derived_state_effect is DerivedStateEffect.NONE
        ),
        "destructiveHint": capability.destructive,
        "idempotentHint": capability.idempotent,
        "openWorldHint": capability.open_world,
    }


CAPABILITY_REGISTRY: Mapping[str, CapabilityDefinition] = MappingProxyType(
    {
        "health": CapabilityDefinition(
            method_id="health",
            description=(
                "Return the canonical Life Index health envelope. Logical read; it performs "
                "no derived-state write."
            ),
            params_type=HealthParams,
            operation_class=OperationClass.READ,
            derived_state_effect=DerivedStateEffect.NONE,
        ),
        "journal.get": CapabilityDefinition(
            method_id="journal.get",
            description=(
                "Read one canonical journal entry by id or relative path. Logical read; it "
                "performs no derived-state write."
            ),
            params_type=JournalGetParams,
            operation_class=OperationClass.READ,
            derived_state_effect=DerivedStateEffect.NONE,
        ),
        "search": CapabilityDefinition(
            method_id="search",
            description=(
                "Run canonical deterministic journal retrieval. Logical read; it may refresh only "
                "rebuildable `.index` derived state and cannot mutate journals, frontmatter, "
                "attachments, "
                "entity graph, metadata cache, or search metrics."
            ),
            params_type=SearchParams,
            operation_class=OperationClass.READ,
            derived_state_effect=DerivedStateEffect.INDEX_REFRESH,
            derived_state_paths=(".index",),
            derived_state_rebuildable=True,
            idempotent=False,
        ),
    }
)
