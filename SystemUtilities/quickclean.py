"""Quick clean: well-known locations whose contents can always be removed, plus the delete/recycle primitives.

Every destructive operation in the app goes through this module, and each one checks `is_deletable` first.
"""

import ctypes
import glob
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from ctypes import wintypes

LOCAL = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
ROAMING = os.environ.get("APPDATA", os.path.join(os.path.dirname(LOCAL), "Roaming"))
LOCALLOW = os.path.join(os.path.dirname(LOCAL), "LocalLow")
WINDIR = os.environ.get("WINDIR", r"C:\Windows")
PROGRAMDATA = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
TEMP = os.environ.get("TEMP", os.path.join(LOCAL, "Temp"))
SYSDRIVE = os.environ.get("SystemDrive", "C:") + "\\"
OLD_DAYS = 7          # log files newer than this are kept - they may be needed to troubleshoot something now
LOG_FILE = re.compile(r"\.(log|etl)(\.\d+|\.old|\.bak)?$|\.old$|\.log\d+$", re.I)
LOG_DIRS = {"logs", "log"}
LOG_SKIP = [os.path.join(PROGRAMDATA, "Microsoft"), os.path.join(LOCAL, "StorageAnalyzer")]


def _old(path):
    try:
        return time.time() - os.stat(path).st_mtime > OLD_DAYS * 86400
    except OSError:
        return False


def _app_logs():
    """Old log files inside folders named Logs/Log, up to 4 levels below the app-data folders."""
    found = []
    for root in (LOCAL, ROAMING, LOCALLOW, PROGRAMDATA):
        base = root.rstrip("\\").count("\\")
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            if any(_inside(dirpath, s) for s in LOG_SKIP):
                dirnames[:] = []
                continue
            in_logs = any(part.lower() in LOG_DIRS for part in dirpath[len(root):].split("\\"))
            if in_logs:
                found += [os.path.join(dirpath, f) for f in filenames
                          if LOG_FILE.search(f) and _old(os.path.join(dirpath, f))]
            elif dirpath.count("\\") - base >= 4:
                dirnames[:] = []          # deep enough - logs live near the top of an app's folder
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
    return found


def _windows_logs():
    """Old Windows setup / update / servicing logs (all regenerated as needed)."""
    found = []
    for pattern in (r"Logs\CBS\*.log", r"Logs\CBS\CbsPersist_*.cab", r"Logs\DISM\*.log", r"Logs\WindowsUpdate\*.etl",
                    r"Logs\MoSetup\*.log", r"Panther\*.log", r"Logs\SIH\*.etl", r"Logs\NetSetup\*.etl"):
        found += [p for p in glob.glob(os.path.join(WINDIR, pattern)) if _old(p)]
    return found


def _driver_leftovers():
    """Folders driver installers unpack into at the drive root (C:\\NVIDIA, C:\\AMD) and leave behind."""
    return [p for p in (os.path.join(SYSDRIVE, "NVIDIA"), os.path.join(SYSDRIVE, "AMD")) if os.path.isdir(p)]


SHORTCUT_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$sh = New-Object -ComObject WScript.Shell
$dirs = @(
  @([Environment]::GetFolderPath('Desktop'), $false), @([Environment]::GetFolderPath('CommonDesktopDirectory'), $false),
  @([Environment]::GetFolderPath('StartMenu'), $true), @([Environment]::GetFolderPath('CommonStartMenu'), $true),
  @([Environment]::GetFolderPath('Recent'), $false))
