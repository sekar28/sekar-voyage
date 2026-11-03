"""Dashboard - a voice-controlled AI dashboard for the second monitor (pywebview, same stack as StorageAnalyzer).

    python app.py            open fullscreen on the second monitor
    python app.py --window   open as a normal window instead
    python app.py --debug    same as the first, with WebView dev tools
    python app.py --serve    serve the UI at http://127.0.0.1:8770/?serve=1 (for development in a browser)

A tray icon (and Ctrl+Alt+D) brings the dashboard back; starting it again while it runs does the same.
"""

import os

# The Intel Fortran runtime inside the speech libraries quits the whole process on a console close / Ctrl+C
# event unless told not to - which killed the dashboard when the terminal that started it closed.
os.environ.setdefault("FOR_DISABLE_CONSOLE_CTRL_HANDLER", "1")

import ctypes
import functools
import json
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import alarm
import assistant
import pcagent
import secrets_store
import telegram_link
import tray
import tts
import voice
import widgetsmith
from llm import DEFAULT_HOST, LLMError, Ollama, OpenAICompatible
from widgets import SourceError, agenda, cyber, music, news, pcmon, photos, stocks, tasks, timers, weather, whatsapp

APP_NAME = "Sekar's Dashboard"           # what you see; the data folder and internal ids keep "Dashboard"
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local")), "Dashboard")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
PHOTO_CACHE = os.path.join(DATA_DIR, "photo_cache")
VOICES_DIR = os.path.join(DATA_DIR, "voices")
WEB_STORAGE = os.path.join(DATA_DIR, "webview")      # keeps WhatsApp Web linked between runs
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
ICON = os.path.join(UI_DIR, "dashboard.ico")
INSTANCE_PATH = os.path.join(DATA_DIR, "instance.json")   # port of the running copy, so a second start shows it
WIDGET_STORE = widgetsmith.Store(os.path.join(DATA_DIR, "custom_widgets"))   # widgets made in Widget Studio
WIDGET_SDK = os.path.join(UI_DIR, "widget-sdk.js")
SERVE_PORT = 8770
VK_SPACE, VK_D = 0x20, 0x44
WHATSAPP_URL = "https://web.whatsapp.com/"
WHATSAPP_POLL = 20                            # seconds between chat-list reads
YOUTUBE_SIGNIN = "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com/"

DEFAULT_SETTINGS = {
    # AI - same fields as StorageAnalyzer, so the two apps are set up the same way
    "provider": "ollama",                     # ollama | openai | anthropic
    "ollama_host": DEFAULT_HOST, "ollama_model": None,
    "openai_base": "https://api.openai.com/v1", "openai_name": "OpenAI", "openai_model": "",
    "anthropic_model": "claude-haiku-5-5",    # quick and inexpensive for short voice commands
    "ai_on": True,
    # tiles
    "photo_folders": [], "photo_include_cloud": True, "photo_seconds": 12, "photo_cache_mb": 1500,
    "watchlist": ["^NSEI", "^BSESN", "^GSPC", "^IXIC", "^DJI", "AAPL", "MSFT", "NVDA", "BTC-USD"],
    "idle_minutes": 10,                       # show the slideshow full screen after this long untouched; 0 = never
    "whatsapp_watch": True,                   # keep WhatsApp Web open in the background to show unread chats
    # Widget positions on a 12 x 8 grid. Widgets not listed are hidden (and not polled).
    "layout": [{"id": "photos", "x": 0, "y": 0, "w": 5, "h": 8}, {"id": "music", "x": 5, "y": 0, "w": 4, "h": 4},
               {"id": "stocks", "x": 9, "y": 0, "w": 3, "h": 4}, {"id": "cyber", "x": 5, "y": 4, "w": 4, "h": 4},
               {"id": "whatsapp", "x": 9, "y": 4, "w": 3, "h": 2}, {"id": "assistant", "x": 9, "y": 6, "w": 3, "h": 2}],
    "news_feeds": news.DEFAULT_FEEDS,
    "timers": [],                             # running timers / reminders (survive restarts)
    # Task list + Telegram link. The bot token is only ever the "telegram" secret in Credential Manager.
    "tasks": [], "tasks_imported": False,     # tasks_imported: the old Widget Studio "Task Aging List" was copied over
    "telegram_chat_id": None,                # the one private chat allowed to command the bot (set by pairing)
    "tasks_repeat_hours": 12,                 # overdue tasks nag again after this many hours until completed
    "tasks_digest_time": "", "tasks_digest_last": "",   # daily Telegram summary of pending tasks; blank = off
    "duck_level": 20,                         # music volume % while you speak or it replies; 0 = pause
    "briefing_time": "", "briefing_days": [0, 1, 2, 3, 4], "briefing_last": "",
    "world_clocks": [["New York", "America/New_York"], ["London", "Europe/London"]],   # [label, IANA time zone]
    "weather_city": "", "weather_lat": None, "weather_lon": None, "weather_label": "", "weather_units": "celsius",
    # voice
    "voice_on": True, "wake_word": "hey_jarvis",
    "stt_mode": "cloud", "stt_base": voice.STT_PRESETS[0]["base"], "stt_model": voice.STT_PRESETS[0]["model"],
    "whisper_model": "auto", "whisper_device": "auto", "stt_pause": voice.DEFAULT_PAUSE,
    "speak_replies": True, "tts_voice": tts.DEFAULT_VOICE,
    "screen": None,                           # index into webview.screens; None = pick the second monitor
    # Widget Studio's agent. Its key is only ever the "widget_agent" secret in Credential Manager (this PC, this user).
    "widget_provider": "gemini",              # gemini | openai | anthropic | ollama
    "widget_base": "", "widget_model": "auto",
    "widget_reuse_key": False,                # use a key already saved on this PC for the same provider (opt-in)
    "widget_model_last": "",                  # Gemini "auto": the model that last built a widget, tried first
}
WIDGET_PROVIDERS = {"gemini": "Google Gemini", "openai": "OpenAI-compatible", "anthropic": "Claude",
                    "ollama": "Ollama (local)"}
OPENAI_PRESETS = [
    {"name": "OpenAI", "base": "https://api.openai.com/v1"},
    {"name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai"},
    {"name": "OpenRouter", "base": "https://openrouter.ai/api/v1"},
    {"name": "Groq", "base": "https://api.groq.com/openai/v1"},
    {"name": "Mistral", "base": "https://api.mistral.ai/v1"},
    {"name": "DeepSeek", "base": "https://api.deepseek.com/v1"},
    {"name": "LM Studio (local)", "base": "http://localhost:1234/v1"},
]
SECRETS = ("openai", "anthropic", "youtube", "stt", "widget_agent", "telegram")   # openai/anthropic are shared with StorageAnalyzer
GRID_W, GRID_H = 12, 8
WIDGETS = {   # id: (name, min w, min h)
    "photos": ("Photos", 2, 2), "music": ("Music", 3, 3), "stocks": ("Markets", 3, 2), "cyber": ("Cyber threats", 3, 2),
    "whatsapp": ("WhatsApp", 2, 2), "assistant": ("Assistant", 2, 2), "weather": ("Weather", 3, 2),
    "pc": ("PC monitor", 2, 2), "calendar": ("Calendar", 2, 2), "timers": ("Timers", 2, 2), "news": ("News", 3, 2),
    "tasks": ("Tasks", 2, 2),
}


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds():
    """Seconds since the last keyboard / mouse input anywhere on the PC."""
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


def all_widgets():
    """Built-in widgets plus the ones made in Widget Studio (ids "cw:<id>"): id -> (name, min w, min h)."""
    out = dict(WIDGETS)
    for m in WIDGET_STORE.list():
        out["cw:" + m["id"]] = (m.get("name", "Widget"), m.get("min_w", 2), m.get("min_h", 2))
    return out


def clean_layout(layout):
    """Keep known widgets, inside the grid, at least their minimum size, without overlaps (later ones lose)."""
    known = all_widgets()
    taken, out = set(), []
    for item in layout or []:
        wid = item.get("id")
        if wid not in known or any(o["id"] == wid for o in out):
            continue
        _, mw, mh = known[wid]
        w = max(mw, min(GRID_W, int(item.get("w", mw))))
        h = max(mh, min(GRID_H, int(item.get("h", mh))))
        x = max(0, min(GRID_W - w, int(item.get("x", 0))))
        y = max(0, min(GRID_H - h, int(item.get("y", 0))))
        cells = {(cx, cy) for cx in range(x, x + w) for cy in range(y, y + h)}
        if cells & taken:
            continue
        taken |= cells
        out.append({"id": wid, "x": x, "y": y, "w": w, "h": h})
    return out


