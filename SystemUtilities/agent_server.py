"""Tiny local HTTP link so the Dashboard's "Hey Jarvis" can talk to the System Utilities assistant.

Listens on 127.0.0.1 only, on a random port, and every request must carry the secret token written (with the port)
to %LOCALAPPDATA%\\StorageAnalyzer\\agent.json - a file only this Windows user can read.
"""

import json
import os
import secrets
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import quickclean

AGENT_JSON = os.path.join(quickclean.LOCAL, "StorageAnalyzer", "agent.json")


def start(agent, on_show=None, publish=True):
    """publish=False: serve, but leave agent.json pointing at the copy that's already running (dev --serve runs)."""
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _ok(self):
            if self.client_address[0] != "127.0.0.1" or not secrets.compare_digest(
                    self.headers.get("X-Agent-Token", ""), token):
                self._json({"error": "wrong or missing token"}, 401)   # 401 tells the Dashboard to re-read agent.json
                return False
            return True

        def _json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._ok():
                return
            url = urlparse(self.path)
            if url.path == "/ping":
                return self._json({"ok": True, "name": "System Utilities"})
            if url.path == "/events":
                since = int((parse_qs(url.query).get("since") or ["0"])[0] or 0)
                return self._json(agent.events_since(since))
            if url.path == "/state":
                return self._json(agent.state())
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            if not self._ok():
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json({"error": "bad json"}, 400)
            path = urlparse(self.path).path
            if path == "/ask":
                return self._json(agent.ask(str(body.get("text", "")), str(body.get("source", "dashboard"))))
            if path == "/show":
                if on_show:
                    on_show()
                return self._json({"ok": True})
            self._json({"error": "not found"}, 404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True, name="agent-server").start()
    if publish:
        os.makedirs(os.path.dirname(AGENT_JSON), exist_ok=True)
        with open(AGENT_JSON, "w", encoding="utf-8") as f:
            json.dump({"port": server.server_address[1], "token": token, "pid": os.getpid()}, f)
    return server


def running_copy():
    """True if another System Utilities answers on the address in agent.json."""
    try:
        return bool(_request("GET", "/ping").get("ok"))
    except (OSError, ValueError, KeyError):
        return False


def remove():
    """Delete agent.json if it's ours (on quit)."""
    try:
        with open(AGENT_JSON, encoding="utf-8") as f:
            if json.load(f).get("pid") == os.getpid():
                os.remove(AGENT_JSON)
    except (OSError, ValueError):
        pass


def _request(method, path, body=None, timeout=3):
    with open(AGENT_JSON, encoding="utf-8") as f:
        info = json.load(f)
    req = urllib.request.Request(f"http://127.0.0.1:{info['port']}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Agent-Token": info["token"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def show_running_copy():
    """True if System Utilities is already running - it is brought to the front instead of starting a second copy."""
    try:
        if not _request("GET", "/ping").get("ok"):
            return False
        _request("POST", "/show", {})
        return True
    except (OSError, ValueError, KeyError):
        return False
