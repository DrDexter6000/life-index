"""Fake ACP agent with slow-but-valid handshake responses.

Each handshake RPC responds before a per-RPC timeout can fire, but the
cumulative initialize -> authenticate -> session/new flow exceeds a short
overall handshake deadline. This catches implementations that enforce only
per-RPC timeouts.
"""

import json
import sys
import time

AUTH_METHODS = [{"id": "api-key", "name": "API Key"}]
SESSION_ID = "slow-session-abc123"
SLEEP_SECONDS = 0.35


def _write_response(response):
    time.sleep(SLEEP_SECONDS)
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


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
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": 1,
                        "serverInfo": {"name": "slow-acp", "version": "0.1.0"},
                        "authMethods": AUTH_METHODS,
                        "capabilities": {},
                    },
                }
            )
        elif method == "authenticate":
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"status": "ok"},
                }
            )
        elif method == "session/new":
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "sessionId": SESSION_ID,
                        "cwd": params.get("cwd", "/tmp"),
                    },
                }
            )
        else:
            _write_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    main()
