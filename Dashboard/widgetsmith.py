"""Widget Studio: an AI agent that writes small dashboard widgets from a description.

A widget is a sandboxed mini-app - HTML/CSS/JS that runs in <iframe sandbox="allow-scripts"> (opaque origin, no
access to the dashboard, its keys or other widgets) under a strict Content-Security-Policy. It talks to the
dashboard only through the Widget SDK (ui/widget-sdk.js) over postMessage; internet data comes through
fetch_for_widget() below, which only reaches the https sites approved for that widget and never the PC or the LAN.

Generated code is stored and served to the frame; it is never run by Python."""

import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import threading
import time
import urllib.parse
import uuid

from llm import LLMError

MAX_HTML = 80_000
MAX_STORE = 100_000
MAX_FETCH = 2_000_000
FETCH_TIMEOUT = 15
MAX_VERSIONS = 10
SCRIPT_HOSTS = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
# Best first. "auto" tries these in order and moves on when a model is busy (503) or over quota (429).
GEMINI_PREFS = [r"^gemini-pro-latest$", r"^gemini-[\d.]+-pro$", r"^gemini-[\d.]+-pro-preview$",
                r"^gemini-[\d.]+-flash$", r"^gemini-flash-latest$"]
FLASH_FALLBACKS = 3     # how many numbered Flash models to try (newest first) - availability changes by the hour
SECRET_RE = re.compile(r"\{\{secret:([A-Z][A-Z0-9_]{1,40})\}\}")
HOST_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,63}$")
ALLOWED_HEADERS = {"accept", "content-type", "authorization", "accept-language"}

# The dashboard's dark theme, so generated widgets match the built-in ones (same values as ui/app.css).
THEME_CSS = """:root { color-scheme: dark; --bg: #0b0d12; --tile: #15171d; --tile-2: #1c1f27; --line: #2a2d36;
  --grid: #2c2c2a; --ink: #f0efec; --ink-2: #c3c2b7; --ink-3: #8b8a83; --accent: #5b9cf0; --series: #5b9cf0;
  --good: #0ca30c; --good-ink: #3fcf5a; --bad: #d03b3b; --bad-ink: #ff7b72; --warn: #e8a33b;
  font-family: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: transparent; color: var(--ink); font-size: 14px; overflow: hidden; }"""

