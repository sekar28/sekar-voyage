"""Performance: what is running, which background helpers are safe to close, memory trimming and startup apps.

Everything here reads processes with the Windows API (ctypes) - no extra packages. Nothing is closed unless the
caller passes items taken from the latest snapshot, and Windows / other users' / this app's own processes never are.
"""

import ctypes
import os
import re
import struct
import subprocess
import tempfile
import time
import winreg
from ctypes import wintypes

import drivers
import sysinfo

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
version = ctypes.WinDLL("version", use_last_error=True)

PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED = 0x1000
TH32CS_SNAPPROCESS = 0x2
WINDIR = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + os.sep

# Windows itself - never offered, whatever their state.
PROTECTED = {
    "system", "registry", "idle", "smss", "csrss", "wininit", "winlogon", "services", "lsass", "lsaiso", "svchost",
    "dwm", "explorer", "sihost", "fontdrvhost", "ctfmon", "audiodg", "spoolsv", "conhost", "taskhostw", "runtimebroker",
    "startmenuexperiencehost", "shellexperiencehost", "searchhost", "searchindexer", "textinputhost", "dllhost",
    "msmpeng", "nissrv", "securityhealthservice", "securityhealthsystray", "smartscreen", "memory compression",
    "applicationframehost", "lockapp", "wudfhost", "dashost", "secure system", "systemsettings", "ngciso",
    "sgrmbroker", "mpdefendercoreservice", "useroobebroker", "crossdeviceresume", "windowsterminal", "openconsole",
}

# Known non-essential helpers: (process name, optional path pattern, why it's safe to close). Only offered when the
# app has no window open - e.g. chrome.exe is "safe" only when Chrome keeps running after you closed it.
SAFE_HELPERS = [
    (r"googleupdate|googlecrashhandler(64)?", None, "Google's updater - it starts again on its own when needed."),
    (r"updater", r"\\google\\", "Google's updater - it starts again on its own when needed."),
    (r"microsoftedgeupdate", None, "Edge's updater - it starts again on its own when needed."),
    (r"msedge", None, "Edge kept running in the background after you closed it (Startup boost / background apps)."),
    (r"chrome", None, "Chrome kept running in the background after you closed it (\"Continue running background apps\")."),
    (r"brave|opera|vivaldi|firefox", None, "The browser kept running in the background after you closed its windows."),
    (r"adobearm|adobeupdateservice|adobe_licensing_wf.*|adobegcclient|agsservice", None,
     "Adobe's updater / licence checker - Adobe apps start it again when you open them."),
    (r"adobeipcbroker|adobe desktop service|ccxprocess|cclibrary|coresync|creative cloud.*|adobecollabsync|acrotray|acrocef|adobenotificationclient",
     None, "Adobe Creative Cloud helper - it starts again when you open an Adobe app."),
    (r"steam|steamwebhelper|steamservice", None, "Steam sitting in the tray - open Steam again when you want to play."),
    (r"epicgameslauncher|epicwebhelper|eadesktop|eacefsubprocess|eabackgroundservice|origin|battle\.net|upc|ubisoftconnect|galaxyclient.*|goggalaxy.*",
     None, "Game launcher sitting in the tray - open it again when you want to play."),
    (r"spotify", None, "Spotify in the background with no window - closing it just stops the tray icon."),
    (r"discord", None, "Discord in the tray - you won't get its notifications until you open it again."),
    (r"teams|ms-teams|msteams", None, "Teams in the tray - you won't get calls or chats until you open it again."),
    (r"zoom|zwebview2agent", None, "Zoom in the tray - open it again before a meeting."),
    (r"skype|skypeapp|skypebackgroundhost", None, "Skype in the background - you won't get calls until you open it."),
    (r"jusched|jucheck|jp2launcher", None, "Java's updater - it isn't needed to run Java programs."),
    (r"ituneshelper|itunes", None, "iTunes helper - only needed while an iPhone/iPod is connected."),
    (r"phoneexperiencehost|yourphone.*", None, "Phone Link in the background - it starts again when you open Phone Link."),
    (r"gamebar|gamebarftserver|gamebarpresencewriter", None, "Xbox Game Bar in the background - press Win+G to start it again."),
    (r"widgets|widgetservice|widgetboard|microsoftstartfeedprovider", None,
     "Windows Widgets / news feed - they start again when you open the Widgets board."),
    (r"copilotapp|copilotapphost|m365copilot", None, "Copilot running in the background - it starts again when you open it."),
    (r"norton.*ui", None, "Norton's tray window - closing it doesn't switch off any protection service."),
    (r".*crashpad_handler|.*crashhandler|.*crashreporter.*|.*crash_reporter", None,
     "Crash reporter that waits for an app to crash - not needed for anything to work."),
    (r"cortana|bingsvc", None, "Search/Bing helper - it starts again when needed."),
    (r"onedrivelauncher|filecoauth", None, "Office/OneDrive helper - it starts again when needed."),
]
SAFE_RE = [(re.compile(f"^(?:{n})$", re.I), re.compile(p, re.I) if p else None, why) for n, p, why in SAFE_HELPERS]
REVIEW_NOTES = {
    "msedgewebview2": "Web view that other apps draw their windows with (Widgets, Teams, Copilot…) - closing it breaks those apps.",
    "onedrive": "Keeps your files synced with OneDrive - closing it pauses syncing until you sign in again or restart.",
    "onedrive.sync.service": "OneDrive's sync engine - closing it pauses syncing.",
    "nvcontainer": "NVIDIA background service - closing it can switch off the overlay and driver features.",
}
APP_KEEP = {"ollama": "Runs the local AI model this app uses.", "ollama app": "Runs the local AI model this app uses.",
            "ollama_llama_server": "Runs the local AI model this app uses."}


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


