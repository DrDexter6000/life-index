"""
Life Index - Topic Taxonomy (Deterministic)
===========================================
Valid topic set for journal classification.

This is the deterministic SSOT for topic validation. It does not
depend on any LLM, network, or optional dependency.
"""

VALID_TOPICS: set[str] = {
    "work",
    "learn",
    "health",
    "relation",
    "think",
    "create",
    "life",
}

__all__ = ["VALID_TOPICS"]
