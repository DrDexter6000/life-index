#!/usr/bin/env python3
"""Local/private eval data path helpers.

Public releases ship the eval harness, not the query/baseline corpus.  Local
eval data is resolved from an explicit directory first, then from the active
Life Index data directory.
"""

from __future__ import annotations

import os
from pathlib import Path

EVAL_DATA_ENV = "LIFE_INDEX_EVAL_DATA_DIR"
EVAL_DIR_NAME = ".eval"
GOLDEN_QUERIES_FILENAME = "golden_queries.yaml"
GOLDEN_REJECTION_FILENAME = "golden_rejection_queries.yaml"
BASELINES_DIRNAME = "baselines"
FIXTURES_DIRNAME = "fixtures"


def get_eval_data_dir(data_dir: Path | None = None) -> Path:
    """Return the conventional local/private eval data directory."""
    explicit = os.environ.get(EVAL_DATA_ENV)
    if explicit:
        return Path(explicit)

    base = data_dir or os.environ.get("LIFE_INDEX_DATA_DIR")
    if base:
        return Path(base) / EVAL_DIR_NAME

    return Path.home() / "Documents" / "Life-Index" / EVAL_DIR_NAME


def get_golden_queries_path(data_dir: Path | None = None) -> Path:
    return get_eval_data_dir(data_dir) / GOLDEN_QUERIES_FILENAME


def get_golden_rejection_queries_path(data_dir: Path | None = None) -> Path:
    return get_eval_data_dir(data_dir) / GOLDEN_REJECTION_FILENAME


def get_baselines_dir(data_dir: Path | None = None) -> Path:
    return get_eval_data_dir(data_dir) / BASELINES_DIRNAME


def get_fixtures_dir(data_dir: Path | None = None) -> Path:
    return get_eval_data_dir(data_dir) / FIXTURES_DIRNAME


def resolve_eval_file(
    explicit_path: Path | None,
    filename: str,
    *,
    data_dir: Path | None = None,
) -> Path:
    """Resolve an explicit eval file or its conventional private location."""
    if explicit_path is not None:
        return Path(explicit_path)
    return get_eval_data_dir(data_dir) / filename