def safe(fn):
    """Return errors to JavaScript as {"__error__": message} instead of raising across the bridge."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            return {"__error__": str(e) or type(e).__name__}
    return wrapper


class Api:
    """Methods callable from JavaScript (names starting with _ are not exposed)."""

    def __init__(self):
        self._window = None
        self._wa = None                       # WhatsApp Web window
        self._screen = None
        self._fullscreen = False
        self._tray = None
        self._quitting = False
        self._events = []
        self._events_lock = threading.Lock()
        self._settings = self._load_settings()
        self._settings["tasks"] = list(self._settings.get("tasks") or [])    # not the shared default list
        self._import_old_task_widget()
        self._llm, self._llm_error = None, None
        self._rebuild_llm()
        self._ui = {"volume": 60, "song": None, "maximized": None}
        self._photos, self._photos_scanning = [], False
        self._renders = 0
        self._speaker = tts.Speaker(VOICES_DIR, self._settings.get("tts_voice"))
        self._voice = None
        self._voice_state = {"state": "off", "detail": None}
        self._wa_chats = {"state": "off", "chats": []}
        self._explained = {}                  # article link -> AI explanation
        self._yt_signed_in = None             # None = not checked yet
        self._timers_lock = threading.Lock()
        self._bell = alarm.Bell()
        self._alarm_ducked = False
        self._followup_until = 0              # System Utilities asked a question: the next request is the answer
        self._agent_expects = threading.local()
        self._studio = {}                     # Widget Studio sessions: session id -> {id, existing, history, draft}
        self._widget_models = None            # Gemini models to try, best first (looked up once)
        self._tasks_lock = threading.Lock()
        self._tasks_checked = 0
        self._tg = telegram_link.Bot(lambda: secrets_store.get_secret("telegram"),
                                     lambda: self._settings.get("telegram_chat_id"), self._set_telegram_chat,
                                     self._tg_text, lambda: self._quitting)
        self._tg.start()
        threading.Thread(target=self._tasks_loop, daemon=True, name="tasks").start()   # own thread: sending can be slow
        pcagent.Poller(self._on_agent_event, lambda: self._quitting).start()
        threading.Thread(target=self._clock_loop, daemon=True).start()
        threading.Thread(target=self._scan_photos, daemon=True).start()

    # ---------------------------------------------------------------- plumbing
    def _emit(self, event, data=None):
        if self._window is not None:
            try:
                self._window.evaluate_js(f"App.on({json.dumps(event)}, {json.dumps(data)})")
            except Exception:
                pass                          # window closing
        else:
            with self._events_lock:
                self._events.append([event, data])
                del self._events[:-200]

    def _drain_events(self):
        with self._events_lock:
            events, self._events = self._events, []
        return events

    def _ui_do(self, do, **data):
        self._emit("ui", {"do": do, **data})

    # ---------------------------------------------------------------- window
    def _hwnd(self):
        try:
            return self._window.native.Handle.ToInt64()
        except Exception:
            return None

    def _show(self):
        """Un-hide / un-minimize the dashboard and put it above other windows on its screen."""
        if self._window is None:
            return
        try:
            self._window.show()
        except Exception:
            pass
        hwnd = self._hwnd()
        if hwnd:
            user32 = ctypes.windll.user32
            SW_SHOWMAXIMIZED, SW_RESTORE = 3, 9
            if user32.IsIconic(hwnd) or self._fullscreen:
                # pywebview's fullscreen is a borderless maximized window, so bring it back maximized
                user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED if self._fullscreen else SW_RESTORE)
            HWND_TOPMOST, HWND_NOTOPMOST, flags = -1, -2, 0x0001 | 0x0002   # SWP_NOSIZE | SWP_NOMOVE
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            user32.SetForegroundWindow(hwnd)

    def _hide(self):
        if self._window is not None:
            self._window.hide()

    def _quit(self):
        if self._quitting:                    # tray Quit closes the window, whose closed event lands here again
            return
        self._quitting = True
        if self._voice is not None:
            self._voice.stop()
        if self._tray is not None:
            self._tray.stop()
        try:
            os.remove(INSTANCE_PATH)
        except OSError:
            pass
        for w in (self._wa, self._window):
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass

    # ---------------------------------------------------------------- settings
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except (OSError, ValueError):
            return dict(DEFAULT_SETTINGS)

    def _save_settings(self):
        os.makedirs(DATA_DIR, exist_ok=True)
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
            if isinstance(self._llm, Ollama) and not self._llm.model:
                threading.Thread(target=self._pick_ollama_model, daemon=True).start()
        except Exception as e:
            self._llm, self._llm_error = None, str(e)

    def _pick_ollama_model(self):
        try:
            self._llm.models()                # selects a preferred installed model
        except LLMError as e:
            self._llm_error = str(e)

    def _ai(self):
        return self._llm if self._settings.get("ai_on") else None

    def _settings_view(self):
        from llm_anthropic import SUGGESTED
        s = self._settings
        return {**s, **{f"{k}_key": secrets_store.hint(secrets_store.get_secret(k)) for k in SECRETS},
                "presets": OPENAI_PRESETS, "anthropic_models": SUGGESTED, "stt_presets": voice.STT_PRESETS,
                "wake_words": voice.WAKE_WORDS, "whisper_models": voice.WHISPER_MODELS, "default_photo_folders": photos.default_folders(),
                "screens": self._screens(), "ai_label": self._llm.label if self._llm else None,
                "ai_model": getattr(self._llm, "model", None), "ai_error": self._llm_error,
                "tts_engine": self._speaker.engine, "voice_missing": voice.missing_packages(),
                "local_whisper": voice.LocalWhisper().available(), "stt_modes": voice.STT_MODES,
                "whisper_devices": voice.WHISPER_DEVICES, "youtube_signed_in": self._yt_signed_in,
                "widgets": {k: {"name": v[0], "min_w": v[1], "min_h": v[2], "custom": k.startswith("cw:")}
                            for k, v in all_widgets().items()},
                "custom_widgets": WIDGET_STORE.list(),
                "widget_providers": WIDGET_PROVIDERS, "widget_reuse_available": bool(self._reusable_key()),
                "grid": [GRID_W, GRID_H], "default_layout": DEFAULT_SETTINGS["layout"],
                "calendar_names": [name for name, _ in self._calendars()],
                "whisper_status": self._voice.local.status() if self._voice is not None else "voice off"}

    @staticmethod
    def _screens():
        try:
            import webview
            return [{"i": i, "label": f"{s.width}×{s.height} at {s.x},{s.y}"} for i, s in enumerate(webview.screens)]
        except Exception:
            return []

    @safe
    def settings_get(self):
        return self._settings_view()

    @safe
    def settings_save(self, form):
        s = dict(self._settings)
        for key in DEFAULT_SETTINGS:
            if key in form:
                s[key] = form[key]
        if s["provider"] not in ("ollama", "openai", "anthropic"):
            raise ValueError("Unknown provider.")
        if s["widget_provider"] not in WIDGET_PROVIDERS:
            raise ValueError("Unknown widget agent provider.")
        s["widget_reuse_key"] = bool(s.get("widget_reuse_key"))
        s["photo_folders"] = [p for p in s.get("photo_folders") or [] if p.strip()]
        s["watchlist"] = [x.strip().upper() for x in s.get("watchlist") or [] if x.strip()]
        s["layout"] = clean_layout(s.get("layout"))
        s["news_feeds"] = [[str(n).strip(), str(u).strip()] for n, u in (s.get("news_feeds") or [])
                           if str(u).strip().startswith("http")] or news.DEFAULT_FEEDS
        s["duck_level"] = max(0, min(100, int(s.get("duck_level") or 0)))
        try:
            s["tasks_repeat_hours"] = max(1.0, min(168.0, float(s.get("tasks_repeat_hours") or 12)))
        except (TypeError, ValueError):
            s["tasks_repeat_hours"] = 12.0
        s["tasks_digest_time"] = str(s.get("tasks_digest_time") or "")[:5]
        s["world_clocks"] = [[str(label).strip() or str(tz).split("/")[-1].replace("_", " "), str(tz).strip()]
                             for label, tz in (s.get("world_clocks") or []) if str(tz).strip()][:4]
        if "calendars_new" in form:           # "Name | https://...ics" per line; stored like a key
            cals = []
            for line in str(form["calendars_new"]).splitlines():
                name, _, url = line.rpartition("|") if "|" in line else ("", "", line)
                url = url.strip().replace("webcal://", "https://")
                if url.startswith("https://"):
                    cals.append([name.strip() or f"Calendar {len(cals) + 1}", url])
            if cals:
                secrets_store.set_secret("calendars", json.dumps(cals))
        if form.get("calendars_clear"):
            secrets_store.delete_secret("calendars")
        s["weather_city"] = (s.get("weather_city") or "").strip()
        if s["weather_city"] != self._settings.get("weather_city") or (s["weather_city"] and s.get("weather_lat") is None):
            if s["weather_city"]:
                place = weather.find_place(s["weather_city"])     # raises if the city isn't found
                s.update(weather_lat=place["lat"], weather_lon=place["lon"], weather_label=place["label"])
            else:
                s.update(weather_lat=None, weather_lon=None, weather_label="")
        for name in SECRETS:                  # a typed key replaces the stored one; blank keeps it
            if form.get(f"{name}_key_new"):
                secrets_store.set_secret(name, form[f"{name}_key_new"].strip())
            if form.get(f"{name}_key_clear"):
                secrets_store.delete_secret(name)
        old = self._settings
        self._settings = s
        self._save_settings()
        self._rebuild_llm()
        if form.get("telegram_key_clear"):
            self._tg.unpair()                 # no token, no link
        if form.get("telegram_key_new") or form.get("telegram_key_clear"):
            self._tg.reload()
        self._widget_models = None            # provider / model / key may have changed
        if (old["photo_folders"], old["photo_include_cloud"]) != (s["photo_folders"], s["photo_include_cloud"]):
            threading.Thread(target=self._scan_photos, daemon=True).start()
        if old["tts_voice"] != s["tts_voice"]:
            self._speaker = tts.Speaker(VOICES_DIR, s["tts_voice"])
        if (old["voice_on"], old["wake_word"]) != (s["voice_on"], s["wake_word"]):
            self._restart_voice()
        if not s["speak_replies"]:
            self._speaker.stop()
        if old.get("weather_lat") != s.get("weather_lat") or old.get("weather_units") != s.get("weather_units"):
            self._ui_do("weather")
        return self._settings_view()

    @safe
    def weather_find(self, city):
        return weather.find_place(city)

    @safe
    def layout_save(self, layout):
        self._settings["layout"] = clean_layout(layout)
        self._save_settings()
        return self._settings["layout"]

    def _shown(self, wid):
        return any(item["id"] == wid for item in self._settings.get("layout", []))

    # ---------------------------------------------------------------- Widget Studio (AI-made widgets)
    def _reusable_key(self, provider=None):
        """A key already saved on this PC for the widget agent's provider (only used if you tick the box)."""
        s = self._settings
        provider = provider or s.get("widget_provider", "gemini")
        if provider == "gemini":
            if voice.is_gemini(s.get("stt_base")) and secrets_store.get_secret("stt"):
                return secrets_store.get_secret("stt")
            if voice.is_gemini(s.get("openai_base")):
                return secrets_store.get_secret("openai")
            return None
        return secrets_store.get_secret(provider) if provider in ("openai", "anthropic") else None

    def _widget_agent(self):
        s = self._settings
        provider = s.get("widget_provider", "gemini")
        key = secrets_store.get_secret("widget_agent") or (self._reusable_key() if s.get("widget_reuse_key") else None)
        choice = s.get("widget_model") or "auto"
        if provider == "ollama":
            host = s.get("ollama_host") or DEFAULT_HOST
            model = None if choice == "auto" else choice
            if model is None:                 # auto: the model the main AI runs, else Ollama's best installed one
                main = self._llm if isinstance(self._llm, Ollama) else None
                model = (main.model if main else None) or s.get("ollama_model")
                if not model:
                    probe = Ollama(host)
                    probe.models()            # raises "Is Ollama running?" if it isn't
                    model = probe.model
            return widgetsmith.Agent(lambda m: Ollama(host, m), [model])
        if not key:
            raise widgetsmith.NeedKey()
        if provider == "anthropic":
            from llm_anthropic import Claude
            return widgetsmith.Agent(lambda m: Claude(key, m), ["claude-opus-5-5" if choice == "auto" else choice])
        if provider == "openai":
            base = s.get("widget_base") or s.get("openai_base")
            model = None if choice == "auto" else choice
            if model is None:                 # auto: the service's best everyday chat model (same pick as AI settings)
                probe = OpenAICompatible(base, key)
                probe.models()
                model = probe.model
            return widgetsmith.Agent(lambda m: OpenAICompatible(base, key, m), [model])
        if self._widget_models is None:       # Gemini: best Pro first, then Flash (looked up once per run)
            self._widget_models = widgetsmith.gemini_models(
                OpenAICompatible(widgetsmith.GEMINI_BASE, key, "gemini-flash-latest", "Google Gemini"), choice)
            last = s.get("widget_model_last")   # the model that worked last time, even before a restart
            if choice == "auto" and last in self._widget_models:
                self._widget_models.remove(last)
                self._widget_models.insert(0, last)
        # The Agent reorders this same list in place, so the model that last worked is tried first next time.
        return widgetsmith.Agent(lambda m: OpenAICompatible(widgetsmith.GEMINI_BASE, key, m, "Google Gemini",
                                                            reasoning_effort="low"), self._widget_models)

    def _session(self, sid):
        sess = self._studio.get(sid)
        if sess is None:
            raise RuntimeError("That Widget Studio session has ended - open the Studio again.")
        return sess

    def _secret_name(self, wid, name):
        return f"widget/{wid}/{name}"

    @safe
    def widget_studio_open(self, wid=None):
        """Start a Studio session: a new widget, or editing a kept one (wid)."""
        sid = widgetsmith.Store.new_id()
        if wid:
            draft = {"manifest": WIDGET_STORE.manifest(wid), "html": WIDGET_STORE.html(wid)}
            sess = {"id": wid, "existing": True, "history": WIDGET_STORE.history(wid), "draft": draft}
        else:
            sess = {"id": widgetsmith.Store.new_id(), "existing": False, "history": [], "draft": None}
        self._studio[sid] = sess
        return self._studio_view(sid)

    def _studio_view(self, sid):
        sess = self._session(sid)
        d = sess["draft"]
        return {"session": sid, "id": sess["id"], "existing": sess["existing"], "history": sess["history"],
                "manifest": d["manifest"] if d else None,
                "keys": {n: bool(secrets_store.get_secret(self._secret_name(sess["id"], n)))
                         for n in (d["manifest"]["secrets"] if d else [])}}

    @safe
    def widget_studio_send(self, sid, text=None, problems=None):
        """One agent round: a request / change (text), or fixing problems the preview reported."""
        sess = self._session(sid)
        try:
            agent = self._widget_agent()
        except widgetsmith.NeedKey:
            return {"need_key": True, "provider": WIDGET_PROVIDERS[self._settings.get("widget_provider", "gemini")],
                    "reuse_available": bool(self._reusable_key())}
        if text:
            sess["history"].append({"role": "user", "text": str(text)[:2000]})
        get_key = lambda name: secrets_store.get_secret(self._secret_name(sess["id"], name))
        agent.get_secret = get_key
        agent.on_progress = lambda msg: self._emit("studio_progress", {"session": sid, "text": msg})
        out = agent.build(sess["history"][:-1] if text else sess["history"], text, sess["draft"], problems)
        rounds = 0
        while "html" in out and rounds < 3:   # rules broken or a data source that doesn't work: fix before you see it
            found = widgetsmith.static_problems(out["html"], out["manifest"])
            if not found:
                self._emit("studio_progress", {"session": sid, "text": "Testing the widget's data sources…"})
                found = widgetsmith.check_sources(out["html"], out["manifest"], get_key)
            if not found:
                break
            rounds += 1
            self._emit("studio_progress", {"session": sid, "text": f"Fixing: {found[0][:140]}"})
            out = agent.build(sess["history"], None, {"manifest": out["manifest"], "html": out["html"]}, found)
        if "question" in out:
            sess["history"].append({"role": "agent", "text": out["question"]})
            return {**self._studio_view(sid), "question": out["question"]}
        left = widgetsmith.static_problems(out["html"], out["manifest"]) or \
            widgetsmith.check_sources(out["html"], out["manifest"], get_key)
        sess["draft"] = {"manifest": out["manifest"], "html": out["html"]}
        sess["history"].append({"role": "agent", "text": out["note"] or "Done."})
        if (self._settings.get("widget_provider", "gemini") == "gemini" and out.get("model")
                and out["model"] != self._settings.get("widget_model_last")):
            self._settings["widget_model_last"] = out["model"]     # tried first next time, even after a restart
            self._save_settings()
        return {**self._studio_view(sid), "note": out["note"], "model": out.get("model"), "problems": left}

    @safe
    def widget_studio_key(self, sid, name, value):
        """Save a key a widget needs (e.g. an API key for its data site) - for this widget, on this PC only."""
        sess = self._session(sid)
        if not sess["draft"] or name not in sess["draft"]["manifest"]["secrets"]:
            raise ValueError("This widget doesn't use that key.")
        if value:
            secrets_store.set_secret(self._secret_name(sess["id"], name), str(value).strip())
        else:
            secrets_store.delete_secret(self._secret_name(sess["id"], name))
        return self._studio_view(sid)

    @safe
    def widget_keep(self, sid):
        sess = self._session(sid)
        if not sess["draft"]:
            raise RuntimeError("There's no widget to keep yet.")
        d = sess["draft"]
        problems = widgetsmith.static_problems(d["html"], d["manifest"])
        if problems:
            raise RuntimeError("This widget still breaks the sandbox rules: " + " ".join(problems))
        manifest = WIDGET_STORE.save(sess["id"], d["manifest"], d["html"], sess["history"])
        sess["existing"] = True
        self._emit("widgets_changed", {"id": sess["id"]})
        return {"id": "cw:" + sess["id"], "manifest": manifest, "settings": self._settings_view()}

    @safe
    def widget_studio_close(self, sid):
        """Close the Studio. A widget that was never kept leaves nothing behind (no files, no keys)."""
        sess = self._studio.pop(sid, None)
        if sess and not sess["existing"]:
            for name in (sess["draft"] or {}).get("manifest", {}).get("secrets", []):
                secrets_store.delete_secret(self._secret_name(sess["id"], name))
            WIDGET_STORE.delete(sess["id"])
        return True

    @safe
    def widget_delete(self, wid):
        m = WIDGET_STORE.manifest(wid)
        for name in m.get("secrets", []):
            secrets_store.delete_secret(self._secret_name(wid, name))
        WIDGET_STORE.delete(wid)
        self._settings["layout"] = [i for i in self._settings.get("layout", []) if i["id"] != "cw:" + wid]
        self._save_settings()
        self._emit("widgets_changed", {"id": wid, "deleted": True})
        return self._settings_view()

    def _widget_target(self, kind, ref):
        """(id, manifest) for a running widget ("widget", id) or a Studio preview ("draft", session)."""
        if kind == "draft":
            sess = self._session(ref)
            if not sess["draft"]:
                raise RuntimeError("Nothing to preview yet.")
            return sess["id"], sess["draft"]["manifest"]
        return ref, WIDGET_STORE.manifest(ref)

    @safe
    def widget_fetch(self, kind, ref, url, opts=None):
        wid, manifest = self._widget_target(kind, ref)
        return widgetsmith.fetch_for_widget(wid, manifest, url, opts or {},
                                            lambda name: secrets_store.get_secret(self._secret_name(wid, name)))

    @safe
    def widget_store(self, kind, ref, op, key, value=None):
        wid, _ = self._widget_target(kind, ref)
        if op == "get":
            return WIDGET_STORE.data_get(wid, key)
        if op == "set":
            return WIDGET_STORE.data_set(wid, key, value)
        raise ValueError("Unknown store operation.")

    @safe
    def widget_say(self, text):
        self._say(str(text)[:300])            # respects "mute replies"
        return True

    @safe
    def widget_export(self, wid):
        """The widget as a shareable .dashwidget file: manifest and code only - never keys or saved data."""
        text = WIDGET_STORE.export(wid)
        name = re.sub(r"[^\w-]+", "-", WIDGET_STORE.manifest(wid).get("name", "widget")).strip("-") or "widget"
        if self._window is None:              # browser preview: the page downloads it
            return {"text": text, "filename": f"{name}.dashwidget"}
        import webview
        path = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=f"{name}.dashwidget",
                                               file_types=("Dashboard widget (*.dashwidget)",))
        if not path:
            return {"cancelled": True}
        path = path if isinstance(path, str) else path[0]
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {"saved": path}

    @safe
    def widget_import(self, text):
        manifest, html = WIDGET_STORE.import_(text)
        wid = widgetsmith.Store.new_id()
        manifest = WIDGET_STORE.save(wid, manifest, html, [{"role": "agent", "text": "Imported from a widget file."}])
        self._emit("widgets_changed", {"id": wid})
        return {"id": "cw:" + wid, "manifest": manifest, "settings": self._settings_view()}

    def _frame(self, kind, ref):
        """(html page, CSP) for a widget's sandboxed frame."""
        if kind == "draft":
            sess = self._session(ref)
            if not sess["draft"]:
                raise RuntimeError("no draft")
            wid, manifest, html = sess["id"], sess["draft"]["manifest"], sess["draft"]["html"]
        else:
            wid, manifest, html = ref, WIDGET_STORE.manifest(ref), WIDGET_STORE.html(ref)
        with open(WIDGET_SDK, encoding="utf-8") as f:
            sdk = f.read()
        return widgetsmith.frame_html(manifest, html, sdk, wid), widgetsmith.csp(manifest)

    def _find_widget(self, words):
        """A kept widget whose name best matches the spoken words."""
        want = set(re.findall(r"\w{3,}", (words or "").lower())) - {"widget", "the", "show", "read"}
        best, score = None, 0
        for m in WIDGET_STORE.list():
            have = set(re.findall(r"\w{3,}", (m.get("name", "") + " " + m.get("description", "")).lower()))
            hit = len(want & have)
            if hit > score:
                best, score = m, hit
        return best

    # ---------------------------------------------------------------- PC / calendar / news
    @safe
    def pc_stats(self):
        return pcmon.snapshot()

    def _calendars(self):
        try:
            return [tuple(c) for c in json.loads(secrets_store.get_secret("calendars") or "[]")]
        except ValueError:
            return []

    @safe
    def calendar_events(self, force=False):
        cals = self._calendars()
        if not cals:
            return {"events": [], "errors": [], "none": True}
        return agenda.events(cals, force)

    @safe
    def news_list(self, force=False):
        return news.latest(self._settings.get("news_feeds"), force)

    # ---------------------------------------------------------------- timers & reminders
    def _add_timer(self, kind, at, label):
        t = timers.new(kind, at, label)
        with self._timers_lock:
            self._settings["timers"] = sorted(self._settings.get("timers", []) + [t], key=lambda x: x["at"])
            self._save_settings()
        self._emit("timers", self._settings["timers"])
        return t

    @safe
    def timers_list(self):
        return self._settings.get("timers", [])

    @safe
    def timer_cancel(self, tid=None, label=None):
        """By id, else by words in the label, else the one ringing, else the soonest one."""
        with self._timers_lock:
            items = self._settings.get("timers", [])
            gone = [t for t in items if t["id"] == tid] if tid else \
                [t for t in items if label and label.lower() in t["label"].lower()] or \
                [t for t in items if t.get("fired_at")] or items[:1]
            self._settings["timers"] = [t for t in items if t not in gone]
            self._save_settings()
        self._after_timer_change()
        return gone

    @safe
    def timer_ack(self, tid=None):
        """Stop the bell and clear finished timers (one, or all of them)."""
        with self._timers_lock:
            items = self._settings.get("timers", [])
            done = [t for t in items if t.get("fired_at") and (tid is None or t["id"] == tid)]
            self._settings["timers"] = [t for t in items if t not in done]
            self._save_settings()
        self._after_timer_change()
        return done

    @safe
    def timer_snooze(self, tid=None, seconds=300):
        """A finished timer goes off again in `seconds` (5 minutes by default)."""
        now = time.time()
        with self._timers_lock:
            hit = [t for t in self._settings.get("timers", []) if t.get("fired_at") and (tid is None or t["id"] == tid)]
            for t in hit:
                t.pop("fired_at", None)
                t["created"], t["at"] = now, now + seconds
            self._settings["timers"].sort(key=lambda x: x["at"])
            self._save_settings()
        self._after_timer_change()
        return hit

    @safe
    def timer_extend(self, tid, seconds=60):
        with self._timers_lock:
            for t in self._settings.get("timers", []):
                if t["id"] == tid:
                    if t.get("fired_at"):         # +1 on a finished timer restarts it for a minute
                        t.pop("fired_at")
                        t["created"], t["at"] = time.time(), time.time() + seconds
                    else:
                        t["at"] += seconds
            self._save_settings()
        self._after_timer_change()
        return True

    def _after_timer_change(self):
        if not self._ringing():
            self._bell.stop()
            if self._alarm_ducked:            # music back up once every alarm is dealt with
                self._alarm_ducked = False
                self._ui_do("duck", on=False)
        self._emit("timers", self._settings["timers"])

    def _ringing(self):
        return any(t.get("fired_at") for t in self._settings.get("timers", []))

    # ---------------------------------------------------------------- tasks (and their Telegram link)
    def _tasks_view(self):
        now = time.time()
        return [{**t, "age": tasks.age_text(t["created"], now), "added_text": tasks.added_text(t["created"], now),
                 "overdue": tasks.is_overdue(t, now),
                 "due_text": tasks.due_text(t.get("due"), now)}
                for t in tasks.ordered(self._settings.get("tasks", []), now)]

    def _import_old_task_widget(self):
        """Once: copy the to-dos of the Widget Studio widget "Task Aging List" into the built-in task list (the old
        widget's files are left alone)."""
        if self._settings.get("tasks_imported"):
            return
        self._settings["tasks_imported"] = True
        try:
            root = os.path.join(DATA_DIR, "custom_widgets")
            for wid in os.listdir(root):
                with open(os.path.join(root, wid, "manifest.json"), encoding="utf-8") as f:
                    if json.load(f).get("name") != "Task Aging List":
                        continue
                with open(os.path.join(root, wid, "store.json"), encoding="utf-8") as f:
                    todos = json.load(f).get("todos") or []
                for td in todos:
                    try:
                        created = datetime.fromisoformat(str(td["createdAt"]).replace("Z", "+00:00")).timestamp()
                    except (KeyError, ValueError):
                        created = time.time()
                    t = tasks.new(str(td.get("text", "")).strip() or "(untitled)", None, created)
                    if td.get("completed"):
                        t["done_at"] = time.time()
                    self._settings["tasks"].append(t)
        except (OSError, ValueError, AttributeError):
            pass
        self._save_settings()

    def _tasks_changed(self):
        self._save_settings()
        self._emit("tasks", self._tasks_view())

    @safe
    def tasks_list(self):
        return self._tasks_view()

    @safe
    def task_add(self, text):
        with self._tasks_lock:
            reply, changed = tasks.handle("add " + str(text), self._settings["tasks"])
            if changed:
                self._tasks_changed()
        return reply

    def _task_op(self, tid, op):
        with self._tasks_lock:
            items = self._settings["tasks"]
            t = next((x for x in items if x["id"] == tid), None)
            if t is not None:
                op(items, t)
                self._tasks_changed()
        return self._tasks_view()

    @safe
    def task_complete(self, tid):
        return self._task_op(tid, lambda items, t: t.update(done_at=t.get("done_at") or time.time()))

    @safe
    def task_reopen(self, tid):
        return self._task_op(tid, lambda items, t: t.update(done_at=None, alerted_at=0, alert_level=0))

    @safe
    def task_delete(self, tid):
        return self._task_op(tid, lambda items, t: items.remove(t))

    def _tg_text(self, text):
        """A message from the paired Telegram chat: run it as a task command and return the reply."""
        m = re.match(r"^/?pc\b[\s:,-]*(.*)$", text.strip(), re.I | re.S)
        if m:
            return self._tg_pc(m.group(1).strip())
        with self._tasks_lock:
            reply, changed = tasks.handle(text, self._settings["tasks"])
            if changed:
                self._tasks_changed()
        return reply

    # Words the System Utilities agent treats as answering a waiting question (yes / no / review), plus clean-up verbs.
    _TG_PC_BLOCK = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|go ahead|do it|please do|confirm\w*|proceed|no|nope|"
                              r"cancel|decline|review|clean\w*|delete\w*|remove\w*|organi[sz]e\w*|empty|wipe|uninstall\w*)\b", re.I)

    def _tg_pc(self, question):
        """Read-only question for the System Utilities agent. Nothing that could confirm or start a change is forwarded,
        and a proposal the agent still makes is declined straight away: changes are made at the PC."""
        if not question:
            return "Ask me about your PC, e.g. /pc how much disk space is free?"
        if self._TG_PC_BLOCK.search(question):
            return "Over Telegram I can only look things up on your PC, not change it. Rephrase it as a question, or do it at the PC."

        def work():
            try:
                out = pcagent.ask(question)
                say = out["say"] or "No answer."
                if out["expect_reply"]:                   # the agent proposed something: decline it, nothing runs
                    try:
                        pcagent.ask("no")
                    except pcagent.AgentError:
                        pass
                    say += "\n\n(That would change your PC, so I cancelled it. Do it at the PC.)"
            except pcagent.AgentError as e:
                say = str(e)
            except Exception:
                say = "Couldn't reach the System Utilities agent."
            try:
                self._tg.send(say)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()
        return "🔎 Asking your PC…"

    def _set_telegram_chat(self, chat_id):
        self._settings["telegram_chat_id"] = chat_id
        self._save_settings()
        self._emit("telegram", self._tg.public())

    @safe
    def telegram_status(self):
        return self._tg.public()

    @safe
    def telegram_pair(self):
        if not secrets_store.get_secret("telegram"):
            raise ValueError("Paste the bot token in Settings and press Save first.")
        return self._tg.pair_start()

    @safe
    def telegram_unpair(self):
        self._tg.unpair()
        return self._tg.public()

    @safe
    def telegram_test(self):
        self._tg.send("✅ Test message from your Dashboard.\n\n" + tasks.digest_text(self._settings["tasks"]))
        return True

    def _tasks_loop(self):
        while not self._quitting:
            threading.Event().wait(20)
            try:
                self._tasks_tick()
            except Exception:
                pass

    def _tasks_tick(self):
        """About once a minute: drop old completed tasks, text overdue / ageing ones, and the optional daily digest."""
        now = time.time()
        if now - self._tasks_checked < 60:
            return
        self._tasks_checked = now
        messages, undo = [], {}
        with self._tasks_lock:
            items = self._settings["tasks"]
            kept = tasks.purge(items, now)
            changed = len(kept) != len(items)
            if changed:
                self._settings["tasks"] = items = kept
            if self._settings.get("telegram_chat_id") and self._tg.public()["state"] == "ok":
                undo = {t["id"]: (t["alerted_at"], t["alert_level"]) for t in items}
                for t, why in tasks.pending_alerts(items, now, float(self._settings.get("tasks_repeat_hours") or 12)):
                    messages.append((t["id"], tasks.alert_text(t, why, now)))
                digest_at, today = self._settings.get("tasks_digest_time"), datetime.now().strftime("%Y-%m-%d")
                if digest_at and datetime.now().strftime("%H:%M") >= digest_at and \
                        self._settings.get("tasks_digest_last") != today:
                    self._settings["tasks_digest_last"] = today
                    if any(not t.get("done_at") for t in items):
                        messages.append((None, tasks.digest_text(items, now)))
                    changed = True
            if changed or messages:
                self._save_settings()
        for i, (tid, text) in enumerate(messages):
            try:
                self._tg.send(text)
            except telegram_link.TelegramError:
                with self._tasks_lock:                # not delivered (offline?): mark them unsent, retry in a minute
                    for tid2, _ in messages[i:]:
                        if tid2 is None:
                            self._settings["tasks_digest_last"] = ""
                        for t in self._settings["tasks"]:
                            if t["id"] == tid2 and tid2 in undo:
                                t["alerted_at"], t["alert_level"] = undo[tid2]
                    self._save_settings()
                break
        if changed:
            self._emit("tasks", self._tasks_view())

    def _clock_loop(self):
        """Every second: fire due timers / reminders; once a day, the automatic morning briefing."""
        while not self._quitting:
            threading.Event().wait(1)
            now = time.time()
            with self._timers_lock:
                due = [t for t in self._settings.get("timers", []) if t["at"] <= now and not t.get("fired_at")]
                for t in due:
                    t["fired_at"] = now               # kept (and flashing) until acknowledged
                if due:
                    self._save_settings()
            for t in due:
                self._fire(t)
            try:
                self._maybe_auto_briefing()
            except Exception:
                pass

    def _fire(self, t):
        text = f"Time's up: {t['label']}." if t["kind"] == "timer" else f"Reminder: {t['label']}."
        self._emit("timers", self._settings["timers"])
        self._emit("timer_due", {**t, "text": text})
        self._show()
        if not self._alarm_ducked:
            self._alarm_ducked = True
            self._ui_do("duck", on=True)
        if self._tray is not None and self._tray.icon is not None:
            try:
                self._tray.icon.notify(text, APP_NAME)
            except Exception:
                pass
        # Ring for at least 5 s, say the label (even when replies are muted - you asked for this one), then keep
        # ringing until you stop or snooze it (or 2 minutes pass; the widget keeps flashing after that).
        self._bell.ring(say=lambda: self._speaker.say_and_wait(text))

    # ---------------------------------------------------------------- morning briefing
    def _briefing_text(self):
        now = datetime.now()
        hour = now.hour
        parts = [("Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening")
                 + now.strftime(f". It's %A, {now.day} %B.")]
        try:
            parts.append(weather.spoken(self._weather(), self._settings.get("weather_label", "")))
        except Exception:
            pass
        if self._calendars():
            try:
                evs = agenda.events(self._calendars())["events"]
                parts.append(agenda.spoken_day(evs, now.date()))
                if any(not e["all_day"] for e in evs):
                    parts.append(agenda.spoken_next(evs))
            except Exception:
                pass
        if self._shown("stocks"):
            try:
                qs = [q for q in stocks.watchlist(self._settings["watchlist"][:3]) if not q.get("error")]
                parts.append(" ".join(stocks.describe(q) for q in qs))
            except Exception:
                pass
        unread = [c for c in self._wa_chats.get("chats", []) if c.get("unread")]
        if self._shown("whatsapp") and self._wa_chats.get("state") == "ok":
            parts.append(f"You have unread WhatsApp messages from {', '.join(c['name'] for c in unread[:4])}."
                         if unread else "No unread WhatsApp messages.")
        try:
            top = cyber.latest()["news"][:1]
            if top and self._shown("cyber"):
                parts.append(f"In security news: {top[0]['title']}.")
        except Exception:
            pass
        try:
            top = news.latest(self._settings.get("news_feeds"))["news"][:1]
            if top and self._shown("news"):
                parts.append(f"Top headline: {top[0]['title']}.")
        except Exception:
            pass
        if self._settings.get("timers"):
            running = [t for t in self._settings["timers"] if not t.get("fired_at")]
            if running:
                parts.append("Running: " + timers.spoken_list(running))
        return " ".join(p for p in parts if p)

    @safe
    def briefing(self):
        return self._briefing_text()

    def _maybe_auto_briefing(self):
        s = self._settings
        if not s.get("briefing_time"):
            return
        now = datetime.now()
        today = now.date().isoformat()
        if s.get("briefing_last") == today or now.weekday() not in s.get("briefing_days", []):
            return
        if now.strftime("%H:%M") < s["briefing_time"] or idle_seconds() > 120:
            return                            # wait until it's time and someone is using the PC
        s["briefing_last"] = today
        self._save_settings()
        self._show()
        self._handle("good morning", spoken=True, how="scheduled")

    # ---------------------------------------------------------------- weather
    def _weather(self, force=False):
        s = self._settings
        if s.get("weather_lat") is None:
            raise SourceError("Set your city in Settings → Tiles to see the weather.")
        return weather.forecast(s["weather_lat"], s["weather_lon"], s.get("weather_units", "celsius"), force)

    @safe
    def weather_now(self, force=False):
        return {**self._weather(force), "place": self._settings.get("weather_label")}

    # ---------------------------------------------------------------- spoken replies
    @safe
    def replies_mute(self, muted):
        self._settings["speak_replies"] = not muted
        self._save_settings()
        if muted:
            self._speaker.stop()
        self._emit("muted", muted)
        return not self._settings["speak_replies"]

    @safe
    def stop_speaking(self):
        self._speaker.stop()
        return True

    @safe
    def say_text(self, text):
        """"Read aloud" buttons: speak this now (even if automatic replies are muted - you asked for it)."""
        self._speaker.stop()
        self._speaker.say(text, on_start=lambda: self._ui_do("duck", on=True),
                          on_end=lambda: self._ui_do("duck", on=False))
        return True

    # ---------------------------------------------------------------- cyber explain
    @safe
    def cyber_explain(self, link):
        return self._explain(link, "cyber")

    @safe
    def news_explain(self, kind, link):
        return self._explain(link, kind)

    def _stories(self, kind):
        return (news.latest(self._settings.get("news_feeds")) if kind == "news" else cyber.latest()).get("news") or []

    def _explain(self, link, kind="cyber"):
        if link in self._explained:
            return self._explained[link]
        story = next((it for it in self._stories(kind) if it["link"] == link), None)
        if story is None:
            raise SourceError("That story is no longer in the list - refresh the news.")
        try:
            text = cyber.article_text(link)
        except SourceError:
            text = ""
        source = "article"
        if len(text) < 300:                   # site blocked us or the page is mostly script: use the feed summary
            text, source = story["summary"], "summary"
        out = {"link": link, "title": story["title"], "source": story["source"], "from": source, "kind": kind,
               "text": assistant.explain_story(self._ai(), story["title"], text, kind)}
        self._explained[link] = out
        return out

    # ---------------------------------------------------------------- YouTube account
    @safe
    def youtube_signin(self):
        """Sign in to Google inside the dashboard's own browser profile, so the embedded player plays as you."""
        if self._window is None:
            return {"url": YOUTUBE_SIGNIN}
        import webview
        win = webview.create_window("Sign in to YouTube - close this window when you're done", YOUTUBE_SIGNIN,
                                    screen=self._screen, width=520, height=720, on_top=True)

        def done():
            self._ui_do("reload_player")
            threading.Thread(target=self._check_youtube, daemon=True).start()
        win.events.closed += done
        return {"opened": True}

    def _check_youtube(self):
        """Load youtube.com in a hidden window of the same profile and ask the page whether you're signed in."""
        if self._window is None:
            return
        import webview
        win = webview.create_window("YouTube check", "https://www.youtube.com/", hidden=True)
        signed_in = None
        try:
            for _ in range(30):
                threading.Event().wait(1)
                try:
                    v = win.evaluate_js("window.ytcfg && ytcfg.get ? String(!!ytcfg.get('LOGGED_IN')) : ''")
                except Exception:
                    v = ""
                if v in ("true", "false"):
                    signed_in = v == "true"
                    break
        finally:
            try:
                win.destroy()
            except Exception:
                pass
        self._yt_signed_in = signed_in
        self._emit("youtube", {"signed_in": signed_in})

    @safe
    def ai_test(self, form):
        """Try the AI settings in the form without saving them."""
        s = {**self._settings, **{k: v for k, v in form.items() if k in DEFAULT_SETTINGS}}
        client = self._make_client(s, form.get("openai_key_new") or None, form.get("anthropic_key_new") or None)
        names = client.models()
        reply = client.chat("Reply with one short sentence.", "Say hello to the dashboard owner.", max_tokens=60)
        return {"ok": True, "models": names[:300], "model": client.model, "label": client.label, "reply": reply}

    @safe
    def init(self):
        return {"settings": self._settings_view(), "voice": self._voice_state, "serve": self._window is None}

    @safe
    def ui_state(self, state):
        """The page reports what's playing / the volume / which tile is maximized (context for the AI)."""
        self._ui.update({k: state[k] for k in ("volume", "song", "maximized") if k in state})
        return True

    @safe
    def open_url(self, url):
        if urllib.parse.urlparse(url).scheme in ("http", "https"):
            webbrowser.open(url)
        return True

    # ---------------------------------------------------------------- photos
    def _photo_folders(self):
        return self._settings.get("photo_folders") or photos.default_folders()

    def _scan_photos(self):
        self._photos_scanning = True
        self._emit("photos", self.photos_info())
        try:
            self._photos = photos.scan(self._photo_folders(), self._settings.get("photo_include_cloud", True))
        finally:
            self._photos_scanning = False
        self._emit("photos", self.photos_info())

    @safe
    def photos_info(self):
        return {"count": len(self._photos), "scanning": self._photos_scanning,
                "seconds": self._settings.get("photo_seconds", 12), "folders": self._photo_folders()}

    def _photo_file(self, n):
        if not self._photos:
            raise FileNotFoundError("no photos")
        path = self._photos[n % len(self._photos)]
        out = photos.render(path, PHOTO_CACHE)
        self._renders += 1
        if self._renders % 50 == 0:
            photos.prune(PHOTO_CACHE, self._settings.get("photo_cache_mb", 1500) * 1024 * 1024)
        return out, path

    def _prefetch_photo(self, n):
        def go():
            try:
                self._photo_file(n)
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()

    # ---------------------------------------------------------------- tiles
    @safe
    def cyber_news(self, force=False):
        return cyber.latest(force)

    @safe
    def stocks_list(self, rng="1d"):
        return stocks.watchlist(self._settings["watchlist"], rng)

    @safe
    def stock_chart(self, symbol, rng="1d"):
        return stocks.quote(symbol, rng)

    @safe
    def music_search(self, query):
        return music.search(query, secrets_store.get_secret("youtube"))

    # ---------------------------------------------------------------- WhatsApp
    def _wa_create(self, hidden):
        import webview
        self._wa = webview.create_window("WhatsApp — say \"close WhatsApp\" to go back", WHATSAPP_URL,
                                         screen=self._screen, on_top=True, hidden=hidden, background_color="#111b21")

        def closing():
            # Closing with the X only hides it, so the unread-chats tile keeps working.
            if self._quitting or not self._settings.get("whatsapp_watch"):
                return True
            threading.Thread(target=self._wa.hide, daemon=True).start()
            return False
        self._wa.events.closing += closing
        self._wa.events.closed += lambda: setattr(self, "_wa", None)

    def _watch_whatsapp(self):
        """Background: open WhatsApp Web hidden and read its chat list every WHATSAPP_POLL seconds."""
        if self._window is None or not self._settings.get("whatsapp_watch"):
            return
        if self._wa is None:
            self._wa_create(hidden=True)
        while not self._quitting and self._settings.get("whatsapp_watch"):
            threading.Event().wait(WHATSAPP_POLL)
            if self._wa is None or not self._shown("whatsapp"):
                continue
            result = whatsapp.read(self._wa)
            if result != self._wa_chats:
                self._wa_chats = result
                self._emit("whatsapp", result)

    @safe
    def whatsapp_chats(self):
        if self._window is None:
            return {"state": "browser", "chats": []}
        return self._wa_chats

    @safe
    def whatsapp_open(self):
        if self._window is None:               # browser dev mode: the page opens a tab instead
            return {"url": WHATSAPP_URL}
        if self._wa is None:
            self._wa_create(hidden=False)
        self._wa.show()
        self._wa.maximize()
        return {"opened": True}

    @safe
    def whatsapp_close(self):
        if self._wa is not None:
            self._wa.hide()
        return True

    # ---------------------------------------------------------------- voice
    def _stt_key(self):
        key = secrets_store.get_secret("stt")
        if not key and "api.openai.com" in self._settings.get("stt_base", ""):
            key = secrets_store.get_secret("openai")   # reuse the OpenAI key when it's the same service
        return key

    def _on_voice_state(self, state, detail=None):
        previous = self._voice_state.get("state")
        self._voice_state = {"state": state, "detail": detail}
        self._emit("voice", self._voice_state)
        # Lower the music while you talk; it comes back when the request is done (or the reply's own duck ends).
        if state == "recording":
            self._ui_do("duck", on=True)
        elif previous in ("recording", "transcribing") and state not in ("recording", "transcribing"):
            self._ui_do("duck", on=False)

    def _start_voice(self):
        if self._voice is not None or not self._settings.get("voice_on"):
            return
        self._voice = voice.VoiceLoop(lambda: self._settings, self._stt_key, self._on_voice_state,
                                      # in a thread, so a slow answer doesn't stop the mic loop
                                      lambda text, how: threading.Thread(
                                          target=self._handle, args=(text, True, how), daemon=True).start(),
                                      lambda: self._speaker.speaking, os.path.join(DATA_DIR, "last_request.wav"))
        self._voice.start()

    def _restart_voice(self):
        if self._voice is not None:
            self._voice.stop()
            self._voice = None
        if self._settings.get("voice_on"):
            threading.Timer(0.5, self._start_voice).start()
        else:
            self._on_voice_state("off")

    @safe
    def voice_toggle(self, on):
        self._settings["voice_on"] = bool(on)
        self._save_settings()
        self._restart_voice()
        return self._voice_state

    @safe
    def voice_listen(self):
        """Mic button / hotkey: start recording without the wake word."""
        if self._voice is None:
            raise RuntimeError("Voice is off - turn it on first.")
        self._voice.push_to_talk()
        return True

    def _say(self, text, after=None):
        """Speak a reply (unless replies are muted); `after` runs once it has been said. True if it's spoken."""
        if text and self._settings.get("speak_replies", True):
            def end():
                self._ui_do("duck", on=False)
                if after:
                    after()
            self._speaker.say(text, on_start=lambda: self._ui_do("duck", on=True), on_end=end)
            return True
        return False

    # ---------------------------------------------------------------- System Utilities agent
    def _agent_ask(self, text, spoken):
        def starting():
            self._ui_do("toast", text=f"Starting {pcagent.APP_NAME}…")
            if spoken:
                self._say(f"Starting {pcagent.APP_NAME}…")
        out = pcagent.ask(text, on_starting=starting)
        self._agent_expects.value = out["expect_reply"]
        return out["say"] or ("I'm on it." if out["busy"] else "Done.")

    def _expect_answer(self, spoken):
        """The agent asked a question: route the next request (within 20 s) to it, and when the question was
        spoken, open the mic once it has finished - no wake word needed for the answer."""
        def listen():
            self._followup_until = time.time() + 20
            if self._voice is not None:
                self._voice.push_to_talk()
        return listen if spoken else None

    def _on_agent_event(self, ev):
        """An alert or a finished job reported by System Utilities: shown and said like a reply."""
        say = str(ev.get("say") or "")
        if not say:
            return
        if ev.get("kind") == "alert":
            self._show()
        if ev.get("critical"):                # System Utilities sends each critical alert once; only those get the bell
            self._bell.chime()
        self._emit("reply", {"text": say, "action": "pc_agent", "source": "agent", "kind": ev.get("kind")})
        after = self._expect_answer(True) if ev.get("expect_reply") else None
        if not self._say(say, after) and ev.get("expect_reply"):
            self._followup_until = time.time() + 20

    # ---------------------------------------------------------------- commands
    @safe
    def command(self, text):
        """A typed command; same path as a spoken one, but the reply is only spoken if it was spoken."""
        threading.Thread(target=self._handle, args=(text, False), daemon=True).start()
        return True

    def _handle(self, text, spoken, how=None):
        self._emit("heard", {"text": text, "spoken": spoken, "how": how})
        if spoken:
            self._show()                      # you're talking to it, so make sure it's visible
        state = {**self._ui, "watchlist": self._settings["watchlist"], "alarm": self._ringing(),
                 "headlines": [it["title"] for it in (cyber._cache.get("data") or {}).get("news", [])]}
        try:
            w = self._weather()
            state["weather"] = weather.summary_for_ai(w, self._settings.get("weather_label", ""))
        except Exception:
            pass
        self._agent_expects.value = False
        try:
            if time.time() < self._followup_until:     # the answer to System Utilities' question
                self._followup_until = 0
                action, source = {"action": "pc_agent", "text": text}, "agent"
            else:
                action, source = assistant.interpret(self._ai(), text, state)
            if action.get("action") == "pc_agent":
                source = "agent"
            reply = self._run(action, spoken)
        except (LLMError, SourceError, RuntimeError, ValueError, KeyError) as e:
            action, source, reply = {"action": "error"}, "error", str(e)
        self._emit("reply", {"text": reply, "action": action.get("action"), "source": source})
        expects = self._agent_expects.value
        after = self._expect_answer(spoken) if expects else None
        said = self._say(reply, after) if spoken else False
        if expects and not said:              # typed or muted: the next typed / wake-word request answers it
            self._followup_until = time.time() + 20

    def _run(self, a, spoken=False):
        act = a.get("action")
        if act == "pc_agent":
            return self._agent_ask(a.get("text") or "", spoken)
        if act == "play_song":
            hits = music.search(a.get("query", ""), secrets_store.get_secret("youtube"))
            self._ui_do("play", items=hits, query=a.get("query"))
            return f"Playing {hits[0]['title']}."
        if act in ("pause", "resume", "next", "previous", "next_photo", "previous_photo", "restore"):
            self._ui_do(act)
            return ""
        if act == "volume":
            level = max(0, min(100, int(a.get("level", 60))))
            self._ui_do("volume", level=level)
            return f"Volume {level}."
        if act == "maximize":
            tile = a.get("tile")
            if tile == "whatsapp":
                return self._run({"action": "open_whatsapp"})
            self._ui_do("maximize", tile=tile)
            return ""
        if act == "stock_quote":
            q = stocks.quote(a.get("symbol", ""))
            self._ui_do("stock_focus", symbol=q["symbol"])
            return stocks.describe(q)
        if act == "market_summary":
            quotes = [q for q in stocks.watchlist(self._settings["watchlist"]) if not q.get("error")]
            self._ui_do("maximize", tile="stocks")
            return " ".join(stocks.describe(q) for q in quotes[:4]) or "I couldn't load the market data."
        if act in ("add_stock", "remove_stock"):
            sym = a.get("symbol", "").strip().upper()
            wl = [x for x in self._settings["watchlist"] if x != sym]
            if act == "add_stock":
                stocks.quote(sym)              # raises if Yahoo doesn't know the ticker
                wl.append(sym)
            self._settings["watchlist"] = wl
            self._save_settings()
            self._ui_do("watchlist")
            return f"{'Added' if act == 'add_stock' else 'Removed'} {sym}."
        if act == "cyber_brief":
            data = cyber.latest()
            self._ui_do("maximize", tile="cyber")
            try:
                return assistant.cyber_brief(self._ai(), cyber.headlines_for_ai(data))
            except LLMError:
                top = data["news"][:3]
                return "Top security stories: " + ". ".join(it["title"] for it in top) + "." if top else \
                    "I couldn't load the security news."
        if act == "open_whatsapp":
            self.whatsapp_open()
            self._ui_do("whatsapp")
            return ""
        if act == "show_dashboard":
            self._show()
            return ""
        if act == "hide_dashboard":
            self._hide()
            return ""
        if act == "close_whatsapp":
            self.whatsapp_close()
            return ""
        if act in ("mute_replies", "unmute_replies"):
            self.replies_mute(act == "mute_replies")
            return "" if act == "mute_replies" else "OK, I'll speak my answers again."
        if act == "weather":
            w = self._weather()
            return weather.spoken(w, self._settings.get("weather_label", ""))
        if act == "show_weather":
            self._weather()
            self._ui_do("maximize", tile="weather")
            return ""
        if act == "read_whatsapp":
            if self._window is None:
                raise RuntimeError("WhatsApp chats can only be read in the dashboard app, not the browser preview.")
            if self._wa is not None:
                self._wa_chats = whatsapp.read(self._wa)
                self._emit("whatsapp", self._wa_chats)
            return whatsapp.spoken(self._wa_chats)
        if act == "explain_story":
            kind = a.get("kind") or ("news" if self._ui.get("maximized") == "news" else "cyber")
            kind = kind if kind in ("news", "cyber") else "cyber"
            story = assistant.find_story(self._stories(kind), a)
            if story is None:
                return "I couldn't tell which story you mean."
            self._ui_do("explaining", link=story["link"], kind=kind)
            out = self._explain(story["link"], kind)
            self._ui_do("explained", **out)
            return out["text"]
        if act in ("timer", "reminder"):
            at = a.get("at")
            if at is None and a.get("seconds"):
                at = time.time() + float(a["seconds"])
            if at is None and a.get("time"):
                dt = timers.parse_time("at " + str(a["time"]))
                at = dt.timestamp() if dt else None
            if at is None:
                return "When should it go off?"
            t = self._add_timer(act, float(at), a.get("label") or ("timer" if act == "timer" else "reminder"))
            if not self._shown("timers"):
                self._ui_do("toast", text=timers.confirm(t))
            return timers.confirm(t)
        if act == "timer_cancel":
            gone = self.timer_cancel(label=a.get("label"))
            return f"Cancelled {gone[0]['label']}." if gone else "There's nothing to cancel."
        if act == "timer_ack":
            return "OK." if self.timer_ack() else "Nothing is ringing."
        if act == "timer_snooze":
            mins = float(a.get("minutes") or 5)
            hit = self.timer_snooze(seconds=mins * 60)
            return f"Snoozed for {mins:g} minutes." if hit else "Nothing is ringing."
        if act == "timer_list":
            return timers.spoken_list(self._settings.get("timers", []))
        if act == "task_add":
            title = str(a.get("text") or "").strip()
            if not title:
                return "What's the task?"
            with self._tasks_lock:
                reply, changed = tasks.handle("add " + title, self._settings["tasks"])
                if changed:
                    self._tasks_changed()
                t = self._settings["tasks"][-1] if changed else None
            if t is None:
                return reply
            if not self._shown("tasks"):
                self._ui_do("toast", text=f"Task added: {t['title']}")
            return f"OK, I've added {t['title']}" + (f", due {tasks.due_text(t['due'])}." if t.get("due") else " to your tasks.")
        if act == "task_list":
            if self._shown("tasks"):
                self._ui_do("maximize", tile="tasks")
            return tasks.spoken(self._settings["tasks"])
        if act == "task_done":
            ref = str(a.get("ref") or a.get("text") or "").strip().lower()
            ref = re.sub(r"^(?:(?:number|no\.?)\s+|#\s*)", "", ref)
            ref = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                   "eight": "8", "nine": "9", "ten": "10", "first": "1", "second": "2", "third": "3"}.get(ref, ref)
            with self._tasks_lock:
                pending = [x for x in self._settings["tasks"] if not x.get("done_at")]
                t, err = tasks.find(pending, ref) if not ref.isdigit() else tasks.find(self._settings["tasks"], ref)
                if t is None and not ref.isdigit():       # maybe it is already finished
                    t, _ = tasks.find(self._settings["tasks"], ref)
                if t is None:
                    return err
                if t.get("done_at"):
                    return f"{t['title']} is already done."
                t["done_at"] = time.time()
                self._tasks_changed()
            return f"Marked {t['title']} as done."
        if act == "pc_status":
            return pcmon.spoken(pcmon.snapshot())
        if act in ("agenda", "next_event"):
            cals = self._calendars()
            if not cals:
                return "Add your calendar link in Settings, Tiles, to use the calendar."
            evs = agenda.events(cals)["events"]
            if act == "next_event":
                return agenda.spoken_next(evs)
            day = datetime.now().date()
            if str(a.get("day", "")).lower() == "tomorrow":
                day += timedelta(days=1)
            if self._shown("calendar"):
                self._ui_do("maximize", tile="calendar")
            return agenda.spoken_day(evs, day)
        if act == "news_brief":
            data = news.latest(self._settings.get("news_feeds"))
            if self._shown("news"):
                self._ui_do("maximize", tile="news")
            return news.spoken(data)
        if act == "briefing":
            text = self._briefing_text()
            self._ui_do("briefing", text=text)
            return text
        if act == "edit_layout":
            self._ui_do("edit_layout")
            return ""
        if act == "create_widget":
            self._ui_do("widget_studio", request=a.get("request") or "")
            return "Opening Widget Studio. I'll build it now - it takes about a minute."
        if act in ("edit_widget", "read_widget", "show_widget"):
            m = self._find_widget(a.get("name") or a.get("request") or "")
            if m is None:
                return "I couldn't find a widget by that name."
            if act == "edit_widget":
                self._ui_do("widget_studio", id=m["id"], request=a.get("request") or "")
                return f"Opening {m['name']} in Widget Studio."
            if act == "show_widget":
                self._ui_do("maximize", tile="cw:" + m["id"])
                return ""
            self._ui_do("read_widget", id=m["id"])  # the page asks the widget for its summary and says it
            return ""
        if act == "answer":
            return a.get("text", "")
        return "Sorry, I can't do that yet."


