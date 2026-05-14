"""
Life Index - Optional LLM-dependent modules.
============================================

Modules in this package require LLM API configuration and are NOT imported
by default on the deterministic code path. They are loaded only when a user
or agent explicitly opts into LLM-assisted enrichment.

Per CHARTER §1.9, the default execution path of any L2/L3 module must not
hold, configure, or call any LLM. This package exists as the explicit opt-in
location for provider-dependent functionality.
"""

__all__ = ["llm_extract"]
