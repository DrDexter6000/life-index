# Life Index Tools - Shared Library
"""
Shared utilities for Life Index atomic tools.
"""

from .paths import ValidationModeDataDirError, enforce_validation_mode_data_dir
from .config import (
    USER_DATA_DIR,
    JOURNALS_DIR,
    BY_TOPIC_DIR,
    ATTACHMENTS_DIR,
    ABSTRACTS_DIR,
)

# Import submodules for mock patchability (tests use patch("tools.lib.semantic_search"))
# These are not exported to users, only for unittest.mock compatibility
try:
    enforce_validation_mode_data_dir()
    _validation_mode_data_dir_safe = True
except ValidationModeDataDirError:
    _validation_mode_data_dir_safe = False

if _validation_mode_data_dir_safe:
    from . import semantic_search  # noqa: F401
    from . import vector_index_simple  # noqa: F401
    from . import search_index  # noqa: F401
    from . import metadata_cache  # noqa: F401
    from . import file_lock  # noqa: F401
    from . import frontmatter  # noqa: F401
    from . import errors  # noqa: F401
    from . import path_contract  # noqa: F401
    from . import text_normalize  # noqa: F401
    from . import topics  # noqa: F401

__all__ = [
    "USER_DATA_DIR",
    "JOURNALS_DIR",
    "BY_TOPIC_DIR",
    "ATTACHMENTS_DIR",
    "ABSTRACTS_DIR",
]
