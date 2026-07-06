#!/usr/bin/env python3
"""Entity maintenance rhythm exposed through health."""

from __future__ import annotations

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.lib.entity_graph import save_entity_graph


def _run_health(data_dir: Path, monkeypatch, capsys) -> dict:
    from tools.__main__ import health_check

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(__version__="test"))
    health_check()
    return json.loads(capsys.readouterr().out)


def _save_graph(data_dir: Path, entities: list[dict]) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(entities, graph_path)
    return graph_path


def _confirmed_graph() -> list[dict]:
    return [
        {
            "id": "person-alice",
            "type": "actor",
            "primary_name": "Alice",
            "source": "user",
            "status": "confirmed",
            "relationships": [],
        }
    ]


def test_health_entity_maintenance_green_when_current_and_no_pending(
    isolated_data_dir: Path,
    monkeypatch,
    capsys,
) -> None:
    _save_graph(isolated_data_dir, _confirmed_graph())

    payload = _run_health(isolated_data_dir, monkeypatch, capsys)

    entity = payload["data"]["entity_maintenance"]
    assert entity["traffic_light"] == "green"
    assert entity["pending_count"] == 0
    assert entity["audit_age_days"] <= 30
    assert entity["review_command"] == "life-index entity --review"


def test_health_reports_entity_profiles_stale_event(
    isolated_data_dir: Path,
    monkeypatch,
    capsys,
) -> None:
    _save_graph(isolated_data_dir, _confirmed_graph())

    payload = _run_health(isolated_data_dir, monkeypatch, capsys)

    events = payload["events"]
    matching = [event for event in events if event["type"] == "entity_profiles_stale"]
    assert len(matching) == 1
    assert matching[0]["severity"] == "info"
    assert "life-index abstract --entities" in matching[0]["message"]
    assert matching[0]["data"]["suggested_command"] == "life-index abstract --entities"


def test_health_entity_maintenance_yellow_for_pending_candidates(
    isolated_data_dir: Path,
    monkeypatch,
    capsys,
) -> None:
    _save_graph(
        isolated_data_dir,
        _confirmed_graph()
        + [
            {
                "id": "person-morgan",
                "type": "actor",
                "primary_name": "Morgan",
                "source": "agent",
                "status": "candidate",
                "reason": "Host agent hypothesis.",
                "relationships": [],
            }
        ],
    )

    payload = _run_health(isolated_data_dir, monkeypatch, capsys)

    entity = payload["data"]["entity_maintenance"]
    assert entity["traffic_light"] == "yellow"
    assert entity["pending_count"] == 1
    assert entity["suggested_next_step"]["command"] == "life-index entity --review"


def test_health_entity_maintenance_yellow_when_audit_is_stale(
    isolated_data_dir: Path,
    monkeypatch,
    capsys,
) -> None:
    graph_path = _save_graph(isolated_data_dir, _confirmed_graph())
    old = datetime.now(timezone.utc) - timedelta(days=31)
    os.utime(graph_path, (old.timestamp(), old.timestamp()))

    payload = _run_health(isolated_data_dir, monkeypatch, capsys)

    entity = payload["data"]["entity_maintenance"]
    assert entity["traffic_light"] == "yellow"
    assert entity["audit_age_days"] >= 31


def test_health_entity_maintenance_red_for_duplicates(
    isolated_data_dir: Path,
    monkeypatch,
    capsys,
) -> None:
    _save_graph(
        isolated_data_dir,
        [
            {
                "id": "person-morgan-a",
                "type": "actor",
                "primary_name": "Morgan",
                "relationships": [],
            },
            {
                "id": "person-morgan-b",
                "type": "actor",
                "primary_name": "Morgan",
                "relationships": [],
            },
        ],
    )

    payload = _run_health(isolated_data_dir, monkeypatch, capsys)

    entity = payload["data"]["entity_maintenance"]
    assert entity["traffic_light"] == "red"
    assert entity["duplicate_count"] >= 1
    assert entity["suggested_next_step"]["command"] == "life-index entity --review"
