"""Contract tests for the transport-neutral Host Agent capability registry."""

from __future__ import annotations

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
    )

    assert set(CAPABILITY_REGISTRY) == {"health", "journal.get", "search"}
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
