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
        assert "life-index health" in output
        assert "life-index index" in output
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

        session = TempDataDirSession(base_tmp_dir=tmp_path, name="acceptance")
        result = session.prepare()

        assert "acceptance" in Path(result.temp_root).name

    def test_print_report_includes_full_shell_command(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession, print_report
        from contextlib import redirect_stdout
        from io import StringIO

        session = TempDataDirSession(base_tmp_dir=tmp_path, name="sandbox")
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "set LIFE_INDEX_DATA_DIR=" in output
        assert "life-index health" in output
        assert "life-index index" in output

    def test_cleanup_now_option_removes_temp_root_immediately(
        self, tmp_path: Path
    ) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare(cleanup_now=True)

        assert not Path(result.temp_root).exists()
        assert result.summary["cleaned"] == 1

    def test_json_output_contains_execution_profile_fields(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        session = TempDataDirSession(base_tmp_dir=tmp_path)
        result = session.prepare().to_dict()

        assert result["mode"] == "generic"
        assert result["safe_to_delete_after"] is True
        assert "shell_snippet" in result
        assert "LIFE_INDEX_DATA_DIR" in result["shell_snippet"]
        assert "life-index health" in result["shell_snippet"]
        assert "life-index index" in result["shell_snippet"]
        assert "next_steps" in result
        assert isinstance(result["next_steps"], list)
        assert "cleanup_command" in result

    def test_seeded_mode_marks_result_and_preserves_seed_flag(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
        )
        result = session.prepare()

        assert result.seeded is True
        assert result.summary["seeded"] == 1

    def test_seeded_report_warns_data_is_copied_from_source(
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
        )
        result = session.prepare()

        buffer = StringIO()
        with redirect_stdout(buffer):
            print_report(result, use_json=False)

        output = buffer.getvalue()
        assert "种子来源" in output
        assert str(source) in output

    def test_json_output_contains_seeded_source_directory(self, tmp_path: Path) -> None:
        from tools.dev.run_with_temp_data_dir import TempDataDirSession

        source = tmp_path / "source"
        (source / "Journals").mkdir(parents=True)

        session = TempDataDirSession(
            base_tmp_dir=tmp_path,
            source_data_dir=source,
            seed=True,
        )
        result = session.prepare().to_dict()

        assert result["seeded"] is True
        assert result["source_data_dir"] == str(source)
