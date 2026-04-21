#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - Semantic
语义搜索模块
"""

import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 导入配置 (relative imports from tools/lib)
from ..lib.paths import get_user_data_dir, get_journals_dir, get_vec_index_path
from ..lib.config import EMBEDDING_MODEL as EMBEDDING_MODEL_CONFIG
from ..lib.embedding_backends import get_backend_name
from ..lib.errors import ErrorCode, create_error_response
from ..lib.path_contract import merge_journal_path_fields
from ..lib.timing import Timer
from ..lib.search_constants import (
    SEMANTIC_MIN_SIMILARITY,
    SEMANTIC_TOP_K_DEFAULT,
    SEMANTIC_SNIPPET_LENGTH,
)
from ..lib.vector_guards import VectorNotNormalizedError, check_vector_index_normalized

from .utils import parse_frontmatter

SEMANTIC_INDEX_PATH = get_vec_index_path()  # deprecated: use get_vec_index_path()
USER_DATA_DIR = get_user_data_dir()  # deprecated: use get_user_data_dir()
SEMANTIC_MISSING_INDEX_NOTE = "向量索引未建立，请运行 life-index index"


def get_semantic_runtime_status() -> Dict[str, str | bool]:
    """Return whether semantic search can run in the current environment."""
    backend = get_backend_name(EMBEDDING_MODEL_CONFIG)
    if backend != "sentence-transformers":
        return {
            "available": False,
            "reason": f"unsupported embedding backend: {backend}",
            "note": f"不支持的 embedding backend：{backend}。",
        }

    if importlib.util.find_spec("sentence_transformers") is None:
        return {
            "available": False,
            "reason": "sentence-transformers dependency is not installed",
            "note": "sentence-transformers 未安装，当前已降级为关键词搜索。",
        }

    if not get_vec_index_path().exists():
        return {
            "available": False,
            "reason": f"vector index not found: {get_vec_index_path()}",
            "note": SEMANTIC_MISSING_INDEX_NOTE,
        }

    return {
        "available": True,
        "reason": "",
        "note": "",
    }


def search_semantic(
    query: str,
    date_from: str = "",
    date_to: str = "",
    min_similarity: float = SEMANTIC_MIN_SIMILARITY,
    top_k: int = SEMANTIC_TOP_K_DEFAULT,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    执行语义搜索

    Args:
        query: 查询词
        date_from: 起始日期
        date_to: 结束日期
        min_similarity: 最低语义相似度阈值（默认 SEMANTIC_MIN_SIMILARITY）
        top_k: 最大语义召回量（默认 SEMANTIC_TOP_K_DEFAULT）

    Returns:
        语义搜索结果列表与细粒度计时
    """
    results: List[Dict[str, Any]] = []
    timer = Timer()
    _logger = logging.getLogger(__name__)

    try:
        # 尝试使用简单向量索引（Windows 兼容）
        from ..lib.vector_index_simple import get_model, get_index

        model = get_model()
        if model.load():
            with timer.measure("semantic_encode"):
                query_embeddings = model.encode([query])
            if query_embeddings:
                index = get_index()

                # --- Vector normalization guard (E0605) ---
                try:
                    check_vector_index_normalized(index.vectors)
                except VectorNotNormalizedError as exc:
                    _logger.error(
                        "E0605 VECTOR_NOT_NORMALIZED: %s. "
                        "Run 'life-index index --rebuild' to regenerate normalized vectors.",
                        exc,
                    )
                    error_resp = create_error_response(
                        ErrorCode.VECTOR_NOT_NORMALIZED,
                        message=str(exc),
                        details={"bad_samples": exc.details},
                        suggestion=(
                            "Run 'life-index index --rebuild'" " to regenerate normalized vectors"
                        ),
                    )
                    return [error_resp], timer.to_dict()

                with timer.measure("semantic_search"):
                    semantic_raw = index.search(
                        query_embeddings[0],
                        top_k=top_k,
                        date_from=date_from,
                        date_to=date_to,
                    )
                # 转换格式并补充元数据
                for path, score in semantic_raw:
                    if score < min_similarity:
                        continue
                    vec_data = index.get(path)
                    date_str = vec_data.get("date", "") if vec_data else ""
                    if Path(path).is_absolute():
                        resolved_path = Path(path)
                    else:
                        resolved_path = get_user_data_dir() / Path(path)

                    base_result = merge_journal_path_fields(
                        {
                            "date": date_str,
                            "similarity": round(score, 4),
                            "source": "semantic",
                        },
                        resolved_path,
                        journals_dir=get_journals_dir(),
                        user_data_dir=get_user_data_dir(),
                    )
                    # 补充元数据（title, location, weather 等）
                    enriched = enrich_semantic_result(base_result)
                    results.append(enriched)
    except (OSError, IOError, ImportError):
        # 语义搜索失败时返回空列表（可能是模型未安装或文件读取失败）
        pass

    return results, timer.to_dict()


def enrich_semantic_result(semantic_result: Dict) -> Dict:
    """
    为语义搜索结果补充文件元数据（title, snippet 等）

    Args:
        semantic_result: 语义搜索结果（包含 path, date, similarity）

    Returns:
        补充后的结果字典
    """
    path = semantic_result.get("path", "")
    result = semantic_result.copy()

    try:
        file_path = Path(path)
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(content)

            # 补充标题
            if not result.get("title") and metadata.get("title"):
                result["title"] = metadata["title"]

            # 生成摘要片段
            if not result.get("snippet") and body:
                snippet = body[:SEMANTIC_SNIPPET_LENGTH].replace("\n", " ").strip()
                if len(body) > SEMANTIC_SNIPPET_LENGTH:
                    snippet += "..."
                result["snippet"] = snippet

            # 补充其他元数据
            if metadata.get("abstract"):
                result["abstract"] = metadata["abstract"]
            if metadata.get("tags"):
                result["tags"] = metadata["tags"]
            if metadata.get("topic"):
                result["topic"] = metadata["topic"]
            if metadata.get("mood"):
                result["mood"] = metadata["mood"]
            if metadata.get("project"):
                result["project"] = metadata["project"]
            if metadata.get("location"):
                result["location"] = metadata["location"]
            if metadata.get("weather"):
                result["weather"] = metadata["weather"]
            if metadata.get("people"):
                result["people"] = metadata["people"]
            # 保留完整的 metadata 供后续使用
            result["metadata"] = metadata
    except (OSError, IOError):
        pass  # 读取失败时保持原样

    return result
