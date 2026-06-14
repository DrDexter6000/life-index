from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any, cast

from tools.agent_bridge.config import resolve_brain_config
from tools.agent_bridge.resolve import resolve_source

# Modest upper bound for hydrated text before it reaches the ACP prompt.
# The ACP adapter applies its own tighter bound (currently 500 chars).
_MAX_HYDRATED_SNIPPET_LEN = 2000

# Bound the number of per-item doc_id/rel_path fallback searches to avoid
# subprocess storms when many evidence items are blank.
_MAX_FALLBACK_SEARCHES = 10

# Tags that may leak from L2 search highlighting into prompt text.
_MARK_RE = re.compile(r"</?mark>", re.IGNORECASE)


def _cli_smart_search(query: str) -> dict[str, Any]:
    """Subprocess the L2 CLI for a deterministic scaffold. No L2 internals imported."""
    out = subprocess.run(
        [sys.executable, "-m", "tools", "smart-search", "--query", query, "--include-evidence"],
        capture_output=True,
        text=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(out.stdout))


def _cli_search_read_top(query: str, *, limit: int = 10) -> dict[str, Any]:
    """Subprocess the L2 search CLI to read full content for top results.

    Uses the public ``search`` CLI with ``--level 3 --read-top N --limit N``.
    No L2 internals are imported; the call is deterministic and bounded.
    """
    top_n = max(1, min(limit, 20))
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools",
            "search",
            "--query",
            query,
            "--level",
            "3",
            "--read-top",
            str(top_n),
            "--limit",
            str(top_n),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return cast(dict[str, Any], json.loads(out.stdout))


def _normalize_path_sep(pathish: str) -> str:
    """Flip Windows backslashes to forward slashes and strip leading/trailing slashes."""
    return pathish.replace("\\", "/").strip("/")


def _normalize_journal_path(pathish: str) -> str:
    """Normalize a journal identifier so absolute, Journals/, and bare forms match.

    Examples:
      ``D:/Life Index/Journals/2026/06/file.md`` → ``2026/06/file``
      ``Journals/2026/06/file.md`` → ``2026/06/file``
      ``2026/06/file`` → ``2026/06/file``
    """
    norm = _normalize_path_sep(pathish)
    if norm.endswith(".md"):
        norm = norm[:-3]
    # Strip any prefix before ``Journals/`` (handles absolute data-dir paths).
    idx = norm.find("Journals/")
    if idx != -1:
        norm = norm[idx + len("Journals/") :]
    elif norm.startswith("Journals/"):
        norm = norm[len("Journals/") :]
    return norm.strip("/")


def _strip_mark_tags(text: str) -> str:
    """Remove simple ``<mark>`` / ``</mark>`` tags from L2 search output."""
    return _MARK_RE.sub("", text)


def _bound_text(text: Any, max_len: int = _MAX_HYDRATED_SNIPPET_LEN) -> str:
    """Return *text* bounded to *max_len* characters with an ellipsis if truncated."""
    if not isinstance(text, str):
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _extract_text_from_item(item: Any) -> str:
    """Return the best available text snippet from an evidence item."""
    if not isinstance(item, dict):
        return ""
    for key in ("snippet", "abstract", "content"):
        val = item.get(key)
        if isinstance(val, str):
            return val
    return ""


def _item_needs_hydration(item: Any) -> bool:
    """Return True when *item* exists and has no usable snippet/abstract/content."""
    return isinstance(item, dict) and not _extract_text_from_item(item).strip()


