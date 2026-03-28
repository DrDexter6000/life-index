#!/usr/bin/env python3
"""Tests for Web GUI scaffold — Phase 1."""

from pathlib import Path
import tomllib
from unittest.mock import patch

from tools.lib.errors import ErrorCode, LifeIndexError, ERROR_DESCRIPTIONS


class TestWebDependencies:
    """Verify web optional dependencies are declared correctly."""

    def test_web_optional_deps_declared(self) -> None:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        optional_deps = config["project"]["optional-dependencies"]
        assert "web" in optional_deps, "Missing [web] optional dependency group"

        web_deps = optional_deps["web"]
        dep_names = [d.split(">=")[0].split("[")[0].strip() for d in web_deps]
        assert "fastapi" in dep_names
        assert "uvicorn" in dep_names
        assert "jinja2" in dep_names
        assert "python-multipart" in dep_names
        assert "markdown" in dep_names
        assert "httpx" in dep_names

    def test_packages_find_includes_web(self) -> None:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)

        includes = config["tool"]["setuptools"]["packages"]["find"]["include"]
        assert any("web" in pat for pat in includes), (
            f"packages.find.include must contain 'web*', got: {includes}"
        )


class TestWebErrorCodes:
    """Verify E07xx error codes are defined correctly."""

    WEB_CODES = {
        "WEB_GENERAL_ERROR": ("E0700", "ask_user"),
        "URL_DOWNLOAD_FAILED": ("E0701", "skip_optional"),
        "URL_CONTENT_TYPE_REJECTED": ("E0702", "ask_user"),
        "LLM_PROVIDER_UNAVAILABLE": ("E0703", "skip_optional"),
        "LLM_EXTRACTION_FAILED": ("E0704", "skip_optional"),
        "GEOLOCATION_FAILED": ("E0705", "skip_optional"),
        "NOMINATIM_UNAVAILABLE": ("E0706", "skip_optional"),
        "WEB_DEPS_MISSING": ("E0707", "fail"),
    }

    def test_error_codes_exist(self) -> None:
        for name, (code, _) in self.WEB_CODES.items():
            assert hasattr(ErrorCode, name), f"Missing ErrorCode.{name}"
            assert getattr(ErrorCode, name) == code

    def test_recovery_strategies(self) -> None:
        for _, (code, strategy) in self.WEB_CODES.items():
            assert code in LifeIndexError.RECOVERY_STRATEGIES
            assert LifeIndexError.RECOVERY_STRATEGIES[code] == strategy

    def test_error_descriptions(self) -> None:
        for _, (code, _) in self.WEB_CODES.items():
            assert code in ERROR_DESCRIPTIONS
            assert len(ERROR_DESCRIPTIONS[code]) > 0


class TestWebPackageStructure:
    """Verify web/ package is importable and correctly structured."""

    def test_web_package_importable(self) -> None:
        import web

        assert hasattr(web, "__file__")

    def test_web_config_constants(self) -> None:
        from web.config import (
            DEFAULT_HOST,
            DEFAULT_PORT,
            WEB_DIR,
            TEMPLATES_DIR,
            STATIC_DIR,
        )

        assert DEFAULT_HOST == "127.0.0.1"
        assert DEFAULT_PORT == 8765
        assert isinstance(WEB_DIR, Path)
        assert isinstance(TEMPLATES_DIR, Path)
        assert isinstance(STATIC_DIR, Path)
        assert TEMPLATES_DIR == WEB_DIR / "templates"
        assert STATIC_DIR == WEB_DIR / "static"

    def test_web_subpackages_importable(self) -> None:
        import web.routes
        import web.services

    def test_static_directories_exist(self) -> None:
        from web.config import STATIC_DIR, TEMPLATES_DIR

        assert STATIC_DIR.is_dir()
        assert (STATIC_DIR / "css").is_dir()
        assert (STATIC_DIR / "js").is_dir()
        assert TEMPLATES_DIR.is_dir()


class TestAppFactory:
    """Verify FastAPI app factory creates a working application."""

    def test_create_app_returns_fastapi(self) -> None:
        from web.app import create_app
        from fastapi import FastAPI

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_health_endpoint(self) -> None:
        from web.app import create_app
        from fastapi.testclient import TestClient

        client = TestClient(create_app())
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_static_files_mounted(self) -> None:
        from web.app import create_app
        from fastapi.testclient import TestClient

        client = TestClient(create_app())
        response = client.get("/static/css/app.css")
        assert response.status_code == 200

    def test_templates_configured(self) -> None:
        from web.app import create_app

        app = create_app()
        assert hasattr(app.state, "templates")


