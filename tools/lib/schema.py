#!/usr/bin/env python3
"""
Life Index - Schema & Validation Utilities
元数据验证与迁移模块

从 frontmatter.py 提取的 schema 版本管理、字段验证、格式迁移逻辑。

Round 6 新增：链式迁移注册表 + MigrationResult dataclass。
"""

import re
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from typing import Any, Callable

# Schema 版本（用于未来格式变更的向后兼容）
SCHEMA_VERSION = 3


# ---------------------------------------------------------------------------
# Migration chain framework (Round 6 Phase 1 Task 1)
# ---------------------------------------------------------------------------


@_dataclass
class MigrationResult:
    """Single migration step result — deterministic changes + agent-needed items."""

    metadata: dict
    deterministic_changes: list[str] = _field(default_factory=list)
    needs_agent: list[str] = _field(default_factory=list)


# Migration registry: (from_ver, to_ver) -> migration_func
_MIGRATIONS: dict[tuple[int, int], Callable[[dict, str], MigrationResult]] = {}


def register_migration(
    from_ver: int,
    to_ver: int,
) -> Callable[
    [Callable[[dict, str], MigrationResult]],
    Callable[[dict, str], MigrationResult],
]:
    """Decorator: register a version migration function."""

    def decorator(
        func: Callable[[dict, str], MigrationResult],
    ) -> Callable[[dict, str], MigrationResult]:
        _MIGRATIONS[(from_ver, to_ver)] = func
        return func

    return decorator


@register_migration(1, 2)
def _migrate_v1_to_v2(metadata: dict, content: str) -> MigrationResult:
    """v1→v2: add entities field."""
    changes: list[str] = []
    needs: list[str] = []

    if "entities" not in metadata:
        metadata["entities"] = []
        changes.append("added entities: []")

    # Check for semantic fields that need Agent backfill
    if not metadata.get("abstract") and not metadata.get("summary"):
        needs.append("abstract/summary missing — needs Agent extraction")
    if not metadata.get("mood"):
        needs.append("mood empty — needs Agent extraction from content")

    metadata["schema_version"] = 2
    return MigrationResult(
        metadata=metadata,
        deterministic_changes=changes,
        needs_agent=needs,
    )


@register_migration(2, 3)
def _migrate_v2_to_v3(metadata: dict, content: str) -> MigrationResult:
    """v2→v3: remove deprecated placeholder fields."""
    del content  # unused in deterministic migration

    changes: list[str] = []

    if "sentiment_score" in metadata:
        metadata.pop("sentiment_score", None)
        changes.append("removed sentiment_score")
    if "themes" in metadata:
        metadata.pop("themes", None)
        changes.append("removed themes")

    metadata["schema_version"] = 3
    return MigrationResult(metadata=metadata, deterministic_changes=changes)


def get_migration_chain(
    from_ver: int,
    to_ver: int,
) -> list[tuple[int, int, Callable[[dict, str], MigrationResult]]]:
    """Return ordered migration steps from *from_ver* to *to_ver*.

    Each step is a (from_ver, to_ver, func) triple.
    Raises ValueError when a required step is missing from the registry.
    """
    if from_ver == to_ver:
        return []

    chain: list[tuple[int, int, Callable[[dict, str], MigrationResult]]] = []
    current = from_ver
    while current < to_ver:
        next_ver = current + 1
        key = (current, next_ver)
        if key not in _MIGRATIONS:
            raise ValueError(f"no migration path from v{current} to v{next_ver}")
        chain.append((current, next_ver, _MIGRATIONS[key]))
        current = next_ver
    return chain


def run_migration_chain(metadata: dict, content: str = "") -> MigrationResult:
    """Execute the full migration chain for *metadata* up to SCHEMA_VERSION.

    Returns a MigrationResult with the final metadata, all deterministic changes
    collected, and all needs_agent items aggregated.
    """
    # Work on a copy to avoid mutating caller's dict
    working = dict(metadata)
    current_ver = working.get("schema_version", 1)

    if current_ver == SCHEMA_VERSION:
        return MigrationResult(metadata=working)

    # Future version: pin to current (matches legacy migrate_metadata behaviour)
    if current_ver > SCHEMA_VERSION:
        working["schema_version"] = SCHEMA_VERSION
        return MigrationResult(
            metadata=working,
            deterministic_changes=[f"pinned future v{current_ver} to v{SCHEMA_VERSION}"],
        )

    chain = get_migration_chain(current_ver, SCHEMA_VERSION)

    all_changes: list[str] = []
    all_needs: list[str] = []
    for _from_v, _to_v, func in chain:
        result = func(working, content)
        working = result.metadata
        all_changes.extend(result.deterministic_changes)
        all_needs.extend(result.needs_agent)

    return MigrationResult(
        metadata=working,
        deterministic_changes=all_changes,
        needs_agent=all_needs,
    )


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
    迁移元数据到当前 schema 版本（向后兼容 wrapper）

    当读取旧版本 frontmatter 时，自动应用必要的迁移转换。
    内部调用 run_migration_chain()，仅返回 metadata dict。

    Args:
        metadata: 从文件解析的元数据

    Returns:
        迁移后的元数据（添加 schema_version 等）
    """
    result = run_migration_chain(metadata)
    return result.metadata
