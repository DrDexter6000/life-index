"""Transport-neutral, narrow Host Agent access to canonical Core operations."""

from .dispatcher import dispatch
from .registry import CAPABILITY_REGISTRY

__all__ = ["CAPABILITY_REGISTRY", "dispatch"]
