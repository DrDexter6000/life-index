#!/usr/bin/env python3
"""
Life Index - Schema & Validation Utilities
元数据验证与迁移模块

从 frontmatter.py 提取的 schema 版本管理、字段验证、格式迁移逻辑。
"""

import re
from typing import Any

# Schema 版本（用于未来格式变更的向后兼容）
SCHEMA_VERSION = 1


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
    # 如果没有 schema_version，假设为版本 1（当前版本）
    file_version = metadata.get("schema_version", 1)

    if file_version == SCHEMA_VERSION:
        # 版本匹配，无需迁移
        return metadata

    # 未来版本迁移逻辑将在此处添加
    # 例如：
    # if file_version < 2:
    #     # 版本 1 -> 2 的迁移
    #     metadata = _migrate_v1_to_v2(metadata)
    # if file_version < 3:
    #     # 版本 2 -> 3 的迁移
    #     metadata = _migrate_v2_to_v3(metadata)

    # 更新 schema_version 到当前版本
    metadata["schema_version"] = SCHEMA_VERSION

    return metadata