def _ft(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def _entries():
    """[(pid, ppid, exe name)] for every process."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out, e = [], PROCESSENTRY32W(dwSize=ctypes.sizeof(PROCESSENTRY32W))
    try:
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out.append((e.th32ProcessID, e.th32ParentProcessID, e.szExeFile))
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return out


def _details(pid):
    """(path, working set, private bytes, start time, cpu time) - None for processes we may not open."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        return None
    try:
        buf, n = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        path = buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
        mem = PROCESS_MEMORY_COUNTERS_EX(cb=ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX))
        psapi.GetProcessMemoryInfo(h, ctypes.byref(mem), mem.cb)
        c, x, kt, ut = (wintypes.FILETIME() for _ in range(4))
        k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(x), ctypes.byref(kt), ctypes.byref(ut))
        return path, mem.WorkingSetSize, mem.PrivateUsage, _ft(c), _ft(kt) + _ft(ut)
    finally:
        k32.CloseHandle(h)


def _running(pid, start):
    """Still the same, still running process? (An exited process can be opened while anyone holds a handle to it.)"""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        return False
    try:
        c, x, kt, ut = (wintypes.FILETIME() for _ in range(4))
        code = wintypes.DWORD()
        return (k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(x), ctypes.byref(kt), ctypes.byref(ut))
                and _ft(c) == start and k32.GetExitCodeProcess(h, ctypes.byref(code)) and code.value == 259)  # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def _session(pid):
    s = wintypes.DWORD()
    return s.value if k32.ProcessIdToSessionId(pid, ctypes.byref(s)) else None


def _windows():
    """pid -> title of its visible, top-level, un-cloaked windows (what Task Manager calls 'Apps')."""
    titles = {}
    dwm = ctypes.WinDLL("dwmapi")
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):        # GW_OWNER
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        cloaked = wintypes.DWORD()
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)          # DWMWA_CLOAKED
        if cloaked.value:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        titles.setdefault(pid.value, buf.value)
        return True

    user32.EnumWindows(proc(cb), 0)
    return titles


_ver_cache = {}


