"""Jarvis's own ears and voice in System Utilities, for when the Dashboard isn't running.

Only one app listens for "Hey Jarvis" at a time: while the Dashboard runs it owns the wake word (and speaks the
assistant's alerts), and here only push-to-talk works (mic button / Ctrl+Alt+J). When the Dashboard closes, this
takes over the wake word, speaks replies and alerts, and rings the bell for critical ones. It checks every few seconds.

Speech settings (cloud/local speech-to-text, wake word, Whisper model, pause) and the voice files are shared with the
Dashboard when it's installed, so both sound and behave the same.
"""

import ctypes
import json
import os
import threading
import time

import bell
import quickclean
import secrets_store
import tts
import voice

DATA_DIR = os.path.join(quickclean.LOCAL, "StorageAnalyzer")
DASH_DIR = os.path.join(quickclean.LOCAL, "Dashboard")
VOICES_DIR = os.path.join(DASH_DIR, "voices") if os.path.isdir(os.path.join(DASH_DIR, "voices")) \
    else os.path.join(DATA_DIR, "voices")
VK_J = 0x4A                                   # Ctrl+Alt+J: talk to Jarvis
FOLLOWUP_SECONDS = 20
STT_DEFAULTS = {"wake_word": "hey_jarvis", "stt_mode": "cloud", "stt_base": voice.STT_PRESETS[0]["base"],
                "stt_model": voice.STT_PRESETS[0]["model"], "whisper_model": "auto", "whisper_device": "auto",
                "stt_pause": voice.DEFAULT_PAUSE, "tts_voice": None}
MODES = {"wake": 'Listen for "Hey Jarvis" when the Dashboard is closed', "ptt": "Push-to-talk only", "off": "Off"}


def dashboard_running():
    """True while the Dashboard app is open (its instance.json points at a live process)."""
    try:
        with open(os.path.join(DASH_DIR, "instance.json"), encoding="utf-8") as f:
            pid = int(json.load(f)["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


class VoiceHost:
    def __init__(self, api, agent):
        self.api, self.agent = api, agent
        self.speaker = tts.Speaker(VOICES_DIR, self._stt_settings().get("tts_voice"))
        self.bell = bell.Bell()
        self.loop = None
        self.loop_wake = None                 # True / False for the running loop
        self.state = {"state": "off", "detail": None}
        self.dashboard = dashboard_running()
        self._followup_until = 0
        self._stop = threading.Event()
        agent.listeners.append(self._on_event)

    # ------------------------------------------------------------ settings
    def mode(self):
        return self.api._settings.get("agent_voice", "wake")

    def speak_on(self):
        return bool(self.api._settings.get("agent_speak", True))

    def _stt_settings(self):
        """The Dashboard's speech settings when it's installed (same choices in both apps), else defaults."""
        s = dict(STT_DEFAULTS)
        try:
            with open(os.path.join(DASH_DIR, "settings.json"), encoding="utf-8") as f:
                dash = json.load(f)
            s.update({k: dash[k] for k in STT_DEFAULTS if dash.get(k) not in (None, "")})
        except (OSError, ValueError):
            pass
        return s

    @staticmethod
    def _stt_key():
        key = secrets_store.get_secret("stt")
        return key

    def public(self):
        return {**self.state, "mode": self.mode(), "modes": MODES, "speak": self.speak_on(), "dashboard": self.dashboard,
                "wake": bool(self.loop_wake), "hotkey": "Ctrl+Alt+J"}

    # ------------------------------------------------------------ running the mic
    def start(self):
        threading.Thread(target=self._watch, daemon=True, name="voice-host").start()
        voice.Hotkeys({VK_J: self.push_to_talk}).start()

    def stop(self):
        self._stop.set()
        self._stop_loop()
        self.speaker.stop()

    def _watch(self):
        while not self._stop.is_set():
            try:
                self.dashboard = dashboard_running()
                mode = self.mode()
                want = None if mode == "off" else (mode == "wake" and not self.dashboard)
                if want is None:
                    self._stop_loop()
                elif self.loop is None or not self.loop.is_alive() or self.loop_wake != want:
                    if self.loop is None or self.state["state"] not in ("recording", "transcribing"):
                        self._stop_loop()
                        self._start_loop(want)
            except Exception:
                pass
            self._stop.wait(4)

    def _start_loop(self, wake):
        self.loop_wake = wake
        self.loop = voice.VoiceLoop(self._stt_settings, self._stt_key, self._on_state,
                                    lambda text, how: threading.Thread(target=self._heard, args=(text, how), daemon=True).start(),
                                    lambda: self.speaker.speaking, os.path.join(DATA_DIR, "last_request.wav"), wake=wake)
        self.loop.start()

    def _stop_loop(self):
        if self.loop is not None:
            self.loop.stop()
            self.loop.join(timeout=3)
        self.loop, self.loop_wake = None, None
        if self.mode() == "off":
            self._on_state("off")

    def _on_state(self, state, detail=None):
        self.state = {"state": state, "detail": detail}
        self.api._emit("agent_voice", self.public())

    def push_to_talk(self):
        """Mic button / Ctrl+Alt+J: record one request now (no wake word needed)."""
        if self.mode() == "off":
            raise RuntimeError("Voice is off - turn it on in the Jarvis panel.")
        if self.loop is None or not self.loop.is_alive():
            self._start_loop(False)
            for _ in range(40):                       # wait for the microphone to open
                if self.state["state"] == "listening":
                    break
                time.sleep(0.1)
        self.speaker.stop()
        self.loop.push_to_talk()

    # ------------------------------------------------------------ talking
    def _heard(self, text, how):
        r = self.agent.ask(text, "voice")
        self._say(r["say"], ask_again=r["expect_reply"])

    def _say(self, text, ask_again=False, critical=False):
        if critical:
            self.bell.chime()
        if not text or not self.speak_on():
            return
        done = threading.Event()
        self.speaker.say(text, on_end=done.set)
        if ask_again:
            def follow():                              # listen once more without the wake word, for "yes" / "no"
                done.wait(120)
                if self.loop is not None and self.mode() != "off":
                    self.loop.push_to_talk()
            threading.Thread(target=follow, daemon=True).start()

    def _on_event(self, ev):
        """Alerts and finished jobs: spoken here only while the Dashboard is closed (it speaks them otherwise)."""
        if self.dashboard or dashboard_running() or self.mode() == "off":
            return
        threading.Thread(target=self._say, args=(ev["say"], ev.get("expect_reply"), ev.get("critical")),
                         daemon=True).start()
