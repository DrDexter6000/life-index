---
id: ADR-027
title: Write Journal LLM Extract Migration (Phase 1)
status: accepted
created: 2026-05-14
charter_ref: CHARTER §1.5, §1.9, §2.3, §4.1
rfc_ref: RFC-2026-05-14-agent-native-module-principle
owner: 码农A_GLM (worker), 主审_GPT (reviewer)
---

# ADR-027: Write Journal LLM Extract Migration (Phase 1)

## Context

CHARTER v1.3.0 §1.9 (Agent-Native Module Principle) mandates that L2/L3 modules must not hold, configure, or call an LLM on their default execution paths. The existing `write_journal` pipeline violates this:

- `tools/lib/llm_extract.py` is an L2 shared library that calls an OpenAI-compatible API
- `prepare_journal_metadata()` defaults to `use_llm=True`, which checks for LLM availability and calls it
- `tools/lib/__init__.py` imports `llm_extract` unconditionally, making the LLM dependency transitively importable

## Decision

1. **Move `VALID_TOPICS`** from `tools/lib/llm_extract.py` to `tools/lib/topics.py` (deterministic, no LLM dependency)
2. **Move `llm_extract.py`** from `tools/lib/` to `tools/_optional/llm_extract.py` (opt-in only)
3. **Replace** `tools/lib/llm_extract.py` with a backward-compat re-export shim using `__getattr__`
4. **Remove** `from . import llm_extract` from `tools/lib/__init__.py`
5. **Change** `prepare_journal_metadata(use_llm=True)` default to `use_llm=False`
6. **Change** CLI `enrich` subcommand: default is no LLM; `--use-llm` flag for explicit opt-in
7. **Keep** `--no-llm` as no-op in CLI for backward compat

## Artifact Diff Coupling

This ADR is coupled to the following code changes (same logical change):

| File | Change |
|------|--------|
| `tools/lib/topics.py` | **NEW**: deterministic VALID_TOPICS set |
| `tools/_optional/__init__.py` | **NEW**: optional dependency package |
| `tools/_optional/llm_extract.py` | **NEW**: LLM extraction moved here |
| `tools/lib/llm_extract.py` | Replaced with backward-compat shim |
| `tools/lib/__init__.py` | Removed `llm_extract` import |
| `tools/write_journal/prepare.py` | Default `use_llm=False`, conditional import |
| `tools/write_journal/__main__.py` | `--use-llm` opt-in flag; hidden `--no-llm` no-op compat flag |
| `tools/dev/normalize_topic_taxonomy/__init__.py` | Import from `topics.py` |
| `docs/API.md` | Write contract clarifies caller-filled metadata by default |
| `docs/ARCHITECTURE.md` | Topic taxonomy SSOT path updated to `tools/lib/topics.py` |
| `SKILL.md` | Agent-facing topic taxonomy SSOT path updated |
| `tools/lib/AGENTS.md` | Local library ownership notes updated for `topics.py` and migrated shim |
| `tests/unit/test_field_sources.py` | Updated mock targets |
| `tests/unit/test_write_journal_cli.py` | CLI opt-in and `--no-llm` compat coverage |
| `tests/contract/test_agent_native_write.py` | Contract tests for default-no-LLM |

## Consequences

**Positive:**
- `life-index write` works without LLM keys or httpx installed
- `tools.lib` import no longer triggers LLM dependency chain
- Deterministic `VALID_TOPICS` available without LLM proximity
- Backward compat shim prevents import breakage for existing code

**Negative:**
- Users relying on default LLM enrichment in `enrich` command must now pass `--use-llm`
- `--no-llm` remains accepted as a hidden no-op compatibility flag, but is no longer advertised
- The backward-compat shim in `tools/lib/llm_extract.py` should be removed after full migration (Phase 5)

## Compliance

This change brings the write_journal pipeline into compliance with:
- CHARTER §1.5: L2 must not call LLM (default path no longer does)
- CHARTER §1.9: Module default path does not hold/call LLM
- CHARTER §2.3: L2 operations are deterministic by default
- CHARTER §4.1 anti-patterns: No bundled LLM, no hidden provider config
