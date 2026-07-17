"""Contract tests for the transport-neutral Host Agent capability registry."""

from __future__ import annotations

from typing import Any, cast

import pytest


def test_registry_is_the_single_exact_read_authority() -> None:
    """Only the approved three method IDs may be exposed by the registry."""
    from tools.host_agent_channel.registry import (
        CAPABILITY_REGISTRY,
        DerivedStateEffect,
        HealthParams,
        JournalGetParams,
        OperationClass,
        SearchParams,
        projection_annotations,
    )

    assert tuple(CAPABILITY_REGISTRY) == ("health", "journal.get", "search")
    assert CAPABILITY_REGISTRY["health"].params_type is HealthParams
    assert CAPABILITY_REGISTRY["journal.get"].params_type is JournalGetParams
    assert CAPABILITY_REGISTRY["search"].params_type is SearchParams
    assert {capability.operation_class for capability in CAPABILITY_REGISTRY.values()} == {
        OperationClass.READ
    }
    assert CAPABILITY_REGISTRY["health"].derived_state_effect is DerivedStateEffect.NONE
    assert CAPABILITY_REGISTRY["journal.get"].derived_state_effect is DerivedStateEffect.NONE
    assert CAPABILITY_REGISTRY["search"].derived_state_effect is DerivedStateEffect.INDEX_REFRESH
    assert CAPABILITY_REGISTRY["search"].derived_state_paths == (".index",)
    assert CAPABILITY_REGISTRY["search"].derived_state_rebuildable is True
    assert {
        method_id: projection_annotations(capability)
        for method_id, capability in CAPABILITY_REGISTRY.items()
    } == {
        "health": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["health"].idempotent,
            "openWorldHint": False,
        },
        "journal.get": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["journal.get"].idempotent,
            "openWorldHint": False,
        },
        "search": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": CAPABILITY_REGISTRY["search"].idempotent,
            "openWorldHint": False,
        },
    }


def test_registry_is_runtime_immutable_and_describes_the_search_effect() -> None:
    """The closed registry rejects mutation and owns the projection facts."""
    from tools.host_agent_channel.registry import CAPABILITY_REGISTRY

    mutable_registry = cast(Any, CAPABILITY_REGISTRY)
    try:
        with pytest.raises(TypeError):
            mutable_registry["write"] = CAPABILITY_REGISTRY["health"]
    finally:
        if isinstance(mutable_registry, dict):
            mutable_registry.pop("write", None)

    search = CAPABILITY_REGISTRY["search"]
    assert "Logical read" in search.description
    assert "may refresh only rebuildable `.index` derived state" in search.description
    for protected_target in (
        "journals",
        "frontmatter",
        "attachments",
        "entity graph",
        "metadata cache",
        "search metrics",
    ):
        assert protected_target in search.description
    for method_id in ("health", "journal.get"):
        assert "no derived-state write" in CAPABILITY_REGISTRY[method_id].description


def test_forbidden_method_is_rejected_before_any_core_handler_runs(monkeypatch) -> None:
    """Write/case-variant methods never reach the registered-handler boundary."""
    import tools.host_agent_channel.dispatcher as dispatcher

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a forbidden method reached a Core handler")

    monkeypatch.setattr(dispatcher, "_dispatch_registered", fail_if_called)

    with pytest.raises(dispatcher.MethodNotAllowed, match="write"):
        dispatcher.dispatch("write", {"title": "must not run"})
    with pytest.raises(dispatcher.MethodNotAllowed, match="SEARCH"):
        dispatcher.dispatch("SEARCH", {"query": "must not run"})
