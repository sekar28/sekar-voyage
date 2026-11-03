"""Moved to shared/sekar_common/voice.py; this alias keeps `import voice` working."""
import importlib
import os
import sys

_shared = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
if _shared not in sys.path:
    sys.path.insert(0, _shared)
_mod = importlib.import_module("sekar_common.voice")
# Words the dashboard expects; given to Whisper / Gemini so they spell them right.
_mod.VOCAB = ("Dashboard voice commands: play, pause, resume, next song, volume, maximize, go back, photos, music, "
              "YouTube, stocks, market, Nifty, Sensex, Nasdaq, S&P 500, Dow Jones, Bitcoin, cyber attacks, ransomware, "
              "CISA, WhatsApp, Jarvis.")
sys.modules[__name__] = _mod
