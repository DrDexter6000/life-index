"""Shared embedding model loader and encoder for semantic search."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

from .config import EMBEDDING_MODEL as MODEL_CONFIG, get_model_cache_dir


def get_backend_name(model_config: dict[str, Any]) -> str:
    metadata = model_config.get("metadata", {})
    return str(metadata.get("backend") or "sentence-transformers")


def _normalize_embedding(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 1e-8:
        return vector
    return [value / norm for value in vector]


def verify_model_integrity(model_name: str, cache_dir: Path) -> tuple[bool, str]:
    meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"

    if not meta_file.exists():
        return True, "首次使用，将记录模型元数据"

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        expected_hash = meta.get("config_hash", "")
        recorded_version = meta.get("version", "")

        if expected_hash and expected_hash != MODEL_CONFIG.get("config_hash", ""):
            expected = str(MODEL_CONFIG.get("config_hash", ""))[:16]
            return (
                False,
                f"模型配置哈希不匹配！预期：{expected}..., 实际：{expected_hash[:16]}...",
            )

        if recorded_version != MODEL_CONFIG["version"]:
            return (
                False,
                f"模型版本不一致！已记录：{recorded_version}, 当前配置：{MODEL_CONFIG['version']}",
            )

        return True, "模型完整性验证通过"
    except Exception as e:
        return False, f"验证模型完整性失败：{e}"


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
        meta_file.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"Warning: Failed to record model metadata: {e}")


def load_backend_model(
    model_config: dict[str, Any], cache_dir: Path
) -> tuple[Any, str]:
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
            print(f"Loading embedding model: {model_name} via {backend}...")
            cache_dir.mkdir(parents=True, exist_ok=True)

            is_valid, verify_msg = verify_model_integrity(model_name, cache_dir)
            if not is_valid:
                print(f"Warning: Model integrity check failed: {verify_msg}")
                print(
                    "Warning: Will proceed with loading, but embeddings may be inconsistent."
                )

            self._model, self._backend = load_backend_model(MODEL_CONFIG, cache_dir)

            meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"
            if not meta_file.exists():
                record_model_metadata(model_name, cache_dir)

            self._model_verified = True
            print("Model loaded successfully.")
            return True
        except Exception as e:
            print(f"Warning: Failed to load embedding model: {e}")
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
            print(f"Encoding error: {e}")
            return []


__all__ = [
    "SharedEmbeddingModel",
    "encode_texts",
    "get_backend_name",
    "load_backend_model",
    "record_model_metadata",
    "verify_model_integrity",
]
