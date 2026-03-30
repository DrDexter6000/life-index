# Life Index Tools - Shared Library
"""
Shared utilities for Life Index atomic tools.
"""

from .config import (
    USER_DATA_DIR,
    JOURNALS_DIR,
    BY_TOPIC_DIR,
    ATTACHMENTS_DIR,
    ABSTRACTS_DIR,
)

# Import submodules for mock patchability (tests use patch("tools.lib.semantic_search"))
# These are not exported to users, only for unittest.mock compatibility
from . import semantic_search  # noqa: F401
from . import vector_index_simple  # noqa: F401
from . import search_index  # noqa: F401
from . import metadata_cache  # noqa: F401
from . import file_lock  # noqa: F401
from . import frontmatter  # noqa: F401
from . import errors  # noqa: F401
from . import path_contract  # noqa: F401
from . import text_normalize  # noqa: F401
from . import llm_extract  # noqa: F401

__all__ = [
    "USER_DATA_DIR",
    "JOURNALS_DIR",
    "BY_TOPIC_DIR",
    "ATTACHMENTS_DIR",
    "ABSTRACTS_DIR",
]