SYSTEM = """You build widgets for a dark, always-on dashboard shown on a small 16" monitor (1280x720, 12x8 grid; one
grid cell is about 100x80 px). You write ONE self-contained widget: HTML + <style> + <script>.

WHERE IT RUNS
- A sandboxed iframe filling the widget's tile body (the dashboard draws the tile frame and the title bar with the
  widget's name, so don't repeat the name as a big heading). Fill 100% width and height and adapt to any size from
  2x2 cells up to full screen (use flex/grid, clamp(), and the Widget.onResize sizes; no fixed pixel widths).
- No network access: fetch(), XMLHttpRequest, WebSocket, EventSource, localStorage, sessionStorage, cookies,
  IndexedDB, alert/prompt/confirm, eval and new Function are all blocked. Use the SDK instead.
- External scripts: only from https://cdnjs.cloudflare.com or https://cdn.jsdelivr.net with an exact version, and
  only when really needed (prefer plain JS and inline SVG; no chart libraries for one simple chart).
- Images: only data: URIs or https images from the domains you list.

THE WIDGET SDK (global `Widget`, already loaded)
- await Widget.fetch(url, {json: true|false, headers: {...}, method: "GET"|"POST", body: "..."}) -> parsed JSON
  (or text when json:false). https only, and only from hosts listed in "domains". Throws Error on failure.
  For an API key write {{secret:NAME}} inside the URL or a header; the dashboard fills it in. List NAME in "secrets".
- await Widget.store.get(key) / await Widget.store.set(key, value): small saved JSON data (100 KB total) for
  trackers, notes, settings. Survives restarts.
- Widget.say(text): speak a short sentence aloud (only when the user clicked something; never on a timer).
- Widget.onRefresh(fn): fn() is called every refresh_seconds while visible. Also call your load once at start.
- Widget.onResize(fn): fn({w, h, maximized}) with the tile size in grid cells, at start and on every change.
- Widget.summary(fn): fn() returns (or resolves to) one or two plain sentences describing what the widget shows
  right now - it is read aloud when the user says "read the <name> widget".
- Widget.ready(): call once the first content is on screen. Widget.error(message): report a problem you caught.

LOOK AND FEEL
- Use the CSS variables: --ink (text), --ink-2, --ink-3 (secondary/muted), --tile-2 (inner cards), --line,
  --grid (hairlines), --accent / --series (main data colour), --good-ink / --bad-ink (up/down text), --warn.
  Background stays transparent. Font sizes 12-16 px for text; big numbers may use clamp(24px, 9vmin, 72px).
- Charts: inline SVG, 2 px lines, thin hairline grid, one y axis, label values in --ink-3, a hover tooltip.
  Up/down always pairs colour with an arrow or sign (▲ ▼ + −), never colour alone.
- Show a calm loading state, and a friendly one-line message in the widget when data fails (keep the last good
  data visible if you have it). Never show raw error dumps.
- Buttons: real <button> elements with aria-labels; big enough to tap (32 px+).

DATA - NEVER GUESS AN API ADDRESS
- Many APIs you remember don't exist, moved, or block servers. Only use URLs that the probe results in this
  conversation show working (status 200 with the data you need). Read the probe results carefully and write your
  parsing code against the exact structure you saw (field names, nesting, arrays).
- To check sources, answer with only probe lines (up to 4 per answer), e.g.
    <probe>https://api.example.com/v1/scores</probe>
  You'll get back each URL's status, content type and the start of the response (JSON is shown as an outline of
  its structure with sample values). Probe before building any widget that needs data, unless the exact URLs were
  already probed in this conversation. After probing, build with what works or try other sources.
- Known working free sources (still probe the exact URL you'll use):
    cricket live scores: https://static.cricinfo.com/rss/livescores.xml (RSS: item titles like "India 245/3 * v
      Australia"; refreshes every 2 min) and https://site.web.api.espn.com/apis/site/v2/sports/cricket/scorepanel
      (JSON: leagues and events with competitors, scores, status); with a free key: https://api.cricapi.com/v1/...
    football/other sports: https://site.api.espn.com/apis/site/v2/sports/<sport>/<league>/scoreboard
      (e.g. soccer/eng.1, soccer/ind.1, basketball/nba, racing/f1)
    crypto: https://api.coingecko.com/api/v3/...  currency rates: https://api.frankfurter.app/latest
    weather: https://api.open-meteo.com/v1/forecast  stocks: https://query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>
    knowledge: https://en.wikipedia.org/api/rest_v1/page/summary/<Title>  news: the site's RSS feed
- RSS / XML / HTML: fetch with {json: false} and parse with new DOMParser().parseFromString(text, "text/xml").
- If the only good source needs a key, say so in "note", use {{secret:NAME}} and list NAME in "secrets".
- Never ask for or store passwords, card numbers or personal IDs. Never send user data anywhere.
- Times and dates: use the PC's local time zone unless asked otherwise. Currency: INR (₹) unless asked otherwise.

ANSWER FORMAT - exactly one of these:
(a) If the request is genuinely ambiguous in a way that changes what you build (e.g. "my team" - which team?),
    ask ONE short question:
    <question>Which team should it follow?</question>
(b) To check data sources first: only <probe>URL</probe> lines (up to 4).
(c) Otherwise build it:
    <note>One short sentence: what you built or what you changed.</note>
    <manifest>{"name": "Short Title (max 30 chars)", "description": "one line", "default_w": 3, "default_h": 3,
     "min_w": 2, "min_h": 2, "refresh_seconds": 60, "domains": ["api.example.com"], "secrets": [],
     "summary_hint": "what the spoken summary says"}</manifest>
    <widget>
    ...your HTML, <style> and <script> (no <html>, <head> or <body> tags)...
    </widget>
refresh_seconds: 0 if it never needs fresh data, otherwise at least 30. domains: every host you fetch or load
images from (not the script CDNs). Sizes are in grid cells (w 2-12, h 2-8). Keep the widget under 60 KB.
When asked to change an existing widget, return the complete updated widget (same format), changing only what
was asked."""