def _build_search_lookup(search_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a normalized lookup (path -> merged result) from L2 search output."""
    lookup: dict[str, dict[str, Any]] = {}
    merged_results = search_result.get("merged_results")
    if not isinstance(merged_results, list):
        return lookup
    for item in merged_results:
        if not isinstance(item, dict):
            continue
        for key in ("rel_path", "path", "doc_id"):
            raw = item.get(key)
            if isinstance(raw, str) and raw:
                lookup[raw] = item
                norm_sep = _normalize_path_sep(raw)
                if norm_sep and norm_sep != raw:
                    lookup[norm_sep] = item
                norm_journal = _normalize_journal_path(raw)
                if norm_journal and norm_journal != raw and norm_journal != norm_sep:
                    lookup[norm_journal] = item
    return lookup


def _hydrate_blank_item(item: Any, lookup: dict[str, dict[str, Any]]) -> None:
    """Fill a blank evidence/filtered item snippet from the L2 search lookup in place."""
    if not isinstance(item, dict):
        return
    if _extract_text_from_item(item).strip():
        return

    candidate_keys: list[str] = []
    if "document" in item and isinstance(item.get("document"), dict):
        doc_id = item["document"].get("doc_id")
        if isinstance(doc_id, str):
            candidate_keys.append(doc_id)
    for key in ("rel_path", "path", "doc_id"):
        val = item.get(key)
        if isinstance(val, str):
            candidate_keys.append(val)

    for key in candidate_keys:
        match = (
            lookup.get(key)
            or lookup.get(_normalize_path_sep(key))
            or lookup.get(_normalize_journal_path(key))
        )
        if match:
            text = match.get("full_content") or match.get("snippet") or ""
            if isinstance(text, str) and text.strip():
                item["snippet"] = _bound_text(_strip_mark_tags(text))
                return


def _extract_fallback_key(item: Any) -> str | None:
    """Return the best doc_id/rel_path key to use for a fallback L2 search."""
    if not isinstance(item, dict):
        return None
    document = item.get("document")
    if isinstance(document, dict):
        doc_id = document.get("doc_id")
        if isinstance(doc_id, str) and doc_id:
            return doc_id
    for key in ("rel_path", "path", "doc_id"):
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _collect_fallback_keys(scaffold: dict[str, Any]) -> list[str]:
    """Collect unique doc_id/rel_path keys from evidence items that are still blank."""
    keys: list[str] = []
    seen: set[str] = set()

    evidence_pack = scaffold.get("evidence_pack")
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items")
        if isinstance(items, list):
            for item in items:
                if not _item_needs_hydration(item):
                    continue
                key = _extract_fallback_key(item)
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)

    filtered_results = scaffold.get("filtered_results")
    if isinstance(filtered_results, list):
        for item in filtered_results:
            if not _item_needs_hydration(item):
                continue
            key = _extract_fallback_key(item)
            if key and key not in seen:
                seen.add(key)
                keys.append(key)

    return keys


def _hydrate_all_blank_items(
    scaffold: dict[str, Any],
    lookup: dict[str, dict[str, Any]],
) -> None:
    """Hydrate every blank item in *scaffold* from *lookup* in place."""
    evidence_pack = scaffold.get("evidence_pack")
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items")
        if isinstance(items, list):
            for item in items:
                _hydrate_blank_item(item, lookup)

    filtered_results = scaffold.get("filtered_results")
    if isinstance(filtered_results, list):
        for item in filtered_results:
            _hydrate_blank_item(item, lookup)


def _has_evidence_items(scaffold: dict[str, Any]) -> bool:
    """Return True when *scaffold* carries at least one evidence item."""
    evidence_pack = scaffold.get("evidence_pack")
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items")
        if isinstance(items, list) and items:
            return True
    filtered_results = scaffold.get("filtered_results")
    if isinstance(filtered_results, list) and filtered_results:
        return True
    return False


def _has_blank_evidence(scaffold: dict[str, Any]) -> bool:
    """Return True when at least one evidence/filtered item needs hydration."""
    evidence_pack = scaffold.get("evidence_pack")
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items")
        if isinstance(items, list):
            for item in items:
                if _item_needs_hydration(item):
                    return True
    filtered_results = scaffold.get("filtered_results")
    if isinstance(filtered_results, list):
        for item in filtered_results:
            if _item_needs_hydration(item):
                return True
    return False


def _hydrate_blank_evidence(scaffold: dict[str, Any], query: str) -> dict[str, Any]:
    """Fill blank smart-search evidence snippets from the L2 ``search --read-top`` CLI.

    Only items that already have a doc_id/rel_path but no snippet/abstract/content
    are hydrated.  Non-blank items and explicit caller scaffolds are left untouched.
    Known doc_id/rel_path keys are tried first because they can read the target
    document directly. If that does not hydrate all items, the original query is
    used as a bounded fallback.
    """
    if not _has_blank_evidence(scaffold):
        return scaffold

    lookup: dict[str, dict[str, Any]] = {}
    tried_keys: set[str] = set()
    for key in _collect_fallback_keys(scaffold)[:_MAX_FALLBACK_SEARCHES]:
        tried_keys.add(key)
        try:
            fallback_result = _cli_search_read_top(key, limit=1)
            lookup.update(_build_search_lookup(fallback_result))
        except Exception:
            # A single fallback failure must not abort hydration for others.
            continue
    _hydrate_all_blank_items(scaffold, lookup)

    if _has_blank_evidence(scaffold):
        search_result = _cli_search_read_top(query)
        lookup.update(_build_search_lookup(search_result))
        _hydrate_all_blank_items(scaffold, lookup)

    if _has_blank_evidence(scaffold):
        for key in _collect_fallback_keys(scaffold)[:_MAX_FALLBACK_SEARCHES]:
            if key in tried_keys:
                continue
            try:
                fallback_result = _cli_search_read_top(key, limit=1)
                lookup.update(_build_search_lookup(fallback_result))
            except Exception:
                # A single fallback failure must not abort hydration for others.
                continue
        _hydrate_all_blank_items(scaffold, lookup)

    return scaffold


def warm_gateway_scaffold_path(query: str = "__warmup__") -> dict[str, Any]:
    """Best-effort warm the deterministic L3→L2 scaffold path on server start.

    Runs ``build_gateway_scaffold`` and a bounded ``search --read-top`` once
    so the first real grounded query pays less Python import / subprocess /
    index-cache cold cost.

    This is best-effort only: any exception is caught, recorded, and must
    NOT prevent the ACP service from starting.  No ACP init or LLM synthesis
    is performed.

    Returns a dict with ``ok`` (bool) and ``error_message`` (str | None).
    """
    try:
        build_gateway_scaffold(query)
        _cli_search_read_top(query, limit=1)
        return {"ok": True, "error_message": None}
    except Exception as exc:
        return {"ok": False, "error_message": str(exc)}


def hydrate_gateway_scaffold(scaffold: dict[str, Any], query: str) -> dict[str, Any]:
    """Hydrate blank evidence text in an existing gateway scaffold.

    This does not run smart-search. It is safe for explicit caller scaffolds:
    non-blank evidence is returned unchanged, while blank evidence snippets are
    filled through the bounded public L2 ``search --read-top`` path.
    """
    if _has_evidence_items(scaffold):
        scaffold = _hydrate_blank_evidence(scaffold, query)
    return scaffold


def build_gateway_scaffold(query: str) -> dict[str, Any]:
    """Build a gateway-assembled scaffold with hydrated evidence.

    Runs the deterministic L2 smart-search builder and then hydrates blank
    evidence snippets through the public L2 search CLI. This is used only for
    bare gateway queries.
    """
    return hydrate_gateway_scaffold(_cli_smart_search(query), query)


def _build_prompts(scaffold: dict[str, Any]) -> tuple[str, str]:
    instr = scaffold.get("agent_instructions", {})
    system = "You are the user's trusted assistant. " + " ".join(instr.get("steps", []))
    user = json.dumps(
        {
            "query": scaffold.get("query"),
            "filtered_results": scaffold.get("filtered_results", []),
            "evidence_pack": scaffold.get("evidence_pack", {}),
            "answer_scaffold": scaffold.get("answer_scaffold", {}),
        },
        ensure_ascii=False,
    )
    return system, user


def handoff_search(query: str, *, in_context_agent: bool = False) -> dict[str, Any]:
    """Run smart-search scaffold -> resolve brain -> (maybe) synthesize.

    Returns a proposal envelope with keys: source, query, scaffold, synthesis
    (or the m35.agent_bridge_query.v0 envelope when routed through ACP).
    """
    scaffold = _cli_smart_search(query)
    cfg = resolve_brain_config()
    source = resolve_source(cfg, in_context_agent=in_context_agent)

    # ACP query path: route through dedicated ACP query adapter.
    # This path does NOT call client.synthesize (no OpenAI-compatible fallback).
    if source in ("P1", "P2") and cfg.transport == "acp" and cfg.data_exposure_ack:
        from tools.agent_bridge.acp_query import acp_query_adapter

        try:
            result = acp_query_adapter(query, scaffold, cfg)
            return result  # Already m35.agent_bridge_query.v0 envelope
        except Exception:
            # ACP setup failed — degrade deterministically through adapter
            from tools.agent_bridge.acp_query import build_degraded_result, build_provenance

            return build_degraded_result(
                "UNGROUNDED",
                f"ACP query adapter failed for query: {query}",
                build_provenance(cfg, degraded=True),
            )

    # Legacy P1/P2 path (OpenAI-compatible)
    envelope: dict[str, Any] = {
        "source": source,
        "query": query,
        "scaffold": scaffold,
        "synthesis": None,
    }
    if source in ("P1", "P2"):
        # Lazy import: client.py imports openai inside synthesize(),
        # but we guard here so the degrade path never touches the SDK.
        from tools.agent_bridge import client

        system, user = _build_prompts(scaffold)
        envelope["synthesis"] = client.synthesize(cfg, system, user)
    return envelope
