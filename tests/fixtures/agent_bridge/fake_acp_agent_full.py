"""Fake ACP agent that responds to ALL methods including session/prompt.

Used for tests that call acp_synthesize (which sends session/prompt).
Unlike fake_acp_agent.py which hangs on session/prompt to verify probe
never sends it, this variant responds to everything.
"""

import json
import sys

AUTH_METHODS = [{"id": "api-key", "name": "API Key"}]
SESSION_ID = "test-session-abc123"


def main():
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
                },
            }
        elif method == "session/prompt":
            # Respond — unlike fake_acp_agent.py which hangs
            # Emit a session/update notification first, then respond
            update = {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": SESSION_ID,
                    "update": {
                        "content": {"text": "HELLO_FROM_FAKE_ACP", "type": "text"},
                        "sessionUpdate": "agent_message_chunk",
                    },
                },
            }
            sys.stdout.write(json.dumps(update, ensure_ascii=False) + "\n")
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "ok"},
            }
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