class NeedKey(Exception):
    """The widget agent has no API key on this PC yet."""


class WidgetError(Exception):
    pass


# ---------------------------------------------------------------- parsing and checks

def _tag(text, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", text, re.S)
    return m.group(1).strip() if m else None


def parse_answer(text):
    """Agent reply -> {"question"}, {"probe": [urls]} or {"note", "manifest", "html"}. Raises WidgetError."""
    q = _tag(text, "question")
    if q and not _tag(text, "widget"):
        return {"question": q[:400]}
    probes = [u.strip() for u in re.findall(r"<probe>(.*?)</probe>", text, re.S)]
    if probes and not _tag(text, "widget"):
        return {"probe": probes[:4]}
    raw_manifest, html = _tag(text, "manifest"), _tag(text, "widget")
    if raw_manifest is None or html is None:
        # tolerate the html arriving in a fenced block instead of <widget> tags
        m = re.search(r"```html\s*(.*?)```", text, re.S)
        html = html or (m.group(1).strip() if m else None)
    if raw_manifest is None or html is None:
        raise WidgetError("The agent's answer was incomplete (no manifest or no widget code).")
    raw_manifest = re.sub(r"^```(json)?|```$", "", raw_manifest.strip()).strip()
    try:
        manifest = json.loads(raw_manifest)
    except ValueError as e:
        raise WidgetError(f"The agent's manifest wasn't valid JSON: {e}") from e
    html = re.sub(r"^```(html)?|```$", "", html.strip()).strip()
    return {"note": (_tag(text, "note") or "")[:300], "manifest": clean_manifest(manifest), "html": html}


def clean_manifest(m):
    if not isinstance(m, dict):
        raise WidgetError("The manifest isn't an object.")
    num = lambda k, d, lo, hi: max(lo, min(hi, int(m.get(k) or d)))
    out = {
        "name": str(m.get("name") or "Widget").strip()[:30] or "Widget",
        "description": str(m.get("description") or "").strip()[:200],
        "min_w": num("min_w", 2, 1, 12), "min_h": num("min_h", 2, 1, 8),
        "refresh_seconds": int(m.get("refresh_seconds") or 0),
        "summary_hint": str(m.get("summary_hint") or "").strip()[:200],
    }
    out["default_w"] = max(out["min_w"], num("default_w", 3, 1, 12))
    out["default_h"] = max(out["min_h"], num("default_h", 3, 1, 8))
    if out["refresh_seconds"]:
        out["refresh_seconds"] = max(30, min(86400, out["refresh_seconds"]))
    domains = []
    for d in m.get("domains") or []:
        d = str(d).strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0]
        if not HOST_RE.match(d) or d.endswith((".local", ".lan", ".internal", ".localhost")):
            raise WidgetError(f"'{d}' isn't an allowed internet host name.")
        if d not in domains:
            domains.append(d)
    out["domains"] = domains[:10]
    secrets = []
    for s in m.get("secrets") or []:
        s = str(s).strip().upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,40}", s):
            raise WidgetError(f"'{s}' isn't a valid key name.")
        if s not in secrets:
            secrets.append(s)
    out["secrets"] = secrets[:5]
    return out