$out = foreach ($d in $dirs) {
  if (-not $d[0] -or -not (Test-Path -LiteralPath $d[0])) { continue }
  $files = if ($d[1]) { Get-ChildItem -LiteralPath $d[0] -Filter *.lnk -Recurse -File -ErrorAction SilentlyContinue }
           else { Get-ChildItem -LiteralPath $d[0] -Filter *.lnk -File -ErrorAction SilentlyContinue }
  foreach ($f in $files) { try { [pscustomobject]@{ p = $f.FullName; t = $sh.CreateShortcut($f.FullName).TargetPath } } catch {} }
}
ConvertTo-Json -InputObject @($out) -Compress
"""
_shortcut_targets = {}


def _broken_shortcuts():
    """Desktop / Start Menu shortcuts whose target file is gone. Not flagged: shortcuts to a drive that isn't
    connected right now (USB, network), to network paths, to web pages or Store apps (they have no file target),
    and Windows Installer 'advertised' shortcuts (they repair themselves)."""
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_SCRIPT],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        items = json.loads(proc.stdout or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    broken = []
    for it in items:
        target = (it.get("t") or "").strip()
        if not target or target.startswith("\\\\") or "://" in target or not re.match(r"^[a-z]:\\", target, re.I):
            continue
        if not os.path.exists(target[:3]) or _inside(target, os.path.join(WINDIR, "Installer")):
            continue
        if not os.path.exists(target):
            broken.append(it["p"])
            _shortcut_targets[_norm(it["p"])] = target
    return broken

CHROMIUM = [os.path.join(LOCAL, p) for p in (r"Google\Chrome\User Data", r"Microsoft\Edge\User Data",
                                             r"BraveSoftware\Brave-Browser\User Data")]

# Each target: what it is, where, and how it is cleaned.
#   kind "contents":  delete everything inside the folders (the folders themselves stay)
#   kind "files":     delete files matching the glob patterns
#   kind "shortcuts": move the files to the Recycle Bin (restorable)
#   kind "cleanmgr":  let Windows' own Disk Cleanup remove them (folders Windows locks down)
#   kind "recycle":   empty the Recycle Bin
# "finder": a function listing the files/folders at measuring time, on top of (or instead of) "paths".
TARGETS = [
    {"id": "user_temp", "name": "Temporary files (yours)", "icon": "clock", "kind": "contents", "default": True,
     "desc": "Leftovers from apps and installers. Files still in use are skipped automatically.",
     "paths": [TEMP]},
    {"id": "win_temp", "name": "Windows temporary files", "icon": "clock", "kind": "contents", "default": True,
     "admin": True, "desc": "Temporary files created by Windows and system installers.",
     "paths": [os.path.join(WINDIR, "Temp")]},
    {"id": "browser", "name": "Browser caches", "icon": "globe", "kind": "contents", "default": True,
     "desc": "Cached web pages and images from Chrome, Edge, Brave and Firefox. You stay signed in; "
             "sites load a little slower the first time.",
     "apps": ["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe"],
     "paths": [os.path.join(base, "*", sub) for base in CHROMIUM
               for sub in (r"Cache\Cache_Data", "Code Cache", "GPUCache", r"Service Worker\CacheStorage")]
     + [os.path.join(LOCAL, r"Mozilla\Firefox\Profiles\*\cache2")]},
    {"id": "shaders", "name": "Graphics shader caches", "icon": "chip", "kind": "contents", "default": True,
     "desc": "Pre-compiled graphics shaders. Rebuilt automatically; games may stutter briefly on first launch.",
     "paths": [os.path.join(LOCAL, "D3DSCache"), os.path.join(LOCAL, r"NVIDIA\DXCache"),
               os.path.join(LOCAL, r"NVIDIA\GLCache"), os.path.join(LOCALLOW, r"NVIDIA\PerDriverVersion\DXCache"),
               os.path.join(LOCAL, r"AMD\DxCache"), os.path.join(LOCAL, r"AMD\DxcCache")]},
    {"id": "crash", "name": "Crash dumps & error reports", "icon": "bug", "kind": "contents", "default": True,
     "desc": "Reports saved when apps crash. Only useful when troubleshooting a crash.",
     "paths": [os.path.join(LOCAL, "CrashDumps"), os.path.join(LOCAL, r"Microsoft\Windows\WER"),
               os.path.join(PROGRAMDATA, r"Microsoft\Windows\WER\ReportArchive"),
               os.path.join(PROGRAMDATA, r"Microsoft\Windows\WER\ReportQueue"),
               os.path.join(WINDIR, "Minidump")]},
    {"id": "thumbs", "name": "Thumbnail cache", "icon": "image", "kind": "files", "default": True,
     "desc": "Picture previews Explorer keeps. Rebuilt automatically when you browse folders. "
             "Files Explorer is using are skipped.",
     "paths": [os.path.join(LOCAL, r"Microsoft\Windows\Explorer\thumbcache_*.db")]},
    {"id": "winupdate", "name": "Windows Update leftovers", "icon": "download", "kind": "contents", "default": True,
     "admin": True, "desc": "Update packages that are already installed. Windows downloads anything it still needs.",
     "paths": [os.path.join(WINDIR, r"SoftwareDistribution\Download"),
               os.path.join(WINDIR, r"ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache")]},
    {"id": "program_downloads", "name": "Driver installer downloads", "icon": "download", "kind": "contents", "default": True,
     "desc": "Setup copies of graphics drivers the NVIDIA/AMD software downloaded and unpacked. Your installed drivers "
             "keep working - only the installers go.",
     "paths": [os.path.join(PROGRAMDATA, r"NVIDIA Corporation\Downloader")], "finder": _driver_leftovers},
    {"id": "program_logs", "name": "App log files", "icon": "files", "kind": "files", "default": True,
     "desc": f"Old logs apps write while running, older than {OLD_DAYS} days. Recent logs are kept in case you need "
             "to troubleshoot something.", "paths": [], "finder": _app_logs},
    {"id": "program_temp", "name": "App temp files", "icon": "clock", "kind": "contents", "default": True,
     "desc": "Temporary files and web caches of Microsoft Store apps. Recreated as the apps need them.",
     "paths": [os.path.join(LOCAL, r"Packages\*\AC\Temp"), os.path.join(LOCAL, r"Packages\*\AC\INetCache")]},
    {"id": "win_logs", "name": "Windows log files", "icon": "files", "kind": "files", "default": True, "admin": True,
     "desc": f"Old Windows setup, update and servicing logs (older than {OLD_DAYS} days).", "paths": [],
     "finder": _windows_logs},
    {"id": "broken_shortcuts", "name": "Broken shortcuts", "icon": "x", "kind": "shortcuts", "default": True,
     "desc": "Desktop, Start Menu and Recent items shortcuts to programs or files that no longer exist. They go to the "
             "Recycle Bin, so you can restore any of them.", "paths": [], "finder": _broken_shortcuts},
    {"id": "win_setup", "name": "Windows setup files", "icon": "windows", "kind": "cleanmgr", "default": False,
     "admin": True, "desc": "Your previous Windows version and files left from a Windows upgrade. Removed with Windows' "
                            "own Disk Cleanup. After this you can't go back to the previous Windows version.",
     "paths": [os.path.join(SYSDRIVE, "Windows.old"), os.path.join(SYSDRIVE, "$WINDOWS.~BT"),
               os.path.join(SYSDRIVE, "$Windows.~WS"), os.path.join(SYSDRIVE, "ESD")]},
    {"id": "recycle", "name": "Recycle Bin", "icon": "trash", "kind": "recycle", "default": False,
     "desc": "Files you already deleted. Emptying it makes them unrecoverable, so check it first.", "paths": []},
]
TARGET_BY_ID = {t["id"]: t for t in TARGETS}

# Never delete anything at or above these (besides the explicit quick-clean folders inside Windows).
PROTECTED_ROOTS = [WINDIR, os.environ.get("ProgramFiles", r"C:\Program Files"),
                   os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), PROGRAMDATA]


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def running_processes():
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except OSError:
        return set()
    return {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line}


_found = {}   # target id -> what its finder listed last time; the only dynamic paths is_deletable accepts


def resolve(target, run_finder=True):
    """Existing folders/files a target refers to (globs expanded, finder run)."""
    found = []
    for pattern in target["paths"]:
        found += glob.glob(pattern) if any(c in pattern for c in "*?") else ([pattern] if os.path.exists(pattern) else [])
    if target.get("finder"):
        if run_finder:
            _found[target["id"]] = target["finder"]()
        found += _found.get(target["id"], [])
    return found


def _norm(path):
    return os.path.normcase(os.path.abspath(path)).rstrip("\\")


def _inside(path, root):
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + "\\")


def quick_clean_paths():
    """Locations quick clean may delete in: the fixed ones, plus exactly what each finder listed when it was measured.
    Windows setup files are never deleted by this app (Disk Cleanup does it), so they aren't included."""
    return [p for t in TARGETS if t["kind"] != "cleanmgr" for p in resolve(t, run_finder=False)]


