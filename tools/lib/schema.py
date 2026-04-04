#!/usr/bin/env python3
"""
Life Index - Schema & Validation Utilities
元数据验证与迁移模块

从 frontmatter.py 提取的 schema 版本管理、字段验证、格式迁移逻辑。
"""

import re
from typing import Any

# Schema 版本（用于未来格式变更的向后兼容）
SCHEMA_VERSION = 2


def get_required_fields() -> list[str]:
    """获取必需字段列表"""
    return ["title", "date"]


def get_recommended_fields() -> list[str]:
    """获取推荐字段列表"""
    return ["location", "weather", "mood", "people", "abstract", "topic"]


def validate_metadata(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """
    验证元数据完整性

    Returns:
        问题列表，每项包含 level, field, message
    """
    issues = []
    required = get_required_fields()

    for field in required:
        if field not in metadata or not metadata[field]:
            issues.append(
                {
                    "level": "error",
                    "field": field,
                    "message": f"缺少必填字段: {field}",
                }
            )

    # 日期格式验证
    if "date" in metadata and metadata["date"]:
        date_str = str(metadata["date"])
        if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$", date_str):
            issues.append(
                {
                    "level": "warning",
                    "field": "date",
                    "message": f"日期格式可能不正确: {date_str}",
                }
            )

    # Schema 版本验证
    schema_version = metadata.get("schema_version")
    if schema_version is not None and schema_version != SCHEMA_VERSION:
        issues.append(
            {
                "level": "warning",
                "field": "schema_version",
                "message": f"Schema 版本不匹配: 文件={schema_version}, 当前={SCHEMA_VERSION}",
            }
        )

    sentiment_score = metadata.get("sentiment_score")
    if sentiment_score is not None:
        try:
            score = float(sentiment_score)
        except (TypeError, ValueError):
            issues.append(
                {
                    "level": "error",
                    "field": "sentiment_score",
                    "message": "sentiment_score 必须是数字",
                }
            )
        else:
            if score < -1.0 or score > 1.0:
                issues.append(
                    {
                        "level": "error",
                        "field": "sentiment_score",
                        "message": "sentiment_score 必须位于 -1.0 到 1.0 之间",
                    }
                )

    themes = metadata.get("themes")
    if themes is not None and not (
        isinstance(themes, list) and all(isinstance(item, str) for item in themes)
    ):
        issues.append(
            {
                "level": "error",
                "field": "themes",
                "message": "themes 必须是字符串列表",
            }
        )

    entities = metadata.get("entities")
    if entities is not None and not (
        isinstance(entities, list) and all(isinstance(item, str) for item in entities)
    ):
        issues.append(
            {
                "level": "error",
                "field": "entities",
                "message": "entities 必须是字符串列表",
            }
        )

    links = metadata.get("links")
    if links is not None:
        if not isinstance(links, list) or not all(isinstance(item, str) for item in links):
            issues.append(
                {
                    "level": "error",
                    "field": "links",
                    "message": "links 必须是字符串列表",
                }
            )
        else:
            for link in links:
                if link and not re.match(r"^https?://", link):
                    issues.append(
                        {
                            "level": "warning",
                            "field": "links",
                            "message": f"links 可能不是合法 URL: {link}",
                        }
                    )

    related_entries = metadata.get("related_entries")
    if related_entries is not None:
        if not isinstance(related_entries, list) or not all(
            isinstance(item, str) for item in related_entries
        ):
            issues.append(
                {
                    "level": "error",
                    "field": "related_entries",
                    "message": "related_entries 必须是字符串列表",
                }
            )
        else:
            if len(related_entries) > 10:
                issues.append(
                    {
                        "level": "error",
                        "field": "related_entries",
                        "message": "related_entries 最多允许 10 项",
                    }
                )
            for entry in related_entries:
                if entry and not re.match(r"^Journals/.+\.md$", entry):
                    issues.append(
                        {
                            "level": "error",
                            "field": "related_entries",
                            "message": f"related_entries 路径无效: {entry}",
                        }
                    )

    return issues


def get_schema_version() -> int:
    """获取当前 schema 版本"""
    return SCHEMA_VERSION


def migrate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    迁移元数据到当前 schema 版本

    当读取旧版本 frontmatter 时，自动应用必要的迁移转换。
    这是为未来格式变更准备的迁移框架。

    Args:
        metadata: 从文件解析的元数据

    Returns:
        迁移后的元数据（添加 schema_version 等）
    """
    migrated = dict(metadata)
    file_version = migrated.get("schema_version", 1)

    if file_version < 2:
        migrated.setdefault("sentiment_score", None)
        migrated.setdefault("themes", [])
        migrated.setdefault("entities", [])

    migrated["schema_version"] = SCHEMA_VERSION
    return migrated
