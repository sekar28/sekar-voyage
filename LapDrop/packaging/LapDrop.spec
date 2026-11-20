# PyInstaller recipe for LapDrop. Built by build.ps1; run from this folder:
#   python -m PyInstaller --noconfirm LapDrop.spec
import os

APP = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(APP, "lapdrop.py")],
    pathex=[APP],
    datas=[(os.path.join(APP, "ui"), "ui")],
    # Imported inside functions; named here so they are never missed.
    hiddenimports=["segno", "cryptography", "cryptography.x509", "winreg"],
    excludes=["tkinter", "numpy", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LapDrop",
          icon=os.path.join(APP, "ui", "icon.ico"), version=os.path.join(SPECPATH, "version_info.txt"),
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="LapDrop", upx=False)
