"""
Contract tests: Web GUI output MUST match CLI output format.

这些测试确保 Web GUI 的输出格式与 CLI 工具完全一致。
如果这些测试失败，说明 Web 层绕过了 CLI 或做了不当的格式转换。

Phase 1.5.5 新增:
- test_prepare_metadata_alignment: Web/CLI 元数据准备一致性
- test_field_sources_tracking: 字段来源追踪一致性
"""

import asyncio
import os
from pathlib import Path

import pytest

from tools.write_journal.core import write_journal
from tools.write_journal.prepare import prepare_journal_metadata
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
        assert web_fm["tags"] == cli_fm["tags"], (
            f"tags 不一致: {web_fm['tags']} vs {cli_fm['tags']}"
        )

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
        edit_result = edit_journal(
            journal_path, frontmatter_updates={"tags": "tag3, tag4"}
        )

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
                "attachments": [
                    {"source_path": str(attachment), "description": "test"}
                ],
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

    def test_prepare_metadata_alignment(self, temp_data_dir: Path):
        """CLI prepare_journal_metadata 必须生成一致的元数据字段"""
        form_data = {
            "content": "Test content for metadata alignment",
            "date": "2026-03-26",
            "topic": "work",
        }

        # CLI 层准备元数据
        result = prepare_journal_metadata(form_data, use_llm=False)

        # 验证必需字段存在
        assert "title" in result, "必须有 title"
        assert "abstract" in result, "必须有 abstract"
        assert "topic" in result, "必须有 topic"
        assert "location" in result, "必须有 location"
        assert "field_sources" in result, "必须有 field_sources"
        assert "llm_status" in result, "必须有 llm_status"

        # 验证列表字段是列表类型
        assert isinstance(result["topic"], list), "topic 必须是列表"
        assert isinstance(result["mood"], list), "mood 必须是列表"
        assert isinstance(result["tags"], list), "tags 必须是列表"
        assert isinstance(result["people"], list), "people 必须是列表"

        # 验证 field_sources 覆盖所有字段
        expected_fields = {
            "title",
            "abstract",
            "topic",
            "mood",
            "tags",
            "people",
            "location",
            "date",
        }
        assert expected_fields.issubset(result["field_sources"].keys()), (
            f"field_sources 缺少字段: {expected_fields - set(result['field_sources'].keys())}"
        )

    @pytest.mark.asyncio
    async def test_web_prepare_alignment(self, temp_data_dir: Path):
        """Web prepare_journal_data 必须与 CLI produce_journal_metadata 一致"""
        # 延迟导入以避免循环导入
        from web.services.write import prepare_journal_data

        form_data = {
            "content": "Test content for web alignment",
            "date": "2026-03-26",
            "topic": "learn",
        }

        # CLI 层（同步）- 使用规则模式
        cli_result = prepare_journal_metadata(form_data, use_llm=False)

        # Web 层（异步）- 同样使用规则模式以确保一致性
        web_result = await prepare_journal_data(form_data, use_llm=False)

        # 验证关键字段一致
        assert web_result["title"] == cli_result["title"], "title 不一致"
        assert web_result["abstract"] == cli_result["abstract"], "abstract 不一致"
        assert web_result["topic"] == cli_result["topic"], "topic 不一致"
        assert web_result["location"] == cli_result["location"], "location 不一致"

        # 验证列表字段一致
        for field in ["mood", "tags", "people"]:
            assert web_result[field] == cli_result[field], f"{field} 不一致"

    def test_field_sources_values(self, temp_data_dir: Path):
        """field_sources 必须使用正确的来源标识"""
        form_data = {
            "content": "User provided content",
            "date": "2026-03-26",
            "topic": "think",
            "title": "User Title",
            "tags": "tag1, tag2",
        }

        result = prepare_journal_metadata(form_data, use_llm=False)

        # 用户提供的字段
        assert result["field_sources"]["title"] == "user", "用户提供的 title"
        assert result["field_sources"]["topic"] == "user", "用户提供的 topic"
        assert result["field_sources"]["tags"] == "user", "用户提供的 tags"
        assert result["field_sources"]["date"] == "user", "用户提供的 date"

        # 自动填充的字段
        assert result["field_sources"]["location"] == "auto", "自动填充的 location"

        # 规则填充的字段
        assert result["field_sources"]["abstract"] == "rule", "规则填充的 abstract"
