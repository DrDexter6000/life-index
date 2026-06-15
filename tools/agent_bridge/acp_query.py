from __future__ import annotations

import json
import re
from typing import Any, Callable

from tools.agent_bridge.acp_client import _ACPConnection, parse_acp_stream
from tools.agent_bridge.config import BrainConfig

QUERY_SCHEMA_VERSION = "m35.agent_bridge_query.v0"

# ─── Constants ────────────────────────────────────────────────────────
_MAX_EVIDENCE_ENTRIES = 10
_REPAIR_RETRY_MAX = 1
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
# Trailing comma immediately before a closing ``}`` or ``]`` — a common
# weak-model "light schema-shape drift". Used only as a bounded, generic
# syntax repair inside ``_try_loads``; it never relaxes schema / status /
# evidence-ID validation, which all run unchanged on the parsed result.
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


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
    """Build a strict prompt that instructs the model to answer ONLY from supplied evidence.

    The prompt requires output as ``m35.agent_bridge_query.v0`` JSON and
    defines exact status rules (GROUNDED / PARTIAL / UNGROUNDED).
    """
    allowed_str = ", ".join(sorted(allowed_ids)) if allowed_ids else "(none)"
    evidence_lines: list[str] = []
    for sid in sorted(evidence_pack, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0):
        entry = evidence_pack[sid]
        evidence_lines.append(f"  {sid}: {entry['text']}")

    evidence_block = "\n".join(evidence_lines) if evidence_lines else "  (no evidence supplied)"

    return f"""You are an evidence-bound research assistant. Your task is to answer the
following question using ONLY the evidence supplied below.

QUESTION:
{query}

EVIDENCE PACK (only these entries may be cited):
{evidence_block}

ALLOWED EVIDENCE IDs: {allowed_str}

IMPORTANT — EVIDENCE IS ALREADY PROVIDED ABOVE. The full text of every
evidence entry is printed in the EVIDENCE PACK. You do NOT need to look
anywhere else, and you must NOT claim that you lack access to the evidence.
Each entry above that shows text IS a real, non-empty evidence entry. Even
if an entry looks short, it still has content. You MUST NOT answer that an
entry "has no content", "is empty", "could not be read", or "was not
provided" when text is shown for it above. Your answer status (GROUNDED /
PARTIAL / UNGROUNDED) MUST be decided by reading the text already printed
in the EVIDENCE PACK — not by assuming evidence is missing.

INSTRUCTIONS:
1. Answer ONLY from the supplied evidence. Do NOT fabricate, infer, or use
   external knowledge.
2. Every claim in your answer MUST be traceable to at least one supplied
   evidence entry.
3. Cite evidence using ONLY the short IDs (E1, E2, etc.) from the ALLOWED
   set above.
4. If the evidence is insufficient for a complete answer, mark status as
   PARTIAL or UNGROUNDED.
5. Before choosing UNGROUNDED, re-read the EVIDENCE PACK above. If any
   entry with a non-empty text is relevant to the question, you MUST use it
   and mark the answer GROUNDED or PARTIAL instead. Only mark UNGROUNDED
   when every supplied entry's text genuinely fails to address the question.

OUTPUT FORMAT — Respond with exactly ONE JSON object conforming to schema
m35.agent_bridge_query.v0:

{{
  "schema_version": "m35.agent_bridge_query.v0",
  "status": "GROUNDED",
  "answer": "string or null",
  "insights": [
    {{"text": "insight text", "evidence_refs": ["E1"]}}
  ],
  "evidence_refs": ["E1", "E2"],
  "gap": null,
  "provenance": {{
    "transport": "acp", "model": "unknown", "runtime": "acp", "degraded": false
  }},
  "usage": null
}}

NOTE: Do not invent a ``usage`` object. The adapter sets usage from the
ACP RPC response; any model-generated value will be ignored."

STATUS RULES (enforced by validator):
- GROUNDED: answer is non-empty; insights is non-empty with at least one
  evidence_ref each; all refs are from the allowed set; gap is null.
- PARTIAL: answer is present (may be partial); gap is non-empty; refs may
  be incomplete.
- UNGROUNDED: answer is null; insights is empty; evidence_refs is empty;
  gap is non-empty explaining why.

WARNING: Using any evidence ID not in the ALLOWED set will cause your
entire response to be rejected. Only use IDs from: {allowed_str}"""


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

    # Validate insight entries
    for i, ins in enumerate(insights):
        if not isinstance(ins, dict):
            return None, f"insights[{i}] must be a dict"
        if not isinstance(ins.get("text"), str):
            return None, f"insights[{i}].text must be a string"
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

    unknown_ids = all_refs - allowed_ids
    if unknown_ids:
        ids_str = ", ".join(sorted(unknown_ids))
        return None, f"Unknown evidence IDs in response: {ids_str}. Allowed: {sorted(allowed_ids)}"

    # ── Status rule validation ──────────────────────────────────────
    if status == "GROUNDED":
        if not answer:
            return None, "GROUNDED status requires non-empty answer"
        if not insights:
            return None, "GROUNDED status requires non-empty insights"
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


