"""Client for the Sekar's System Utilities voice agent (StorageAnalyzer\\app.py), which does the PC care: clean-up,
organising, drivers, performance. It's optional - when it isn't installed the dashboard just says so.

The agent runs a local HTTP API; its port and token are in %LOCALAPPDATA%\\StorageAnalyzer\\agent.json."""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

AGENT_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local")),
                          "StorageAnalyzer", "agent.json")
APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "StorageAnalyzer", "app.py")
APP_NAME = "Sekar's System Utilities"
SETUP_ID = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F3C2A51-8B7E-4C0D-9A61-5E2B7D4F1C90}_is1"
START_WAIT = 20                              # seconds to wait for a freshly started Sekar's System Utilities
ASK_TIMEOUT = 75
POLL_EVERY = 5
NOT_INSTALLED = "For system lookups and detailed analysis, install Sekar's System Utilities."

_start_lock = threading.Lock()


class AgentError(RuntimeError):
    pass


def _installed_exe():
    """SystemUtilities.exe from its installer's uninstall entry (per-user first, then all users), or None."""
    import winreg
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, SETUP_ID) as k:
                exe = os.path.join(winreg.QueryValueEx(k, "InstallLocation")[0], "SystemUtilities.exe")
        except OSError:
            continue
        if os.path.isfile(exe):
            return exe
    return None


def _start_command():
    """How to start it in the tray: the source copy next to this folder, else the installed app."""
    if os.path.isfile(APP_PY):
        return [_pythonw(), APP_PY, "--tray"], os.path.dirname(APP_PY)
    exe = _installed_exe()
    return ([exe, "--tray"], os.path.dirname(exe)) if exe else (None, None)


def installed():
    return os.path.isfile(APP_PY) or os.path.isfile(AGENT_JSON) or bool(_installed_exe())


def _conn():
    with open(AGENT_JSON, encoding="utf-8") as f:
        info = json.load(f)
    return f"http://127.0.0.1:{int(info['port'])}", str(info["token"])


def _request(method, path, body=None, timeout=10):
    base, token = _conn()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"X-Agent-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def ping():
    try:
        return bool(_request("GET", "/ping", timeout=2).get("ok"))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _pythonw():
    exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return exe if os.path.isfile(exe) else "pythonw"


def ensure_running(on_starting=None):
    """Start Sekar's System Utilities (in the tray) if it isn't answering, and wait for it."""
    if ping():
        return
    with _start_lock:
        if ping():                            # another request started it meanwhile
            return
        cmd, cwd = _start_command()
        if not cmd:
            raise AgentError("Sekar's System Utilities isn't running and I can't find it to start it.")
        if on_starting:
            on_starting()
        subprocess.Popen(["cmd", "/c", "start", ""] + cmd, cwd=cwd, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.time() + START_WAIT
        while time.time() < deadline:
            time.sleep(0.5)
            if ping():
                return
    raise AgentError("Sekar's System Utilities didn't start.")


def ask(text, on_starting=None):
    """-> {"say", "expect_reply", "busy"}. Raises AgentError with a short sentence to speak."""
    if not installed():
        return {"say": NOT_INSTALLED, "expect_reply": False, "busy": False}
    for attempt in (1, 2):
        ensure_running(on_starting)
        try:
            out = _request("POST", "/ask", {"text": text, "source": "dashboard"}, timeout=ASK_TIMEOUT)
            return {"say": str(out.get("say") or ""), "expect_reply": bool(out.get("expect_reply")),
                    "busy": bool(out.get("busy"))}
        except TimeoutError:
            raise AgentError("Sekar's System Utilities took too long to answer.")
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 1:   # restarted with a new token: read agent.json again
                continue
            raise AgentError(f"Sekar's System Utilities had a problem (error {e.code}).")
        except (OSError, ValueError, KeyError) as e:
            if "timed out" in str(e):
                raise AgentError("Sekar's System Utilities took too long to answer.")
            if attempt == 2:
                raise AgentError("I couldn't reach Sekar's System Utilities.")
    raise AgentError("I couldn't reach Sekar's System Utilities.")


def events(since):
    out = _request("GET", f"/events?since={int(since)}", timeout=5)
    return out.get("events") or [], int(out.get("last") or 0)


class Poller(threading.Thread):
    """Every POLL_EVERY seconds hand new agent events (alerts, finished jobs) to on_event. Never starts the app."""

    def __init__(self, on_event, stopped=lambda: False):
        super().__init__(daemon=True)
        self.on_event = on_event
        self.stopped = stopped
        self.last = None                      # None until the first contact: old events aren't replayed

    def run(self):
        while not self.stopped():
            time.sleep(POLL_EVERY)
            if not os.path.isfile(AGENT_JSON):
                continue
            try:
                if self.last is None:
                    _, self.last = events(0)
                    continue
                evs, last = events(self.last)
                if last < self.last:          # Sekar's System Utilities restarted: its ids start again
                    evs, last = events(0)
                self.last = last
            except (OSError, ValueError, KeyError, TypeError):
                continue
            for ev in evs:
                try:
                    self.on_event(ev)
                except Exception:
                    pass
