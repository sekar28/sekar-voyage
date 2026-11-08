# PyInstaller recipe for Sekar's Dashboard, with voice (wake word + local and cloud speech-to-text, CPU only).
# Built by build.ps1; run from this folder:  python -m PyInstaller --noconfirm Dashboard.spec
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

APP = os.path.abspath(os.path.join(SPECPATH, ".."))
SHARED = os.path.abspath(os.path.join(APP, "..", "shared"))

# openWakeWord's data files, but not models already downloaded on this PC: they are CC BY-NC-SA and each PC
# downloads its own on first use (into _internal\openwakeword\resources\models, created then).
oww = [(src, dst) for src, dst in collect_data_files("openwakeword")
       if not src.lower().endswith((".onnx", ".tflite"))]

a = Analysis(
    [os.path.join(APP, "app.py")],
    pathex=[APP, SHARED],
    binaries=collect_dynamic_libs("ctranslate2"),
    datas=[(os.path.join(APP, "ui"), "ui"),
           (os.path.join(APP, "LICENSE"), "."),
           (os.path.join(APP, "THIRD_PARTY_NOTICES.md"), "."),
           (os.path.join(APP, "README.md"), ".")]
          + oww + collect_data_files("faster_whisper"),
    # The alias stubs (llm.py, voice.py, ...) load sekar_common with importlib, which PyInstaller can't see.
    hiddenimports=["sekar_common", "sekar_common.llm", "sekar_common.llm_anthropic", "sekar_common.secrets_store",
                   "sekar_common.voice", "sekar_common.bell", "openwakeword.model", "openwakeword.utils"]
                  # scipy and sklearn load parts of themselves by name (array_api_compat...), unseen by PyInstaller.
                  # Collecting all of scipy skips array_api_compat (its torch/cupy parts fail to import), so name it.
                  + collect_submodules("scipy", filter=lambda m: ".tests" not in m)
                  + collect_submodules("sklearn", filter=lambda m: ".tests" not in m)
                  + [m for pkg in ("scipy._external.array_api_compat", "sklearn.externals.array_api_compat")
                     for m in collect_submodules(pkg, filter=lambda n: not any(
                         x in n for x in (".torch", ".cupy", ".dask", ".jax", ".tests")))]
                  # local speech-to-text (used when there's no cloud key), loaded only when first needed
                  + collect_submodules("faster_whisper") + collect_submodules("ctranslate2") + collect_submodules("av"),
    # Piper is GPL-3.0 and never shipped; NVIDIA GPU libraries are optional and huge; the rest isn't used
    # (torch is only for training wake words). scipy and sklearn stay: openwakeword.model imports them.
    excludes=["piper", "nvidia", "torch", "torchaudio", "tensorflow", "matplotlib", "pandas", "tkinter",
              "IPython", "jupyter"],
    # Shipped as source: its import-time `for obj in [... dir() ...]: exec('del ' + obj)` finds nothing when run
    # from PyInstaller's precompiled copy, and the `del obj` after it fails ("name 'obj' is not defined").
    module_collection_mode={"scipy.stats._distn_infrastructure": "py"},
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Dashboard",
          icon=os.path.join(APP, "ui", "dashboard.ico"), version=os.path.join(SPECPATH, "version_info.txt"),
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Dashboard", upx=False)
