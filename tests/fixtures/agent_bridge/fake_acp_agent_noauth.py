"""Fake ACP agent with no auth methods advertised — for authenticate-skip testing.

Replies to initialize with an empty authMethods list, causing the handshake
to skip the authenticate step (handshake_steps["authenticate"] = "skip").
Also responds to session/new normally (but does NOT respond to session/prompt).
"""

import json
import sys

SESSION_ID = "test-session-noauth"


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
                    "serverInfo": {"name": "fake-acp-noauth", "version": "0.1.0"},
                    "authMethods": [],  # No auth methods — triggers authenticate: "skip"
                    "capabilities": {},
                },
            }
        elif method == "authenticate":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"status": "ok"}}
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
            continue  # Don't respond — probe never sends this
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
