#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Core
核心协调模块
"""

import re
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

from ..lib.config import (
    JOURNALS_DIR,
    FILE_LOCK_TIMEOUT_DEFAULT,
    get_default_location,
    resolve_user_data_dir,
)
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.errors import ErrorCode, create_error_response
from ..lib.workflow_signals import (
    WriteOutcome,
    IndexStatus,
    SideEffectsStatus,
    ConfirmStatus,
    derive_write_outcome,
)
from ..lib.entity_graph import load_entity_graph, resolve_entity
from ..lib.entity_schema import EntityGraphValidationError
from ..lib.entity_candidates import extract_entity_candidates
from ..lib.metadata_cache import (
    get_backlinked_by,
    get_all_cached_metadata,
    init_metadata_cache,
    replace_entry_relations,
)
from ..lib.path_contract import build_journal_path_fields
from ..lib.related_candidates import suggest_related_entries
from ..lib import content_analysis
from ..lib.timing import Timer
from ..lib.logger import get_logger

# 初始化日志器
logger = get_logger(__name__)

# 导入子模块
from .utils import get_year_month, generate_filename, get_next_sequence
from ..lib.frontmatter import format_journal_content as format_content
from .attachments import extract_file_paths_from_content, process_attachments
from .weather import query_weather_for_location, normalize_location
from .index_updater import (
    update_topic_index,
    update_project_index,
    update_tag_indices,
    update_monthly_abstract,
    update_vector_index,
    update_fts_index,
)


def _detect_new_entities(data: Dict[str, Any]) -> list[str]:
    graph_path = resolve_user_data_dir() / "entity_graph.yaml"
    try:
        graph = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        logger.warning("Skipping entity detection due to invalid graph: %s", exc)
        return []
    if not graph:
        return []

    candidates: list[str] = []
    for key in ("people", "location", "project"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    new_entities: list[str] = []
    for candidate in candidates:
        if resolve_entity(candidate, graph) is None and candidate not in new_entities:
            new_entities.append(candidate)
    return new_entities


def extract_explicit_metadata_from_content(content: str) -> Dict[str, str]:
    """从正文中提取明确声明的元数据（地点/天气），不修改正文。

    仅做只读扫描：匹配行首的 "地点:"/"天气:" 等模式并提取值。
    调用方应将提取结果用于填充 data["location"]/data["weather"]，
    但 **不得** 用任何"清理后"的内容覆盖 data["content"]。
    """
    extracted: Dict[str, str] = {}
    if not content:
        return extracted

    patterns = {
        "location": re.compile(
            r"^\s*(?:地点|位置|location)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE
        ),
        "weather": re.compile(
            r"^\s*(?:天气|weather)\s*[:：]\s*(.+?)\s*$", re.IGNORECASE
        ),
    }

    for line in content.splitlines():
        for field, pattern in patterns.items():
            if field in extracted:
                continue
            match = pattern.match(line)
            if match:
                extracted[field] = match.group(1).strip()
                break

    return extracted


def _build_confirmation_payload(
    *,
    journal_path: str | None,
    location: str,
    weather: str,
    related_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "location": location,
        "weather": weather,
        "related_candidates": related_candidates,
        "journal_path": journal_path,
        "supports_related_entry_approval": True,
    }


def apply_confirmation_updates(
    *,
    journal_path: str | Any,
    location: str | None = None,
    weather: str | None = None,
    approved_related_entries: list[str] | None = None,
    approved_related_candidate_ids: list[int] | None = None,
    rejected_related_entries: list[str | int] | None = None,
    rejected_related_candidate_ids: list[int] | None = None,
    candidate_context: list[dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Apply post-write confirmation decisions via edit_journal."""
    from ..edit_journal import edit_journal

    candidate_context = candidate_context or []

    def _normalize_candidate_context(
        candidates: list[dict[str, Any]],
    ) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
        by_id: dict[int, dict[str, Any]] = {}
        by_rel_path: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue  # type: ignore[unreachable]
            rel_path = str(candidate.get("rel_path") or "").strip()
            if not rel_path:
                continue
            candidate_id = candidate.get("candidate_id")
            normalized_candidate = {
                "candidate_id": candidate_id,
                "rel_path": rel_path,
                "title": str(candidate.get("title") or ""),
            }
            if isinstance(candidate_id, int):
                by_id[candidate_id] = normalized_candidate
            by_rel_path[rel_path] = normalized_candidate
        return by_id, by_rel_path

    def _resolve_candidate_refs(
        refs: Sequence[str | int] | None,
        *,
        candidate_ids: Sequence[int] | None = None,
    ) -> tuple[list[str], list[dict[str, Any]], list[int], dict[str, Any] | None]:
        by_id, by_rel_path = _normalize_candidate_context(candidate_context)
        resolved_rel_paths: list[str] = []
        resolved_candidates: list[dict[str, Any]] = []
        resolved_candidate_ids: list[int] = []
        seen_rel_paths: set[str] = set()

        combined_refs: list[str | int] = []
        if refs:
            combined_refs.extend(refs)
        if candidate_ids:
            combined_refs.extend(candidate_ids)

        for ref in combined_refs:
            candidate: dict[str, Any] | None = None
            if isinstance(ref, int):
                candidate = by_id.get(ref)
            elif isinstance(ref, str):
                normalized_ref = ref.strip()
                if not normalized_ref:
                    continue
                candidate = by_rel_path.get(normalized_ref)
                if candidate is None:
                    candidate = {
                        "candidate_id": None,
                        "rel_path": normalized_ref,
                        "title": "",
                    }
            if candidate is None:
                return (
                    [],
                    [],
                    [],
                    create_error_response(
                        ErrorCode.INVALID_INPUT,
                        f"未知候选引用：{ref}",
                        {"candidate_reference": ref},
                        "请传入有效的 candidate_id 或 rel_path，并确保 candidate_context 与确认载荷一致",
                    ),
                )

            rel_path = candidate["rel_path"]
            if rel_path in seen_rel_paths:
                continue
            seen_rel_paths.add(rel_path)
            resolved_rel_paths.append(rel_path)
            resolved_candidates.append(candidate)
            candidate_id = candidate.get("candidate_id")
            if isinstance(candidate_id, int):
                resolved_candidate_ids.append(candidate_id)

        return resolved_rel_paths, resolved_candidates, resolved_candidate_ids, None

    def _build_approval_summary(
        *,
        approved_candidates: list[dict[str, Any]],
        rejected_candidates: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        def _summary_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "rel_path": candidate["rel_path"],
                    "title": candidate.get("title") or "",
                }
                for candidate in candidates
            ]

        return {
            "approved": _summary_rows(approved_candidates),
            "rejected": _summary_rows(rejected_candidates),
        }

    def _build_relation_summary(
        *,
        source_path: Path,
        approved_entries: list[str],
        applied_fields: list[str],
    ) -> dict[str, Any] | None:
        if "related_entries" not in applied_fields:
            return None

        metadata_conn = init_metadata_cache()
        try:
            source_fields = build_journal_path_fields(
                source_path,
                journals_dir=JOURNALS_DIR,
                user_data_dir=resolve_user_data_dir(),
            )
            source_rel_path = source_fields["rel_path"]
            source_backlinks = get_backlinked_by(metadata_conn, source_rel_path)
            approved_context = [
                {
                    "rel_path": rel_path,
                    "backlinked_by": get_backlinked_by(metadata_conn, rel_path),
                }
                for rel_path in approved_entries
            ]
            return {
                "source_entry": {
                    "rel_path": source_rel_path,
                    "related_entries": approved_entries,
                    "backlinked_by": source_backlinks,
                },
                "approved_related_context": approved_context,
            }
        finally:
            metadata_conn.close()

    def _derive_confirm_status(
        *, success: bool, requested_fields: list[str], applied_fields: list[str]
    ) -> str:
        if not success:
            return ConfirmStatus.FAILED
        if not requested_fields or not applied_fields:
            return ConfirmStatus.NOOP
        if len(applied_fields) == len(requested_fields):
            return ConfirmStatus.COMPLETE
        return ConfirmStatus.PARTIAL

    journal_path_obj = Path(journal_path)
    if not journal_path_obj.exists():
        error_result = create_error_response(
            ErrorCode.JOURNAL_NOT_FOUND,
            f"日志文件不存在：{journal_path_obj}",
            {"journal_path": str(journal_path_obj)},
            "请检查日志路径是否正确后重试",
        )
        error_result.update(
            {
                "journal_path": str(journal_path_obj),
                "confirm_status": ConfirmStatus.FAILED,
                "applied_fields": [],
                "ignored_fields": [],
                "approved_related_entries": [],
                "requested_related_entries": approved_related_entries or [],
                "approved_candidate_ids": [],
                "rejected_related_entries": [],
                "rejected_candidate_ids": [],
                "approval_summary": {"approved": [], "rejected": []},
                "relation_summary": None,
            }
        )
        return error_result

    (
        resolved_approved_entries,
        approved_candidates,
        approved_candidate_ids,
        approval_error,
    ) = _resolve_candidate_refs(
        approved_related_entries,
        candidate_ids=approved_related_candidate_ids,
    )
    if approval_error is not None:
        approval_error.update(
            {
                "journal_path": str(journal_path_obj),
                "confirm_status": ConfirmStatus.FAILED,
                "applied_fields": [],
                "ignored_fields": [],
                "approved_related_entries": [],
                "requested_related_entries": approved_related_entries or [],
                "approved_candidate_ids": [],
                "rejected_related_entries": [],
                "rejected_candidate_ids": [],
                "approval_summary": {"approved": [], "rejected": []},
                "relation_summary": None,
            }
        )
        return approval_error

    (
        resolved_rejected_entries,
        rejected_candidates,
        rejected_candidate_ids,
        rejection_error,
    ) = _resolve_candidate_refs(
        rejected_related_entries,
        candidate_ids=rejected_related_candidate_ids,
    )
    if rejection_error is not None:
        rejection_error.update(
            {
                "journal_path": str(journal_path_obj),
                "confirm_status": ConfirmStatus.FAILED,
                "applied_fields": [],
                "ignored_fields": [],
                "approved_related_entries": [],
                "requested_related_entries": approved_related_entries or [],
                "approved_candidate_ids": [],
                "rejected_related_entries": [],
                "rejected_candidate_ids": [],
                "approval_summary": {"approved": [], "rejected": []},
                "relation_summary": None,
            }
        )
        return rejection_error

    frontmatter_updates: Dict[str, Any] = {}
    requested_fields: list[str] = []
    if location is not None:
        frontmatter_updates["location"] = location
        requested_fields.append("location")
    if weather is not None:
        frontmatter_updates["weather"] = weather
        requested_fields.append("weather")
    if resolved_approved_entries:
        frontmatter_updates["add_related_entries"] = resolved_approved_entries
        requested_fields.append("related_entries")

    result = edit_journal(
        journal_path=journal_path_obj,
        frontmatter_updates=frontmatter_updates,
    )

    changes = result.get("changes", {}) if isinstance(result, dict) else {}

    def _field_was_applied(field: str) -> bool:
        if field not in changes:
            return False
        change = changes.get(field)
        if not isinstance(change, dict):
            return True
        return change.get("old") != change.get("new")

    applied_fields = [field for field in requested_fields if _field_was_applied(field)]
    ignored_fields = [
        field for field in requested_fields if not _field_was_applied(field)
    ]

    if isinstance(result, dict):
        result["applied_fields"] = applied_fields
        result["ignored_fields"] = ignored_fields
        result["approved_related_entries"] = (
            resolved_approved_entries if "related_entries" in applied_fields else []
        )
        result["requested_related_entries"] = resolved_approved_entries
        approved_entries = result["approved_related_entries"]
        result["approved_candidate_ids"] = approved_candidate_ids
        result["rejected_related_entries"] = resolved_rejected_entries
        result["rejected_candidate_ids"] = rejected_candidate_ids
        result["approval_summary"] = _build_approval_summary(
            approved_candidates=approved_candidates,
            rejected_candidates=rejected_candidates,
        )
        result["confirm_status"] = _derive_confirm_status(
            success=bool(result.get("success")),
            requested_fields=requested_fields,
            applied_fields=applied_fields,
        )
        result["relation_summary"] = _build_relation_summary(
            source_path=journal_path_obj,
            approved_entries=approved_entries,
            applied_fields=applied_fields,
        )

    return result