def _version_info(path):
    """(company, description) from the exe's version resource."""
    if not path:
        return "", ""
    if path in _ver_cache:
        return _ver_cache[path]
    result = ("", "")
    try:
        size = version.GetFileVersionInfoSizeW(path, None)
        if size:
            buf = ctypes.create_string_buffer(size)
            version.GetFileVersionInfoW(path, 0, size, buf)
            p, n = ctypes.c_void_p(), wintypes.UINT()
            langs = [(0x0409, 0x04B0)]
            if version.VerQueryValueW(buf, r"\VarFileInfo\Translation", ctypes.byref(p), ctypes.byref(n)) and n.value >= 4:
                langs.insert(0, struct.unpack("<HH", ctypes.string_at(p.value, 4)))
            vals = []
            for key in ("CompanyName", "FileDescription"):
                val = ""
                for lang, cp in langs:
                    if version.VerQueryValueW(buf, f"\\StringFileInfo\\{lang:04x}{cp:04x}\\{key}", ctypes.byref(p), ctypes.byref(n)) and n.value:
                        val = ctypes.wstring_at(p.value, n.value).rstrip("\0").strip()
                        break
                vals.append(val)
            result = tuple(vals)
    except OSError:
        pass
    _ver_cache[path] = result
    return result


def _own_family(entries):
    """This app's process, its parents (python / launcher) and its children (WebView2) - never closed."""
    me = os.getpid()
    fam, grew = {me}, True
    while grew:                      # children first - only of this app, not of its parents (Explorer starts everything)
        grew = False
        for pid, ppid, _ in entries:
            if ppid in fam and pid not in fam:
                fam.add(pid)
                grew = True
    parent, p = {pid: ppid for pid, ppid, _ in entries}, me
    while parent.get(p, 0) > 4 and parent[p] not in fam:
        p = parent[p]
        fam.add(p)
    return fam


def _classify(g, windowed):
    """A non-Windows process of this user: open app, known safe helper, or one to review."""
    if "System Utilities" in g["title"]:          # "Sekar's System Utilities" (or an older copy's title)
        return "keep", "Another copy of Sekar's System Utilities."
    if g["title"] or g["name"].lower() in windowed:
        return "app", "Open app with a window - close it yourself or from here (save your work first)."
    for name_re, path_re, why in SAFE_RE:
        if name_re.match(g["name"]) and (not path_re or path_re.search(g["path"])):
            return "safe", why
    return "review", REVIEW_NOTES.get(g["name"].lower(),
                                      "Background process without a window. Close it only if you know what it is.")


