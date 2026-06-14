"""Gateway-side mapping from the minimal internal query envelope to the rich
``m35.agent_bridge_query.v0`` GUI contract.

V6-G2 normalizes the warm Agent Bridge service output without changing the
V5a/V5b LLM adapter's validation, JSON repair, evidence ID whitelist, or
no-OpenAI-fallback behavior.
"""

from __future__ import annotations

from typing import Any

RICH_SCHEMA_VERSION = "m35.agent_bridge_query.v0"
DEFAULT_COMMAND = "agent-bridge query"
DEFAULT_SOURCE = "host-agent"
DEFAULT_EVIDENCE_SOURCE = "life-index search"
DEFAULT_HOST_AGENT = "configured provider label"


def _normalize_path_sep(pathish: str) -> str:
    """Flip Windows backslashes to forward slashes."""
    return pathish.replace("\\", "/")


def _normalize_id_to_gui(real_id: str) -> str:
    """Convert a real journal path ID to the GUI evidence ``id`` format.

    ``Journals/2026/06/life-index_2026-06-02_001.md`` becomes
    ``2026/06/life-index_2026-06-02_001``.
    """
    norm = _normalize_path_sep(real_id).strip("/")
    if norm.startswith("Journals/"):
        norm = norm[len("Journals/") :]
    if norm.endswith(".md"):
        norm = norm[:-3]
    return norm


def _gui_id_to_rel_path(gui_id: str) -> str:
    """Return the canonical ``Journals/.../*.md`` rel_path for a GUI id."""
    norm = _normalize_path_sep(gui_id).strip("/")
    if not norm.endswith(".md"):
        norm = f"{norm}.md"
    if not norm.startswith("Journals/"):
        norm = f"Journals/{norm}"
    return norm


def _extract_real_id_from_item(item: dict[str, Any]) -> str | None:
    """Pick a stable real journal ID from an evidence-pack-style item."""
    document = item.get("document")
    if isinstance(document, dict):
        doc_id = document.get("doc_id")
        if isinstance(doc_id, str) and doc_id:
            return doc_id
    return None


def _extract_real_id_from_filtered(item: dict[str, Any]) -> str | None:
    """Pick a journal-relative ID from a filtered_results entry."""
    for key in ("rel_path", "journal_route_path", "path"):
        val = item.get(key)
        if isinstance(val, str):
            norm = _normalize_path_sep(val).strip("/")
            if norm.startswith("Journals/"):
                return norm
            idx = norm.find("Journals/")
            if idx != -1:
                return norm[idx:]
    return None


def _extract_text_from_item(item: dict[str, Any]) -> str:
    """Return the best available text snippet from an evidence item."""
    for key in ("snippet", "abstract", "content"):
        val = item.get(key)
        if isinstance(val, str):
            return val
    return ""


def _build_scaffold_lookup(scaffold: Any) -> dict[str, dict[str, Any]]:
    """Collect real_id -> {document, snippet} from all scaffold evidence sources."""
    lookup: dict[str, dict[str, Any]] = {}

    def _add(real_id: str, document: dict[str, Any], snippet: str) -> None:
        if not real_id or real_id in lookup:
            return
        lookup[real_id] = {"document": document, "snippet": snippet}

    if not isinstance(scaffold, dict):
        return lookup

    evidence_pack = scaffold.get("evidence_pack")
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items", [])
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                real_id = _extract_real_id_from_item(item)
                if real_id:
                    raw_doc = item.get("document")
                    document: dict[str, Any] = raw_doc if isinstance(raw_doc, dict) else {}
                    _add(real_id, document, _extract_text_from_item(item))

        semantic = evidence_pack.get("semantic_candidates", [])
        if isinstance(semantic, list):
            for item in semantic:
                if not isinstance(item, dict):
                    continue
                real_id = _extract_real_id_from_item(item)
                if real_id:
                    raw_doc = item.get("document")
                    document = raw_doc if isinstance(raw_doc, dict) else {}
                    _add(real_id, document, _extract_text_from_item(item))

    filtered = scaffold.get("filtered_results")
    if isinstance(filtered, list):
        for item in filtered:
            if not isinstance(item, dict):
                continue
            real_id = _extract_real_id_from_filtered(item)
            if real_id:
                document = {"doc_id": real_id}
                title = item.get("title")
                if isinstance(title, str):
                    document["title"] = title
                date = item.get("date")
                if isinstance(date, str):
                    document["date"] = date
                metadata = item.get("metadata")
                if isinstance(metadata, dict):
                    document["metadata"] = metadata
                _add(real_id, document, _extract_text_from_item(item))

    return lookup


def clean_scaffold(scaffold: Any) -> dict[str, Any]:
    """Return the scaffold subset expected by the GUI contract."""
    if not isinstance(scaffold, dict):
        return {
            "intent": "",
            "date_from": "",
            "date_to": "",
            "queries": [],
            "filters": {},
        }

    queries = scaffold.get("queries")
    if isinstance(queries, list) and queries:
        pass
    else:
        # Real smart-search output carries sub_queries under query_plan.
        query_plan = scaffold.get("query_plan")
        if isinstance(query_plan, dict):
            sub_queries = query_plan.get("sub_queries")
            if isinstance(sub_queries, list):
                queries = sub_queries
        if not isinstance(queries, list):
            queries = []

    filters = scaffold.get("filters")
    if not isinstance(filters, dict):
        filters = {}

    return {
        "intent": scaffold.get("intent") or "",
        "date_from": scaffold.get("date_from") or "",
        "date_to": scaffold.get("date_to") or "",
        "queries": queries,
        "filters": filters,
    }


