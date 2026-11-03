"""System Utilities - rich web UI (pywebview) on top of the scanning, clean-up, organiser and driver engines.

    python app.py            open the app window
    python app.py --debug    same, with WebView dev tools
    python app.py --serve    serve the UI at http://127.0.0.1:8765/?serve=1 (for development in a browser)
"""

import ctypes
import functools
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import winreg

import agent as agent_mod
import agent_server
import cleanup
import content
import drivers
import mover
import organiser
import perf
import quickclean
import secrets_store
import sysinfo
import versions
from core import Scanner, open_path, refresh_path, remove_path, reveal_in_explorer, subtree_summary
from llm import DEFAULT_HOST, LLMError, Ollama, OpenAICompatible

SETTINGS_PATH = os.path.join(quickclean.LOCAL, "StorageAnalyzer", "settings.json")
PERF_EXPLAIN_SYSTEM = (
    "You explain Windows background processes to a non-technical user. Given a process's name, path, publisher and "
    "description, say in 2-4 short sentences: what it is, what it does, and whether closing it is safe (and what stops "
    "working if they do). If you don't recognise it, say so plainly and judge only from the path and publisher - "
    "never invent details. No markdown headings.")
DEFAULT_SETTINGS = {
    "provider": "ollama",                     # ollama | openai | anthropic
    "ollama_host": DEFAULT_HOST, "ollama_model": None,
    "openai_base": "https://api.openai.com/v1", "openai_name": "OpenAI", "openai_model": "",
    "anthropic_model": "claude-opus-5-5",
    "price_in": None, "price_out": None,      # optional $ per 1M tokens for OpenAI-compatible services
    "confirm": True,                          # show the token estimate before cloud requests
}
OPENAI_PRESETS = [
    {"name": "OpenAI", "base": "https://api.openai.com/v1"},
    {"name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai"},
    {"name": "OpenRouter", "base": "https://openrouter.ai/api/v1"},
    {"name": "Groq", "base": "https://api.groq.com/openai/v1"},
    {"name": "Mistral", "base": "https://api.mistral.ai/v1"},
    {"name": "DeepSeek", "base": "https://api.deepseek.com/v1"},
    {"name": "Together AI", "base": "https://api.together.xyz/v1"},
    {"name": "LM Studio (local)", "base": "http://localhost:1234/v1"},
]
TYPICAL_OUTPUT = {"review": 700, "explain": 250, "plan": 1200}   # tokens per request, for the estimate

APP_NAME = "Sekar's System Utilities"   # what you see; folders, keys and registry names keep "SystemUtilities"
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
ICON = os.path.join(UI_DIR, "icon.ico")

# What the clean button does for each rule category (anything not listed has no clean button).
CONTENT_CLEAN = {"Windows temporary files", "User temporary files", "Windows Update download cache",
                 "Delivery Optimization cache", "Crash dumps & error reports", "Browser caches", "GPU shader caches"}
RECYCLE = {"Installers & archives in Downloads", "Large log & dump files", "Likely duplicate files (same name & size)",
           "node_modules folders", "Python bytecode caches", "Extracted driver installers"}
DUPLICATES = "Likely duplicate files (same name & size)"
CLOUD_CAT = "Cloud files kept on this PC"


def action_for(item, cat):
    """'clean' (delete contents), 'recycle', 'freeup', 'empty_bin' or None."""
    if cat is None:   # AI suggestion
        ok = item.get("risk") in (cleanup.SAFE, cleanup.REVIEW) and quickclean.is_deletable(item["path"])[0]
        return "recycle" if ok and not cleanup.is_protected(cleanup.rel_path(item["path"])) else None
    if cat.name == CLOUD_CAT:
        return "freeup"
    if cat.name == "Recycle Bin":
        return "empty_bin"
    if cat.name in CONTENT_CLEAN:
        return "clean" if item["kind"] == "dir" else "recycle"
    if cat.name in RECYCLE or cat.name.startswith("Large files untouched"):
        return "recycle"
    return None
MAX_ITEMS = 1500        # rows sent per folder
MAX_CAT_ITEMS = 300     # items sent per clean-up category
AI_BATCH = 5            # folders per AI request
SERVE_PORT = 8765


def safe(fn):
    """Return errors to JavaScript as {"__error__": message} instead of raising across the bridge."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"__error__": str(e) or type(e).__name__}
    return wrapper


def volume_label(root):
    buf = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), buf, 261, None, None, None, None, 0)
    return buf.value if ok else ""


def windows_dark():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


KNOWN_FOLDERS = [   # (label, icon, value name under "User Shell Folders")
    ("Downloads", "download", "{374DE290-123F-4565-9164-39C4925E467B}"),
    ("Documents", "files", "Personal"),
    ("Desktop", "drive", "Desktop"),
    ("Pictures", "image", "My Pictures"),
    ("Videos", "video", "My Video"),
    ("Music", "music", "My Music"),
]


def known_folders():
    """The user's main folders, following OneDrive / custom redirections."""
    out = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
    except OSError:
        key = None
    for label, icon, value in KNOWN_FOLDERS:
        path = None
        if key:
            try:
                path = os.path.expandvars(winreg.QueryValueEx(key, value)[0])
            except OSError:
                pass
        path = path or os.path.join(os.path.expanduser("~"), label)
        if not os.path.isdir(path):
            continue
        try:
            with os.scandir(path) as it:
                entries = list(it)
            files = sum(1 for e in entries if e.is_file(follow_symlinks=False))
        except OSError:
            entries, files = [], 0
        out.append({"name": label, "icon": icon, "path": path, "items": len(entries), "loose": files})
    if key:
        key.Close()
    return out