def is_deletable(path, allowed=None):
    """Hard safety net for every delete: no drive roots, no system/program folders (except quick-clean
    folders inside them), nothing that doesn't exist. `allowed`: a precomputed quick_clean_paths() list."""
    if not path or not os.path.exists(path):
        return False, "It no longer exists."
    norm = _norm(path)
    if len(norm) <= 3:
        return False, "Drive roots can't be deleted."
    if os.path.basename(norm) in ("users", "windows") and len(norm.split("\\")) == 2:
        return False, "System folder."
    if norm == _norm(os.path.expanduser("~")):
        return False, "Your user folder can't be deleted."
    if any(_inside(path, qc) for qc in (allowed if allowed is not None else quick_clean_paths())):
        return True, ""
    if any(_inside(path, root) for root in PROTECTED_ROOTS):
        return False, "Windows and program folders can't be deleted from this app."
    return True, ""


# ---------------------------------------------------------------- measuring

def folder_size(path):
    total = files = 0
    denied = False
    stack = [path]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        if e.is_symlink() or e.is_junction():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        continue
        except PermissionError:
            denied = True
        except OSError:
            continue
    return total, files, denied


class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


def recycle_bin_info():
    info = SHQUERYRBINFO(cbSize=ctypes.sizeof(SHQUERYRBINFO))
    if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) != 0:
        return 0, 0
    return info.i64Size, info.i64NumItems


