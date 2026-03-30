#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


class TestWebHealthRuntimeInfo:
    def test_health_exposes_runtime_data_source_info(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/api/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["version"] == "1.5.5"
        assert "bootstrap_manifest" in payload
        assert payload["bootstrap_manifest"]["repo_version"] == "1.5.5"
        assert "runtime" in payload
        assert "user_data_dir" in payload["runtime"]
        assert "journals_dir" in payload["runtime"]

    def test_health_reports_override_and_readonly_runtime_flags(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path / "sandbox"))
        monkeypatch.setenv("LIFE_INDEX_READONLY_SIMULATION", "1")

        client = TestClient(create_app())
        response = client.get("/api/health")

        assert response.status_code == 200
        runtime = response.json()["runtime"]
        assert runtime["life_index_data_dir_override"] is True
        assert runtime["readonly_simulation"] is True

    def test_health_reports_active_data_source_paths(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        sandbox = tmp_path / "sandbox"
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(sandbox))

        client = TestClient(create_app())
        response = client.get("/api/health")

        assert response.status_code == 200
        runtime = response.json()["runtime"]
        assert runtime["user_data_dir"] == str(sandbox)
        assert runtime["journals_dir"] == str(sandbox / "Journals")


class TestWebRuntimeEndpoint:
    def test_runtime_endpoint_exposes_runtime_contract(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        client = TestClient(create_app())
        response = client.get("/api/runtime")

        assert response.status_code == 200
        payload = response.json()
        assert payload["package_version"] == "1.5.5"
        assert "bootstrap_manifest" in payload
        assert payload["bootstrap_manifest"]["repo_version"] == "1.5.5"
        assert "user_data_dir" in payload
        assert "journals_dir" in payload
        assert "life_index_data_dir_override" in payload
        assert "readonly_simulation" in payload

    def test_runtime_endpoint_reflects_active_override_and_readonly_flags(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        sandbox = tmp_path / "sandbox"
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(sandbox))
        monkeypatch.setenv("LIFE_INDEX_READONLY_SIMULATION", "1")

        client = TestClient(create_app())
        response = client.get("/api/runtime")

        assert response.status_code == 200
        payload = response.json()
        assert payload["user_data_dir"] == str(sandbox)
        assert payload["journals_dir"] == str(sandbox / "Journals")
        assert payload["life_index_data_dir_override"] is True
        assert payload["readonly_simulation"] is True
