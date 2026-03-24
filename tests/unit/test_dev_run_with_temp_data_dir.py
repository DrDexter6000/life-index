#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


class TestRunWithTempDataDir:
    def test_creates_isolated_temp_data_root(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare()

        assert result.summary["created"] == 1
        assert Path(result.data_dir).exists()
        assert Path(result.data_dir).name == "Life-Index"

    def test_seed_mode_copies_existing_user_data(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals" / "2026" / "03").mkdir(parents=True)
        (
            source / "Journals" / "2026" / "03" / "life-index_2026-03-24_001.md"
        ).write_text("demo", encoding="utf-8")

        session = TempDataDirSession(
            base_tmp_dir=tmp_path, source_data_dir=source, seed=True
        )
        result = session.prepare()

        copied = (
            Path(result.data_dir)
            / "Journals"
            / "2026"
            / "03"
            / "life-index_2026-03-24_001.md"
        )
        assert copied.exists()
        assert result.summary["seeded"] == 1

    def test_print_report_includes_env_and_launch_guidance(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "LIFE_INDEX_DATA_DIR" in output
        assert "life-index serve" in output
        assert "删除该临时目录" in output

    def test_cleanup_removes_temp_root(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare()
        root = Path(result.temp_root)

        assert root.exists()
        session.cleanup()
        assert not root.exists()

    def test_name_option_is_reflected_in_temp_root(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path, name="web-acceptance")
        result = session.prepare()

        assert "web-acceptance" in Path(result.temp_root).name

    def test_print_report_includes_full_serve_command(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        session = TempDataDirSession(base_tmp_dir=tmp_path, name="web")
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "set LIFE_INDEX_DATA_DIR=" in output
        assert "life-index serve" in output
        assert "127.0.0.1:8765" in output

    def test_cleanup_now_option_removes_temp_root_immediately(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare(cleanup_now=True)

        assert not Path(result.temp_root).exists()
        assert result.summary["cleaned"] == 1

    def test_for_web_mode_prints_acceptance_checklist(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        session = TempDataDirSession(base_tmp_dir=tmp_path, name="web", for_web=True)
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "Web GUI 验收清单" in output
        assert "Dashboard 首页" in output
        assert "搜索页 drill-down" in output
        assert "journal 页面跳转" in output

    def test_for_web_mode_marks_result_and_outputs_web_url(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path, for_web=True)
        result = session.prepare()

        assert result.for_web is True
        assert result.web_url == "http://127.0.0.1:8765/"

    def test_seeded_web_mode_marks_readonly_simulation(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
            for_web=True,
        )
        result = session.prepare()

        assert result.seeded is True
        assert result.readonly_simulation is True

    def test_seeded_web_report_warns_no_write_back_to_real_user_data(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
            for_web=True,
        )
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "只读仿真验收" in output
        assert "不会回写真实用户目录" in output

    def test_for_web_mode_prints_fuller_checklist_and_post_acceptance_actions(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        session = TempDataDirSession(base_tmp_dir=tmp_path, for_web=True)
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "attachment 渲染" in output
        assert "验收后建议" in output
        assert "删除临时目录" in output
        assert "life-index index --rebuild" in output

    def test_json_output_contains_structured_web_acceptance_fields(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path, for_web=True)
        result = session.prepare().to_dict()

        assert result["for_web"] is True
        assert result["web_url"] == "http://127.0.0.1:8765/"
        assert "life-index serve" in result["serve_command"]
        assert isinstance(result["acceptance_checklist"], list)
        assert any("Dashboard" in item for item in result["acceptance_checklist"])
        assert any("attachment" in item for item in result["acceptance_checklist"])
        assert isinstance(result["post_acceptance_actions"], list)
        assert any(
            "life-index index --rebuild" in item
            for item in result["post_acceptance_actions"]
        )

    def test_json_output_contains_readonly_simulation_for_seeded_web_mode(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
            for_web=True,
        )
        result = session.prepare().to_dict()

        assert result["readonly_simulation"] is True

    def test_seeded_web_mode_shell_snippet_exports_readonly_simulation(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
            for_web=True,
        )
        result = session.prepare()

        assert "LIFE_INDEX_READONLY_SIMULATION" in result.shell_snippet
        assert "set LIFE_INDEX_READONLY_SIMULATION=1" in result.serve_command

    def test_json_output_contains_execution_profile_fields(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path, for_web=True)
        result = session.prepare().to_dict()

        assert result["mode"] == "web_acceptance"
        assert result["browser_url"] == "http://127.0.0.1:8765/"
        assert result["safe_to_delete_after"] is True
        assert "shell_snippet" in result
        assert "LIFE_INDEX_DATA_DIR" in result["shell_snippet"]
        assert "next_steps" in result
        assert isinstance(result["next_steps"], list)
        assert "cleanup_command" in result
        assert (
            "删除" in result["cleanup_command"]
            or "rmtree" in result["cleanup_command"]
            or "Remove-Item" in result["cleanup_command"]
        )
