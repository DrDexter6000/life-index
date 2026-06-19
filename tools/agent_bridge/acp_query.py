from __future__ import annotations

import json
import inspect
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

from tools.agent_bridge.acp_client import _ACPConnection, parse_acp_stream
from tools.agent_bridge.citation_validator import (
    extract_tool_trace_journal_refs,
    normalize_journal_ref,
    validate_citation_gate,
)
from tools.agent_bridge.config import BrainConfig

QUERY_SCHEMA_VERSION = "m35.agent_bridge_query.v0"

# ─── Constants ────────────────────────────────────────────────────────
_MAX_EVIDENCE_ENTRIES = 10
_REPAIR_RETRY_MAX = 1
_PROMPT_RPC_RETRY_MAX = 1
_SKILL_PLAYBOOK_START = "<!-- GROUNDED_QUERY_SKILL_START -->"
_SKILL_PLAYBOOK_END = "<!-- GROUNDED_QUERY_SKILL_END -->"
_MAX_SKILL_PLAYBOOK_CHARS = 6000
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
# Trailing comma immediately before a closing ``}`` or ``]`` — a common
# weak-model "light schema-shape drift". Used only as a bounded, generic
# syntax repair inside ``_try_loads``; it never relaxes schema / status /
# evidence-ID validation, which all run unchanged on the parsed result.
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")
_SENSITIVE_ERROR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b(?:api[_\s-]*key|token|authorization)\b\s*[:=]\s*['\"]?[^\s,'\";\]}]+"),
        "[redacted]",
    ),
    (re.compile(r"(?i)\bbearer\s+['\"]?[^\s,'\";\]}]+"), "[redacted]"),
    (re.compile(r"\b(?:sk|pk|rk|sess)-[A-Za-z0-9_-]{8,}\b"), "[redacted]"),
    (re.compile(r"(?i)\.env(?:\.[A-Za-z0-9_-]+)?"), "[redacted]"),
    (
        re.compile(
            r"(?:/home/[^/\s,'\";\]}]+|[A-Za-z]:[\\/](?:Users|Documents and Settings)"
            r"[\\/][^\\/\s,'\";\]}]+)[^\s,'\";\]}]*",
            re.IGNORECASE,
        ),
        "[local-path-redacted]",
    ),
)


def _safe_exception_summary(exc: Exception) -> str:
    raw = f"{type(exc).__name__}: {exc}"
    for pattern, replacement in _SENSITIVE_ERROR_PATTERNS:
        raw = pattern.sub(replacement, raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:300] or type(exc).__name__


def _load_grounded_query_playbook() -> str:
    """Load the bounded grounded-query playbook from the repository skill file."""
    skill_path = Path(__file__).resolve().parents[2] / "SKILL.md"
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    start = text.find(_SKILL_PLAYBOOK_START)
    end = text.find(_SKILL_PLAYBOOK_END)
    if start == -1 or end == -1 or end <= start:
        return ""
    playbook = text[start + len(_SKILL_PLAYBOOK_START) : end].strip()
    if len(playbook) > _MAX_SKILL_PLAYBOOK_CHARS:
        playbook = playbook[:_MAX_SKILL_PLAYBOOK_CHARS].rstrip() + "\n[truncated]"
    return playbook


