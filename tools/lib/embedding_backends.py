"""Shared embedding model loader and encoder for semantic search."""

from __future__ import annotations

import json
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import EMBEDDING_MODEL as MODEL_CONFIG, get_model_cache_dir

logger = logging.getLogger(__name__)


@dataclass
class ModelIntegrityResult:
    """Result of model integrity verification (Task 1.1.3).

    Attributes:
        is_valid: True if model can be loaded safely
        needs_rebuild: True if vector index must be rebuilt
        message: Human-readable status message
    """

    is_valid: bool
    needs_rebuild: bool
    message: str


def get_backend_name(model_config: dict[str, Any]) -> str:
    metadata = model_config.get("metadata", {})
    return str(metadata.get("backend") or "sentence-transformers")


def _normalize_embedding(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 1e-8:
        return vector
    return [value / norm for value in vector]


def verify_model_integrity(model_name: str, cache_dir: Path) -> ModelIntegrityResult:
    """
    Verify model integrity and determine if rebuild is needed (Task 1.1.2, Task 1.1.3).

    Args:
        model_name: Name of the embedding model
        cache_dir: Directory where model cache is stored

    Returns:
        ModelIntegrityResult with is_valid, needs_rebuild, and message fields

    Semantic changes (Task 1.1.2):
        - Missing meta_file → needs_rebuild=True (first-time use)
        - Version mismatch → needs_rebuild=True (incompatible vectors)
        - Hash mismatch → needs_rebuild=True (config changed)
        - Exception → needs_rebuild=True (conservative fallback)
    """
    meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"

    if not meta_file.exists():
        # First-time use: need to build initial index
        return ModelIntegrityResult(
            is_valid=True, needs_rebuild=True, message="首次使用，将记录模型元数据"
        )

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        expected_hash = meta.get("config_hash", "")
        recorded_version = meta.get("version", "")

        if expected_hash and expected_hash != MODEL_CONFIG.get("config_hash", ""):
            expected = str(MODEL_CONFIG.get("config_hash", ""))[:16]
            return ModelIntegrityResult(
                is_valid=False,
                needs_rebuild=True,
                message=f"模型配置哈希不匹配！预期：{expected}..., 实际：{expected_hash[:16]}...",
            )

        if recorded_version != MODEL_CONFIG["version"]:
            # Version mismatch: incompatible vectors, must rebuild
            return ModelIntegrityResult(
                is_valid=False,
                needs_rebuild=True,
                message=f"模型版本不一致！已记录：{recorded_version}, 当前配置：{MODEL_CONFIG['version']}",
            )

        return ModelIntegrityResult(
            is_valid=True, needs_rebuild=False, message="模型完整性验证通过"
        )
    except Exception as e:
        # Exception: conservative strategy, trigger rebuild
        return ModelIntegrityResult(
            is_valid=False, needs_rebuild=True, message=f"验证模型完整性失败：{e}"
        )


def record_model_metadata(model_name: str, cache_dir: Path) -> None:
    try:
        model_dir = cache_dir / model_name.replace("/", "_")
        model_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "name": model_name,
            "version": MODEL_CONFIG["version"],
            "dimension": MODEL_CONFIG["dimension"],
            "config_hash": MODEL_CONFIG.get("config_hash", ""),
            "recorded_at": __import__("datetime").datetime.now().isoformat(),
            "platform": sys.platform,
        }

        meta_file = model_dir / "model_meta.json"
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to record model metadata: %s", e)


def load_backend_model(model_config: dict[str, Any], cache_dir: Path) -> tuple[Any, str]:
    backend = get_backend_name(model_config)
    model_name = str(model_config["name"])

    if backend != "sentence-transformers":
        raise ValueError(f"Unsupported embedding backend: {backend}")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, cache_folder=str(cache_dir))
    return model, backend


def encode_texts(model: Any, texts: list[str], backend: str) -> list[list[float]]:
    if backend != "sentence-transformers":
        raise ValueError(f"Unsupported embedding backend: {backend}")

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return [list(embedding) for embedding in embeddings]


class SharedEmbeddingModel:
    """Shared singleton embedding model used by all vector backends."""

    _instance: SharedEmbeddingModel | None = None
    _model: Any | None = None
    _backend: str | None = None
    _model_verified: bool = False

    def __new__(cls) -> SharedEmbeddingModel:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self) -> bool:
        if self._model is not None:
            return True

        model_name = str(MODEL_CONFIG["name"])
        cache_dir = get_model_cache_dir()

        try:
            backend = get_backend_name(MODEL_CONFIG)
            logger.info("Loading embedding model: %s via %s...", model_name, backend)
            cache_dir.mkdir(parents=True, exist_ok=True)

            result = verify_model_integrity(model_name, cache_dir)
            if not result.is_valid:
                logger.warning("Model integrity check failed: %s", result.message)
                logger.warning("Will proceed with loading, but embeddings may be inconsistent.")
                if result.needs_rebuild:
                    logger.warning("Vector index needs rebuild to ensure consistency.")

            self._model, self._backend = load_backend_model(MODEL_CONFIG, cache_dir)

            meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"
            if not meta_file.exists():
                record_model_metadata(model_name, cache_dir)

            self._model_verified = True
            logger.info("Model loaded successfully.")
            return True
        except Exception as e:
            logger.warning("Failed to load embedding model: %s", e)
            self._model = None
            self._backend = None
            self._model_verified = False
            return False

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not self.load() or self._model is None:
            return []

        try:
            backend = self._backend or get_backend_name(MODEL_CONFIG)
            return encode_texts(self._model, texts, backend)
        except Exception as e:
            logger.error("Encoding error: %s", e)
            return []


__all__ = [
    "SharedEmbeddingModel",
    "encode_texts",
    "get_backend_name",
    "load_backend_model",
    "record_model_metadata",
    "verify_model_integrity",
]