class TestServeCommand:
    """Verify CLI serve command setup."""

    def test_serve_in_cmd_map(self) -> None:
        main_path = Path(__file__).parent.parent.parent / "tools" / "__main__.py"
        source = main_path.read_text(encoding="utf-8")
        assert '"serve"' in source
        assert "web.__main__" in source

    def test_web_main_has_main_function(self) -> None:
        from web.__main__ import main

        assert callable(main)

    def test_web_main_parses_port_argument(self) -> None:
        from web.__main__ import parse_args

        args = parse_args(["--port", "9000"])
        assert args.port == 9000

    def test_web_main_parses_host_argument(self) -> None:
        from web.__main__ import parse_args

        args = parse_args(["--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"

    def test_web_main_default_values(self) -> None:
        from web.__main__ import parse_args

        args = parse_args([])
        assert args.port == 8765
        assert args.host == "127.0.0.1"
        assert args.reload is False

    def test_web_main_reload_flag(self) -> None:
        from web.__main__ import parse_args

        args = parse_args(["--reload"])
        assert args.reload is True

    def test_web_main_prints_operator_runtime_guidance(self) -> None:
        from web.__main__ import main

        with (
            patch("web.__main__.parse_args") as mock_parse_args,
            patch("web.__main__.check_deps", return_value=(True, None)),
            patch("uvicorn.run") as mock_run,
            patch("builtins.print") as mock_print,
        ):
            mock_parse_args.return_value.host = "127.0.0.1"
            mock_parse_args.return_value.port = 8765
            mock_parse_args.return_value.reload = False

            main()

        assert mock_run.called
        printed_messages = [
            str(call.args[0]) for call in mock_print.call_args_list if call.args
        ]
        assert any(
            "Life Index Web GUI starting" in message for message in printed_messages
        )
        assert any("http://127.0.0.1:8765" in message for message in printed_messages)

    def test_app_startup_logs_active_runtime_data_source(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with patch("builtins.print") as mock_print:
            with TestClient(create_app()):
                pass

        printed_messages = [
            str(call.args[0]) for call in mock_print.call_args_list if call.args
        ]
        assert any(
            "Life Index Web GUI runtime" in message for message in printed_messages
        )


class TestBaseTemplate:
    """Verify base.html template structure and rendering."""

    def test_base_template_exists(self) -> None:
        from web.config import TEMPLATES_DIR

        assert (TEMPLATES_DIR / "base.html").is_file()

    def test_base_template_contains_polished_nav_controls(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8") + (
            TEMPLATES_DIR / "components" / "header.html"
        ).read_text(encoding="utf-8")
        assert "min-h-[44px]" in source
        assert "inline-flex items-center justify-center" in source
        assert "rounded-xl" in source
        assert "rounded-md text-sm font-medium text-white bg-indigo-600" not in source
        assert "切换深色模式" in source
        assert "切换浅色模式" in source

    def test_base_template_bootstraps_theme_before_alpine(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
        bootstrap_marker = "document.documentElement.classList.toggle('dark'"
        alpine_marker = "cdn.jsdelivr.net/npm/alpinejs"

        assert bootstrap_marker in source
        assert source.index(bootstrap_marker) < source.index(alpine_marker)

    def test_base_template_includes_echarts_cdn_and_extra_scripts_block(self) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")

        assert "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js" in source
        assert "{% block extra_scripts %}{% endblock %}" in source

    def test_base_template_uses_clean_layout_without_runtime_transparency_banner(
        self,
    ) -> None:
        from web.config import TEMPLATES_DIR

        source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")

        assert (
            '<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 min-h-[44px]">'
            in source
        )
        assert "当前数据源" not in source

    def test_runtime_banner_is_not_rendered_in_base_template_output(self) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        with TestClient(create_app()) as client:
            response = client.get("/")

        assert response.status_code == 200
        assert "当前数据源" not in response.text

    def test_runtime_banner_readonly_copy_is_not_rendered(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        from fastapi.testclient import TestClient
        from web.app import create_app

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path / "sandbox"))
        monkeypatch.setenv("LIFE_INDEX_READONLY_SIMULATION", "1")

        with TestClient(create_app()) as client:
            response = client.get("/")

        assert response.status_code == 200
        assert "只读仿真" not in response.text

    def test_batch_k_copy_and_cta_polish_present(self) -> None:
        from web.config import TEMPLATES_DIR

        write_source = (TEMPLATES_DIR / "write.html").read_text(encoding="utf-8")
        search_source = (TEMPLATES_DIR / "search.html").read_text(encoding="utf-8")
        results_source = (TEMPLATES_DIR / "partials" / "search_results.html").read_text(
            encoding="utf-8"
        )

        assert 'id="add-url-btn"' in write_source
        assert 'id="submit-btn"' in write_source
        assert "min-h-[46px]" in write_source
        assert 'id="location"' in write_source
        assert "block w-full flex-1" in write_source
        assert "min-h-[44px]" in search_source
        assert "共找到" in results_source
        assert "🔍" in results_source
        assert "开始搜索日志" in results_source