def static_problems(html, manifest):
    """Things that would fail in the sandbox or that widgets may not do - fed back to the agent to fix."""
    p = []
    if len(html.encode()) > MAX_HTML:
        p.append(f"The widget is {len(html.encode()) // 1000} KB; keep it under 60 KB.")
    if re.search(r"<\s*(form|iframe|frame|object|embed|base)\b", html, re.I):
        p.append("Don't use <form>, <iframe>, <object>, <embed> or <base>.")
    if re.search(r"type\s*=\s*[\"']?password", html, re.I):
        p.append("Password fields aren't allowed.")
    if re.search(r"<\s*/?\s*(html|head|body)\b", html, re.I):
        p.append("Leave out <html>, <head> and <body>; write only the widget's content, <style> and <script>.")
    for src in re.findall(r"<script[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", html, re.I):
        host = urllib.parse.urlparse(src).hostname or ""
        if not src.startswith("https://") or host not in SCRIPT_HOSTS:
            p.append(f"Script {src} isn't allowed - only https://cdnjs.cloudflare.com or https://cdn.jsdelivr.net.")
    code = re.sub(r"Widget\.fetch", "", html)
    if re.search(r"(?<![\w.])fetch\s*\(|XMLHttpRequest|new\s+WebSocket|EventSource", code):
        p.append("Use Widget.fetch(...) for data - fetch, XMLHttpRequest, WebSocket and EventSource are blocked.")
    if re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", html):
        p.append("Use Widget.store.get/set - localStorage, sessionStorage, IndexedDB and cookies are blocked.")
    if re.search(r"\beval\s*\(|new\s+Function\s*\(|\b(alert|prompt|confirm)\s*\(", html):
        p.append("eval, new Function, alert, prompt and confirm are blocked.")
    used = set(SECRET_RE.findall(html))
    missing = used - set(manifest["secrets"])
    if missing:
        p.append(f"List these key names in the manifest's secrets: {', '.join(sorted(missing))}.")
    for url in re.findall(r"Widget\.fetch\(\s*[`'\"](https?://[^`'\"/\s$]+)", html):
        host = urllib.parse.urlparse(url).hostname or ""
        if host and not any(host == d or host.endswith("." + d) for d in manifest["domains"]):
            p.append(f"Add {host} to the manifest's domains (or don't fetch from it).")
    if "Widget.ready" not in html:
        p.append("Call Widget.ready() once the first content is shown.")
    return p


FETCH_URL_RE = re.compile(r"Widget\.fetch\(\s*([`'\"])(https://[^`'\"]+)\1")


def outline(value, depth=0, max_depth=4):
    """A compact picture of a JSON value's structure with sample values, so the agent parses the real shape."""
    pad = "  " * depth
    if isinstance(value, dict):
        if depth >= max_depth:
            return "{…}"
        lines = []
        for k, v in list(value.items())[:25]:
            lines.append(f"{pad}  {json.dumps(k)}: {outline(v, depth + 1, max_depth).lstrip()}")
        more = f"\n{pad}  … {len(value) - 25} more keys" if len(value) > 25 else ""
        return "{\n" + "\n".join(lines) + more + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        return f"[{len(value)} items, first: {outline(value[0], depth + 1, max_depth).lstrip()}]"
    text = json.dumps(value)
    return text if len(text) <= 60 else text[:57] + '…"'


def probe(urls, get_secret=lambda name: None):
    """Fetch URLs for the agent (GET only, same rules as widgets: https, public internet only) -> text report."""
    out = []
    for url in urls:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if not HOST_RE.match(host):
            out.append(f"{url}\n  -> not a valid https internet address")
            continue
        try:
            r = fetch_for_widget("probe", {"domains": [host], "secrets": list(set(SECRET_RE.findall(url)))},
                                 url, {}, get_secret)
        except WidgetError as e:
            out.append(f"{url}\n  -> failed: {e}")
            continue
        body = r["text"]
        try:
            shape = "JSON outline:\n" + outline(json.loads(body))
        except ValueError:
            shape = "Start of response:\n" + body[:2500]
        out.append(f"{url}\n  -> status {r['status']}, {r['content_type'] or 'no content type'}, {len(body)} bytes\n"
                   + shape[:6000])
    return "\n\n".join(out)


