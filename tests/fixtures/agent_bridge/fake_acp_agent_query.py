"""Fake ACP agent that responds to session/prompt with configurable output.

Used for testing the ACP query adapter (acp_query_adapter) and its
parse_and_validate pipeline.  The agent inspects the prompt text to
determine which output variant to emit.

Detected prompt markers:
  - VALID_JSON_TEST       → valid m35.agent_bridge_query.v0 GROUNDED JSON
  - FENCED_JSON_TEST      → valid JSON wrapped in ```json ... ``` fence
  - MIXED_PROSE_TEST      → mixed prose with multiple JSON objects
  - UNKNOWN_EVIDENCE_TEST → valid JSON but with fabricated evidence IDs
  - UNGROUNDED_TEST       → valid UNGROUNDED response
  - INVALID_JSON_TEST     → completely invalid text (not JSON at all)
  - TWO_TURN_TEST         → first emit invalid, second emit valid GROUNDED
  - USAGE_TEST            → model JSON has invented usage; RPC result has real usage
  - INVALID_USAGE_TEST    → model JSON usage is not a dict; RPC result has real usage
  - NO_RPC_USAGE_TEST     → model JSON has usage; RPC result omits usage

Default: valid GROUNDED response referencing E1.
"""

from __future__ import annotations

import json
import sys

AUTH_METHODS = [{"id": "api-key", "name": "API Key"}]
SESSION_ID = "test-session-abc123"
RPC_USAGE = {"input_tokens": 7, "output_tokens": 13}


def _extract_prompt_text(params: dict) -> str:
    """Extract the full prompt text from params."""
    prompt_list = params.get("prompt", [])
    parts: list[str] = []
    for item in prompt_list:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "".join(parts)


def _emit_chunk(text: str) -> None:
    """Emit one agent_message_chunk update with the given text."""
    update = {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": SESSION_ID,
            "update": {
                "content": {"text": text, "type": "text"},
                "sessionUpdate": "agent_message_chunk",
            },
        },
    }
    sys.stdout.write(json.dumps(update, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _emit_read_trace(*refs: str) -> None:
    """Emit a fake tool/read trace update for cited journal refs."""
    update = {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": SESSION_ID,
            "update": {
                "sessionUpdate": "tool_call_update",
                "content": "read " + " ".join(refs),
            },
        },
    }
    sys.stdout.write(json.dumps(update, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _prompt_response(req_id, usage=None):
    """Build a session/prompt JSON-RPC response with optional usage metadata."""
    result: dict = {"status": "ok"}
    if usage is not None:
        result["usage"] = usage
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _valid_grounded_json() -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": "This is a valid grounded answer referencing supplied evidence [E1].",
            "insights": [
                {"text": "Key finding from evidence", "evidence_refs": ["E1"]},
                {"text": "Supporting observation", "evidence_refs": ["E1", "E2"]},
            ],
            "evidence_refs": ["E1", "E2"],
            "gap": None,
            "provenance": {
                "transport": "acp",
                "model": "fake-model",
                "runtime": "fake-acp",
                "degraded": False,
            },
            "usage": {"input_tokens": 100, "output_tokens": 50},
        },
        ensure_ascii=False,
    )


def _valid_ungrounded_json() -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "UNGROUNDED",
            "answer": None,
            "insights": [],
            "evidence_refs": [],
            "gap": "No relevant evidence found in the supplied entries.",
            "provenance": {
                "transport": "acp",
                "model": "fake-model",
                "runtime": "fake-acp",
                "degraded": False,
            },
            "usage": {"input_tokens": 90, "output_tokens": 40},
        },
        ensure_ascii=False,
    )


def _unknown_evidence_json() -> str:
    return json.dumps(
        {
            "schema_version": "m35.agent_bridge_query.v0",
            "status": "GROUNDED",
            "answer": "Answer citing fabricated evidence.",
            "insights": [
                {"text": "Made-up insight", "evidence_refs": ["Z99"]},
            ],
            "evidence_refs": ["Z99"],
            "gap": None,
            "provenance": {
                "transport": "acp",
                "model": "fake-model",
                "runtime": "fake-acp",
                "degraded": False,
            },
            "usage": {"input_tokens": 80, "output_tokens": 30},
        },
        ensure_ascii=False,
    )


def _fenced_json() -> str:
    return "```json\n" + _valid_grounded_json() + "\n```"


def _custom_usage_json(usage_value) -> str:
    """Return a valid GROUNDED envelope with a custom ``usage`` value."""
    payload = {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "GROUNDED",
        "answer": "Grounded answer with custom usage field [E1].",
        "insights": [
            {"text": "Key finding from evidence", "evidence_refs": ["E1"]},
        ],
        "evidence_refs": ["E1"],
        "gap": None,
        "provenance": {
            "transport": "acp",
            "model": "fake-model",
            "runtime": "fake-acp",
            "degraded": False,
        },
        "usage": usage_value,
    }
    return json.dumps(payload, ensure_ascii=False)