def snapshot(sample=1.0):
    """Every process, classified and grouped by program."""
    entries = _entries()
    first = {pid: _details(pid) for pid, _, _ in entries if pid > 4}
    time.sleep(sample)
    second = {pid: _details(pid) for pid in first}
    cpus = os.cpu_count() or 1
    wins = _windows()
    mine, my_session = _own_family(entries), _session(os.getpid())

    groups = {}
    alive = {p for p, _, _ in entries}
    # Sign-in time = when this session's Explorer started. Programs launched at sign-in (tray apps, helpers) lose their
    # launcher right away, so they look orphaned but aren't leftovers - only later orphans count.
    shells = [first[p][3] for p, _, e in entries if e.lower() == "explorer.exe" and first.get(p) and _session(p) == my_session]
    signin = min(shells) if shells else 0
    LOGIN_GRACE = 10 * 60 * 10 ** 7      # 10 minutes, in FILETIME units
    for pid, ppid, exe in entries:
        if pid <= 4:
            continue
        d = second.get(pid) or first.get(pid)
        name = re.sub(r"\.exe$", "", exe, flags=re.I)
        low = name.lower()
        path = d[0] if d else ""
        cpu = 0.0
        if first.get(pid) and second.get(pid) and first[pid][3] == second[pid][3]:
            cpu = max(0.0, (second[pid][4] - first[pid][4]) / (sample * 1e7 * cpus) * 100)
        session = _session(pid)
        if pid in mine and low not in PROTECTED:
            cat, reason = "self", "Part of Sekar's System Utilities (or the program that started it)."
        elif low in PROTECTED or session != my_session or d is None or os.path.normcase(path).startswith(WINDIR):
            cat, reason = "windows", ("Part of Windows." if low in PROTECTED or os.path.normcase(path).startswith(WINDIR)
                                      else "Runs as a service or for another user - not something to close from here.")
        elif low in APP_KEEP:
            cat, reason = "keep", APP_KEEP[low]
        else:
            cat, reason = "review", ""
        key = f"{cat}:{low}"
        g = groups.setdefault(key, {"key": key, "name": name, "cat": cat, "reason": reason, "path": path, "count": 0,
                                    "mem": 0, "private": 0, "cpu": 0.0, "procs": [], "title": "", "orphans": 0})
        g["count"] += 1
        # Orphan: the process that started it has exited (its pid is gone, or now belongs to a newer process).
        parent = first.get(ppid)
        if ppid > 4 and d and d[3] > signin + LOGIN_GRACE and (ppid not in alive or (parent and parent[3] > d[3])):
            g["orphans"] += 1
        if d:
            g["mem"] += d[1]
            g["private"] += d[2]
            g["path"] = g["path"] or path
        g["cpu"] += cpu
        g["procs"].append([pid, d[3] if d else 0])
        if pid in wins and not g["title"]:
            g["title"] = wins[pid]

    windowed = {g["name"].lower() for g in groups.values() if g["title"]}
    for g in groups.values():
        g["cpu"] = round(g["cpu"], 1)
        g["company"], g["desc"] = _version_info(g["path"])
        if g["cat"] == "review":
            g["cat"], g["reason"] = _classify(g, windowed)
            g["key"] = f"{g['cat']}:{g['name'].lower()}"

    out = sorted(groups.values(), key=lambda g: -g["mem"])
    live = sysinfo.live()
    return {"groups": out, "total": sum(g["count"] for g in out), "cpus": cpus, "live": live, "taken_at": time.time()}


# ---------------------------------------------------------------- closing processes

def end_processes(snap, keys, force=False):
    """Close the groups named by key. Only groups from `snap` that are safe / review / app are touched, and each
    process is matched by pid AND start time, so a pid that was reused since the snapshot is never hit."""
    by_key = {g["key"]: g for g in snap["groups"]}
    closed, failed, freed = [], [], 0
    for key in keys:
        g = by_key.get(key)
        if not g or g["cat"] not in ("safe", "review", "app"):
            failed.append({"name": key.split(":", 1)[-1], "error": "not something this app closes"})
            continue
        graceful = g["cat"] == "app" and not force
        last_err = ""
        for pid, start in g["procs"]:
            if not _running(pid, start):
                continue             # already exited (or the pid now belongs to something else - leave it)
            err = _close(pid, graceful)
            if err and not graceful:  # graceful: helper processes have no window to close; they exit with the app
                last_err = err
        alive = lambda: sum(1 for pid, start in g["procs"] if _running(pid, start))
        deadline = time.time() + (6 if graceful else 1)      # apps can take a few seconds to shut down
        while (still := alive()) and time.time() < deadline:
            time.sleep(0.3)
        if still < g["count"]:
            closed.append({"name": g["name"], "count": g["count"] - still})
            freed += g["mem"] * (g["count"] - still) // max(1, g["count"])
        if still:
            failed.append({"name": g["name"], "app": graceful, "error": last_err or (
                "still open - it may be asking to save your work" if graceful else "didn't close")})
    return {"closed": closed, "failed": failed, "freed": freed}


def _close(pid, graceful):
    if graceful:      # WM_CLOSE to its windows - the app can ask to save
        r = subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        return None if r.returncode == 0 else "the app didn't accept the close request"
    h = k32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        return "needs administrator, or Windows protects it" if ctypes.get_last_error() == 5 else "couldn't be opened"
    try:
        return None if k32.TerminateProcess(h, 1) else "Windows refused to close it"
    finally:
        k32.CloseHandle(h)


# ---------------------------------------------------------------- memory