def check_sources(html, manifest, get_secret):
    """Fetch every fixed URL the widget calls; problems for the agent when one doesn't answer with usable data."""
    problems = []
    in_fetch = {u for _, u in FETCH_URL_RE.findall(html)}
    # also addresses kept in constants (const API = "https://..."), as long as they're on the widget's data sites
    literal = re.findall(r"[`'\"](https://[^`'\"\s]+)[`'\"]", html)
    urls = [u for u in dict.fromkeys(list(in_fetch) + literal)
            if (urllib.parse.urlsplit(u).hostname or "") in manifest.get("domains", [])
            and not re.search(r"\.(png|jpe?g|gif|svg|webp|ico)(\?|$)", u, re.I)]
    for url in urls[:6]:
        if "${" in url:
            continue                          # built at run time: can't check it here
        try:
            r = fetch_for_widget("check", manifest, url, {}, get_secret)
        except WidgetError as e:
            if "Add the key" not in str(e):   # a key the person hasn't added yet isn't the agent's fault
                problems.append(f"{url} failed: {e}")
            continue
        if r["status"] >= 400:
            problems.append(f"{url} returned HTTP {r['status']} - this address doesn't work. Probe and use a source "
                            "that does.")
            continue
        call = html[html.find(url) - 20: html.find(url) + len(url) + 120]
        if url in in_fetch and "json: false" not in call.replace("json:false", "json: false"):
            try:
                json.loads(r["text"])
            except ValueError:
                problems.append(f"{url} returns {r['content_type'] or 'text'}, not JSON - fetch it with {{json: false}} "
                                "and parse it (DOMParser for XML/RSS/HTML), or use a JSON source.")
    return problems


def _retry_after(error_text):
    """Seconds Gemini asks us to wait after a per-minute 429 (None if it doesn't say)."""
    m = re.search(r"retry(?:Delay\"?:\s*\"| in )([\d.]+)\s*s", error_text, re.I)
    return float(m.group(1)) if m else None


class Agent:
    """make_client(model) -> an llm client (OpenAICompatible / Claude / Ollama). models: list to try, best first.
    get_secret(name) -> a widget key, for probing / checking URLs that need one."""

    MAX_PROBE_ROUNDS = 2

    def __init__(self, make_client, models, get_secret=lambda name: None, on_progress=None):
        self.make_client = make_client
        self.models = models or [None]
        self.get_secret = get_secret
        self.on_progress = on_progress or (lambda text: None)

    def build(self, history, request, current=None, problems=None):
        """history: [{"role": "user"|"agent", "text"}]. current: {"manifest", "html"} being edited, or None.
        problems: errors from the self-check / static checks to fix. -> {"question"} or a built widget + "model".
        The agent may first probe data sources (up to MAX_PROBE_ROUNDS) - those results go back to it."""
        parts = []
        if history:
            parts.append("Conversation so far:\n" + "\n".join(f"{h['role'].upper()}: {h['text']}" for h in history[-12:]))
        if current:
            parts.append("Current widget manifest:\n" + json.dumps(current["manifest"]) +
                         "\n\nCurrent widget code:\n<widget>\n" + current["html"] + "\n</widget>")
        if problems:
            parts.append("The current widget has these problems - fix all of them and return the complete widget:\n- "
                         + "\n- ".join(problems))
        if request:
            parts.append(("Change requested: " if current else "Build this widget: ") + request)
        parts.append(time.strftime("Today is %A %d %B %Y, local time %H:%M (UTC%z)."))
        user = "\n\n".join(parts)
        for round_ in range(self.MAX_PROBE_ROUNDS + 1):
            out = self._ask(user)
            if "probe" not in out:
                return out
            if round_ == self.MAX_PROBE_ROUNDS:
                user += "\n\nNo more probing: build the widget now with the sources that worked."
                return self._ask(user)
            self.on_progress(f"Checking data sources: {', '.join(urllib.parse.urlsplit(u).hostname or u for u in out['probe'])}")
            user += ("\n\nYour probes:\n" + "\n".join(f"<probe>{u}</probe>" for u in out["probe"]) +
                     "\n\nProbe results:\n" + probe(out["probe"], self.get_secret))
        return out

    def _ask(self, user):
        last_error = None
        for model in list(self.models):
            for attempt in (1, 2):
                try:
                    client = self.make_client(model)
                    if hasattr(client, "base") and hasattr(client, "key"):   # OpenAI-style service (Gemini, OpenAI...)
                        text = stream_chat(client, SYSTEM, user, max_tokens=16000)
                    else:
                        text = client.chat(SYSTEM, user, timeout=150, max_tokens=16000)
                except LLMError as e:
                    last_error = e
                    wait = _retry_after(str(e)) if "429" in str(e) else None
                    if wait is not None and wait <= 45 and attempt == 1:   # a per-minute limit: wait it out once
                        self.on_progress(f"Waiting {wait:.0f} s for the AI service's per-minute limit…")
                        time.sleep(wait + 1)
                        continue
                    # busy, over quota, retired or not allowed for this key: next model (a bad key still stops)
                    if re.search(r"HTTP (403|404|429|500|502|503|504)|rate|overloaded|high demand|quota|"
                                 r"no longer available|timed out", str(e), re.I):
                        break
                    raise
                out = parse_answer(text)
                out["model"] = getattr(client, "model", model)
                if model in self.models and model != self.models[0]:   # it worked: try it first next time
                    self.models.remove(model)
                    self.models.insert(0, model)
                return out
        raise last_error or LLMError("No model available for the widget agent.")


