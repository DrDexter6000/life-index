"""Runtime data-source helpers for the Web GUI."""

from __future__ import annotations

import os
from typing import Any

from tools.lib.config import resolve_journals_dir, resolve_user_data_dir


def get_runtime_info() -> dict[str, Any]:
    user_data_dir = resolve_user_data_dir()
    journals_dir = resolve_journals_dir()
    return {
        "user_data_dir": str(user_data_dir),
        "journals_dir": str(journals_dir),
        "life_index_data_dir_override": bool(os.environ.get("LIFE_INDEX_DATA_DIR")),
        "readonly_simulation": os.environ.get("LIFE_INDEX_READONLY_SIMULATION") == "1",
    }