def _try_loads(text: str) -> Any | None:
    """Best-effort ``json.loads`` with one bounded, generic light-drift repair.

    First attempts strict ``json.loads``. On failure, applies exactly one
    generic repair — stripping trailing commas immediately before ``}`` or
    ``]`` — and retries once. Returns the parsed object, or ``None`` if both
    attempts fail.

    This relaxes only JSON *syntax* tolerance (a deterministic, model-agnostic
    normalization). Every downstream schema-version, allowed-evidence-ID,
    status-rule, and grounded/partial/ungrounded validation runs unchanged on
    the returned object, so no safety contract is weakened.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    repaired = _TRAILING_COMMA_RE.sub(r"\1", text)
    if repaired != text:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
    return None


def _normalize_journal_id(pathish: str) -> str:
    """Normalize a path-like ID to forward slashes with no leading/trailing slashes."""
    return pathish.replace("\\", "/").strip("/")


def _extract_rpc_usage(response: dict | None) -> dict | None:
    """Return ``response['result']['usage']`` only when it is a dict.

    The ACP ``session/prompt`` RPC is the authoritative source of usage
    metadata.  Model-generated ``usage`` fields in the JSON body are not
    trusted and are overwritten by this value.
    """
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    usage = result.get("usage")
    return usage if isinstance(usage, dict) else None


def _extract_real_id_from_item(item: dict) -> str | None:
    """Return the journal entry ID from an EvidencePack-style item."""
    document = item.get("document")
    if isinstance(document, dict):
        doc_id = document.get("doc_id")
        if isinstance(doc_id, str) and doc_id:
            return doc_id
    return None


def _extract_text_from_item(item: Any) -> str:
    """Return the best available text snippet from an evidence item."""
    if not isinstance(item, dict):
        return ""
    for key in ("snippet", "abstract", "content"):
        val = item.get(key)
        if isinstance(val, str):
            return val
    return ""


def _extract_real_id_from_filtered(item: dict) -> str | None:
    """Pick a journal-relative ID from a filtered_results entry.

    Prefer ``rel_path`` when it starts with ``Journals/``; otherwise try to
    normalize ``journal_route_path`` to a journal-relative ID.  Absolute
    paths are only used as a last resort, and then only to extract a
    ``Journals/`` suffix.
    """
    rel_path = item.get("rel_path")
    if isinstance(rel_path, str):
        norm = _normalize_journal_id(rel_path)
        if norm.startswith("Journals/"):
            return norm

    journal_route_path = item.get("journal_route_path")
    if isinstance(journal_route_path, str):
        norm = _normalize_journal_id(journal_route_path)
        if norm.startswith("Journals/"):
            return norm
        idx = norm.find("Journals/")
        if idx != -1:
            return norm[idx:]

    path = item.get("path")
    if isinstance(path, str):
        norm = _normalize_journal_id(path)
        if norm.startswith("Journals/"):
            return norm
        idx = norm.find("Journals/")
        if idx != -1:
            return norm[idx:]

    return None


def build_evidence_pack(scaffold: dict) -> tuple[dict, dict[str, str]]:
    """Extract candidate evidence entries from a smart-search scaffold.

    Assigns stable short IDs (E1, E2, ...) to each candidate, bounded to
    ``_MAX_EVIDENCE_ENTRIES`` entries.  Returns a 2-tuple of
    ``(evidence_pack_dict, short_id_to_real_id_mapping)``.
    """
    candidates: list[dict] = []
    seen: set[str] = set()

    def add_candidate(real_id: str, text: str) -> None:
        if not real_id or real_id in seen:
            return
        seen.add(real_id)
        if isinstance(text, str) and len(text) > 500:
            text = text[:500] + "..."
        candidates.append({"real_id": real_id, "text": text or ""})

    # Gather from evidence_pack (structured EvidencePack output)
    evidence_pack = scaffold.get("evidence_pack", {})
    if isinstance(evidence_pack, dict):
        items = evidence_pack.get("items", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    rid = _extract_real_id_from_item(item)
                    if rid:
                        add_candidate(rid, _extract_text_from_item(item))

        # Semantic candidates use the same shape and are valid evidence, but
        # only if not already covered by the main item list.
        semantic_candidates = evidence_pack.get("semantic_candidates", [])
        if isinstance(semantic_candidates, list):
            for item in semantic_candidates:
                if isinstance(item, dict):
                    rid = _extract_real_id_from_item(item)
                    if rid:
                        add_candidate(rid, _extract_text_from_item(item))

    # Gather from filtered_results as a fallback for entries not already
    # covered by the structured evidence pack.
    filtered_results = scaffold.get("filtered_results", [])
    if isinstance(filtered_results, list):
        for item in filtered_results:
            if isinstance(item, dict):
                rid = _extract_real_id_from_filtered(item)
                if rid:
                    add_candidate(rid, _extract_text_from_item(item))

    # Bound and assign short IDs
    bounded = candidates[:_MAX_EVIDENCE_ENTRIES]
    evidence = {}
    mapping: dict[str, str] = {}
    for i, c in enumerate(bounded):
        short_id = f"E{i + 1}"
        evidence[short_id] = {"short_id": short_id, "text": c["text"]}
        mapping[short_id] = c["real_id"]

    return evidence, mapping


def build_query_prompt(query: str, evidence_pack: dict, allowed_ids: set[str]) -> str:
    """Build the agentic ACP query prompt.

    The supplied evidence pack is only a deterministic seed/hint.  The host
    agent is expected to use its available Life Index CLI/file-read tools for
    multi-hop evidence gathering, then return the same query envelope schema.
    """
    allowed_str = ", ".join(sorted(allowed_ids)) if allowed_ids else "(none)"
    data_dir = os.environ.get("LIFE_INDEX_DATA_DIR") or "(active LIFE_INDEX_DATA_DIR)"
    validation_mode = os.environ.get("LIFE_INDEX_VALIDATION_MODE") or "(unset)"
    python_executable = sys.executable or "python"
    evidence_lines: list[str] = []
    for sid in sorted(evidence_pack, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0):
        entry = evidence_pack[sid]
        evidence_lines.append(f"  {sid}: {entry['text']}")

    evidence_block = "\n".join(evidence_lines) if evidence_lines else "  (no evidence supplied)"
    grounded_query_playbook = _load_grounded_query_playbook()
    if not grounded_query_playbook:
        grounded_query_playbook = (
            "## Grounded Query Skill Playbook\n"
            "Use deterministic Life Index navigation/search/read tools, then return "
            "answer.insights[] with quote, interpretation, and evidence_refs."
        )

    return f"""You are an evidence-bound Life Index research assistant. Your task is to
