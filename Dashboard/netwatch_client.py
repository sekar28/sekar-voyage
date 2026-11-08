"""Client for Sekar's Network Watch (..\\NetworkWatch\\app.py). The Dashboard's Network tile only displays what that
app reports - it does no scanning itself. Network Watch must be installed and running; its local read-only API's
port and token are in %LOCALAPPDATA%\\NetworkWatch\\api.json."""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API_JSON = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local")),
                        "NetworkWatch", "api.json")
APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "NetworkWatch", "app.py")
APP_NAME = "Sekar's Network Watch"


def installed():
    return os.path.isfile(APP_PY) or os.path.isfile(API_JSON)


def _request(method, path, body=None, timeout=4):
    with open(API_JSON, encoding="utf-8") as f:
        info = json.load(f)
    req = urllib.request.Request(f"http://127.0.0.1:{int(info['port'])}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-NetWatch-Token": str(info["token"]), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def summary():
    """What Network Watch sees, plus {"running": True}; or {"running": False, "installed": bool}."""
    if not os.path.isfile(API_JSON):
        return {"running": False, "installed": installed()}
    try:
        out = _request("GET", "/summary")
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        return {"running": False, "installed": installed()}
    out["running"] = True
    return out


def open_app(view=""):
    """Bring Network Watch to the front (on a given view), or start it if it's installed but not running."""
    try:
        _request("POST", "/show", {"view": view})
        return True
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if not os.path.isfile(APP_PY):
        raise RuntimeError(f"{APP_NAME} isn't installed.")
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    subprocess.Popen(["cmd", "/c", "start", "", pyw if os.path.isfile(pyw) else "pythonw", APP_PY],
                     cwd=os.path.dirname(APP_PY), creationflags=subprocess.CREATE_NO_WINDOW)
    return True