def build_evidence(
    scaffold: Any,
    accepted_real_ids: list[str],
) -> list[dict[str, Any]]:
    """Build the rich ``evidence[]`` list from scaffold metadata.

    Only entries whose real journal ID appears in *accepted_real_ids* are
    included, preserving the adapter's evidence whitelist guard and avoiding
    any extra journal file reads.
    """
    lookup = _build_scaffold_lookup(scaffold)
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    for real_id in accepted_real_ids:
        if not isinstance(real_id, str) or not real_id or real_id in seen:
            continue
        seen.add(real_id)
        entry = lookup.get(real_id)
        if entry is None:
            # Unknown IDs are dropped; the adapter already rejected them, so
            # this is defensive against malformed downstream input.
            continue

        document = entry.get("document") or {}
        if not isinstance(document, dict):
            document = {}

        gui_id = _normalize_id_to_gui(real_id)
        rel_path = _gui_id_to_rel_path(gui_id)
        title = document.get("title") or ""
        date = document.get("date") or ""
        snippet = entry.get("snippet", "")
        if not isinstance(snippet, str):
            snippet = ""
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        evidence.append(
            {
                "id": gui_id,
                "rel_path": rel_path,
                "title": title,
                "date": date,
                "snippet": snippet,
                "metadata": metadata,
            }
        )

    return evidence


def build_answer(
    internal: Any,
    evidence: list[dict[str, Any]],
    scaffold: Any,
) -> dict[str, Any]:
    """Map the internal envelope to the rich ``answer`` object."""
    mode = internal.get("status") if isinstance(internal, dict) else None
    if mode not in ("GROUNDED", "PARTIAL", "UNGROUNDED"):
        mode = "UNGROUNDED"

    summary = internal.get("answer") if isinstance(internal, dict) else None
    if not isinstance(summary, str):
        summary = ""

    gap = internal.get("gap") if isinstance(internal, dict) else None
    if not isinstance(gap, str):
        gap = None

    evidence_lookup = {e["id"]: e for e in evidence}
    valid_evidence_ids = set(evidence_lookup)
    insights: list[dict[str, Any]] = []

    internal_insights = internal.get("insights") if isinstance(internal, dict) else None
    if isinstance(internal_insights, list):
        for ins in internal_insights:
            if not isinstance(ins, dict):
                continue
            refs = ins.get("evidence_refs")
            if not isinstance(refs, list):
                refs = []
            gui_refs: list[str] = []
            for r in refs:
                if not isinstance(r, str):
                    continue
                gui_ref = _normalize_id_to_gui(r)
                # Drop refs that do not resolve to a top-level evidence entry.
                # This prevents insights from pointing at IDs absent from the
                # finalized evidence list.
                if gui_ref in valid_evidence_ids:
                    gui_refs.append(gui_ref)

            interpretation = ins.get("text")
            if not isinstance(interpretation, str):
                interpretation = ""

            theme = scaffold.get("intent") if isinstance(scaffold, dict) else ""
            if not isinstance(theme, str):
                theme = ""

            quote = ""
            date = ""
            if gui_refs:
                first = evidence_lookup.get(gui_refs[0], {})
                raw_quote = first.get("snippet")
                quote = raw_quote if isinstance(raw_quote, str) else ""
                raw_date = first.get("date")
                date = raw_date if isinstance(raw_date, str) else ""

            insights.append(
                {
                    "theme": theme,
                    "quote": quote,
                    "date": date,
                    "interpretation": interpretation,
                    "evidence_refs": gui_refs,
                }
            )

    return {
        "mode": mode,
        "summary": summary,
        "insights": insights,
        "related_findings": [],
        "gap": gap,
        "explanation": gap if mode == "UNGROUNDED" else None,
        "what_was_found": [],
        "suggestions": [],
    }


def build_provenance(
    internal: Any,
    host_agent: str = DEFAULT_HOST_AGENT,
) -> dict[str, Any]:
    """Build the rich ``provenance`` object from the internal envelope."""
    internal_prov = internal.get("provenance") if isinstance(internal, dict) else None
    if not isinstance(internal_prov, dict):
        internal_prov = {}

    return {
        "evidence_source": DEFAULT_EVIDENCE_SOURCE,
        "host_agent": host_agent,
        "degraded": bool(internal_prov.get("degraded", False)),
    }


def map_to_rich_envelope(
    query: str,
    scaffold: Any,
    internal: Any,
    *,
    host_agent: str = DEFAULT_HOST_AGENT,
) -> dict[str, Any]:
    """Map the minimal internal ``m35.agent_bridge_query.v0`` envelope to the
    rich GUI contract shape.

    The internal envelope is the validated output from
    ``tools.agent_bridge.acp_query`` (or a degraded envelope).  This function
    is deterministic, performs no LLM calls, and does not read journal files.
    """
    if not isinstance(internal, dict):
        internal = {}

    mode = internal.get("status")
    if mode not in ("GROUNDED", "PARTIAL", "UNGROUNDED"):
        mode = "UNGROUNDED"

    evidence_refs = internal.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        evidence_refs = []

    evidence = build_evidence(scaffold, evidence_refs)
    answer = build_answer(internal, evidence, scaffold)
    provenance = build_provenance(internal, host_agent)

    return {
        "success": True,
        "schema_version": RICH_SCHEMA_VERSION,
        "command": DEFAULT_COMMAND,
        "source": DEFAULT_SOURCE,
        "query": query,
        "mode": mode,
        "scaffold": clean_scaffold(scaffold),
        "evidence": evidence,
        "answer": answer,
        "synthesis": answer["summary"],
        "events": [],
        "provenance": provenance,
    }