answer the following question by actively gathering journal evidence through
the available Life Index CLI and file-read tools, then returning a strictly
validated JSON answer.

QUESTION:
{query}

SEED EVIDENCE PACK (deterministic hints, not the evidence boundary):
{evidence_block}

SEED EVIDENCE IDs: {allowed_str}

Grounded Query Skill Playbook:
{grounded_query_playbook}

IMPORTANT:
- You MUST use the active Life Index data directory exposed to your runtime.
- Current LIFE_INDEX_DATA_DIR: {data_dir}
- Current LIFE_INDEX_VALIDATION_MODE: {validation_mode}
- Current Python executable: {python_executable}
- Prefer Life Index CLI commands such as smart-search/search/read-top, then
  read the cited journal files when needed. When using a terminal, invoke the
  CLI with the current Python executable above and preserve LIFE_INDEX_DATA_DIR
  / LIFE_INDEX_VALIDATION_MODE in that process.
- Do NOT use web search, browser tools, external internet, or unstated prior
  knowledge for evidence. Do not rely on hidden session memory. This is a
  local journal query.
- Do NOT use the queue command or queue the answer for a later turn. Return the
  final JSON directly in the current ACP turn.
- Do NOT search for virtual environments, inspect repository setup, or guess
  runtime paths. Use the current Python executable above.
- Do NOT create, edit, patch, or write any files. Do NOT save the answer to a
  temporary file. Return the final JSON directly in the ACP message.
- You may use seed IDs (E1, E2, ...) only when the seed text is sufficient.
  For any evidence found through tools, cite canonical journal IDs in the form
  Journals/YYYY/MM/name.md.
- Use the magazine output model: `answer` is a concise summary, and
  `insights[]` carries the evidence. The summary may be connective prose and
  does not need an inline evidence id, but it must not introduce dates, counts,
  locations, events, or conclusions that are not covered by the cited insights.
- Every substantive insight MUST include `quote`, `interpretation`, and at
  least one `evidence_refs` item. The quote should be a short journal excerpt
  or close excerpt with no raw double quotes; use Chinese corner quotes if the
  source text contains quotes. The interpretation explains why that evidence
  matters for the question.
- If the answer contains an aggregate count, one insight MUST repeat the exact
  count string in its interpretation and cite the journal entries that make up
  that count. Do not put a count only in the summary.
- The top-level evidence_refs MUST exactly equal the union of all
  insights[].evidence_refs. Do not list every document you found, searched, or
  classified; list only the journal IDs actually used by returned insights.
- Do NOT cite phrases like "[all March entries]" or "[search results]".
  Citation markers must be seed IDs or concrete Journals/YYYY/MM/name.md ids.
- JSON strings must be valid JSON: avoid raw double quotes inside strings, or
  use Chinese corner quotes like 「...」 instead.
- If you cannot gather enough evidence, return PARTIAL or UNGROUNDED with a
  concrete gap. Never produce an empty answer with zero evidence as if it were
  complete.

INSTRUCTIONS:
1. Answer ONLY from cited Life Index journal evidence. Do NOT fabricate,
   infer from hidden memory, or use external knowledge.
