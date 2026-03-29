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
from . import semantic_search
from . import vector_index_simple
from . import search_index
from . import metadata_cache
from . import file_lock
from . import frontmatter
from . import errors
from . import path_contract
from . import text_normalize
from . import llm_extract

__all__ = [
    "USER_DATA_DIR",
    "JOURNALS_DIR",
    "BY_TOPIC_DIR",
    "ATTACHMENTS_DIR",
    "ABSTRACTS_DIR",
]