def write_journal(data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """
    写入日志的主函数
    自动处理默认值和天气查询

    Returns:
        {
            "success": bool,
            "write_outcome": str,  # success | success_pending_confirmation |
                                   # success_degraded | failed
            "journal_path": str,
            "updated_indices": [str],
            "index_status": str,
            "side_effects_status": str,
            "attachments_processed": [dict],
            "location_used": str,
            "weather_used": str,
            "weather_auto_filled": bool,
            "needs_confirmation": bool,
            "confirmation_message": str,
            "metrics": {"total_ms": float, "weather_query_ms": float, ...},
            "error": str (optional)
        }
    """
    # 性能计时器
    timer = Timer().start()

    result: Dict[str, Any] = {
        "success": False,
        "write_outcome": WriteOutcome.FAILED,
        "journal_path": None,
        "updated_indices": [],
        "index_status": IndexStatus.NOT_STARTED,
        "side_effects_status": SideEffectsStatus.NOT_STARTED,
        "attachments_processed": [],
        "attachments_detected_count": 0,
        "attachments_processed_count": 0,
        "attachments_failed_count": 0,
        "location_used": "",
        "location_auto_filled": False,
        "weather_used": "",
        "weather_auto_filled": False,
        "needs_confirmation": False,
        "confirmation_message": "",
        "confirmation": {},
        "related_candidates": [],
        "new_entities_detected": [],
        "entity_candidates": [],
        "error": None,
        "metrics": {},
    }

    try:
        # 验证必需字段
        date_str = data.get("date")
        if not date_str:
            logger.error("缺少必需字段：date")
            raise ValueError("缺少必需字段：date")

        logger.info(f"开始写入日志：date={date_str}, title={data.get('title', 'N/A')}")

        content = data.get("content", "")
        explicit_metadata = extract_explicit_metadata_from_content(content)
        # NOTE: data["content"] is NOT overwritten — user content is preserved 100%.

        # ===== 第一层：用户提及为准 =====
        # 如果正文里明确写了地点和天气，优先使用正文中的信息

        # ===== 第二层：自动填充 =====
        # 处理地点：如果未提供，使用默认值
        location = explicit_metadata.get("location") or data.get("location", "").strip()
        if not location:
            location = get_default_location()
            result["location_auto_filled"] = True
            result["location_used"] = location
            # 天气查询使用实际默认地点
            location_for_weather = normalize_location(location)
        else:
            # 规范化地点（处理城市级别输入）
            location_for_weather = normalize_location(location)
            result["location_used"] = location
        data["location"] = location

        # 处理天气：如果未提供，自动查询
        weather = explicit_metadata.get("weather") or data.get("weather", "").strip()
        if not weather:
            # 尝试获取天气（使用英文格式的地点）
            logger.debug(f"查询天气：location={location_for_weather}")
            with timer.measure("weather_query"):
                queried_weather = query_weather_for_location(
                    location_for_weather, date_str
                )
            if queried_weather:
                weather = queried_weather
                result["weather_used"] = weather
                result["weather_auto_filled"] = True
                logger.info(f"天气查询成功：{weather}")
            else:
                weather = ""
                result["weather_used"] = ""
                logger.warning("天气查询失败，使用空值")
        else:
            result["weather_used"] = weather
            logger.debug(f"使用用户提供的天气：{weather}")

        data["weather"] = weather
        try:
            entity_graph = load_entity_graph(
                resolve_user_data_dir() / "entity_graph.yaml"
            )
        except EntityGraphValidationError as exc:
            logger.warning(
                "Skipping entity graph enrichment due to invalid graph: %s", exc
            )
            entity_graph = []
        data["entities"] = content_analysis.match_entities(
            data.get("people"),
            data.get("location"),
            data.get("project"),
            entity_graph,
        )
        result["new_entities_detected"] = _detect_new_entities(data)

        # Round 7 Phase 2: Structured entity candidates
        result["entity_candidates"] = extract_entity_candidates(
            metadata=data,
            content=str(data.get("content", "")),
            graph=entity_graph,
        )

        metadata_conn = init_metadata_cache()
        try:
            candidate_entries = get_all_cached_metadata(metadata_conn)
        finally:
            metadata_conn.close()
        current_entry = {
            "date": data.get("date"),
            "topic": data.get("topic"),
            "people": data.get("people"),
            "project": data.get("project"),
            "tags": data.get("tags"),
            "related_entries": data.get("related_entries", []),
        }
        result["related_candidates"] = suggest_related_entries(
            current_entry, candidate_entries
        )
        result["confirmation"] = _build_confirmation_payload(
            journal_path=None,
            location=location,
            weather=weather,
            related_candidates=result["related_candidates"],
        )
        result["prepared_metadata"] = dict(data)

        # ===== 文件锁保护 =====
        # 使用文件锁保护序列号生成和写入操作，防止并发冲突
        logger.debug("获取文件锁...")
        with timer.measure("lock_acquire"):
            lock = FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_DEFAULT)

        try:
            with lock:
                # ===== 原子写入（带重试）=====
                # 处理并发写入时的序列号冲突（现在有锁保护，主要用于健壮性）
                max_retries = 3
                year = 0
                month = 0
                journal_path = None
                month_dir = None

                with timer.measure("sequence_gen"):
                    for retry in range(max_retries):
                        # 获取年月和序列号
                        year, month = get_year_month(date_str)
                        sequence = get_next_sequence(date_str)

                        # 构建路径
                        month_dir = JOURNALS_DIR / str(year) / f"{month:02d}"
                        filename = generate_filename(date_str, sequence)
                        journal_path = month_dir / filename

                        logger.debug(f"尝试生成文件名：{filename}, retry={retry}")

                        # 如果文件已存在且不是最后一次重试，重新获取序列号
                        if journal_path.exists() and retry < max_retries - 1:
                            logger.debug(f"文件已存在，准备重试：{journal_path}")
                            continue  # 重试
                        break  # 文件不存在，或最后一次重试直接使用

                # 类型安全断言（循环必定至少执行一次）
                assert journal_path is not None
                assert month_dir is not None

                # 从内容中自动检测文件路径
                content = data.get("content", "")
                auto_detected_paths = extract_file_paths_from_content(content)
                result["attachments_detected_count"] = len(auto_detected_paths)
                logger.debug(f"从内容中检测到 {len(auto_detected_paths)} 个附件路径")

                # 处理附件（显式附件 + 自动检测附件）
                attachments = data.get("attachments", [])
                with timer.measure("attachments"):
                    processed_attachments = process_attachments(
                        attachments, date_str, dry_run, auto_detected_paths
                    )
                result["attachments_processed"] = processed_attachments
                result["attachments_processed_count"] = len(
                    [
                        att
                        for att in processed_attachments
                        if not str(att.get("filename", "")).startswith("[")
                    ]
                )
                result["attachments_failed_count"] = (
                    len(processed_attachments) - result["attachments_processed_count"]
                )
                if processed_attachments:
                    logger.info(f"处理了 {len(processed_attachments)} 个附件")

                # 更新数据中的附件信息（用于生成内容）
                data["attachments"] = processed_attachments

                # 生成内容（format_journal_content 已包含 frontmatter + body）
                full_content = format_content(data)

                if dry_run:
                    result["journal_path"] = str(journal_path)
                    result["confirmation"] = _build_confirmation_payload(
                        journal_path=str(journal_path),
                        location=location,
                        weather=weather,
                        related_candidates=result["related_candidates"],
                    )
                    result["content_preview"] = full_content[:500]
                    result["success"] = True
                    timer.stop()
                    result["metrics"] = timer.to_dict()
                    return result

                # ===== 事务性写入 =====
                # 1. 准备所有索引更新所需数据
                topic = data.get("topic")
                project = data.get("project")
                tags = data.get("tags", [])

                # 2. 使用临时文件进行原子写入
                month_dir.mkdir(parents=True, exist_ok=True)
                temp_path = journal_path.with_suffix(".tmp")
                try:
                    logger.info(f"写入日志文件：{journal_path}")
                    with timer.measure("file_write"):
                        with open(temp_path, "w", encoding="utf-8") as f:
                            f.write(full_content)

                    # 3. 更新月度摘要
                    with timer.measure("abstract_update"):
                        abstract_result = None
                        abstract_error = None
                        abstract_success = False
                        try:
                            abstract_result = update_monthly_abstract(
                                year, month, dry_run
                            )
                            abstract_success = True
                        except (OSError, IOError, RuntimeError) as e:
                            abstract_error = str(e)

                    # 4. 更新索引
                    updated_indices = []
                    vector_index_error = None
                    fts_index_error = None
                    with timer.measure("index_update"):
                        try:
                            if topic:
                                indices = update_topic_index(topic, journal_path, data)
                                updated_indices.extend([str(i) for i in indices])

                            if project:
                                idx = update_project_index(project, journal_path, data)
                                if idx:
                                    updated_indices.append(str(idx))

                            if tags:
                                indices = update_tag_indices(tags, journal_path, data)
                                updated_indices.extend([str(i) for i in indices])

                            # 6. 更新向量索引（Write-Through）
                            try:
                                vector_updated = update_vector_index(journal_path, data)
                                if vector_updated:
                                    logger.info("向量索引已同步更新")
                            except Exception as e:
                                # 向量索引更新失败不阻塞写入
                                vector_index_error = str(e)
                                logger.warning(
                                    f"向量索引更新失败（不影响日志写入）：{e}"
                                )

                            # 7. 更新 FTS 索引（Write-Through）
                            try:
                                fts_updated = update_fts_index(journal_path, data)
                                if fts_updated:
                                    logger.info("FTS 索引已同步更新")
                            except Exception as e:
                                fts_index_error = str(e)
                                logger.warning(
                                    f"FTS 索引更新失败（不影响日志写入）：{e}"
                                )

                        except (OSError, IOError, RuntimeError) as e:
                            # 索引更新失败，清理临时文件
                            logger.error(f"索引更新失败：{e}")
                            if temp_path.exists():
                                temp_path.unlink()
                            raise RuntimeError(f"索引更新失败，事务已回滚：{e}")

                    # 5. 所有操作成功，原子性重命名临时文件
                    temp_path.replace(journal_path)
                    logger.info(f"日志文件写入成功：{journal_path}")

                    metadata_conn = init_metadata_cache()
                    try:
                        source_rel_path = build_journal_path_fields(
                            journal_path,
                            journals_dir=JOURNALS_DIR,
                            user_data_dir=resolve_user_data_dir(),
                        )["rel_path"]
                        replace_entry_relations(
                            metadata_conn,
                            source_rel_path,
                            data.get("related_entries", []),
                        )
                    finally:
                        metadata_conn.close()

                    # 记录结果
                    result["journal_path"] = str(journal_path)
                    result["monthly_abstract_updated"] = abstract_result
                    if abstract_error:
                        result["monthly_abstract_error"] = abstract_error
                    if vector_index_error:
                        result["vector_index_error"] = vector_index_error
                    if fts_index_error:
                        result["fts_index_error"] = fts_index_error
                    result["updated_indices"] = updated_indices

                    if vector_index_error or fts_index_error:
                        result["index_status"] = IndexStatus.DEGRADED
                    else:
                        result["index_status"] = IndexStatus.COMPLETE

                    if (
                        abstract_success
                        and not vector_index_error
                        and not fts_index_error
                    ):
                        result["side_effects_status"] = SideEffectsStatus.COMPLETE
                    else:
                        result["side_effects_status"] = SideEffectsStatus.DEGRADED

                except (OSError, IOError, RuntimeError):
                    # 确保临时文件被清理
                    if temp_path.exists():
                        temp_path.unlink()
                    raise

        except LockTimeoutError as e:
            # 锁超时，返回结构化错误
            logger.error(f"文件锁超时：{e}")
            return create_error_response(
                ErrorCode.LOCK_TIMEOUT,
                f"无法获取写入锁，请稍后重试：{e}",
                {
                    "lock_path": str(get_journals_lock_path()),
                    "timeout": FILE_LOCK_TIMEOUT_DEFAULT,
                },
                "等待几秒后重试，或检查是否有其他进程正在写入",
            )

        result["success"] = True

        # ===== 第三层：写入后确认 =====
        result["needs_confirmation"] = True
        if result["needs_confirmation"]:
            relation_lines = ""
            if result["related_candidates"]:
                candidate_lines = ["\n\n可考虑关联以下日志："]
                for index, candidate in enumerate(
                    result["related_candidates"], start=1
                ):
                    candidate_lines.append(
                        (
                            f"{index}. {candidate['rel_path']} | "
                            f"{candidate['date']} | {candidate['title']}"
                        )
                    )
                relation_lines = "\n".join(candidate_lines)

            result["confirmation"] = _build_confirmation_payload(
                journal_path=str(journal_path),
                location=location,
                weather=weather,
                related_candidates=result["related_candidates"],
            )

            result["confirmation_message"] = (
                f"日志已保存至：{journal_path}\n\n"
                f"本次记录地点：{location}\n"
                f"- 天气：{weather if weather else '（未获取）'}\n\n"
                f"请确认这个地点是否正确。"
                f"如果不对，请告诉我正确地点。"
                f"我会基于新地点更新地点和天气。"
                f"{relation_lines}"
            )

    except (ValueError, IOError, RuntimeError, OSError) as e:
        logger.error(f"写入日志失败：{e}", exc_info=True)
        result["error"] = str(e)
        result["index_status"] = IndexStatus.NOT_STARTED
        result["side_effects_status"] = SideEffectsStatus.NOT_STARTED

    # 添加性能指标
    timer.stop()
    result["metrics"] = timer.to_dict()

    # 推导 write_outcome（Agent 只需读这一个字段即可判断下一步）
    result["write_outcome"] = derive_write_outcome(
        success=result["success"],
        needs_confirmation=result["needs_confirmation"],
        index_status=result["index_status"],
        side_effects_status=result["side_effects_status"],
    )

    if result["success"]:
        logger.info(f"写入完成，总耗时：{result['metrics'].get('total_ms', 0):.2f}ms")

    return result