def trim_memory():
    """Ask every process we may touch to hand back memory it isn't using (EmptyWorkingSet). Windows pages it back in
    when needed, so the effect is temporary - useful when RAM is nearly full."""
    before = sysinfo.live()
    trimmed = 0
    for pid, _, _ in _entries():
        if pid <= 4:
            continue
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED | PROCESS_SET_QUOTA, False, pid)
        if h:
            try:
                trimmed += bool(psapi.EmptyWorkingSet(h))
            finally:
                k32.CloseHandle(h)
    time.sleep(0.8)
    after = sysinfo.live()
    return {"before": before, "after": after, "freed": max(0, before["mem_used"] - after["mem_used"]), "processes": trimmed}


PURGE_SCRIPT = r"""
param([string]$Out)
try {
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class Mem {
  [StructLayout(LayoutKind.Sequential, Pack = 1)] public struct TokPriv { public int Count; public long Luid; public int Attr; }
  [DllImport("advapi32.dll", SetLastError = true)] static extern bool OpenProcessToken(IntPtr h, int acc, ref IntPtr tok);
  [DllImport("advapi32.dll", SetLastError = true)] static extern bool LookupPrivilegeValue(string host, string name, ref long luid);
  [DllImport("advapi32.dll", SetLastError = true)] static extern bool AdjustTokenPrivileges(IntPtr tok, bool all, ref TokPriv st, int len, IntPtr prev, IntPtr rlen);
  [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
  [DllImport("ntdll.dll")] static extern int NtSetSystemInformation(int cls, ref int info, int len);
  public static int Purge() {
    IntPtr tok = IntPtr.Zero;
    OpenProcessToken(GetCurrentProcess(), 0x28, ref tok);
    TokPriv tp = new TokPriv(); tp.Count = 1; tp.Attr = 2;
    LookupPrivilegeValue(null, "SeProfileSingleProcessPrivilege", ref tp.Luid);
    AdjustTokenPrivileges(tok, false, ref tp, 0, IntPtr.Zero, IntPtr.Zero);
    int cmd = 4;                                  // MemoryPurgeStandbyList
    return NtSetSystemInformation(80, ref cmd, 4); // SystemMemoryListInformation
  }
}
'@
  $status = [Mem]::Purge()
  Set-Content -Path $Out -Value ('{0}' -f $status) -Encoding UTF8
} catch { Set-Content -Path $Out -Value ('error: ' + $_.Exception.Message) -Encoding UTF8 }
"""


def purge_standby():
    """Clear the standby list (cached file data) - needs administrator; uses the UAC prompt."""
    work = tempfile.mkdtemp(prefix="sysutil-mem-")
    script, out = os.path.join(work, "purge.ps1"), os.path.join(work, "result.txt")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(PURGE_SCRIPT)
    before = sysinfo.live()
    drivers.run_elevated("powershell.exe", f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}" -Out "{out}"')
    try:
        with open(out, encoding="utf-8-sig") as f:
            status = f.read().strip()
    except OSError:
        raise RuntimeError("The memory clean didn't report back.")
    if status != "0":
        raise RuntimeError(f"Windows didn't clear the standby cache ({status}).")
    time.sleep(0.5)
    after = sysinfo.live()
    return {"before": before, "after": after, "freed": max(0, before["mem_used"] - after["mem_used"])}