def health_score(p):
    """0-100 tidiness score for a folder profile."""
    score = 100
    if p["direct_count"] >= 10:
        score -= min(25, p["direct_count"] // 4)
        if len(p["direct_types"]) >= 4:
            score -= 10
    score -= min(15, len(p["duplicates"]) * 2)
    score -= min(15, len(p["copies"]))
    score -= min(10, len(p["empty"]))
    score -= min(15, len(p["deep"]) // 10)
    return max(0, score)


# ---------------------------------------------------------------- JSON shapes

def _dir_json(node, path):
    return {"kind": "dir", "name": node.name, "path": path, "size": node.size, "cloud": node.cloud,
            "files": node.file_count, "denied": node.denied}


def _file_json(f, parent):
    name, size, mtime, cloud = f
    return {"kind": "file", "name": name, "path": os.path.join(parent, name),
            "size": 0 if cloud else size, "cloud": size if cloud else 0, "mtime": mtime}


def _kids(node, path, limit=10):
    """Second ring of the sunburst: a folder's biggest children, loose files grouped into one slice."""
    kids = [{"kind": "dir", "name": d.name, "path": os.path.join(path, d.name), "size": d.size} for d in node.dirs]
    loose = sum(f[1] for f in node.files if not f[3])
    if loose:
        kids.append({"kind": "files", "name": f"{len(node.files):,} files", "path": path, "size": loose})
    kids.sort(key=lambda k: -k["size"])
    return [k for k in kids[:limit] if k["size"] > 0]


def _item_json(item, cat):
    return {"path": item["path"], "size": item["size"], "kind": item["kind"], "note": item.get("note", ""),
            "risk": item.get("risk", cat.risk), "action": item.get("action", ""), "impact": item.get("impact", ""),
            "reclaim": item.get("reclaim", item["size"]), "cloud": cleanup.is_cloud_synced(item["path"]),
            "act": action_for(item, None if cat.source == "ai" else cat)}


def _cat_json(cat):
    acts = {action_for(i, cat) for i in cat.items}
    return {"name": cat.name, "risk": cat.risk, "impact": cat.impact, "how": cat.how, "source": cat.source,
            "total": cat.total, "count": len(cat.items),
            "bulk": next(iter(acts)) if cat.risk == cleanup.SAFE and len(acts) == 1 and None not in acts else None,
            "items": [_item_json(i, cat) for i in cat.items[:MAX_CAT_ITEMS]]}


def dup_keeper(paths):
    """The copy to keep: the one nearest the top of the folder, then the oldest."""
    def rank(path):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = float("inf")
        return path.count(os.sep), mtime, path.lower()
    return min(paths, key=rank)


def _dup_groups_json(groups):
    out = []
    for paths in groups:
        try:
            size = os.path.getsize(paths[0])
        except OSError:
            size = 0
        out.append({"name": os.path.basename(paths[0]), "size": size, "paths": paths, "keep": dup_keeper(paths)})
    return out


def _profile_json(p, node):
    def part(key, n=100):
        return {"count": len(p[key]), "sample": p[key][:n]}
    return {
        "path": p["path"], "name": node.name, "size": p["size"], "file_count": p["file_count"],
        "direct_count": p["direct_count"], "direct_size": p["direct_size"],
        "direct_types": p["direct_types"], "years": p["years"],
        "subfolder_count": len(p["subfolders"]), "subfolders": p["subfolders"][:60],
        "by_type": subtree_summary(node, p["path"])["by_type"],
        "issues": organiser.rule_issues(p), "score": health_score(p),
        "duplicates": {"count": len(p["duplicates"]), "waste": p["duplicate_waste"],
                       "sample": _dup_groups_json(p["duplicates"][:50])},
        "copies": part("copies"), "empty": part("empty"), "deep": part("deep"),
    }


class Api:
    """Methods callable from JavaScript (names starting with _ are not exposed)."""

    def __init__(self):
        self._window = None
        self._events = []
        self._events_lock = threading.Lock()
        self._root = None
        self._top = []
        self._scanner = None
        self._cats = []
        self._ai_items = []
        self._ai_cat = None
        self._profile = None
        self._settings = self._load_settings()
        self._llm, self._llm_error = None, None
        self._rebuild_llm()
        self._ai_enabled = True
        self._plan = None       # (folder, plan) - the last plan shown in organiser mode
        self._preview = None    # mover.preview() result the user is looking at
        self._vdupes = None     # last duplicate-versions result
        self._cls_last = None   # last document classification (for the "left behind" reasons)
        self._drv_list = None   # drivers.list_drivers() cache
        self._drv_updates = None
        self._drv_lock = threading.Lock()
        self._drv_check_lock = threading.Lock()
        self._perf = None       # perf.snapshot() - closing only ever acts on what this listed
        self.agent = None       # the voice assistant (agent.Agent), created in main()
        self.voice = None       # its own ears and voice (voice_host.VoiceHost) for when the Dashboard is closed
        self._tray = None
        self._quitting = False

    # ---------------------------------------------------------------- plumbing
    def _emit(self, event, data=None):
        if self._window is not None:
            self._window.evaluate_js(f"App.on({json.dumps(event)}, {json.dumps(data)})")
        else:
            with self._events_lock:
                self._events.append([event, data])

    def _drain_events(self):
        with self._events_lock:
            events, self._events = self._events, []
        return events

    def _need_root(self):
        if self._root is None:
            raise RuntimeError("Scan a drive or folder first.")
        return self._root

    def _node(self, path=None):
        root = self._need_root()
        node = root.find(path) if path else root
        if node is None:
            raise FileNotFoundError(f"Not part of the scanned data: {path}")
        return node

    def _need_ai(self):
        if not self._ai_enabled:
            raise RuntimeError("AI is turned off. Turn it on in the sidebar to use this.")
        if self._llm is None:
            raise LLMError(self._llm_error or "AI isn't set up - open AI settings.")
        return self._llm

    # ---------------------------------------------------------------- AI provider settings
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except (OSError, ValueError):
            return dict(DEFAULT_SETTINGS)

    def _save_settings(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=1)

    @staticmethod
    def _make_client(s, openai_key=None, anthropic_key=None):
        if s["provider"] == "openai":
            return OpenAICompatible(s["openai_base"], openai_key or secrets_store.get_secret("openai"),
                                    s.get("openai_model") or None, s.get("openai_name") or None)
        if s["provider"] == "anthropic":
            from llm_anthropic import Claude
            return Claude(anthropic_key or secrets_store.get_secret("anthropic"), s.get("anthropic_model"))
        return Ollama(s.get("ollama_host") or DEFAULT_HOST, s.get("ollama_model"))

    def _rebuild_llm(self):
        try:
            self._llm, self._llm_error = self._make_client(self._settings), None
        except Exception as e:
            self._llm, self._llm_error = None, str(e)

    def _price(self, client):
        if hasattr(client, "price"):
            return client.price()
        s = self._settings
        if s["provider"] == "openai" and s.get("price_in") is not None and s.get("price_out") is not None:
            return float(s["price_in"]), float(s["price_out"])
        return None

    def _usage(self, client):
        u = dict(client.usage)
        p = self._price(client)
        u["cost"] = round(u["input"] * p[0] / 1e6 + u["output"] * p[1] / 1e6, 4) if p else None
        u["local"] = client.is_local
        return u

    def _settings_view(self):
        s = self._settings
        from llm_anthropic import SUGGESTED
        return {**s, "openai_key": secrets_store.hint(secrets_store.get_secret("openai")),
                "anthropic_key": secrets_store.hint(secrets_store.get_secret("anthropic")),
                "presets": OPENAI_PRESETS, "anthropic_models": SUGGESTED,
                "label": self._llm.label if self._llm else None, "error": self._llm_error}

    @safe
    def ai_settings_get(self):
        return self._settings_view()

    @safe
    def ai_settings_save(self, form):
        s = dict(self._settings)
        for key in DEFAULT_SETTINGS:
            if key in form:
                s[key] = form[key]
        for k in ("price_in", "price_out"):
            s[k] = float(s[k]) if s.get(k) not in (None, "") else None
        if s["provider"] not in ("ollama", "openai", "anthropic"):
            raise ValueError("Unknown provider.")
        for name in ("openai", "anthropic"):           # a typed key replaces the stored one; blank keeps it
            if form.get(f"{name}_key_new"):
                secrets_store.set_secret(name, form[f"{name}_key_new"].strip())
            if form.get(f"{name}_key_clear"):
                secrets_store.delete_secret(name)
        self._settings = s
        self._save_settings()
        self._rebuild_llm()
        return self._settings_view()

    @safe
    def ai_test(self, form):
        """Try the settings in the form without saving them."""
        s = {**self._settings, **{k: v for k, v in form.items() if k in DEFAULT_SETTINGS}}
        client = self._make_client(s, form.get("openai_key_new") or None, form.get("anthropic_key_new") or None)
        names = client.models()
        return {"ok": True, "models": names[:300], "model": client.model, "label": client.label}

    # ---------------------------------------------------------------- general
    @safe
    def init(self):
        return {"cloud_note": cleanup.CLOUD_NOTE, "dark": windows_dark(), "admin": quickclean.is_admin()}

    @safe
    def known_folders(self):
        return known_folders()

    @safe
    def sys_specs(self):
        if getattr(self, "_specs", None) is None:
            self._specs = sysinfo.specs()
        return self._specs

    @safe
    def sys_live(self):
        return sysinfo.live()

    @safe
    def set_ai_enabled(self, on):
        self._ai_enabled = bool(on)
        return self._ai_enabled

    @safe
    def restart_as_admin(self):
        if not quickclean.relaunch_as_admin(os.path.abspath(__file__)):
            raise RuntimeError("Administrator access was not granted.")
        if self._window is not None:
            threading.Timer(0.5, self._window.destroy).start()
        return True

    # ---------------------------------------------------------------- quick clean
    @safe
    def quick_targets(self):
        """Describe the quick-clean locations now; their sizes arrive as 'quick_size' events."""
        targets = [{k: t.get(k) for k in ("id", "name", "desc", "icon", "kind", "default", "admin")}
                   for t in quickclean.TARGETS]

        def measure_all():
            for t in quickclean.TARGETS:
                self._emit("quick_size", quickclean.measure(t))
            self._emit("quick_measured")
        threading.Thread(target=measure_all, daemon=True).start()
        return {"targets": targets, "admin": quickclean.is_admin()}

    @safe
    def quick_clean(self, ids):
        results = []
        for target_id in ids:
            self._emit("quick_cleaning", {"id": target_id})
            try:
                res = quickclean.clean_target(target_id)
            except Exception as e:
                res = {"id": target_id, "freed": 0, "deleted": 0, "skipped": 0, "error": str(e)}
            self._emit("quick_cleaned", res)
            self._emit("quick_size", quickclean.measure(quickclean.TARGET_BY_ID[target_id]))
            results.append(res)
        if self._root is not None:   # keep the scanned tree in sync with what was removed
            for target_id in ids:
                for p in quickclean.resolve(quickclean.TARGET_BY_ID[target_id], run_finder=False):
                    if os.path.isdir(p):
                        refresh_path(self._root, p)
        return {"freed": sum(r["freed"] for r in results), "skipped": sum(r["skipped"] for r in results),
                "results": results}

    @safe
    def quick_details(self, target_id):
        if target_id not in quickclean.TARGET_BY_ID:
            raise ValueError("Unknown location.")
        return quickclean.details(target_id)

    # ---------------------------------------------------------------- cleaning scan results
    def _find_item(self, path):
        for cat in self._cats:
            for item in cat.items:
                if item["path"] == path:
                    return item, cat
        if self._ai_cat:
            for item in self._ai_cat.items:
                if item["path"] == path:
                    return item, None
        return None, None

    def _apply(self, act, item):
        """Run one clean action and update the scanned tree. Returns bytes freed and files skipped."""
        path, root = item["path"], self._root
        if act == "clean":
            freed, _, skipped = quickclean.clean_contents(path)
            node = refresh_path(root, path)
            return freed, skipped, (node.size if node else 0)
        if act == "recycle":
            quickclean.send_to_recycle_bin(path)
            remove_path(root, path)
            return item["size"], 0, 0
        if act == "freeup":
            before = item["size"]
            quickclean.free_up_space(path)
            node = refresh_path(root, path)
            left = node.size if node else 0
            return max(0, before - left), 0, left
        if act == "empty_bin":
            freed, _, _ = quickclean.empty_recycle_bin()
            node = refresh_path(root, path)
            return freed, 0, (node.size if node else 0)
        raise PermissionError("This item can't be cleaned from the app - see 'How to clean'.")

    def _drop(self, item, cat, left):
        """Remove a cleaned item from its list (or shrink it if files were left behind)."""
        items = self._ai_cat.items if cat is None else cat.items
        if left >= 1024 ** 2:
            item["size"] = item["reclaim"] = left
            return
        items.remove(item)
        if cat is not None and cat.name == DUPLICATES:   # the last remaining copy is no longer a duplicate
            name = os.path.basename(item["path"]).lower()
            same = [i for i in items if os.path.basename(i["path"]).lower() == name and i["size"] == item["size"]]
            if len(same) == 1:
                items.remove(same[0])
        if cat is not None and not cat.items:
            self._cats.remove(cat)

    @safe
    def clean_item(self, path):
        item, cat = self._find_item(path)
        if item is None:
            raise LookupError("This is not one of the clean-up suggestions (try finding candidates again).")
        act = action_for(item, cat)
        freed, skipped, left = self._apply(act, item)
        self._drop(item, cat, left)
        return {"path": path, "action": act, "freed": freed, "skipped": skipped,
                "categories": [_cat_json(c) for c in self._cats],
                "ai_items": [_item_json(i, self._ai_cat) for i in self._ai_cat.items] if self._ai_cat else None}

    # ---------------------------------------------------------------- drivers
    def _listing(self, refresh=False):
        with self._drv_lock:
            if refresh or self._drv_list is None:
                self._drv_list = drivers.list_drivers()
            return self._drv_list

    @safe
    def drivers_list(self, refresh=False):
        listing = self._listing(refresh)
        tools = drivers.vendor_tools(listing)
        rows = [{**d, "source": drivers.update_source(d, listing, tools)} for d in listing["drivers"]]
        return {**listing, "drivers": rows, "tools": tools, "admin": quickclean.is_admin()}

    @safe
    def drivers_check(self, refresh=False):
        """Ask Windows Update (slow, ~30-60 s). Concurrent callers share one search."""
        with self._drv_check_lock:
            if refresh or self._drv_updates is None:
                self._drv_updates = drivers.check_updates(self._listing()["system"])
            return self._drv_updates

    @safe
    def drivers_summary(self):
        listing = self._listing()
        dated = [d for d in listing["drivers"] if not d["virtual"] and d["age"] is not None]
        upd = self._drv_updates
        return {
            "system": listing["system"], "count": len(listing["drivers"]), "total": listing["total"],
            "old": sum(1 for d in dated if d["age"] > 3), "older": sum(1 for d in dated if 1 <= d["age"] <= 3),
            "updates": None if upd is None else sum(1 for u in upd["updates"] if not u["downgrade"]),
            "blocked": None if upd is None else sum(1 for u in upd["updates"] if u["downgrade"]),
            "checked_at": upd["checked_at"] if upd else None,
        }

    @safe
    def drivers_install(self, ids, restore_point=True):
        upd = self._drv_updates
        if not upd:
            raise RuntimeError("Check for updates first.")
        allowed = {u["id"] for u in upd["updates"] if not u["downgrade"]}
        ids = [i for i in ids if i in allowed]       # never install something the check didn't offer, or a downgrade
        if not ids:
            raise ValueError("Nothing selected that can be installed.")
        result = drivers.install_updates(ids, restore_point, lambda step: self._emit("driver_progress", {"step": step}))
        self._drv_list = self._drv_updates = None    # re-read after installing
        return result

    @safe
    def open_vendor_tool(self, target):
        listing = self._listing()
        if target not in {t["target"] for t in drivers.vendor_tools(listing)}:
            raise ValueError("Unknown tool.")
        drivers.open_tool(target)
        return True

    @safe
    def restart_pc(self):
        subprocess.run(["shutdown", "/r", "/t", "10", "/c", f"Restarting ({APP_NAME})"],
                       creationflags=subprocess.CREATE_NO_WINDOW, check=True)
        return True

    # ---------------------------------------------------------------- performance
    def _perf_snap(self, refresh=True):
        if refresh or self._perf is None:
            self._perf = perf.snapshot()
        return self._perf

    @safe
    def perf_snapshot(self):
        s = self._perf_snap()
        return {**s, "startup": perf.startup_items(s), "power": perf.power_mode()}

    @safe
    def perf_summary(self):
        s = self._perf_snap(refresh=False)
        safe_groups = [g for g in s["groups"] if g["cat"] == "safe"]
        return {"live": sysinfo.live(), "safe": len(safe_groups), "safe_mem": sum(g["mem"] for g in safe_groups),
                "processes": s["total"], "startup_on": sum(1 for i in perf.startup_items(s) if i["enabled"]),
                "top": [{"name": g["desc"] or g["name"], "mem": g["mem"]} for g in s["groups"]
                        if g["cat"] in ("app", "safe", "review")][:3]}

    @safe
    def perf_end(self, keys, force=False):
        if self._perf is None:
            raise RuntimeError("Refresh the process list first.")
        result = perf.end_processes(self._perf, keys, bool(force))
        result["live"] = sysinfo.live()
        return result

    @safe
    def perf_trim(self):
        return perf.trim_memory()

    @safe
    def perf_purge_standby(self):
        return perf.purge_standby()

    @safe
    def perf_set_startup(self, item_id, enabled):
        return perf.set_startup(item_id, bool(enabled))

    @safe
    def perf_power_settings(self):
        perf.open_power_settings()
        return True

    @safe
    def perf_reveal(self, key):
        g = next((g for g in (self._perf or {}).get("groups", []) if g["key"] == key), None)
        if not g or not g["path"]:
            raise FileNotFoundError("Location unknown.")
        reveal_in_explorer(g["path"])
        return True

    @safe
    def perf_explain(self, key):
        """Ask the AI what a background process is. Sends its name, file path, publisher and description only."""
        client = self._need_ai()
        g = next((g for g in (self._perf or {}).get("groups", []) if g["key"] == key), None)
        if not g:
            raise RuntimeError("Refresh the process list first.")
        client.reset_usage()
        info = (f"process: {g['name']}.exe ({g['count']} running)\npath: {g['path'] or 'unknown'}\n"
                f"publisher: {g['company'] or 'unknown'}\ndescription: {g['desc'] or 'none'}\n"
                f"memory: {g['mem'] // 2**20} MB\nhas a window: {'yes' if g['title'] else 'no'}")
        answer = client.chat(PERF_EXPLAIN_SYSTEM, info, max_tokens=400)
        return {"answer": answer, "model": client.model, "usage": self._usage(client)}

    # ---------------------------------------------------------------- assistant ("Hey Jarvis")
    def _need_agent(self):
        if self.agent is None:
            raise RuntimeError("The assistant isn't running.")
        return self.agent

    @safe
    def agent_state(self):
        a = self._need_agent()
        return {**a.state(), "startup": self._run_at_startup(), "cloud": bool(self._llm and not self._llm.is_local),
                "label": self._llm.label if self._llm else None,
                "voice": self.voice.public() if self.voice is not None else None}

    @safe
    def agent_voice_listen(self):
        """Mic button: record one request now."""
        if self.voice is None:
            raise RuntimeError("Voice isn't available.")
        self.voice.push_to_talk()
        return self.voice.public()

    @safe
    def agent_voice_settings(self, mode=None, speak=None):
        if mode in ("wake", "ptt", "off"):
            self._settings["agent_voice"] = mode
        if speak is not None:
            self._settings["agent_speak"] = bool(speak)
            if not speak and self.voice is not None:
                self.voice.speaker.stop()
        self._save_settings()
        return self.voice.public() if self.voice is not None else None

    @safe
    def agent_ask(self, text):
        return self._need_agent().ask(text, "panel")

    @safe
    def agent_answer(self, answer):
        """Yes / No / Review buttons on the assistant's question."""
        a = self._need_agent()
        r = {"yes": lambda: a.confirm("click"), "no": a.decline, "review": a.review}[answer]()
        a._line("jarvis", r.say)
        return {"say": r.say}

    @safe
    def agent_learned(self):
        return self._need_agent().mem.learned()

    @safe
    def agent_forget(self, what="all"):
        mem = self._need_agent().mem
        if what == "all":
            mem.forget_all()
        elif what.startswith("pattern:"):
            kind, _, cat = what[len("pattern:"):].partition("|")
            mem._q("DELETE FROM decisions WHERE kind=? AND category=?", (kind, cat))
            mem.set_pref(f"{kind}.{cat}", None)
        elif what.startswith("pref:"):
            mem.set_pref(what[len("pref:"):], None)
        return mem.learned()

    @safe
    def agent_teach(self, kind, category, choice):
        """'What Jarvis has learned' buttons: keep / delete for a category, ok / suspicious for a program."""
        mem = self._need_agent().mem
        if kind == "process":
            mem.tag_process(category, choice if choice in ("ok", "suspicious") else None)
        else:
            mem.set_pref(f"{kind}.{category}", choice if choice in ("keep", "delete") else None)
        return mem.learned()

    @safe
    def agent_settings(self, monitor=None, startup=None):
        if monitor is not None:
            self._settings["agent_monitor"] = bool(monitor)
            self._save_settings()
        if startup is not None:
            self._set_run_at_startup(bool(startup))
        return self.agent_state()

    @safe
    def current_candidates(self):
        """The clean-up suggestions as they are now (what the assistant found), without recomputing them."""
        return {"categories": [_cat_json(c) for c in self._cats],
                "ai_items": [_item_json(i, self._ai_cat) for i in self._ai_cat.items] if self._ai_cat else None,
                "model": getattr(self._llm, "model", None)}

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _run_at_startup(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as k:
                winreg.QueryValueEx(k, "SystemUtilities")
                return True
        except OSError:
            return False

    def _set_run_at_startup(self, on):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                exe = sys.executable.replace("python.exe", "pythonw.exe")
                script = "" if getattr(sys, "frozen", False) else f' "{os.path.abspath(__file__)}"'   # installed .exe
                winreg.SetValueEx(k, "SystemUtilities", 0, winreg.REG_SZ, f'"{exe}"{script} --tray')
            else:
                try:
                    winreg.DeleteValue(k, "SystemUtilities")
                except OSError:
                    pass

    def _show(self):
        if self._window is None:
            return
        try:
            self._window.show()
            self._window.restore()
        except Exception:
            pass
        hwnd = ctypes.windll.user32.FindWindowW(None, self._window.title)
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)

    def _hide(self):
        if self._window is not None:
            self._window.hide()

    def _quit(self):
        if self._quitting:
            return
        self._quitting = True
        if self.agent is not None:
            self.agent.stop()
        if self.voice is not None:
            self.voice.stop()
        agent_server.remove()
        if self._tray is not None:
            self._tray.stop()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass

    # ---------------------------------------------------------------- duplicate versions
    @safe
    def find_version_dupes(self, path):
        node = self._node(path)
        self._vdupes = versions.find(node, node.path, lambda done, total, name: self._emit(
            "vdupe_progress", {"done": done, "total": total, "name": name}))
        return self._vdupes

    @safe
    def remove_version_dupes(self, paths):
        r = self._vdupes
        if not r:
            raise RuntimeError("Check for duplicate versions first.")
        owner = {d["path"]: g for g in r["groups"] for d in g["dupes"]}   # only copies the check found
        removed = freed = 0
        failed = []
        for p in paths:
            g = owner.get(p)
            name = os.path.basename(p)
            if g is None:
                failed.append(f"{name}: not a verified duplicate")
                continue
            keep = g["keep"]["path"]
            try:
                if not os.path.exists(keep) or os.path.getsize(keep) != g["size"] or os.path.getsize(p) != g["size"]:
                    failed.append(f"{name}: files changed since the check - run it again")
                    continue
                quickclean.send_to_recycle_bin(p)
            except Exception as e:
                failed.append(f"{name}: {e}")
                continue
            if self._root is not None:
                remove_path(self._root, p)
            g["dupes"] = [d for d in g["dupes"] if d["path"] != p]
            removed += 1
            freed += g["size"]
        r["groups"] = [g for g in r["groups"] if g["dupes"]]
        return {"removed": removed, "freed": freed, "failed": failed[:5], "result": versions.summarise(r)}

    @safe
    def clean_category(self, name):
        cat = next((c for c in self._cats if c.name == name), None)
        if cat is None:
            raise LookupError(f"No category named {name}.")
        if _cat_json(cat)["bulk"] is None:
            raise PermissionError("Only 'Safe' categories can be cleaned in one go - clean items one by one.")
        freed = skipped = 0
        errors = []
        items = list(cat.items)
        for n, item in enumerate(items):
            self._emit("clean_progress", {"name": name, "done": n, "total": len(items), "path": item["path"]})
            try:
                f, s, left = self._apply(action_for(item, cat), item)
                freed, skipped = freed + f, skipped + s
                self._drop(item, cat, left)
            except Exception as e:
                errors.append(f"{os.path.basename(item['path'])}: {e}")
        return {"name": name, "freed": freed, "skipped": skipped, "errors": errors[:5],
                "categories": [_cat_json(c) for c in self._cats]}

    @safe
    def list_drives(self):
        drives = []
        for d in os.listdrives():
            try:
                u = shutil.disk_usage(d)
            except OSError:
                continue
            drives.append({"path": d, "letter": d.rstrip("\\"), "label": volume_label(d) or "Local Disk",
                           "total": u.total, "used": u.used, "free": u.free})
        return drives

    @safe
    def list_models(self):
        client = self._need_ai()
        try:
            names = client.models()
        except LLMError:
            if client.is_local:
                raise
            names = []          # some APIs don't list models; the configured one still works
        if client.model and client.model not in names:
            names = [client.model] + names
        return {"models": names, "current": client.model, "provider": self._settings["provider"],
                "label": client.label, "local": client.is_local, "confirm": self._settings["confirm"]}

    @safe
    def set_model(self, name):
        client = self._need_ai()
        client.model = name
        self._settings[{"openai": "openai_model", "anthropic": "anthropic_model"}.get(
            self._settings["provider"], "ollama_model")] = name
        self._save_settings()
        return True

    @safe
    def ai_estimate(self, op, path=None):
        """Token (and cost) estimate for an AI action, built from the exact prompts it would send."""
        client = self._need_ai()
        if op == "review":
            root = self._need_root()
            if not self._cats:
                self._cats = cleanup.find_candidates(root)
            folders = cleanup.unknown_big_folders(root, self._cats)
            requests = [cleanup.review_prompt(folders[i:i + AI_BATCH]) for i in range(0, len(folders), AI_BATCH)]
        elif op == "explain":
            requests = [cleanup.explain_prompt(*self._explain_args(path))]
        elif op == "plan":
            node = self._node(path)
            if not self._profile or self._profile["path"] != node.path:
                self._profile = organiser.profile_folder(node, node.path)
            requests = [organiser.plan_prompt(self._profile)]
        else:
            raise ValueError(f"Unknown AI action {op}")
        counts = [client.count_tokens(system, user) for system, user in requests]
        tokens_in = sum(c[0] for c in counts)
        tokens_out = TYPICAL_OUTPUT[op] * len(requests)
        p = self._price(client)
        return {"op": op, "requests": len(requests), "input": tokens_in, "exact": all(c[1] for c in counts),
                "output": tokens_out, "label": client.label, "model": client.model, "local": client.is_local,
                "cost": round(tokens_in * p[0] / 1e6 + tokens_out * p[1] / 1e6, 4) if p else None,
                "thinking": self._settings["provider"] == "anthropic"}

    @safe
    def pick_folder(self):
        if self._window is None:
            return None
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return os.path.normpath(result[0]) if result else None

    @safe
    def reveal(self, path):
        reveal_in_explorer(path)
        return True

    @safe
    def open_item(self, path):
        open_path(path)
        return True

    @safe
    def copy_text(self, text):
        subprocess.run("clip", input=("﻿" + text).encode("utf-16-le"), check=True)
        return True

    # ---------------------------------------------------------------- scanning
    @safe
    def start_scan(self, path):
        if self._scanner and self._scanner.is_alive():
            raise RuntimeError("A scan is already running.")
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Folder not found: {path}")
        q = queue.Queue()
        self._scanner = Scanner(path, q)
        self._root, self._top, self._cats, self._ai_cat, self._profile = None, [], [], None, None
        started = time.monotonic()

        def pump():
            while True:
                msg = q.get()
                if msg[0] == "progress":
                    self._emit("scan_progress", {"files": msg[1], "dirs": msg[2], "path": msg[3],
                                                 "elapsed": time.monotonic() - started})
                elif msg[0] == "done":
                    _, root, top, files, dirs = msg
                    self._root, self._top = root, top
                    self._emit("scan_done", {"path": root.path, "size": root.size, "cloud": root.cloud,
                                             "files": files, "dirs": dirs, "elapsed": time.monotonic() - started})
                    return
                else:
                    self._emit("scan_cancelled")
                    return

        self._scanner.start()
        threading.Thread(target=pump, daemon=True).start()
        return True

    @safe
    def cancel_scan(self):
        if self._scanner:
            self._scanner.cancelled = True
        return True

    # ---------------------------------------------------------------- browsing
    @safe
    def get_folder(self, path=None):
        node = self._node(path)
        path = node.path
        dirs = sorted(node.dirs, key=lambda d: -d.size)
        items = [_dir_json(d, os.path.join(path, d.name)) for d in dirs]
        for item, d in zip(items[:40], dirs[:40]):
            item["kids"] = _kids(d, item["path"])
        items += [_file_json(f, path) for f in node.files]
        items.sort(key=lambda e: (e["size"], e["cloud"]), reverse=True)
        rest = items[MAX_ITEMS:]

        crumbs = []
        n = node
        while n is not None:
            crumbs.append({"name": n.name.rstrip("\\") if n.parent is None else n.name, "path": n.path})
            n = n.parent
        return {
            "path": path, "name": crumbs[0]["name"], "size": node.size, "cloud": node.cloud,
            "files": node.file_count, "dirs": len(node.dirs), "loose": len(node.files),
            "parent": node.parent.path if node.parent else None, "crumbs": crumbs[::-1],
            "items": items[:MAX_ITEMS], "more": {"count": len(rest), "size": sum(e["size"] for e in rest)},
        }

    @safe
    def get_largest(self):
        return [{"path": p, "name": os.path.basename(p), "dir": os.path.dirname(p), "size": s}
                for s, p in self._top if os.path.exists(p)]

    # ---------------------------------------------------------------- clean-up mode
    @safe
    def find_candidates(self):
        self._cats = cleanup.find_candidates(self._need_root())
        self._ai_cat = None
        return [_cat_json(c) for c in self._cats]

    @safe
    def ai_review(self):
        client = self._need_ai()
        client.reset_usage()
        root = self._need_root()
        if not self._cats:
            self._cats = cleanup.find_candidates(root)
        folders = cleanup.unknown_big_folders(root, self._cats)
        self._emit("ai_review_start", {"total": len(folders), "model": client.model})
        self._ai_cat = None
        for start in range(0, len(folders), AI_BATCH):
            self._emit("ai_review_progress", {"done": start, "total": len(folders)})
            cat = cleanup.ai_review_folders(client, folders[start:start + AI_BATCH], batch=AI_BATCH)
            if self._ai_cat is None:
                self._ai_cat = cat
            else:
                self._ai_cat.items += cat.items
            self._emit("ai_review_batch", {"items": [_item_json(i, cat) for i in cat.items],
                                           "done": min(start + AI_BATCH, len(folders)), "total": len(folders)})
        return {"count": len(self._ai_cat.items) if self._ai_cat else 0, "model": client.model,
                "usage": self._usage(client)}

    def _explain_args(self, path):
        root = self._need_root()
        node = root.find(path) if os.path.isdir(path) else None
        size = mtime = None
        if node is None:
            parent = root.find(os.path.dirname(path))
            name = os.path.basename(path).lower()
            match = next((f for f in parent.files if f[0].lower() == name), None) if parent else None
            if match:
                size, mtime = match[1], match[2]
            else:
                st = os.stat(path)
                size, mtime = st.st_size, st.st_mtime
        return node, path, size, mtime

    @safe
    def ai_explain(self, path):
        client = self._need_ai()
        client.reset_usage()
        answer = cleanup.ai_explain(client, *self._explain_args(path))
        return {"answer": answer, "model": client.model, "usage": self._usage(client)}

    # ---------------------------------------------------------------- organiser mode
    @safe
    def analyse_folder(self, path):
        node = self._node(path)
        self._profile = organiser.profile_folder(node, node.path)
        return _profile_json(self._profile, node)

    @safe
    def remove_duplicates(self, groups):
        """Recycle extra copies from the health check's duplicate sets - only copies whose contents are identical
        (SHA-256). One copy of each set is always kept. Online-only copies are never compared (that would download them)."""
        p = self._profile
        if not p:
            raise RuntimeError("Analyse the folder first.")
        known = [set(g) for g in p["duplicates"]]
        removed = freed = 0
        notes = []
        for paths in groups:
            name = os.path.basename(paths[0]) if paths else "?"
            if not paths or not any(set(paths) <= k for k in known):
                notes.append(f"{name}: not one of the duplicates found by the health check")
                continue
            local = []
            for path in paths:
                try:
                    if not os.stat(path, follow_symlinks=False).st_file_attributes & content.CLOUD_ONLY:
                        local.append(path)
                except OSError:
                    continue
            if len(local) < 2:
                notes.append(f"{name}: copies are online-only, so they weren't compared (that would download them)")
                continue
            by_hash = {}
            for path in local:
                try:
                    by_hash.setdefault(versions.file_hash(path), []).append(path)
                except OSError:
                    notes.append(f"{name}: couldn't read {path}")
            same_sets = [s for s in by_hash.values() if len(s) > 1]
            if not same_sets:
                notes.append(f"{name}: same name and size but different contents - all copies kept")
            for same in same_sets:
                keep = dup_keeper(same)
                for path in same:
                    if path == keep:
                        continue
                    try:
                        size = os.path.getsize(path)
                        quickclean.send_to_recycle_bin(path)
                    except Exception as e:
                        notes.append(f"{name}: {e}")
                        continue
                    if self._root is not None:
                        remove_path(self._root, path)
                    removed += 1
                    freed += size
        self._profile = None
        return {"removed": removed, "freed": freed, "notes": notes[:6]}

    @safe
    def plan_estimate(self, path):
        """Everything the AI-analysis dialog shows: the plan's cost, and what deep analysis would add."""
        ai = self._ai_enabled and self._llm is not None
        plan = self.ai_estimate("plan", path) if ai else None
        if plan and plan.get("__error__"):
            raise RuntimeError(plan["__error__"])
        deep = self.classify_preview(path)
        if deep.get("__error__"):
            raise RuntimeError(deep["__error__"])
        return {"ai": ai, "plan": plan, "deep": deep, "label": self._llm.label if ai else None,
                "model": self._llm.model if ai else None, "local": (self._llm.is_local if ai else True)}

    def _deep_first(self, path, deep_mode):
        """Run document classification and return (its moves, its result) to merge in front of a plan."""
        r = self.classify_run(path, deep_mode)
        if r.get("__error__"):
            raise RuntimeError(r["__error__"])
        return self._plan[1]["moves"], r

    @staticmethod
    def _merge(plan, deep_moves, deep_result):
        """Document classification first (it read the files, so it wins for them), then the plan's own moves.
        mover.preview gives each file to the first suggestion that matches it."""
        plan["moves"] = deep_moves + plan.get("moves", [])
        seen = {s["folder"] for s in plan.get("structure", []) if isinstance(s, dict)}
        plan["structure"] = plan.get("structure", []) + [
            {"folder": g["folder"], "purpose": g["label"] + " (from deep analysis)"}
            for g in deep_result["groups"] if g["folder"] not in seen]
        plan["deep"] = deep_result
        return plan

    @staticmethod
    def _sum_usage(*usages):
        usages = [u for u in usages if u]
        if not usages:
            return None
        costs = [u["cost"] for u in usages if u.get("cost") is not None]
        return {"input": sum(u["input"] for u in usages), "output": sum(u["output"] for u in usages),
                "requests": sum(u["requests"] for u in usages), "cost": round(sum(costs), 4) if costs else None,
                "local": all(u.get("local") for u in usages)}

    @safe
    def ai_plan(self, path, deep=False, deep_mode="full"):
        client = self._need_ai()
        deep_moves, deep_result = self._deep_first(path, deep_mode) if deep else ([], None)
        client.reset_usage()
        node = self._node(path)
        if not self._profile or self._profile["path"] != node.path:
            self._profile = organiser.profile_folder(node, node.path)
        plan = organiser.ai_organise(client, self._profile)
        plan["model"] = client.model
        plan["usage"] = self._sum_usage(self._usage(client), deep_result and deep_result.get("usage"))
        if deep:
            self._merge(plan, deep_moves, deep_result)
        self._plan = (node.path, plan)
        return plan

    @safe
    def rule_plan(self, path, deep=False, deep_mode="full"):
        deep_moves, deep_result = self._deep_first(path, deep_mode) if deep else ([], None)
        node = self._node(path)
        if not self._profile or self._profile["path"] != node.path:
            self._profile = organiser.profile_folder(node, node.path)
        plan = organiser.rule_plan(node, self._profile)
        if deep:
            self._merge(plan, deep_moves, deep_result)
            plan["usage"] = deep_result.get("usage")
        self._plan = (node.path, plan)
        return plan

    # ---------------------------------------------------------------- smart document classification
    def _classify_scan(self, path):
        """Sort the folder's own documents into: decided by name, cached, needs AI on the name, needs a read."""
        node = self._node(path)
        cache = content.load_cache()
        docs, cloud, ignored = [], 0, 0
        for name, size, mtime, cloud_only in node.files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in content.DOC_EXTS:
                ignored += 1                      # images, videos, installers, archives, code...
                continue
            if cloud_only:
                cloud += 1                        # never opened: that would download it
                continue
            f = {"name": name, "path": os.path.join(node.path, name), "ext": ext, "size": size, "mtime": mtime}
            rule = content.rule_classify(name)
            hit = cache.get(content.cache_key(f["path"], size, mtime))
            if rule:
                f.update(category=rule, method="name", summary="")
            elif hit:
                f.update(category=hit["category"], summary=hit["summary"], method=hit["method"])
            elif content.is_opaque(name):
                f["tier"] = "unreadable" if ext in content.LEGACY else "read"
            else:
                f["tier"] = "names"
            docs.append(f)
        return node, docs, cloud, ignored

    def _ollama_available(self):
        try:
            return bool(Ollama(self._settings.get("ollama_host")).models())
        except LLMError:
            return False

    @safe
    def classify_preview(self, path):
        node, docs, cloud, ignored = self._classify_scan(path)
        names = [f["name"] for f in docs if f.get("tier") == "names"]
        reads = [f for f in docs if f.get("tier") == "read"]
        # Excerpts are read locally now (nothing leaves the PC) so the token estimate is real; reused by the run.
        self._snippets = {}
        for f in reads:
            try:
                self._snippets[f["path"]] = content.extract_snippet(f["path"])
            except (OSError, ValueError) as e:
                self._snippets[f["path"]] = e
        readable = [f for f in reads if isinstance(self._snippets.get(f["path"]), str) and self._snippets[f["path"]]]
        client = self._llm if self._ai_enabled else None
        estimate = None
        if client and (names or readable):
            prompts = content.names_prompts(names) + content.content_prompts(
                [(f["name"], self._snippets[f["path"]]) for f in readable])
            counts = [client.count_tokens(s, u) for s, u in prompts]
            t_in, t_out = sum(c[0] for c in counts), 25 * len(names) + 40 * len(readable)
            p = self._price(client)
            estimate = {"input": t_in, "output": t_out, "exact": all(c[1] for c in counts), "requests": len(prompts),
                        "cost": round(t_in * p[0] / 1e6 + t_out * p[1] / 1e6, 4) if p else None}
        cloud_ai = bool(client) and not client.is_local
        return {
            "folder": node.path, "name": node.name, "docs": len(docs),
            "by_name": sum(1 for f in docs if f.get("method") == "name"),
            "cached": sum(1 for f in docs if f.get("method") in ("ai-name", "read")),
            "names": names, "reads": [f["name"] for f in readable],
            "no_text": [f["name"] for f in reads if self._snippets.get(f["path"]) == ""],
            "unreadable": [f["name"] for f in docs if f.get("tier") == "unreadable"]
                          + [f["name"] for f in reads if isinstance(self._snippets.get(f["path"]), Exception)],
            "cloud_skipped": cloud, "ignored": ignored, "ai": bool(client),
            "local": not cloud_ai, "label": client.label if client else None, "model": client.model if client else None,
            "estimate": estimate, "ollama": self._ollama_available() if cloud_ai else False,
        }

    @safe
    def classify_run(self, path, mode="full"):
        """mode: full (names + read where needed) | names_only (never read file contents) | local (use Ollama)."""
        node, docs, cloud, ignored = self._classify_scan(path)
        client = None
        if self._ai_enabled:
            if mode == "local":
                client = Ollama(self._settings.get("ollama_host"), self._settings.get("ollama_model"))
                client.models()
            else:
                client = self._need_ai()
            client.reset_usage()
        cache = content.load_cache()
        progress = lambda stage, done, total: self._emit("classify_progress", {"stage": stage, "done": done, "total": total})

        def remember(f):
            cache[content.cache_key(f["path"], f["size"], f["mtime"])] = {
                "category": f["category"], "summary": f["summary"], "method": f["method"]}

        named = [f for f in docs if f.get("tier") == "names"]
        if client and named:
            sizes = [min(content.NAMES_BATCH, len(named) - s) for s in range(0, len(named), content.NAMES_BATCH)]
            results = content.ask(client, content.names_prompts([f["name"] for f in named]), sizes,
                                  content.NAMES_MAX_TOKENS, progress, "Classifying by name")
            for f, (cat, summary) in zip(named, results):
                f.update(category=cat, summary=summary, method="ai-name")
                remember(f)

        reads = [f for f in docs if f.get("tier") == "read"]
        if client and reads and mode != "names_only":
            snippets = getattr(self, "_snippets", {})
            items, readable = [], []
            for f in reads:
                snip = snippets.get(f["path"])
                if snip is None:
                    try:
                        snip = content.extract_snippet(f["path"])
                    except (OSError, ValueError) as e:
                        snip = e
                if isinstance(snip, Exception):
                    f.update(method="unreadable", summary=str(snip))
                elif not snip:
                    f.update(method="no-text", summary="No text inside - probably a scanned image")
                else:
                    items.append((f["name"], snip))
                    readable.append(f)
            sizes = [min(content.CONTENT_BATCH, len(items) - s) for s in range(0, len(items), content.CONTENT_BATCH)]
            results = content.ask(client, content.content_prompts(items), sizes, content.CONTENT_MAX_TOKENS,
                                  progress, "Reading documents with unclear names")
            for f, (cat, summary) in zip(readable, results):
                f.update(category=cat, summary=summary, method="read")
                remember(f)
        content.save_cache(cache)

        groups = {}
        unrecognised = []
        for f in docs:
            entry = {"name": f["name"], "path": f["path"], "size": f["size"], "summary": f.get("summary", ""),
                     "method": f.get("method") or ("unreadable" if f.get("tier") == "unreadable" else "unrecognised")}
            if f.get("category"):
                groups.setdefault(f["category"], []).append(entry)
            else:
                unrecognised.append(entry)
        out_groups = [{"key": k, "label": content.CATEGORIES[k][0], "folder": content.CATEGORIES[k][1],
                       "files": sorted(v, key=lambda e: e["name"].lower())}
                      for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))]
        # Same shape as an organisation plan, so "Organise for me" (preview + undo) can apply it.
        moves = [{"what": e["name"], "to": g["folder"], "why": g["label"]} for g in out_groups for e in g["files"]]
        self._plan = (node.path, {"summary": "", "structure": [{"folder": g["folder"], "purpose": g["label"]} for g in out_groups],
                                  "moves": moves, "issues": [], "tips": [], "model": "classification"})
        self._preview = None
        self._cls_last = {"folder": node.path, "unrecognised": {e["name"]: e["method"] for e in unrecognised}}
        return {"folder": node.path, "name": node.name, "groups": out_groups, "unrecognised": unrecognised,
                "cloud_skipped": cloud, "ignored": ignored, "model": client.model if client else None,
                "label": client.label if client else None, "usage": self._usage(client) if client else None}

    @safe
    def preview_organise(self, path):
        node = self._node(path)
        if not self._plan or self._plan[0] != node.path:
            raise RuntimeError("Make a plan for this folder first.")
        self._preview = mover.preview(node, node.path, self._plan[1])
        return {k: v for k, v in self._preview.items() if k != "assigned"}

    @safe
    def apply_organise(self, path, names):
        p = self._preview
        if not p or p["folder"] != path:
            raise RuntimeError("The preview is out of date - open it again.")
        moves = [(n, p["assigned"][n]) for n in names if n in p["assigned"]]   # only what the preview offered
        before = self._loose_files(path)
        result = mover.apply(path, moves, lambda done, total: self._emit("organise_progress",
                                                                        {"done": done, "total": total}))
        achieved = {}
        for item in result["done"]:
            achieved[item["to"]] = achieved.get(item["to"], 0) + 1
        result["achieved"] = [{"folder": k, "count": v} for k, v in sorted(achieved.items(), key=lambda kv: -kv[1])]
        result["left"] = self._left_behind(path, p, set(names), result["failed"])
        result["before"] = len(before)
        self._preview = self._plan = self._profile = None
        if self._root is not None:
            refresh_path(self._root, path)
        return result

    @staticmethod
    def _loose_files(path):
        try:
            with os.scandir(path) as it:
                return [e for e in it if e.is_file(follow_symlinks=False)]
        except OSError:
            return []

    def _left_behind(self, path, preview, ticked, failed):
        """Every file still loose in the folder after organising, with the reason it stayed."""
        failed = {f["name"]: f["error"] for f in failed}
        skipped = {s["name"]: s["reason"] for s in preview.get("skipped", [])}
        unclassified = (self._cls_last or {}).get("unrecognised", {}) \
            if (getattr(self, "_cls_last", None) or {}).get("folder") == path else {}
        why_unclassified = {"no-text": "couldn't be classified - no readable text inside (probably a scan)",
                            "unreadable": "couldn't be classified - old or damaged format the app can't read",
                            "unrecognised": "couldn't be classified - the name says nothing and it wasn't read"}
        left = []
        for e in self._loose_files(path):
            name = e.name
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if name in failed:
                reason = f"couldn't be moved - {failed[name]}"
            elif name in preview["assigned"] and name not in ticked:
                reason = "you unticked it in the preview"
            elif name in skipped:
                reason = f"left on purpose - {skipped[name]}"
            elif st.st_file_attributes & (0x2 | 0x4):
                reason = "left on purpose - hidden or system file"
            elif name in unclassified:
                reason = why_unclassified.get(unclassified[name], why_unclassified["unrecognised"])
            else:
                reason = "the plan didn't suggest a place for it"
            warn = None
            if name.lower().endswith(".pdf") and st.st_size < 1024:
                warn = f"only {st.st_size} bytes - possibly a broken or incomplete download"
            left.append({"name": name, "path": e.path, "size": st.st_size, "reason": reason, "warn": warn})
        left.sort(key=lambda f: (f["reason"], f["name"].lower()))
        return left

    @safe
    def undo_organise(self, undo_id):
        result = mover.undo(undo_id)
        self._profile = None
        if self._root is not None:
            refresh_path(self._root, result["folder"])
        return result