FIRST_TOKEN_WAIT = 30     # seconds: a model that sends nothing this long is busy - try the next one
TOTAL_WAIT = 180


def stream_chat(client, system, user, max_tokens=16000):
    """Chat Completions with stream=True, so a stalled model is detected after FIRST_TOKEN_WAIT seconds instead of
    a full timeout. Returns the whole text. Raises LLMError ("timed out" / "HTTP nnn") like llm.py does."""
    import urllib.error
    import urllib.request
    payload = {"model": client.model, "stream": True, "max_tokens": max_tokens, "temperature": 0.2,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if getattr(client, "reasoning_effort", None):
        payload["reasoning_effort"] = client.reasoning_effort
    req = urllib.request.Request(client.base + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **client._headers()})
    start, parts = time.time(), []
    try:
        with urllib.request.urlopen(req, timeout=FIRST_TOKEN_WAIT) as resp:   # also the longest gap between chunks
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = (json.loads(data).get("choices") or [{}])[0].get("delta") or {}
                    except ValueError:
                        continue
                    parts.append(delta.get("content") or "")
                if time.time() - start > TOTAL_WAIT:
                    raise LLMError(f"{client.label} timed out (took over {TOTAL_WAIT} s).")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        delay = _retry_after(body)            # keep the "retry in N s" hint even when the body is long
        raise LLMError(f"{client.label} returned HTTP {e.code}: {body[:300]}" +
                       (f" (retry in {delay}s)" if delay is not None else "")) from e
    except (TimeoutError, socket.timeout) as e:
        raise LLMError(f"{client.label} timed out (no answer for {FIRST_TOKEN_WAIT} s).") from e
    except OSError as e:
        if "timed out" in str(e):
            raise LLMError(f"{client.label} timed out.") from e
        raise LLMError(f"Cannot reach {client.label} ({e}).") from e
    from llm import strip_thinking
    return strip_thinking("".join(parts))


def gemini_models(client, choice="auto"):
    """Models to try for Gemini: the chosen one, or (auto) best Pro then Flash from what the key can use."""
    if choice and choice != "auto":
        return [choice]
    try:
        names = client.models()
    except LLMError:
        return ["gemini-pro-latest", "gemini-flash-latest"]
    out = []
    for pattern in GEMINI_PREFS:
        hits = [n for n in names if re.match(pattern, n) and n not in out]
        keep = FLASH_FALLBACKS if "flash" in pattern and "latest" not in pattern else 1
        out += sorted(hits, key=lambda n: [int(x) for x in re.findall(r"\d+", n)] or [0], reverse=True)[:keep]
    return out or ["gemini-flash-latest"]


# ---------------------------------------------------------------- storage

