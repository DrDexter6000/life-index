"""Fake ACP agent for unit testing _ACPConnection handshake.

Reads JSON-RPC from stdin, responds to initialize/authenticate/session/new.
Does NOT respond to session/prompt (hangs until stdin closed), which lets
tests verify that _ACPConnection handshake completes and acp_synthesize
sends the prompt separately.
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
            # Don't respond — let caller close stdin to trigger EOF
            # This ensures tests can verify that probe never sends session/prompt
            continue
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