# ---------------------------------------------------------------- local web server (UI, photos, dev API)

def start_server(api, port, dev_api):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=UI_DIR, **kwargs)

        def log_message(self, *args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _json(self, data, code=200):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _photo(self):
            try:
                n = int(self.path.split("/")[2].split("?")[0])
                out, _ = api._photo_file(n)
            except Exception:
                return self.send_error(404)
            api._prefetch_photo(n + 1)
            with open(out, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _widget_frame(self):
            """/cw/<id>/frame (a kept widget) or /cw/draft/<session>/frame (a Studio preview), with its CSP."""
            parts = self.path.split("?")[0].strip("/").split("/")
            try:
                if len(parts) == 4 and parts[1] == "draft" and parts[3] == "frame":
                    page, policy = api._frame("draft", parts[2])
                elif len(parts) == 3 and parts[2] == "frame":
                    page, policy = api._frame("widget", parts[1])
                else:
                    return self.send_error(404)
            except Exception:
                return self.send_error(404)
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", policy)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/photo/"):
                return self._photo()
            if self.path.startswith("/cw/"):
                return self._widget_frame()
            if dev_api and self.path.startswith("/api/_events"):
                return self._json(api._drain_events())
            if self.path == "/_show":         # a second start of the app asks this one to come forward
                api._show()
                return self._json("Dashboard")
            return super().do_GET()

        def do_POST(self):
            name = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
            method = getattr(api, name, None) if dev_api and name and not name.startswith("_") else None
            if not callable(method):
                return self._json({"__error__": f"Unknown method {name}"}, 404)
            length = int(self.headers.get("Content-Length", 0))
            self._json(method(*json.loads(self.rfile.read(length) or b"[]")))

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def pick_screen(webview, choice):
    screens = list(webview.screens)
    if choice is not None and 0 <= int(choice) < len(screens):
        return screens[int(choice)]
    if len(screens) < 2:
        return screens[0] if screens else None
    # The extra 16" monitor: the smallest screen that isn't the primary one (the primary sits at 0,0).
    others = [s for s in screens if (s.x, s.y) != (0, 0)] or screens[1:]
    return min(others, key=lambda s: s.width * s.height)


def show_running_copy():
    """True if a dashboard is already running (it is brought to the front instead of opening a second one)."""
    try:
        with open(INSTANCE_PATH, encoding="utf-8") as f:
            port = json.load(f)["port"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_show", timeout=2) as resp:
            return json.loads(resp.read()) == "Dashboard"
    except (OSError, ValueError, KeyError):
        return False


def main():
    if "--serve" not in sys.argv and show_running_copy():
        return
    api = Api()
    if "--serve" in sys.argv:
        start_server(api, SERVE_PORT, dev_api=True)
        print(f"Serving on http://127.0.0.1:{SERVE_PORT}/?serve=1", flush=True)
        api._start_voice()
        threading.Event().wait()
        return
    import webview
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dashboard.App")
    port = start_server(api, 0, dev_api=False)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INSTANCE_PATH, "w", encoding="utf-8") as f:
        json.dump({"port": port, "pid": os.getpid()}, f)
    tray.ensure_ico(ICON)
    api._screen = pick_screen(webview, api._settings.get("screen"))
    api._fullscreen = "--window" not in sys.argv
    window = webview.create_window(
        APP_NAME, url=f"http://127.0.0.1:{port}/index.html", js_api=api, screen=api._screen,
        fullscreen=api._fullscreen, width=1280, height=760, min_size=(900, 560), background_color="#0b0d12")
    api._window = window
    window.events.closed += api._quit
    api._tray = tray.Tray(api)
    api._tray.start()
    voice.Hotkeys({VK_SPACE: lambda: api._voice and api._voice.push_to_talk(),   # Ctrl+Alt+Space: talk
                   VK_D: api._show}).start()                                       # Ctrl+Alt+D: show dashboard

    def started():
        api._start_voice()
        threading.Thread(target=api._watch_whatsapp, daemon=True).start()
        threading.Thread(target=api._check_youtube, daemon=True).start()
    webview.start(started, debug="--debug" in sys.argv, icon=ICON,
                  private_mode=False, storage_path=WEB_STORAGE)


if __name__ == "__main__":
    main()
