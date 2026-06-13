"""Localhost-only HTTP service for the V5b warm ACP session manager.

V5b-2 host integration.  Wraps ``ACPWarmSessionManager`` in a stdlib
``ThreadingHTTPServer`` bound to loopback only.  Exposes:

  GET  /healthz          non-blocking health snapshot
  POST /query            JSON query or SSE streaming query
  POST /shutdown         graceful shutdown

The service pre-warms the ACP manager on startup but keeps running if
warm-up fails, reporting a degraded state via ``/healthz``.
"""

from __future__ import annotations

import argparse
import json
import queue
import signal
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from tools.agent_bridge.acp_query import build_degraded_result, build_provenance
from tools.agent_bridge.acp_session_manager import ACPWarmSessionManager
from tools.agent_bridge.config import BrainConfig, resolve_brain_config

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8787
_SSE_TIMEOUT = 300.0


class ACPThreadingServer(ThreadingHTTPServer):
    """ThreadingHTTPServer variant with daemon request threads.

    Daemon threads let the interpreter exit even if a request handler is
    still running, which is important for clean test shutdown and for the
    ``/shutdown`` endpoint.  ``server_close()`` is invoked after
    ``shutdown()`` to release the listening socket promptly.
    """

    daemon_threads = True

    def shutdown_and_close(self) -> None:
        """Stop the serve loop and close the listening socket."""
        self.shutdown()
        self.server_close()


def _schedule_async_shutdown(
    manager: ACPWarmSessionManager,
    server: ACPThreadingServer,
) -> None:
    """Close *manager* then shut down *server* from a daemon thread.

    ``HTTPServer.shutdown()`` must never be called from the same thread that
    is running ``serve_forever()``; doing so deadlocks because ``shutdown()``
    waits for the serve loop to notice the shutdown request, which cannot
    happen while the serve loop is blocked in the signal handler.  This
    helper offloads the entire teardown sequence to a background thread so
    both the ``/shutdown`` endpoint and SIGTERM/SIGINT handlers return
    immediately.
    """

    def _run() -> None:
        try:
            manager.close()
        finally:
            server.shutdown_and_close()

    threading.Thread(target=_run, daemon=True).start()


def _make_signal_handler(
    manager: ACPWarmSessionManager,
    server: ACPThreadingServer,
) -> Callable[[int, Any], None]:
    """Return a signal handler that schedules async shutdown."""

    def _on_signal(signum: int, frame: Any) -> None:
        _schedule_async_shutdown(manager, server)

    return _on_signal


def is_loopback(host: str) -> bool:
    """Return True if *host* resolves only to loopback addresses.

    Rejects ``0.0.0.0``, empty hostnames, and any address outside the
    IPv4 loopback range (127.0.0.0/8) or IPv6 loopback (::1).
    """
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False

    for info in infos:
        addr = str(info[4][0])
        if addr.startswith("::ffff:"):
            addr = addr.split("::ffff:", 1)[1]
        if addr == "127.0.0.1" or addr.startswith("127.") or addr == "::1":
            continue
        return False
    return True


class ACPServiceHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the warm ACP service."""

    manager: ACPWarmSessionManager
    server_instance: ACPThreadingServer

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging to keep output quiet."""
        pass

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return None
        raw = self.rfile.read(content_length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json(200, self.manager.health())
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/shutdown":
            # Offload manager close + server shutdown to a background thread
            # so the HTTP response can be flushed before the socket is closed
            # and so this handler never blocks on shutdown().
            _schedule_async_shutdown(self.manager, self.server_instance)
            self._send_json(200, {"status": "shutting down"})
            return

        if parsed.path != "/query":
            self._send_json(404, {"error": "not found"})
            return

        payload = self._read_json_body()
        if payload is None:
            self._send_json(400, {"error": "invalid json body"})
            return

        query = payload.get("query")
        scaffold = payload.get("scaffold", {})
        if not isinstance(query, str) or not query:
            self._send_json(400, {"error": "query must be a non-empty string"})
            return
        if not isinstance(scaffold, dict):
            self._send_json(400, {"error": "scaffold must be an object"})
            return

        accept = self.headers.get("Accept", "")
        use_sse = "text/event-stream" in accept

        if not use_sse:
            result = self.manager.query(query, scaffold)
            self._send_json(200, result)
            return

        self._handle_sse_query(query, scaffold)

    def _handle_sse_query(self, query: str, scaffold: dict[str, Any]) -> None:
        """Stream query results as server-sent events.

        Runs the manager query in a worker thread so that incremental
        ``agent_message_chunk`` updates can be emitted as ``event: chunk``
        frames before the final ``event: result`` envelope.
        """
        sse_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        def enqueue(chunk: str) -> None:
            sse_queue.put(("chunk", chunk))

        def run_query() -> None:
            try:
                result = self.manager.query(query, scaffold, stream_callback=enqueue)
                sse_queue.put(("result", result))
            except Exception as exc:
                cfg: BrainConfig = self.manager._cfg
                provenance = build_provenance(cfg, conn_meta=None, degraded=True)
                degraded = build_degraded_result(
                    "UNGROUNDED", f"SSE query failed: {exc}", provenance
                )
                sse_queue.put(("result", degraded))

        worker = threading.Thread(target=run_query, daemon=True)
        worker.start()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            while True:
                try:
                    kind, data = sse_queue.get(timeout=_SSE_TIMEOUT)
                except queue.Empty:
                    break
                if kind == "chunk":
                    try:
                        self._write_sse_event("chunk", data)
                    except (OSError, ValueError):
                        break
                    continue
                if kind == "result":
                    try:
                        self._write_sse_event("result", data)
                    except (OSError, ValueError):
                        break
                    break
        finally:
            # Ensure the worker does not hold the manager lock forever
            # if the client disappeared mid-stream.
            worker.join(timeout=10.0)
            # Close the HTTP connection so the client sees EOF after the
            # final event instead of waiting on a keep-alive socket.
            self.close_connection = True

    def _write_sse_event(self, event: str, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()


def _build_server(
    host: str,
    port: int,
    cfg: BrainConfig,
    *,
    connection_factory: Any = None,
    adapter: Any = None,
) -> tuple[ACPThreadingServer, ACPWarmSessionManager]:
    """Create a warm ACP service bound to *host*:*port*.

    The optional *connection_factory* and *adapter* arguments are forwarded to
    ``ACPWarmSessionManager`` so tests can inject fakes without monkeypatching
    the class itself.
    """
    manager_kwargs: dict[str, Any] = {}
    if connection_factory is not None:
        manager_kwargs["connection_factory"] = connection_factory
    if adapter is not None:
        manager_kwargs["adapter"] = adapter
    manager = ACPWarmSessionManager(cfg, **manager_kwargs)
    manager.start()

    ACPServiceHandler.manager = manager
    server = ACPThreadingServer((host, port), ACPServiceHandler)
    ACPServiceHandler.server_instance = server
    return server, manager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.agent_bridge.service",
        description="Localhost-only HTTP service for the warm ACP manager.",
    )
    parser.add_argument(
        "--host",
        default=_DEFAULT_HOST,
        help=f"Bind host (loopback only). Default: {_DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_DEFAULT_PORT,
        help=f"Bind port. Default: {_DEFAULT_PORT}",
    )
    args = parser.parse_args(argv)

    if not is_loopback(args.host):
        print(
            f"error: refusing to bind to non-loopback host {args.host!r}",
            file=sys.stderr,
        )
        return 1

    cfg = resolve_brain_config()
    server, manager = _build_server(args.host, args.port, cfg)

    signal.signal(signal.SIGTERM, _make_signal_handler(manager, server))
    signal.signal(signal.SIGINT, _make_signal_handler(manager, server))

    bind_host, bind_port = server.server_address[:2]
    display_host = bind_host.decode("utf-8") if isinstance(bind_host, bytes) else bind_host
    print(f"ACP warm service listening on http://{display_host}:{bind_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