2. Every factual claim in your summary MUST be covered by at least one
   structured cited insight.
3. Cite evidence using seed short IDs from the SEED set above or canonical
   Journals/YYYY/MM/name.md IDs discovered by your tool reads.
4. If the evidence is insufficient for a complete answer, mark status as
   PARTIAL or UNGROUNDED.
5. Before choosing UNGROUNDED, run at least one relevant Life Index search or
   read the relevant seed evidence. Only mark UNGROUNDED when the checked
   evidence genuinely fails to address the question.

OUTPUT FORMAT — Respond with exactly ONE JSON object conforming to schema
m35.agent_bridge_query.v0:

{{
  "schema_version": "m35.agent_bridge_query.v0",
  "status": "GROUNDED",
  "answer": "A short magazine-style summary. No new facts beyond insights.",
  "insights": [
    {{
      "theme": "optional short theme",
      "quote": "short journal excerpt with no raw double quotes",
      "interpretation": "why this evidence matters",
      "evidence_refs": ["E1"]
    }}
  ],
  "evidence_refs": ["E1", "E2"],
  "gap": null,
  "provenance": {{
    "transport": "acp", "model": "unknown", "runtime": "acp", "degraded": false
  }},
  "usage": null
}}

NOTE: Do not invent a ``usage`` object. The adapter sets usage from the
ACP RPC response; any model-generated value will be ignored.

STATUS RULES (enforced by validator):
- GROUNDED: answer is non-empty; insights is non-empty with at least one
  evidence_ref each; all refs are seed IDs or canonical Journals/... ids;
  each insight has quote or interpretation; gap is null.
- PARTIAL: answer is present (may be partial); gap is non-empty; refs may
  be incomplete.
- UNGROUNDED: answer is null; insights is empty; evidence_refs is empty;
  gap is non-empty explaining why.

