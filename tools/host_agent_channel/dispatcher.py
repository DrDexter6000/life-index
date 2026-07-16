"""Transport-neutral dispatch gate for the closed Host Agent capability registry."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from typing import Any

from .registry import (
    CAPABILITY_REGISTRY,
    CapabilityDefinition,
    CapabilityParams,
    HealthParams,
    JournalGetParams,
    SearchParams,
)


class MethodNotAllowed(ValueError):
    """Raised before Core execution for every non-canonical method id."""


class InvalidParameters(ValueError):
    """Raised before Core execution for malformed typed channel parameters."""


def dispatch(method_id: str, params: CapabilityParams | dict[str, Any]) -> dict[str, Any]:
    """Dispatch one exact registered method; adapters supply only structured inputs."""
    capability = CAPABILITY_REGISTRY.get(method_id)
    if capability is None:
        raise MethodNotAllowed(f"Method not allowed: {method_id}")
    return _dispatch_registered(capability, _coerce_params(capability, params))


def _coerce_params(
    capability: CapabilityDefinition,
    params: CapabilityParams | dict[str, Any],
) -> CapabilityParams:
    """Validate a mapping into the one registered typed parameter object."""
    expected_type = capability.params_type
    if isinstance(params, expected_type):
        typed = params
    else:
        if not isinstance(params, Mapping):
            raise InvalidParameters(f"{capability.method_id} parameters must be an object.")
        allowed = {field.name for field in fields(expected_type)}
        unknown = sorted(set(params) - allowed)
        if unknown:
            raise InvalidParameters(
                f"{capability.method_id} received unsupported parameter(s): {', '.join(unknown)}."
            )
        try:
            typed = expected_type(**dict(params))
        except TypeError as exc:
            raise InvalidParameters(f"Invalid {capability.method_id} parameters: {exc}") from exc

    if isinstance(typed, HealthParams):
        return typed
    if isinstance(typed, JournalGetParams):
        _validate_journal_get(typed)
        return typed
    if isinstance(typed, SearchParams):
        _validate_search(typed)
        return typed
    raise InvalidParameters(f"Unsupported typed parameters for {capability.method_id}.")


def _validate_journal_get(params: JournalGetParams) -> None:
    if (params.path is None) == (params.id is None):
        raise InvalidParameters("journal.get requires exactly one of path or id.")
    if params.path is not None and not isinstance(params.path, str):
        raise InvalidParameters("journal.get path must be a string.")
    if params.id is not None and not isinstance(params.id, str):
        raise InvalidParameters("journal.get id must be a string.")


def _validate_search(params: SearchParams) -> None:
    text_fields = (
        "query",
        "topic",
        "project",
        "date_from",
        "date_to",
        "location",
        "weather",
    )
    for field_name in text_fields:
        value = getattr(params, field_name)
        if value is not None and not isinstance(value, str):
            raise InvalidParameters(f"search {field_name} must be a string or null.")
    for field_name in ("tags", "mood", "people"):
        value = getattr(params, field_name)
        if value is not None and (
            not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value)
        ):
            raise InvalidParameters(f"search {field_name} must be an array of strings or null.")
    integer_fields = ("year", "month", "level", "limit", "offset")
    for field_name in integer_fields:
        value = getattr(params, field_name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise InvalidParameters(f"search {field_name} must be an integer or null.")
    if params.level not in (1, 2, 3):
        raise InvalidParameters("search level must be 1, 2, or 3.")
    if params.limit < 0:
        raise InvalidParameters("search limit must be non-negative.")
    if params.offset < 0:
        raise InvalidParameters("search offset must be non-negative.")
    if params.month is not None and params.month not in range(1, 13):
        raise InvalidParameters("search month must be between 1 and 12.")
    if params.semantic_policy not in {"fallback", "hybrid"}:
        raise InvalidParameters("search semantic_policy must be fallback or hybrid.")
    for field_name in ("use_index", "semantic", "explain", "enable_source_tier"):
        if not isinstance(getattr(params, field_name), bool):
            raise InvalidParameters(f"search {field_name} must be a boolean.")
    for field_name in ("semantic_weight", "fts_weight"):
        value = getattr(params, field_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise InvalidParameters(f"search {field_name} must be a number.")


def _dispatch_registered(
    capability: CapabilityDefinition,
    params: CapabilityParams,
) -> dict[str, Any]:
    """Call the same canonical application functions used by the direct CLI."""
    if capability.method_id == "health":
        from tools.__main__ import build_health_payload

        return build_health_payload()
    if capability.method_id == "journal.get":
        from tools.journal.__main__ import run_journal_get

        assert isinstance(params, JournalGetParams)
        return run_journal_get(path=params.path, id=params.id)
    if capability.method_id == "search":
        from tools.search_journals.__main__ import run_search

        assert isinstance(params, SearchParams)
        return run_search(
            query=params.query,
            topic=params.topic,
            project=params.project,
            tags=params.tags,
            mood=params.mood,
            people=params.people,
            date_from=params.date_from,
            date_to=params.date_to,
            location=params.location,
            weather=params.weather,
            year=params.year,
            month=params.month,
            level=params.level,
            use_index=params.use_index,
            semantic=params.semantic,
            semantic_weight=params.semantic_weight,
            fts_weight=params.fts_weight,
            explain=params.explain,
            semantic_policy=params.semantic_policy,
            enable_source_tier=params.enable_source_tier,
            limit=params.limit,
            offset=params.offset,
            source_safe=True,
        )
    raise MethodNotAllowed(f"Method not allowed: {capability.method_id}")
