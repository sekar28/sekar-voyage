# PyInstaller recipe for Sekar's System Utilities (typing-only build: no wake word, speech-to-text or bell).
# Built by build.ps1; run from this folder:  python -m PyInstaller --noconfirm SystemUtilities.spec
import os

APP = os.path.abspath(os.path.join(SPECPATH, ".."))
SHARED = os.path.abspath(os.path.join(APP, "..", "shared"))

a = Analysis(
    [os.path.join(APP, "app.py")],
    pathex=[APP, SHARED],
    datas=[(os.path.join(APP, "ui"), "ui"),
           (os.path.join(APP, "LICENSE"), "."),
           (os.path.join(APP, "THIRD_PARTY_NOTICES.md"), "."),
           (os.path.join(APP, "docs", "HELP.md"), "docs")],
    # The alias stubs (llm.py, ...) load sekar_common with importlib, which PyInstaller can't see.
    hiddenimports=["sekar_common", "sekar_common.llm", "sekar_common.llm_anthropic", "sekar_common.secrets_store",
                   "agent"],
    # Voice is optional and left out of this build; Piper is GPL-3.0 and never shipped.
    excludes=["voice_host", "voice", "tts", "bell", "sekar_common.voice", "sekar_common.bell",
              "numpy", "sounddevice", "openwakeword", "faster_whisper", "ctranslate2", "onnxruntime", "piper",
              "pillow_heif", "tkinter", "storage_analyzer"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SystemUtilities",
          icon=os.path.join(APP, "ui", "icon.ico"), version=os.path.join(SPECPATH, "version_info.txt"),
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SystemUtilities", upx=False)
