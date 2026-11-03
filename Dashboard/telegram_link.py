"""Telegram link for the task list: a small bot that texts you about overdue / ageing tasks and takes commands back.
Standard library only. The bot token is the "telegram" secret in the Windows Credential Manager (never a file).

Only ONE Telegram account may command it: your private chat is paired by sending the bot "/pair <code>", where the
code is shown in the dashboard's Settings. Messages from any other chat are ignored. It long-polls Telegram, so it
needs no open port and no public address."""

import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"
PAIR_MINUTES = 10
PAIR_ATTEMPTS = 5


class TelegramError(Exception):
    pass


class Bot:
    def __init__(self, get_token, get_chat_id, set_chat_id, on_text, quitting):
        """get_token() -> str|None; get_chat_id() -> int|None; set_chat_id(int|None); on_text(text) -> reply str;
        quitting() -> True once the app is closing."""
        self._get_token, self._get_chat_id, self._set_chat_id = get_token, get_chat_id, set_chat_id
        self._on_text, self._quitting = on_text, quitting
        self._wake = threading.Event()
        self._pair_code, self._pair_until, self._pair_tries = None, 0.0, 0
        self.status = {"state": "off", "bot": None, "error": None}
        self._token_seen = None
        self._offset = 0

    # ---------------------------------------------------------------- API
    def _call(self, method, params=None, timeout=15):
        token = self._get_token()
        if not token:
            raise TelegramError("No bot token saved.")
        data = urllib.parse.urlencode(params or {}).encode()
        req = urllib.request.Request(API.format(token=token, method=method), data=data)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"ok": False, "description": f"HTTP {e.code}"}
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TelegramError(str(getattr(e, "reason", e)).replace(token, "<token>")) from None
        if not body.get("ok"):
            raise TelegramError(str(body.get("description", "Telegram refused the request.")).replace(token, "<token>"))
        return body["result"]

    def send(self, text, chat_id=None):
        chat_id = chat_id or self._get_chat_id()
        if not chat_id:
            raise TelegramError("Not paired yet.")
        for i in range(0, len(text), 4000):          # Telegram's limit is 4096 characters
            self._call("sendMessage", {"chat_id": chat_id, "text": text[i:i + 4000]})

    def check(self):
        """Look up the bot (validates the token). Returns its @username."""
        me = self._call("getMe")
        return "@" + me.get("username", "")

    # ---------------------------------------------------------------- pairing
    def pair_start(self):
        """A fresh one-time code to send to the bot as '/pair <code>'. Valid for a few minutes."""
        self._pair_code = f"{secrets.randbelow(10**6):06d}"
        self._pair_until, self._pair_tries = time.time() + PAIR_MINUTES * 60, 0
        self._wake.set()
        return {"code": self._pair_code, "minutes": PAIR_MINUTES, "bot": self.status.get("bot")}

    def unpair(self):
        self._set_chat_id(None)
        self._pair_code = None

    def reload(self):
        """Token changed: re-check it and restart the poll."""
        self._token_seen = None
        self.status = {"state": "off", "bot": None, "error": None}
        self._wake.set()

    def public(self):
        return {**self.status, "paired": bool(self._get_chat_id()),
                "pairing": bool(self._pair_code and time.time() < self._pair_until)}

    # ---------------------------------------------------------------- polling
    def start(self):
        threading.Thread(target=self._run, daemon=True, name="telegram").start()

    def _run(self):
        backoff = 5
        while not self._quitting():
            token = self._get_token()
            if not token:
                self.status = {"state": "off", "bot": None, "error": None}
                self._token_seen = None
                self._wake.wait(30)
                self._wake.clear()
                continue
            try:
                if token != self._token_seen:
                    self.status = {"state": "connecting", "bot": None, "error": None}
                    name = self.check()
                    self._call("deleteWebhook")          # long polling cannot work while a webhook is set
                    self._token_seen, self._offset = token, 0
                    self.status = {"state": "ok", "bot": name, "error": None}
                updates = self._call("getUpdates", {"offset": self._offset, "timeout": 25,
                                                    "allowed_updates": json.dumps(["message"])}, timeout=40)
                backoff = 5
                for u in updates:
                    self._offset = u["update_id"] + 1
                    try:
                        self._handle(u.get("message") or {})
                    except TelegramError:
                        pass
                if self.status["state"] != "ok":
                    self.status = {**self.status, "state": "ok", "error": None}
            except TelegramError as e:
                self.status = {**self.status, "state": "error", "error": str(e)}
                self._token_seen = None if "Unauthorized" in str(e) else self._token_seen
                self._wake.wait(backoff)
                self._wake.clear()
                backoff = min(backoff * 2, 120)
            except Exception as e:                        # never let the thread die
                self.status = {**self.status, "state": "error", "error": type(e).__name__}
                self._wake.wait(30)
                self._wake.clear()

    def _handle(self, msg):
        chat = msg.get("chat") or {}
        text = (msg.get("text") or "").strip()
        cid = chat.get("id")
        if not cid or not text or chat.get("type") != "private":
            return
        paired = self._get_chat_id()
        if paired and cid == paired:
            reply = self._on_text(text)
            if reply:
                self.send(reply, cid)
            return
        if paired:
            return                                       # someone else: ignored, no reply
        if text.lower().startswith("/pair"):
            code = text[5:].strip()
            live = self._pair_code and time.time() < self._pair_until
            if live and secrets.compare_digest(code, self._pair_code):
                self._set_chat_id(cid)
                self._pair_code = None
                self.send("✅ Paired. Your task list is now linked.\n\n" + self._on_text("help"), cid)
                return
            self._pair_tries += 1
            if self._pair_tries >= PAIR_ATTEMPTS:
                self._pair_code = None
            self.send("That code isn't right or has expired. Open Dashboard → Settings → Tiles → Telegram for a new one.", cid)
        elif text.lower().startswith("/start"):
            self.send("Hi! To link this chat to your Dashboard tasks, open Dashboard → Settings → Tiles → Telegram, "
                      "press 'Pair', then send me: /pair <the code>", cid)
