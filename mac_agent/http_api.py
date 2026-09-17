"""Authenticated HTTP API used by Meta Muse to control the Mac Connector."""
from __future__ import annotations

import hmac
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .actions import execute
from .capabilities import capability_index

MAX_BODY_BYTES = 512 * 1024
MAX_RESULTS = 200


class _State:
    def __init__(self, cfg):
        self.cfg = cfg
        self.results: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.paused_file = Path(cfg["base_dir"]) / "PAUSED"


class Handler(BaseHTTPRequestHandler):
    state: _State = None

    def _auth(self) -> bool:
        token = os.environ.get("MAC_AGENT_TOKEN", "")
        if not token:
            return False
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {token}"
        return hmac.compare_digest(auth, expected)

    def _send(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

    def do_GET(self):
        if not self._auth():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, {"ok": True, "version": __version__,
                                    "mode": self.state.cfg.get("mode", "restricted"),
                                    "paused": self.state.paused_file.exists()})
        if path == "/capabilities":
            return self._send(200, capability_index(self.state.cfg))
        if path.startswith("/result/"):
            task_id = path[len("/result/"):]
            with self.state.lock:
                result = self.state.results.get(task_id)
            if result is None:
                return self._send(404, {"ok": False, "error": "unknown task"})
            return self._send(200, {"ok": True, **result})
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self._auth():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        if self.state.paused_file.exists():
            return self._send(423, {"ok": False, "error": "connector is paused"})
        if urlparse(self.path).path != "/task":
            return self._send(404, {"ok": False, "error": "not found"})
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            return self._send(415, {"ok": False, "error": "application/json required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, {"ok": False, "error": "invalid content length"})
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send(413, {"ok": False, "error": "request body too large or empty"})
        try:
            task = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "invalid JSON"})
        if not isinstance(task, dict):
            return self._send(400, {"ok": False, "error": "task must be an object"})
        task_id = str(task.get("task_id") or uuid.uuid4())
        action = str(task.get("action") or "")
        params = task.get("params", {})
        result = execute(action, params, self.state.cfg)
        status = result.pop("status", None) or ("done" if result.get("ok") else "error")
        with self.state.lock:
            if len(self.state.results) >= MAX_RESULTS:
                self.state.results.pop(next(iter(self.state.results)), None)
            self.state.results[task_id] = {
                "task_id": task_id,
                "action": action,
                "status": status,
                "result": result,
            }
        return self._send(200, {"ok": True, "task_id": task_id, "status": status})


def serve(cfg: dict, host: str = "127.0.0.1", port: int = 8899):
    Handler.state = _State(cfg)
    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
