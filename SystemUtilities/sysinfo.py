"""System specs for the Home screen: hardware details (read once) and live CPU / memory / battery readings."""

import ctypes
import json
import subprocess
from ctypes import wintypes

SPECS_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$mem = @(Get-CimInstance Win32_PhysicalMemory)
$os = Get-CimInstance Win32_OperatingSystem
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$vram = @{}
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue |
  ForEach-Object { $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
    if ($p.DriverDesc -and $p.'HardwareInformation.qwMemorySize') { $vram[$p.DriverDesc] = [int64]$p.'HardwareInformation.qwMemorySize' } }
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  [pscustomobject]@{ name = $_.Name; vram = $(if ($vram[$_.Name]) { $vram[$_.Name] } else { [int64]$_.AdapterRAM });
    width = $_.CurrentHorizontalResolution; height = $_.CurrentVerticalResolution; hz = $_.CurrentRefreshRate } })
$disks = @(Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{ name = $_.FriendlyName; media = "$($_.MediaType)"; bus = "$($_.BusType)"; size = [int64]$_.Size } })
[pscustomobject]@{
  cpu = [pscustomobject]@{ name = $cpu.Name.Trim(); cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors; mhz = $cpu.MaxClockSpeed }
  ram = [pscustomobject]@{ total = [int64]($mem | Measure-Object Capacity -Sum).Sum; sticks = $mem.Count;
                           speed = ($mem | Measure-Object ConfiguredClockSpeed -Maximum).Maximum }
  gpus = $gpus; disks = $disks
  os = [pscustomobject]@{ name = $os.Caption; version = $cv.DisplayVersion; build = "$($cv.CurrentBuild).$($cv.UBR)" }
} | ConvertTo-Json -Depth 4 -Compress
"""


def specs():
    proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SPECS_SCRIPT],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    data = json.loads(proc.stdout)
    cpu = data["cpu"]
    for junk in ("(R)", "(TM)", "(tm)", " CPU", "  "):
        cpu["name"] = cpu["name"].replace(junk, " " if junk == "  " else "")
    cpu["name"] = " ".join(cpu["name"].replace(" @", "").split())
    # Real graphics first (skip remote-desktop / virtual display adapters)
    data["gpus"] = sorted((g for g in data["gpus"] or [] if g.get("name") and "virtual" not in g["name"].lower()
                           and "remote" not in g["name"].lower()), key=lambda g: -(g.get("vram") or 0))
    data["disks"] = sorted(data["disks"] or [], key=lambda d: (d.get("media") != "SSD", -(d.get("size") or 0)))
    return data


# ---------------------------------------------------------------- live readings (cheap, called every few seconds)

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


_last_times = None


def _cpu_percent():
    """CPU load since the previous call (GetSystemTimes: idle / kernel(incl. idle) / user)."""
    global _last_times
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
    now = tuple((t.dwHighDateTime << 32) | t.dwLowDateTime for t in (idle, kernel, user))
    prev, _last_times = _last_times, now
    if prev is None:
        return None
    d_idle, d_kernel, d_user = (a - b for a, b in zip(now, prev))
    busy = d_kernel + d_user
    return round(100 * (busy - d_idle) / busy, 1) if busy else 0.0


# ---------------------------------------------------------------- GPU usage (like Task Manager)
# Windows' "GPU Engine" performance counters: per process and engine (3D, video decode, copy...). An adapter's usage is
# its busiest engine type, summed over processes. Reading these never wakes a sleeping laptop GPU (nvidia-smi can).

class _PdhValue(ctypes.Structure):
    _fields_ = [("CStatus", wintypes.DWORD), ("doubleValue", ctypes.c_double)]


class _PdhItem(ctypes.Structure):
    _fields_ = [("szName", wintypes.LPWSTR), ("FmtValue", _PdhValue)]


_gpu = {"query": None, "counter": None, "names": None, "failed": False}
_LUID = __import__("re").compile(r"luid_0x([0-9a-f]+)_0x([0-9a-f]+)_.*engtype_(\w+)", __import__("re").I)


def _gpu_names():
    """{low 32 bits of the adapter LUID: name} from the DirectX registry (skips the Basic Render Driver)."""
    import winreg
    names = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\DirectX") as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                try:
                    with winreg.OpenKey(root, winreg.EnumKey(root, i)) as k:
                        desc = winreg.QueryValueEx(k, "Description")[0]
                        luid = winreg.QueryValueEx(k, "AdapterLuid")[0]
                except OSError:
                    continue
                if "basic render" not in desc.lower():
                    names[luid & 0xFFFFFFFF] = desc
    except OSError:
        pass
    return names


def gpu_usage():
    """[{"name", "pct"}] per graphics adapter, busiest first; None on the first call (counters need two readings)."""
    g = _gpu
    if g["failed"]:
        return None
    pdh = ctypes.windll.pdh
    if g["query"] is None:
        q, c = wintypes.HANDLE(), wintypes.HANDLE()
        if pdh.PdhOpenQueryW(None, None, ctypes.byref(q)) != 0 or pdh.PdhAddEnglishCounterW(
                q, r"\GPU Engine(*)\Utilization Percentage", None, ctypes.byref(c)) != 0:
            g["failed"] = True
            return None
        g["query"], g["counter"], g["names"] = q, c, _gpu_names()
        pdh.PdhCollectQueryData(q)
        return None
    if pdh.PdhCollectQueryData(g["query"]) != 0:
        return None
    size, count = wintypes.DWORD(0), wintypes.DWORD(0)
    PDH_FMT_DOUBLE, PDH_MORE_DATA = 0x200, 0x800007D2
    if pdh.PdhGetFormattedCounterArrayW(g["counter"], PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), None) \
            & 0xFFFFFFFF != PDH_MORE_DATA:
        return []
    buf = (ctypes.c_byte * size.value)()
    if pdh.PdhGetFormattedCounterArrayW(g["counter"], PDH_FMT_DOUBLE, ctypes.byref(size), ctypes.byref(count), buf) != 0:
        return []
    items = ctypes.cast(buf, ctypes.POINTER(_PdhItem))
    per = {}                                  # luid -> {engine type: summed %}
    for i in range(count.value):
        m = _LUID.search(items[i].szName or "")
        if not m or items[i].FmtValue.CStatus not in (0, 1):
            continue
        luid = int(m.group(2), 16)
        eng = per.setdefault(luid, {})
        eng[m.group(3).lower()] = eng.get(m.group(3).lower(), 0.0) + max(0.0, items[i].FmtValue.doubleValue)
    out = []
    for luid, name in g["names"].items():
        engines = per.get(luid, {})
        out.append({"name": name, "pct": round(min(100.0, max(engines.values(), default=0.0)), 1)})
    return sorted(out, key=lambda a: -a["pct"])


def live():
    mem = MEMORYSTATUSEX(dwLength=ctypes.sizeof(MEMORYSTATUSEX))
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    power = SYSTEM_POWER_STATUS()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power))
    has_battery = not (power.BatteryFlag & 128) and power.BatteryLifePercent != 255
    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    return {
        "cpu": _cpu_percent(),
        "mem_used": mem.ullTotalPhys - mem.ullAvailPhys, "mem_total": mem.ullTotalPhys, "mem_pct": mem.dwMemoryLoad,
        "battery": power.BatteryLifePercent if has_battery else None,
        "plugged": power.ACLineStatus == 1, "charging": bool(power.BatteryFlag & 8),
        "uptime": ctypes.windll.kernel32.GetTickCount64() // 1000,
        "gpus": gpu_usage(),
    }