# ---------------------------------------------------------------- startup apps

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
SOURCES = [   # (id, hive, run key or startup folder, StartupApproved subkey, label)
    ("hkcu", winreg.HKEY_CURRENT_USER, RUN, "Run", "Your account"),
    ("hklm", winreg.HKEY_LOCAL_MACHINE, RUN, "Run", "All users"),
    ("hklm32", winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32", "All users"),
    ("ufolder", winreg.HKEY_CURRENT_USER, os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
     "StartupFolder", "Startup folder"),
    ("cfolder", winreg.HKEY_LOCAL_MACHINE, os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\StartUp"),
     "StartupFolder", "Startup folder (all users)"),
]
HIVE_NAME = {winreg.HKEY_CURRENT_USER: "HKCU", winreg.HKEY_LOCAL_MACHINE: "HKLM"}


def _approved(hive, sub, name):
    try:
        with winreg.OpenKey(hive, f"{APPROVED}\\{sub}") as k:
            data, _ = winreg.QueryValueEx(k, name)
            return not (data and data[0] & 1)          # 02/06 = on, 03/07 = off
    except OSError:
        return True


def _exe_of(command):
    command = os.path.expandvars(command or "").strip()
    m = re.match(r'"([^"]+)"', command) or re.match(r"(.+?\.exe)\b", command, re.I)
    return os.path.normcase(m.group(1)) if m else ""


def startup_items(snap=None):
    running = {}
    for g in (snap or {}).get("groups", []):
        if g["path"]:
            running[os.path.normcase(g["path"])] = running.get(os.path.normcase(g["path"]), 0) + g["mem"]
    items = []
    for sid, hive, where, sub, label in SOURCES:
        entries = []
        if sub == "StartupFolder":
            try:
                entries = [(f, os.path.join(where, f)) for f in os.listdir(where) if f.lower() != "desktop.ini"]
            except OSError:
                pass
        else:
            try:
                with winreg.OpenKey(hive, where) as k:
                    i = 0
                    while True:
                        try:
                            name, cmd, _ = winreg.EnumValue(k, i)
                        except OSError:
                            break
                        entries.append((name, str(cmd)))
                        i += 1
            except OSError:
                pass
        for name, cmd in entries:
            exe = _exe_of(cmd) if sub != "StartupFolder" else ""
            company, desc = _version_info(exe) if exe and os.path.exists(exe) else ("", "")
            items.append({"id": f"{sid}|{name}", "name": os.path.splitext(name)[0] if sub == "StartupFolder" else name,
                          "desc": desc, "company": company, "command": cmd, "where": label,
                          "enabled": _approved(hive, sub, name), "admin": hive == winreg.HKEY_LOCAL_MACHINE,
                          "running_mem": running.get(exe, 0)})
    items.sort(key=lambda i: (not i["enabled"], i["name"].lower()))
    return items


def set_startup(item_id, enabled):
    """Turn a startup entry on/off the way Task Manager does (StartupApproved flag) - nothing is deleted."""
    sid, _, name = item_id.partition("|")
    src = next((s for s in SOURCES if s[0] == sid), None)
    if not src or not name:
        raise ValueError("Unknown startup item.")
    _, hive, _, sub, _ = src
    data = (b"\x02" if enabled else b"\x03") + b"\x00" * 3 + (b"\x00" * 8 if enabled else
                                                                 struct.pack("<Q", int(time.time() * 1e7) + 116444736000000000))
    if hive == winreg.HKEY_CURRENT_USER:
        with winreg.CreateKeyEx(hive, f"{APPROVED}\\{sub}", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, data)
    else:
        drivers.run_elevated("reg.exe", f'add "HKLM\\{APPROVED}\\{sub}" /v "{name}" /t REG_BINARY /d {data.hex()} /f')
        if _approved(hive, sub, name) != enabled:
            raise RuntimeError("Windows didn't save the change.")
    return {"id": item_id, "enabled": _approved(hive, sub, name)}


# ---------------------------------------------------------------- power mode

POWER_MODES = {"961cc777-2547-4f9d-8174-7d86181b8a7a": "Best power efficiency",
               "00000000-0000-0000-0000-000000000000": "Balanced",
               "ded574b5-45a0-4f42-8737-46345c09c238": "Best performance"}


def power_mode():
    class GUID(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
    g = GUID()
    try:
        if ctypes.windll.powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(g)) != 0:
            return None
    except (OSError, AttributeError):
        return None
    d = bytes(g.d)
    text = f"{g.a:08x}-{g.b:04x}-{g.c:04x}-{d[:2].hex()}-{d[2:].hex()}"
    return POWER_MODES.get(text, "Custom")


def open_power_settings():
    os.startfile("ms-settings:powersleep")