def acp_query_adapter(
    query: str,
    scaffold: dict,
    cfg: BrainConfig,
    *,
    connection: _ACPConnection | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> dict:
    """Route an ACP transport query through ``session/prompt`` and return a validated
    ``m35.agent_bridge_query.v0`` envelope.

    Algorithm:
    1. Build evidence pack and allowed ID set from the scaffold.
    2. Build a strict prompt instructing the model to answer from evidence only.
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

        # Snapshot collected length before this query so we only parse chunks
        # produced for the current prompt (prevents warm-connection contamination).
        pre_prompt_len = len(conn.collected)

        # 4. Send session/prompt and capture the authoritative RPC response.
        #    Incremental agent_message_chunk updates are forwarded through
        #    stream_callback inside rpc() as they arrive.
        prompt_resp = conn.rpc(
            "session/prompt",
            {
                "sessionId": conn.session_id,
                "prompt": [{"type": "text", "text": prompt}],
            },
            stream_callback=stream_callback,
        )
        rpc_usage = _extract_rpc_usage(prompt_resp)

        # 5. Collect text via parse_acp_stream from only new chunks
        collected_text = parse_acp_stream(conn.collected[pre_prompt_len:])

        # 6. Parse and validate
        validated, error = parse_and_validate(collected_text, allowed_ids)

        if validated is not None:
            # Success — map short IDs back to real IDs
            evidence_refs = validated.get("evidence_refs", [])
            mapped_refs = [id_mapping.get(r, r) for r in evidence_refs]
            validated["evidence_refs"] = mapped_refs

            for ins in validated.get("insights", []):
                if isinstance(ins, dict):
                    refs = ins.get("evidence_refs", [])
                    if isinstance(refs, list):
                        ins["evidence_refs"] = [id_mapping.get(r, r) for r in refs]

            validated["provenance"] = build_provenance(cfg, conn_meta, degraded=False)
            validated["usage"] = rpc_usage
            validated.setdefault("schema_version", QUERY_SCHEMA_VERSION)
            return validated

        # 7. First failure — bounded retry with repair prompt
        # Snapshot collected messages: only parse new messages from the retry
        # to avoid concatenating the original (failed) output with the retry.
        pre_retry_len = len(conn.collected)

        repair_prompt = (
            "Your previous response failed validation with the following error:\n"
            f"  {error}\n\n"
            "Please respond with ONLY the JSON object conforming to schema "
            "m35.agent_bridge_query.v0.  Do NOT include any markdown fences, "
            "explanations, or prose outside the JSON object.  Use only evidence "
            f"IDs from: {', '.join(sorted(allowed_ids)) if allowed_ids else '(none)'}.\n\n"
            "Output:"
        )

        prompt_resp_retry = conn.rpc(
            "session/prompt",
            {
                "sessionId": conn.session_id,
                "prompt": [{"type": "text", "text": repair_prompt}],
            },
            stream_callback=stream_callback,
        )
        rpc_usage_retry = _extract_rpc_usage(prompt_resp_retry)

        collected_text_retry = parse_acp_stream(conn.collected[pre_retry_len:])

        validated_retry, error_retry = parse_and_validate(collected_text_retry, allowed_ids)

        if validated_retry is not None:
            evidence_refs_retry = validated_retry.get("evidence_refs", [])
            mapped_refs_retry = [id_mapping.get(r, r) for r in evidence_refs_retry]
            validated_retry["evidence_refs"] = mapped_refs_retry

            for ins in validated_retry.get("insights", []):
                if isinstance(ins, dict):
                    refs = ins.get("evidence_refs", [])
                    if isinstance(refs, list):
                        ins["evidence_refs"] = [id_mapping.get(r, r) for r in refs]

            validated_retry["provenance"] = build_provenance(cfg, conn_meta, degraded=False)
            validated_retry["usage"] = rpc_usage_retry
            validated_retry.setdefault("schema_version", QUERY_SCHEMA_VERSION)
            return validated_retry

        # 8. Both attempts failed — degrade
        return build_degraded_result(
            "UNGROUNDED",
            f"Model output failed validation after retry: {error_retry}",
            build_provenance(cfg, conn_meta, degraded=True),
        )

    except Exception:
        # Transport-level failure — degrade deterministically
        return build_degraded_result(
            "UNGROUNDED",
            f"ACP query adapter failed for query: {query}",
            build_provenance(cfg, conn_meta, degraded=True),
        )

    finally:
        if own_conn and conn is not None:
            try:
                conn.__exit__(None, None, None)
            except Exception:
                pass
