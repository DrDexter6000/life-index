"""Web GUI configuration constants."""

from pathlib import Path

from tools.lib.config import ATTACHMENTS_DIR, JOURNALS_DIR, USER_DATA_DIR

DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 8765

WEB_DIR: Path = Path(__file__).parent
TEMPLATES_DIR: Path = WEB_DIR / "templates"
STATIC_DIR: Path = WEB_DIR / "static"

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "WEB_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
    "USER_DATA_DIR",
    "JOURNALS_DIR",
    "ATTACHMENTS_DIR",
]