# ---------------------------------------------------------------- dev server

def serve(api, port=SERVE_PORT):
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=UI_DIR, **kwargs)

        def log_message(self, *args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")   # always serve the latest UI files while developing
            super().end_headers()

        def _json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/api/_events"):
                return self._json(api._drain_events())
            return super().do_GET()

        def do_POST(self):
            name = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
            method = getattr(api, name, None) if name and not name.startswith("_") else None
            if not callable(method):
                return self._json({"__error__": f"Unknown method {name}"}, 404)
            length = int(self.headers.get("Content-Length", 0))
            args = json.loads(self.rfile.read(length) or b"[]")
            self._json(method(*args))

    print(f"Serving on http://127.0.0.1:{port}/?serve=1", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def start_tray(api):
    """Notification-area icon, so the assistant keeps monitoring while the window is closed."""
    import pystray
    from PIL import Image
    from pystray import Menu, MenuItem as Item

    def toggle_monitor():
        api._settings["agent_monitor"] = not api._settings.get("agent_monitor", True)
        api._save_settings()
    menu = Menu(
        Item(f"Open {APP_NAME}", lambda: api._show(), default=True),
        Item("Assistant", lambda: (api._show(), api._emit("agent_show", {"view": "assistant"}))),
        Item("Monitor in the background", toggle_monitor, checked=lambda item: bool(api._settings.get("agent_monitor", True))),
        Menu.SEPARATOR,
        Item("Quit", lambda: api._quit()),
    )
    icon = pystray.Icon("SystemUtilities", Image.open(ICON), f"{APP_NAME} - Jarvis is watching your PC", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def main():
    if "--serve" not in sys.argv and agent_server.show_running_copy():
        return                                  # already running (maybe in the tray): it was brought to the front
    api = Api()
    api.agent = agent_mod.Agent(api)
    # A dev --serve run next to the real app mustn't take over agent.json (the Dashboard and a second start use it).
    agent_server.start(api.agent, on_show=lambda: api._show(),
                       publish="--serve" not in sys.argv or not agent_server.running_copy())
    if "--no-monitor" not in sys.argv:
        api.agent.start_monitor()
    if "--no-voice" not in sys.argv:
        try:
            import voice_host
            api.voice = voice_host.VoiceHost(api, api.agent)
            api.voice.start()
        except Exception:
            api.voice = None                    # voice packages missing: the typed assistant still works
    if "--serve" in sys.argv:
        return serve(api)
    import webview
    # Own taskbar identity, so Windows shows our icon instead of grouping the window under Python.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SystemUtilities.App")
    title = APP_NAME + (" (Administrator)" if quickclean.is_admin() else "")
    window = webview.create_window(
        title, url=os.path.join(UI_DIR, "index.html"), js_api=api, hidden="--tray" in sys.argv,
        width=1400, height=860, min_size=(1000, 620),
        background_color="#0e1015" if windows_dark() else "#f4f6fb")
    api._window = window
    try:
        api._tray = start_tray(api)
    except Exception:
        api._tray = None                        # no tray: closing the window quits as before

    def closing():
        # With background monitoring on, the X only hides the window - the tray icon's Quit really exits.
        if api._quitting or api._tray is None or not api._settings.get("agent_monitor", True):
            return True
        threading.Thread(target=api._hide, daemon=True).start()
        return False
    window.events.closing += closing
    window.events.closed += lambda: api._quit()
    webview.start(debug="--debug" in sys.argv, icon=ICON)


if __name__ == "__main__":
    main()
