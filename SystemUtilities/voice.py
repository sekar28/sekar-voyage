"""Moved to shared/sekar_common/voice.py; this alias keeps `import voice` working."""
import importlib
import os
import sys

_shared = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
if _shared not in sys.path:
    sys.path.insert(0, _shared)
_mod = importlib.import_module("sekar_common.voice")
# Words the assistant expects; given to Whisper / Gemini so they spell them right.
_mod.VOCAB = ("PC care voice commands for Jarvis: clean junk, temp files, Downloads, Documents, duplicates, organise, "
              "processes, orphan processes, suspicious, startup apps, boost, RAM, memory, CPU, drivers, Windows Update, "
              "Recycle Bin, Defender, yes, no, review, undo, Sekar's System Utilities.")
sys.modules[__name__] = _mod