class Store:
    """%LOCALAPPDATA%\\Dashboard\\custom_widgets\\<id>\\ {manifest.json, widget.html, history.json, store.json, versions\\}"""

    def __init__(self, root):
        self.root = root
        self._lock = threading.Lock()

    def _dir(self, wid):
        if not re.fullmatch(r"[a-f0-9]{8,32}", wid or ""):
            raise WidgetError("Bad widget id.")
        return os.path.join(self.root, wid)

    @staticmethod
    def new_id():
        return uuid.uuid4().hex[:12]

    def list(self):
        out = []
        if not os.path.isdir(self.root):
            return out
        for wid in sorted(os.listdir(self.root)):
            try:
                out.append({"id": wid, **self.manifest(wid)})
            except (OSError, ValueError, WidgetError):
                continue
        return out

    def exists(self, wid):
        return os.path.isfile(os.path.join(self._dir(wid), "manifest.json"))

    def manifest(self, wid):
        with open(os.path.join(self._dir(wid), "manifest.json"), encoding="utf-8") as f:
            return json.load(f)

    def html(self, wid):
        with open(os.path.join(self._dir(wid), "widget.html"), encoding="utf-8") as f:
            return f.read()

    def history(self, wid):
        try:
            with open(os.path.join(self._dir(wid), "history.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def save(self, wid, manifest, html, history):
        d = self._dir(wid)
        os.makedirs(os.path.join(d, "versions"), exist_ok=True)
        with self._lock:
            if os.path.isfile(os.path.join(d, "widget.html")):      # keep the previous version
                stamp = time.strftime("%Y%m%d-%H%M%S")
                shutil.copyfile(os.path.join(d, "widget.html"), os.path.join(d, "versions", f"{stamp}.html"))
                old = sorted(os.listdir(os.path.join(d, "versions")))
                for name in old[:-MAX_VERSIONS]:
                    os.remove(os.path.join(d, "versions", name))
            now = time.time()
            prev = self.manifest(wid) if self.exists(wid) else {}
            manifest = {**manifest, "created": prev.get("created", now), "updated": now}
            for name, data in (("manifest.json", json.dumps(manifest, indent=1)), ("widget.html", html),
                               ("history.json", json.dumps(history[-40:], indent=1))):
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(data)
        return manifest

    def delete(self, wid):
        shutil.rmtree(self._dir(wid), ignore_errors=True)

    # small per-widget data (Widget.store)
    def data_get(self, wid, key):
        try:
            with open(os.path.join(self._dir(wid), "store.json"), encoding="utf-8") as f:
                return json.load(f).get(str(key))
        except (OSError, ValueError):
            return None

    def data_set(self, wid, key, value):
        d = self._dir(wid)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "store.json")
        with self._lock:
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                data = {}
            if value is None:
                data.pop(str(key), None)
            else:
                data[str(key)] = value
            text = json.dumps(data)
            if len(text) > MAX_STORE:
                raise WidgetError("This widget's saved data is full (100 KB).")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return True

    # sharing: manifest + code only - never keys or saved data
    def export(self, wid):
        m = {k: v for k, v in self.manifest(wid).items() if k not in ("created", "updated")}
        return json.dumps({"format": "dashwidget/1", "manifest": m, "html": self.html(wid)}, indent=1)

    def import_(self, text):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise WidgetError("That isn't a widget file.") from e
        if not isinstance(data, dict) or data.get("format") != "dashwidget/1":
            raise WidgetError("That isn't a widget file.")
        manifest = clean_manifest(data.get("manifest"))
        html = str(data.get("html") or "")
        problems = static_problems(html, manifest)
        if problems:
            raise WidgetError("This widget file has problems: " + " ".join(problems))
        return manifest, html


# ---------------------------------------------------------------- the frame page

def frame_html(manifest, html, sdk_js, wid):
    config = json.dumps({"id": wid, "refresh": manifest.get("refresh_seconds", 0)})
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<style>{THEME_CSS}</style><script>window.__WIDGET__ = {config};\n{sdk_js}</script></head>"
            f"<body>{html}</body></html>")


