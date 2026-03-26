"""
Contract tests: Web GUI output MUST match CLI output format.

这些测试确保 Web GUI 的输出格式与 CLI 工具完全一致。
如果这些测试失败，说明 Web 层绕过了 CLI 或做了不当的格式转换。
"""

import os
from pathlib import Path

import pytest

from tools.write_journal.core import write_journal
from tools.edit_journal import edit_journal
from tools.lib.frontmatter import parse_frontmatter


@pytest.fixture
def temp_data_dir(tmp_path: Path):
    """创建临时数据目录并设置环境变量"""
    data_dir = tmp_path / "life-index-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "Journals").mkdir(exist_ok=True)
    (data_dir / "attachments").mkdir(exist_ok=True)
    (data_dir / "by-topic").mkdir(exist_ok=True)

    old_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(data_dir)

    # 重新导入 config 以使用新路径
    import importlib
    import tools.lib.config as config

    importlib.reload(config)

    yield data_dir

    # 恢复环境变量
    if old_env is not None:
        os.environ["LIFE_INDEX_DATA_DIR"] = old_env
    else:
        os.environ.pop("LIFE_INDEX_DATA_DIR", None)
    importlib.reload(config)


class TestWebCLIAlignment:
    """Web GUI 与 CLI 格式对齐测试"""

    def test_tags_format_alignment(self, temp_data_dir: Path):
        """tags 字段必须是数组格式，不是逗号分隔字符串"""
        web_result = write_journal(
            {
                "title": "Web test",
                "content": "test",
                "date": "2026-03-26",
                "tags": "tag1, tag2, tag3",
            },
            dry_run=False,
        )
        cli_result = write_journal(
            {
                "title": "CLI test",
                "content": "test",
                "date": "2026-03-26",
                "tags": ["tag1", "tag2", "tag3"],
            },
            dry_run=False,
        )

        web_journal = Path(web_result["journal_path"])
        cli_journal = Path(cli_result["journal_path"])

        web_fm, _ = parse_frontmatter(web_journal.read_text(encoding="utf-8"))
        cli_fm, _ = parse_frontmatter(cli_journal.read_text(encoding="utf-8"))

        assert isinstance(web_fm["tags"], list), "Web tags 必须是数组"
        assert (
            web_fm["tags"] == cli_fm["tags"]
        ), f"tags 不一致: {web_fm['tags']} vs {cli_fm['tags']}"

    def test_mood_format_alignment(self, temp_data_dir: Path):
        """mood 字段必须是数组格式"""
        web_result = write_journal(
            {
                "title": "Web test",
                "content": "test",
                "date": "2026-03-26",
                "mood": "开心, 充实",
            },
            dry_run=False,
        )
        cli_result = write_journal(
            {
                "title": "CLI test",
                "content": "test",
                "date": "2026-03-26",
                "mood": ["开心", "充实"],
            },
            dry_run=False,
        )

        web_journal = Path(web_result["journal_path"])
        cli_journal = Path(cli_result["journal_path"])

        web_fm, _ = parse_frontmatter(web_journal.read_text(encoding="utf-8"))
        cli_fm, _ = parse_frontmatter(cli_journal.read_text(encoding="utf-8"))

        assert isinstance(web_fm["mood"], list), "Web mood 必须是数组"
        assert web_fm["mood"] == cli_fm["mood"], f"mood 不一致"

    def test_edit_preserves_array_format(self, temp_data_dir: Path):
        """编辑时必须保留数组格式"""
        result = write_journal(
            {
                "title": "Test",
                "content": "test",
                "date": "2026-03-26",
                "tags": ["tag1", "tag2"],
            },
            dry_run=False,
        )

        journal_path = Path(result["journal_path"])
        edit_result = edit_journal(journal_path, frontmatter_updates={"tags": "tag3, tag4"})

        assert edit_result["success"]

        fm, _ = parse_frontmatter(journal_path.read_text(encoding="utf-8"))
        assert isinstance(fm["tags"], list), "编辑后 tags 必须仍是数组"
        assert fm["tags"] == ["tag3", "tag4"], f"tags 错误: {fm['tags']}"

    def test_attachment_format_alignment(self, temp_data_dir: Path):
        """附件格式必须包含完整元数据"""
        attachment = temp_data_dir / "test.txt"
        attachment.write_text("test content", encoding="utf-8")

        result = write_journal(
            {
                "title": "Test",
                "content": "test",
                "date": "2026-03-26",
                "attachments": [{"source_path": str(attachment), "description": "test"}],
            },
            dry_run=False,
        )

        journal_path = Path(result["journal_path"])
        fm, _ = parse_frontmatter(journal_path.read_text(encoding="utf-8"))

        assert isinstance(fm["attachments"], list), "attachments 必须是数组"
        if fm["attachments"]:
            att = fm["attachments"][0]
            assert "filename" in att, "附件必须有 filename"
            assert "rel_path" in att, "附件必须有 rel_path"