def measure(target):
    """Size info for one target, shaped for the UI."""
    result = {"id": target["id"], "size": 0, "files": 0, "denied": False, "locations": 0, "running": []}
    if target["kind"] == "recycle":
        result["size"], result["files"] = recycle_bin_info()
        return result
    paths = resolve(target)
    result["locations"] = len(paths)
    for p in paths:
        if os.path.isdir(p):
            size, files, denied = folder_size(p)
        else:
            try:
                size, files, denied = os.path.getsize(p), 1, False
            except OSError:
                size, files, denied = 0, 0, True
        result["size"] += size
        result["files"] += files
        result["denied"] |= denied
    if target.get("apps"):
        running = running_processes()
        result["running"] = [a for a in target["apps"] if a in running]
    if target.get("admin") and result["size"] and not is_admin():
        result["denied"] = True        # Windows only lets an administrator remove these
    return result


def details(target_id, limit=50):
    """What a target holds: each location with its size, and the largest files (for the 'See data' list)."""
    t = TARGET_BY_ID[target_id]
    out = {"id": target_id, "locations": [], "files": [], "shortcuts": []}
    if t["kind"] == "recycle":
        return out
    paths = resolve(t)
    files = []
    if t["kind"] == "shortcuts":
        out["shortcuts"] = [{"name": os.path.splitext(os.path.basename(p))[0], "path": p,
                             "target": _shortcut_targets.get(_norm(p), "")} for p in paths]
        return out
    by_loc = {}
    for p in paths:
        if os.path.isdir(p):
            size = n = 0
            for dirpath, _, names in os.walk(p, onerror=lambda e: None):
                for name in names:
                    fp = os.path.join(dirpath, name)
                    try:
                        s = os.lstat(fp).st_size
                    except OSError:
                        continue
                    size += s
                    n += 1
                    files.append((s, fp))
            out["locations"].append({"path": p, "size": size, "files": n})
        else:
            try:
                s = os.lstat(p).st_size
            except OSError:
                continue
            files.append((s, p))
            loc = by_loc.setdefault(os.path.dirname(p), {"path": os.path.dirname(p), "size": 0, "files": 0})
            loc["size"] += s
            loc["files"] += 1
    out["locations"] += by_loc.values()
    out["locations"].sort(key=lambda l: -l["size"])
    files.sort(reverse=True)
    out["files"] = [{"name": os.path.basename(fp), "folder": os.path.dirname(fp), "size": s} for s, fp in files[:limit]]
    out["total_files"] = len(files)
    return out


# ---------------------------------------------------------------- deleting

def _remove_file(path):
    try:
        size = os.lstat(path).st_size
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE)   # clear read-only and retry
            os.remove(path)
        return size, True
    except OSError:
        return 0, False


def clean_contents(folder):
    """Delete everything inside `folder` (bottom-up), skipping anything locked. Returns (freed, deleted, skipped)."""
    ok, why = is_deletable(folder)
    if not ok:
        raise PermissionError(why)
    freed = deleted = skipped = 0
    for dirpath, dirnames, filenames in os.walk(folder, topdown=False, onerror=lambda e: None):
        for name in filenames:
            size, done = _remove_file(os.path.join(dirpath, name))
            freed += size
            deleted += done
            skipped += not done
        if dirpath != folder:
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
    return freed, deleted, skipped


def empty_recycle_bin():
    size, items = recycle_bin_info()
    flags = 0x1 | 0x2 | 0x4   # SHERB_NOCONFIRMATION | NOPROGRESSUI | NOSOUND
    hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    if hr not in (0, -2147418113):   # S_OK, or E_UNEXPECTED when already empty
        raise OSError(f"Could not empty the Recycle Bin (error {hr & 0xffffffff:#x}).")
    return size, items, 0