def _mixed_prose() -> str:
    return (
        "Let me help you with that query.\n\n"
        + _valid_grounded_json()
        + "\n\nI hope that answers your question. Here's another thought:\n\n"
        + '{"some": "other json"}'
    )


def main() -> None:
    prompt_count = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": 1,
                    "serverInfo": {"name": "fake-acp", "version": "0.1.0"},
                    "authMethods": AUTH_METHODS,
                    "capabilities": {},
                },
            }
        elif method == "authenticate":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "ok"},
            }
        elif method == "session/new":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "sessionId": SESSION_ID,
                    "cwd": params.get("cwd", "/tmp"),
                    "model": "fake-model",
                },
            }
        elif method == "session/prompt":
            prompt_text = _extract_prompt_text(params)
            prompt_count += 1

            # Determine RPC usage for this response.  Most scenarios include
            # authoritative usage metadata; NO_RPC_USAGE_TEST deliberately omits it.
            rpc_usage = None if "NO_RPC_USAGE_TEST" in prompt_text else RPC_USAGE

            # TWO_TURN_TEST: first turn emits invalid, second emits valid
            if "TWO_TURN_TEST" in prompt_text:
                if prompt_count == 1:
                    _emit_chunk("not valid json at all")
                else:
                    _emit_read_trace(
                        "Journals/2026/06/life-index_2026-06-10_001.md",
                        "Journals/2026/06/life-index_2026-06-11_001.md",
                    )
                    _emit_chunk(_valid_grounded_json())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "VALID_JSON_TEST" in prompt_text:
                _emit_read_trace(
                    "Journals/2026/06/life-index_2026-06-10_001.md",
                    "Journals/2026/06/life-index_2026-06-11_001.md",
                )
                _emit_chunk(_valid_grounded_json())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "FENCED_JSON_TEST" in prompt_text:
                _emit_read_trace(
                    "Journals/2026/06/life-index_2026-06-10_001.md",
                    "Journals/2026/06/life-index_2026-06-11_001.md",
                )
                _emit_chunk(_fenced_json())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "MIXED_PROSE_TEST" in prompt_text:
                _emit_chunk(_mixed_prose())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "UNKNOWN_EVIDENCE_TEST" in prompt_text:
                _emit_chunk(_unknown_evidence_json())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "UNGROUNDED_TEST" in prompt_text:
                _emit_chunk(_valid_ungrounded_json())
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "INVALID_JSON_TEST" in prompt_text:
                _emit_chunk("This is just some random text, not JSON at all.")
                resp = _prompt_response(req_id, usage=rpc_usage)

            elif "NO_RPC_USAGE_TEST" in prompt_text:
                # Model JSON has usage, but RPC omits it → final usage must be None.
                # Check this before USAGE_TEST because the marker is a superstring.
                _emit_read_trace("Journals/2026/06/life-index_2026-06-10_001.md")
                _emit_chunk(_custom_usage_json({"input_tokens": 100, "output_tokens": 50}))
                resp = _prompt_response(req_id, usage=None)

            elif "USAGE_TEST" in prompt_text:
                # Model JSON invents usage; RPC result is authoritative.
                _emit_read_trace("Journals/2026/06/life-index_2026-06-10_001.md")
                _emit_chunk(_custom_usage_json({"input_tokens": 9999, "output_tokens": 9999}))
                resp = _prompt_response(req_id, usage=RPC_USAGE)

            elif "INVALID_USAGE_TEST" in prompt_text:
                # Model JSON provides malformed usage; RPC result saves it.
                _emit_read_trace("Journals/2026/06/life-index_2026-06-10_001.md")
                _emit_chunk(_custom_usage_json("not a dict"))
                resp = _prompt_response(req_id, usage=RPC_USAGE)

            else:
                # Default: valid GROUNDED referencing E1
                _emit_read_trace("Journals/2026/06/life-index_2026-06-10_001.md")
                simple = json.dumps(
                    {
                        "schema_version": "m35.agent_bridge_query.v0",
                        "status": "GROUNDED",
                        "answer": "Default grounded answer referencing E1 [E1].",
                        "insights": [
                            {"text": "Default insight", "evidence_refs": ["E1"]},
                        ],
                        "evidence_refs": ["E1"],
                        "gap": None,
                        "provenance": {
                            "transport": "acp",
                            "model": "fake-model",
                            "runtime": "fake-acp",
                            "degraded": False,
                        },
                        "usage": {"input_tokens": 50, "output_tokens": 30},
                    },
                    ensure_ascii=False,
                )
                _emit_chunk(simple)
                resp = _prompt_response(req_id, usage=rpc_usage)
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }

        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
