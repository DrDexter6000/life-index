"""
Life Index - Optional LLM-dependent modules.
============================================

Modules in this package require LLM API configuration and are NOT imported
by default on the deterministic code path. They are isolated for explicit
developer experiments or future host-agent integrations, not core tools.

Per CHARTER APEX, deterministic tools must not hold, configure, or call any
LLM. This package exists as the isolated location for provider-dependent
functionality outside default tool and agent paths.
"""

__all__ = ["llm_extract"]