def clean_target(target_id):
    t = TARGET_BY_ID[target_id]
    if t["kind"] == "recycle":
        freed, deleted, skipped = empty_recycle_bin()
    elif t["kind"] == "cleanmgr":
        freed, deleted, skipped = run_disk_cleanup(t)
    elif t["kind"] == "shortcuts":
        freed = deleted = skipped = 0
        for p in resolve(t, run_finder=False):     # exactly the shortcuts that were listed as broken
            try:
                size = os.lstat(p).st_size
                if send_to_recycle_bin(p):
                    freed, deleted = freed + size, deleted + 1
                    continue
            except OSError:
                pass
            skipped += 1                          # e.g. an all-users shortcut without administrator rights
        _found[target_id] = [p for p in _found.get(target_id, []) if os.path.exists(p)]
    else:
        freed = deleted = skipped = 0
        paths = resolve(t)
        allowed = quick_clean_paths()
        for p in paths:
            if os.path.isdir(p):
                f, d, s = clean_contents(p)
            elif is_deletable(p, allowed)[0]:
                f, done = _remove_file(p)
                d, s = int(done), int(not done)
            else:
                f, d, s = 0, 0, 1
            freed, deleted, skipped = freed + f, deleted + d, skipped + s
    return {"id": target_id, "freed": freed, "deleted": deleted, "skipped": skipped}


CLEANMGR_SET = 7717
CLEANMGR_SCRIPT = r"""
param([string]$Out)
$base = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches'
$want = 'Previous Installations', 'Temporary Setup Files', 'Windows Upgrade Log Files', 'Setup Log Files', 'Windows ESD installation files'
try {
  foreach ($k in Get-ChildItem $base) {      # tick only the setup-related items for this preset, untick the rest
    $v = $(if ($want -contains $k.PSChildName) { 2 } else { 0 })
    Set-ItemProperty -Path $k.PSPath -Name 'StateFlags%(set)d' -Value $v -Type DWord -ErrorAction SilentlyContinue
  }
  Start-Process -FilePath "$env:WINDIR\System32\cleanmgr.exe" -ArgumentList '/sagerun:%(set)d' -Wait
  Set-Content -Path $Out -Value 'ok' -Encoding UTF8
} catch { Set-Content -Path $Out -Value ('error: ' + $_.Exception.Message) -Encoding UTF8 }
""" % {"set": CLEANMGR_SET}


def run_disk_cleanup(target):
    """Previous Windows installation & upgrade leftovers: Windows locks these down, so its own Disk Cleanup removes
    them (elevated, with only the setup-related boxes ticked)."""
    import drivers                    # the elevation helper lives there
    before = sum(folder_size(p)[0] for p in resolve(target))
    work = tempfile.mkdtemp(prefix="sysutil-cleanmgr-")
    script, out = os.path.join(work, "cleanmgr.ps1"), os.path.join(work, "result.txt")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(CLEANMGR_SCRIPT)
    drivers.run_elevated("powershell.exe", f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}" -Out "{out}"')
    try:
        with open(out, encoding="utf-8-sig") as f:
            status = f.read().strip()
    except OSError:
        raise RuntimeError("Disk Cleanup didn't report back.")
    if status != "ok":
        raise RuntimeError(f"Disk Cleanup failed ({status}).")
    after = sum(folder_size(p)[0] for p in resolve(target))
    return max(0, before - after), int(before > after), 0


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]


def send_to_recycle_bin(path):
    """Move a file or folder to the Recycle Bin (restorable). Windows asks first if it is too big to recycle."""
    ok, why = is_deletable(path)
    if not ok:
        raise PermissionError(why)
    FO_DELETE = 3
    flags = 0x40 | 0x10 | 0x4 | 0x400 | 0x4000  # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI | WANTNUKEWARNING
    op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=os.path.abspath(path) + "\0", fFlags=flags)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise OSError("Windows could not move it to the Recycle Bin (it may be open in another program)."
                      if rc else "Cancelled.")
    return not os.path.exists(path)


def free_up_space(folder):
    """OneDrive/iCloud: make files online-only (keeps them in the cloud, frees local disk)."""
    if not os.path.isdir(folder):
        raise FileNotFoundError(folder)
    subprocess.run(["attrib", "+U", "-P", os.path.join(folder, "*"), "/S", "/D"], capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW, check=False)
    return True


def relaunch_as_admin(script):
    """Start this app elevated (UAC prompt). Returns True if the user accepted."""
    import sys
    exe = sys.executable.replace("python.exe", "pythonw.exe")
    args = "" if getattr(sys, "frozen", False) else f'"{script}"'   # the installed .exe is the app itself
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
    return rc > 32
