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
    }