def csp(manifest):
    imgs = " ".join(f"https://{d}" for d in manifest.get("domains", []))
    scripts = " ".join(f"https://{h}" for h in SCRIPT_HOSTS)
    return (f"default-src 'none'; script-src 'unsafe-inline' {scripts}; style-src 'unsafe-inline'; "
            f"img-src data: blob: {imgs}; font-src data:; connect-src 'none'; media-src 'none'; "
            f"base-uri 'none'; form-action 'none'; frame-src 'none'; worker-src 'none'")


# ---------------------------------------------------------------- the data proxy

class _PinnedHTTPS(http.client.HTTPSConnection):
    """Connects to the IP we already checked (no second DNS lookup), with TLS verified for the real host name."""

    def __init__(self, host, ip, timeout):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _public_ip(host):
    """The first address of host, refusing anything private, local or reserved (LAN, this PC, link-local...)."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise WidgetError(f"Can't find {host}.") from e
    addrs = [info[4][0] for info in infos]
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise WidgetError(f"{host} points to a private or local address - widgets can only reach the internet.")
    return addrs[0]


_last_call = {}
_rate_lock = threading.Lock()


def fetch_for_widget(wid, manifest, url, opts, get_secret):
    """One request for a widget. Only https, only approved hosts, never private addresses, keys filled in here."""
    opts = opts if isinstance(opts, dict) else {}
    method = str(opts.get("method") or "GET").upper()
    if method not in ("GET", "POST"):
        raise WidgetError("Widgets can only GET or POST.")
    body = opts.get("body")
    if body is not None and (not isinstance(body, str) or len(body) > 20_000):
        raise WidgetError("The request body must be text under 20 KB.")

    def fill(text):
        def sub(m):
            name = m.group(1)
            if name not in manifest.get("secrets", []):
                raise WidgetError(f"Key {name} isn't declared by this widget.")
            value = get_secret(name)
            if not value:
                raise WidgetError(f"Add the key {name} for this widget in Widget Studio.")
            return value
        return SECRET_RE.sub(sub, text)

    headers = {"User-Agent": "Mozilla/5.0 (Dashboard widget)", "Accept": "application/json, text/*;q=0.9, */*;q=0.5"}
    for k, v in (opts.get("headers") or {}).items():
        k = str(k).strip()
        if k.lower() in ALLOWED_HEADERS or k.lower().startswith("x-"):
            headers[k] = fill(str(v))[:2000]
    with _rate_lock:                             # at most one request per second per widget
        wait = _last_call.get(wid, 0) + 1.0 - time.time()
        _last_call[wid] = time.time() + max(0, wait)
    if wait > 0:
        time.sleep(wait)

    for _ in range(4):                           # follows up to 3 redirects, checking each one
        parts = urllib.parse.urlsplit(fill(str(url)))
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host or parts.port not in (None, 443) or parts.username:
            raise WidgetError("Widgets can only fetch https://host/... addresses.")
        if not any(host == d or host.endswith("." + d) for d in manifest.get("domains", [])):
            raise WidgetError(f"{host} isn't one of this widget's approved sites.")
        ip = _public_ip(host)
        conn = _PinnedHTTPS(host, ip, FETCH_TIMEOUT)
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        try:
            conn.request(method, path, body=body.encode() if body else None, headers={**headers, "Host": host})
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308) and resp.getheader("Location"):
                url = urllib.parse.urljoin(f"https://{host}{path}", resp.getheader("Location"))
                method, body = ("GET", None) if resp.status == 303 else (method, body)
                continue
            data = resp.read(MAX_FETCH + 1)
            if len(data) > MAX_FETCH:
                raise WidgetError("That response is too big for a widget (over 2 MB).")
            ctype = resp.getheader("Content-Type", "")
            charset = (re.search(r"charset=([\w-]+)", ctype) or [None, "utf-8"])[1]
            return {"status": resp.status, "content_type": ctype, "text": data.decode(charset, "replace")}
        except (OSError, http.client.HTTPException) as e:
            raise WidgetError(f"Couldn't reach {host}: {e}") from e
        finally:
            conn.close()
    raise WidgetError("Too many redirects.")