WARNING: Any GROUNDED or PARTIAL answer with fabricated, missing, or
non-journal citations, any insight without evidence_refs, or any summary fact
not covered by cited insights will be rejected before it reaches the user.
Seed IDs available in this prompt:
{allowed_str}"""


def parse_and_validate(  # noqa: C901
    raw_text: str, allowed_ids: frozenset[str]
) -> tuple[dict | None, str | None]:
    """Parse raw model text into a validated ``m35.agent_bridge_query.v0`` envelope.

    Applies bounded JSON repair (strip markdown fence, extract single object)
    before validating schema and status rules.  Returns ``(validated_dict, None)``
    on success and ``(None, error_message)`` on failure.
    """
    parsed: Any = None

    # 1. Try direct parse (with bounded trailing-comma repair)
    stripped = raw_text.strip()
    parsed = _try_loads(stripped)

    # 2. Strip markdown JSON fence (one level)
    if parsed is None:
        m = _FENCE_RE.search(stripped)
        if m:
            inner = m.group(1).strip()
            parsed = _try_loads(inner)

    # 3. Extract exactly one top-level JSON object
    if parsed is None:
        matches = _JSON_OBJECT_RE.findall(stripped)
        if len(matches) == 1:
            parsed = _try_loads(matches[0])
        elif len(matches) > 1:
            return None, "Multiple JSON objects found in output — rejected as mixed prose"

    if parsed is None:
        return None, "Failed to parse any valid JSON from model output"

    if not isinstance(parsed, dict):
        return None, f"Parsed JSON is not a dict: {type(parsed).__name__}"

    # ── Schema validation ──────────────────────────────────────────
    schema_version = parsed.get("schema_version")
    if not isinstance(schema_version, str):
        return None, f"schema_version missing or not a string: {schema_version!r}"
    if schema_version != QUERY_SCHEMA_VERSION:
        return None, (
            f"schema_version must be exactly {QUERY_SCHEMA_VERSION!r}, " f"got: {schema_version!r}"
        )

    status = parsed.get("status")
    if status not in ("GROUNDED", "PARTIAL", "UNGROUNDED"):
        return None, f"status must be GROUNDED, PARTIAL, or UNGROUNDED, got: {status!r}"

    answer = parsed.get("answer")
    if answer is not None and not isinstance(answer, str):
        return None, f"answer must be string or null, got: {type(answer).__name__}"

    insights = parsed.get("insights")
    if not isinstance(insights, list):
        return None, f"insights must be a list, got: {type(insights).__name__}"

    evidence_refs = parsed.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return None, f"evidence_refs must be a list, got: {type(evidence_refs).__name__}"

    gap = parsed.get("gap")
    if gap is not None and not isinstance(gap, str):
        return None, f"gap must be string or null, got: {type(gap).__name__}"

    # Validate insight entries.  V6-CM accepts the structured magazine
    # shape (quote + interpretation) while preserving the legacy text field.
    for i, ins in enumerate(insights):
        if not isinstance(ins, dict):
            return None, f"insights[{i}] must be a dict"
        text = ins.get("text")
        quote = ins.get("quote")
        interpretation = ins.get("interpretation")
        theme = ins.get("theme")
        for field_name, value in (
            ("text", text),
            ("quote", quote),
            ("interpretation", interpretation),
            ("theme", theme),
        ):
            if value is not None and not isinstance(value, str):
                return None, f"insights[{i}].{field_name} must be a string when present"
        if not any(
            isinstance(value, str) and value.strip() for value in (text, quote, interpretation)
        ):
            return None, (f"insights[{i}] must include non-empty text, quote, or interpretation")
        refs = ins.get("evidence_refs")
        if not isinstance(refs, list):
            return None, f"insights[{i}].evidence_refs must be a list"

    # Validate evidence_refs entries are strings
    for i, ref in enumerate(evidence_refs):
        if not isinstance(ref, str):
            return None, f"evidence_refs[{i}] must be a string"

    # ── Evidence ID validation (all refs must be in allowed_ids) ──
    all_refs: set[str] = set(evidence_refs)
    for ins in insights:
        refs = ins.get("evidence_refs", [])
        if isinstance(refs, list):
            all_refs.update(r for r in refs if isinstance(r, str))

    unknown_ids = {
        ref for ref in all_refs if ref not in allowed_ids and normalize_journal_ref(ref) is None
    }
    if unknown_ids:
        ids_str = ", ".join(sorted(unknown_ids))
        return None, (
            f"Unknown evidence IDs in response: {ids_str}. Allowed seed IDs: "
            f"{sorted(allowed_ids)} or canonical Journals/YYYY/MM/name.md ids"
        )

    # ── Status rule validation ──────────────────────────────────────
    if status == "GROUNDED":
        if not answer:
            return None, "GROUNDED status requires non-empty answer"
        if not insights:
            return None, "GROUNDED status requires non-empty insights"
        if not evidence_refs:
            return None, "GROUNDED status requires non-empty evidence_refs"
        for i, ins in enumerate(insights):
            refs = ins.get("evidence_refs", [])
            if not isinstance(refs, list) or len(refs) == 0:
                msg = (
                    f"GROUNDED status requires each insight to have "
                    f"evidence_refs (insight {i} missing)"
                )
                return None, msg
        if gap is not None:
            return None, "GROUNDED status requires gap to be null"
    elif status == "PARTIAL":
        if not gap:
            return None, "PARTIAL status requires non-empty gap"
    elif status == "UNGROUNDED":
        if answer is not None:
            return None, "UNGROUNDED status requires answer to be null"
        if insights:
            return None, "UNGROUNDED status requires empty insights"
        if evidence_refs:
            return None, "UNGROUNDED status requires empty evidence_refs"
        if not gap:
            return None, "UNGROUNDED status requires non-empty gap"

    return parsed, None


def build_degraded_result(status: str, gap: str, provenance: dict) -> dict:
    """Build a deterministic degraded ``m35.agent_bridge_query.v0`` envelope.

    Never returns GROUNDED status.  Suitable for cases where model output
    is unrecoverable or validation fails.
    """
    if status not in ("PARTIAL", "UNGROUNDED"):
        status = "UNGROUNDED"

    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "status": status,
        "answer": (
            None if status == "UNGROUNDED" else "Degraded: model output could not be validated."
        ),
        "insights": [],
        "evidence_refs": [],
        "gap": gap,
        "provenance": provenance,
        "usage": None,
    }


def build_provenance(
    cfg: BrainConfig, conn_meta: dict | None = None, degraded: bool = False
) -> dict:
    """Build a provenance dict for the ACP query envelope.

    Extracts model and runtime info from *conn_meta* when available
    (e.g. from ``session/new`` result or ``initialize`` server info).
    Falls back to ``cfg.model`` or ``"unknown"``.
    """
    model = "unknown"
    runtime = "acp"

    if conn_meta:
        session_new_result = conn_meta.get("session_new_result") or {}
        if isinstance(session_new_result, dict):
            model = session_new_result.get("model") or model

        initialize_result = conn_meta.get("initialize_result") or {}
        if isinstance(initialize_result, dict):
            server_info = initialize_result.get("serverInfo") or {}
            if isinstance(server_info, dict):
                runtime = server_info.get("name") or runtime
            if runtime == "acp":
                agent_info = initialize_result.get("agentInfo") or {}
                if isinstance(agent_info, dict):
                    runtime = agent_info.get("name") or runtime

    if model == "unknown" and cfg.model:
        model = cfg.model

    return {
        "transport": "acp",
        "model": model,
        "runtime": runtime,
        "degraded": degraded,
    }


def _finalize_validated_envelope(
    validated: dict,
    *,
    id_mapping: dict[str, str],
    cfg: BrainConfig,
    conn_meta: dict,
    rpc_usage: dict | None,
    turn_messages: list[dict],
) -> tuple[dict | None, str | None]:
    """Run the deterministic citation gate and attach authoritative metadata."""
    trace_refs = extract_tool_trace_journal_refs(turn_messages)
    citation = validate_citation_gate(
        validated,
        short_id_mapping=id_mapping,
        tool_trace_refs=trace_refs,
        apply_mapping=True,
    )
    if not citation.ok:
        return None, citation.error or "Citation validation failed"

    provenance = build_provenance(cfg, conn_meta, degraded=False)
    provenance["citation_trace_checked"] = citation.trace_checked
    if citation.trace_checked:
        provenance["citation_trace_refs"] = trace_refs

    validated["provenance"] = provenance
    validated["usage"] = rpc_usage
    validated.setdefault("schema_version", QUERY_SCHEMA_VERSION)
    return validated, None


def _is_queued_placeholder(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return bool(normalized) and "queued for the next turn" in normalized


def _supports_stream_progress(conn: _ACPConnection) -> bool:
    try:
        return "stream_progress" in inspect.signature(conn.rpc).parameters
    except (TypeError, ValueError):
        return False


def _send_prompt_turn(
    conn: _ACPConnection,
    prompt_text: str,
    *,
    stream_callback: Callable[[Any], None] | None = None,
) -> tuple[dict, list[dict]]:
    """Send one ``session/prompt`` turn with one bounded retry on RPC failure.

    The retry is intentionally scoped to prompt RPCs, not handshake/startup.
    If a failed attempt emitted partial chunks before raising, those chunks are
    ignored by returning only the successful attempt's newly collected messages.
    """
    last_exc: Exception | None = None
    for _attempt in range(_PROMPT_RPC_RETRY_MAX + 1):
        start_len = len(conn.collected)
        try:
            resp = conn.rpc(
                "session/prompt",
                {
                    "sessionId": conn.session_id,
                    "prompt": [{"type": "text", "text": prompt_text}],
                },
                stream_callback=stream_callback,
                **({"stream_progress": True} if _supports_stream_progress(conn) else {}),
            )
            return resp, conn.collected[start_len:]
        except Exception as exc:
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("ACP session/prompt failed without an exception")


def acp_query_adapter(
    query: str,
    scaffold: dict,
    cfg: BrainConfig,
    *,
    connection: _ACPConnection | None = None,
    stream_callback: Callable[[Any], None] | None = None,
) -> dict:
    """Route an ACP transport query through ``session/prompt`` and return a validated
    ``m35.agent_bridge_query.v0`` envelope.

    Algorithm:
    1. Build evidence pack and allowed ID set from the scaffold.
    2. Build an agentic prompt that treats scaffold evidence as a seed hint.
    3. Create or reuse an ``_ACPConnection``, send ``session/prompt``, collect text.
    4. Parse and validate the collected text.
    5. On success: map short evidence IDs back to real IDs and return the envelope.
    6. On first failure: one bounded retry with a repair prompt.
    7. On second failure: return a deterministic degraded result.
    """
    # 1. Build evidence pack
    evidence_pack, id_mapping = build_evidence_pack(scaffold)
    allowed_ids = frozenset(id_mapping.keys())

    # 2. Build prompt
    prompt = build_query_prompt(query, evidence_pack, set(allowed_ids))

    # 3. Create or reuse ACP connection
    own_conn = connection is None
    conn = connection

    conn_meta: dict = {}
    collected_text: str = ""

    try:
        if conn is None:
            conn = _ACPConnection(cfg)
            conn.__enter__()

        # Extract best available metadata from matched handshake responses.
        conn_meta["session_id"] = getattr(conn, "session_id", "")
        conn_meta["initialize_result"] = getattr(conn, "initialize_result", None)
        conn_meta["session_new_result"] = getattr(conn, "session_new_result", None)

        # 4. Send session/prompt and capture the authoritative RPC response.
        #    Incremental agent_message_chunk updates are forwarded through
        #    stream_callback inside rpc() as they arrive.
        prompt_resp, turn_messages = _send_prompt_turn(
            conn,
            prompt,
            stream_callback=stream_callback,
        )
        rpc_usage = _extract_rpc_usage(prompt_resp)

        # 5. Collect text via parse_acp_stream from only new chunks
        collected_text = parse_acp_stream(turn_messages)

        # 6. Parse and validate
        validated, error = parse_and_validate(collected_text, allowed_ids)

        if validated is not None:
            finalized, citation_error = _finalize_validated_envelope(
                validated,
                id_mapping=id_mapping,
                cfg=cfg,
                conn_meta=conn_meta,
                rpc_usage=rpc_usage,
                turn_messages=turn_messages,
            )
            if finalized is not None:
                return finalized
            error = citation_error

        if _is_queued_placeholder(collected_text):
            return build_degraded_result(
                "UNGROUNDED",
                "ACP runtime queued the prompt instead of returning a final answer.",
                build_provenance(cfg, conn_meta, degraded=True),
            )

        # 7. First failure — bounded retry with repair prompt
        repair_prompt = (
            "Your previous response failed validation with the following error:\n"
            f"  {error}\n\n"
            "Please respond with ONLY the JSON object conforming to schema "
            "m35.agent_bridge_query.v0.  Do NOT include any markdown fences, "
            "explanations, or prose outside the JSON object. Do NOT create, edit, "
            "patch, or write any files; return the JSON directly in this ACP "
            "message. You may cite seed "
            f"IDs from: {', '.join(sorted(allowed_ids)) if allowed_ids else '(none)'}, "
            "and you may cite additional journal evidence as "
            "Journals/YYYY/MM/life-index_YYYY-MM-DD_NNN.md if you read or searched it "
            "during this ACP turn. Use the magazine model: answer is a concise "
            "summary, and every substantive insight has quote, interpretation, "
            "and evidence_refs. The summary may be connective prose without inline "
            "ids, but it must not introduce dates, counts, locations, events, or "
            "conclusions not covered by cited insights. The top-level evidence_refs "
            "MUST exactly equal the union of all insights[].evidence_refs; do not "
            "list every document you found or classified. Do not use non-file "
            "citation phrases like [all March entries]. Avoid raw double quotes "
            "inside JSON strings; use Chinese corner quotes instead.\n\n"
            "Output:"
        )

        prompt_resp_retry, retry_messages = _send_prompt_turn(
            conn,
            repair_prompt,
            stream_callback=stream_callback,
        )
        rpc_usage_retry = _extract_rpc_usage(prompt_resp_retry)

        collected_text_retry = parse_acp_stream(retry_messages)

        validated_retry, error_retry = parse_and_validate(collected_text_retry, allowed_ids)

        if validated_retry is not None:
            finalized_retry, citation_error_retry = _finalize_validated_envelope(
                validated_retry,
                id_mapping=id_mapping,
                cfg=cfg,
                conn_meta=conn_meta,
                rpc_usage=rpc_usage_retry,
                turn_messages=turn_messages + retry_messages,
            )
            if finalized_retry is not None:
                return finalized_retry
            error_retry = citation_error_retry

        # 8. Both attempts failed — degrade
        return build_degraded_result(
            "UNGROUNDED",
            f"Model output failed validation after retry: {error_retry}",
            build_provenance(cfg, conn_meta, degraded=True),
        )

    except Exception as exc:
        # Transport-level failure — degrade deterministically
        safe_error = _safe_exception_summary(exc)
        return build_degraded_result(
            "UNGROUNDED",
            f"ACP query adapter failed for query: {query} ({safe_error})",
            build_provenance(cfg, conn_meta, degraded=True),
        )

    finally:
        if own_conn and conn is not None:
            try:
                conn.__exit__(None, None, None)
            except Exception:
                pass
