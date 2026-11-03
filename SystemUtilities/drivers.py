"""Drivers: list what is installed, ask Windows Update for driver updates, install the chosen ones (elevated),
and point to the vendors' own update tools."""

import ctypes
import json
import os
import re
import subprocess
import tempfile
import time
from ctypes import wintypes
from datetime import date
from urllib.parse import quote

CLASSES = ["DISPLAY", "NET", "MEDIA", "SYSTEM", "BLUETOOTH", "CAMERA", "IMAGE", "BIOMETRIC", "FIRMWARE", "HIDCLASS",
           "MOUSE", "KEYBOARD", "USB", "HDC", "SCSIADAPTER", "SOFTWARECOMPONENT", "EXTENSION", "PRINTER"]
GROUPS = {"DISPLAY": "Graphics", "NET": "Network", "MEDIA": "Audio & media", "BLUETOOTH": "Bluetooth",
          "CAMERA": "Camera", "IMAGE": "Camera", "SYSTEM": "System & chipset", "HIDCLASS": "Input devices",
          "MOUSE": "Input devices", "KEYBOARD": "Input devices", "USB": "USB", "HDC": "Storage controllers",
          "SCSIADAPTER": "Storage controllers", "SOFTWARECOMPONENT": "Software components",
          "EXTENSION": "Software components", "FIRMWARE": "Firmware", "BIOMETRIC": "Biometrics", "PRINTER": "Printers"}
VIRTUAL = re.compile(r"virtual|vpn|\btap-|tunnel|vmware|vmnet|wireguard|openvpn|nordlynx|hyper-v|wan miniport|xvdd", re.I)
VENDORS = [("NVIDIA", "nvidia"), ("Intel", "intel"), ("AMD", r"\bamd\b|advanced micro"), ("Realtek", "realtek"),
           ("MSI", r"micro-star|\bmsi\b"), ("Qualcomm", "qualcomm"), ("MediaTek", "mediatek"), ("Broadcom", "broadcom")]
OEM_SUPPORT = {   # laptop/desktop makers: where their driver packages (incl. Realtek audio/LAN) live
    "MSI": "https://www.msi.com/search/{model}", "Dell": "https://www.dell.com/support/home",
    "HP": "https://support.hp.com/drivers", "Lenovo": "https://pcsupport.lenovo.com/",
    "ASUS": "https://www.asus.com/support/download-center/", "Acer": "https://www.acer.com/support/drivers-and-manuals",
}
VENDOR_TOOLS = {
    "NVIDIA": {"label": "NVIDIA app", "url": "https://www.nvidia.com/en-us/software/nvidia-app/",
               "exe": [r"%ProgramFiles%\NVIDIA Corporation\NVIDIA app\CEF\NVIDIA app.exe",
                       r"%ProgramFiles%\NVIDIA Corporation\NVIDIA GeForce Experience\NVIDIA GeForce Experience.exe"]},
    "Intel": {"label": "Intel Driver & Support Assistant",
              "url": "https://www.intel.com/content/www/us/en/support/detect.html", "exe": []},
    "AMD": {"label": "AMD Software", "url": "https://www.amd.com/en/support/download/drivers.html",
            "exe": [r"%ProgramFiles%\AMD\CNext\CNext\RadeonSoftware.exe"]},
}
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _powershell(script, timeout=300):
    proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=NO_WINDOW)
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError((proc.stderr.strip() or "PowerShell returned nothing").splitlines()[-1])
    return json.loads(out)


def vendor_of(*names):
    text = " ".join(n or "" for n in names)
    for vendor, pattern in VENDORS:
        if re.search(pattern, text, re.I):
            return vendor
    return None


def _age(iso):
    if not iso:
        return None
    y, m, d = map(int, iso.split("-"))
    if y < 2000:             # generic Windows drivers carry a placeholder date (1968)
        return None
    return round((date.today() - date(y, m, d)).days / 365.25, 1)


LIST_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$classes = '%s' -split ','
$all = Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -and $_.DriverVersion }
$d = $all | Where-Object { $classes -contains $_.DeviceClass -and $_.DriverProviderName -ne 'Microsoft' } | ForEach-Object {
  [pscustomobject]@{ name = $_.DeviceName; cls = $_.DeviceClass; provider = $_.DriverProviderName; mfr = $_.Manufacturer;
    version = $_.DriverVersion; date = $(if ($_.DriverDate) { $_.DriverDate.ToString('yyyy-MM-dd') } else { $null }) } }
$cs = Get-CimInstance Win32_ComputerSystem; $bios = Get-CimInstance Win32_BIOS; $os = Get-CimInstance Win32_OperatingSystem
[pscustomobject]@{ drivers = @($d); total = @($all).Count;
  system = [pscustomobject]@{ manufacturer = $cs.Manufacturer; model = $cs.Model; bios = $bios.SMBIOSBIOSVersion;
    bios_date = $(if ($bios.ReleaseDate) { $bios.ReleaseDate.ToString('yyyy-MM-dd') }); os = $os.Caption; build = $os.BuildNumber } } |
  ConvertTo-Json -Depth 4 -Compress
""" % ",".join(CLASSES)


def list_drivers():
    data = _powershell(LIST_SCRIPT, timeout=120)
    seen, drivers = set(), []
    for d in data.get("drivers") or []:
        key = (d["name"], d["version"])
        if key in seen:
            continue
        seen.add(key)
        drivers.append({
            "name": d["name"], "group": GROUPS.get(d["cls"], "Other"), "cls": d["cls"],
            "provider": d.get("provider") or d.get("mfr") or "", "version": d["version"], "date": d.get("date"),
            "age": _age(d.get("date")), "vendor": vendor_of(d.get("provider"), d.get("mfr"), d["name"]),
            "virtual": bool(VIRTUAL.search(d["name"])),
        })
    drivers.sort(key=lambda d: (d["group"], d["name"].lower()))
    system = data["system"]
    system["bios_age"] = _age(system.get("bios_date"))
    system["oem"] = vendor_of(system.get("manufacturer")) or next(
        (k for k in OEM_SUPPORT if k.lower() in (system.get("manufacturer") or "").lower()), None)
    return {"system": system, "drivers": drivers, "total": data.get("total", len(drivers)),
            "listed_at": time.time()}


CHECK_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$s = New-Object -ComObject Microsoft.Update.Session
$r = $s.CreateUpdateSearcher().Search("IsInstalled=0 and Type='Driver' and IsHidden=0")
$u = foreach ($x in $r.Updates) {
  [pscustomobject]@{ id = $x.Identity.UpdateID; title = $x.Title; cls = $x.DriverClass; mfr = $x.DriverManufacturer;
    model = $x.DriverModel; date = $(if ($x.DriverVerDate) { $x.DriverVerDate.ToString('yyyy-MM-dd') });
    size = [int64]$x.MaxDownloadSize; eula = [bool]$x.EulaAccepted; reboot = [bool]($x.InstallationBehavior.RebootBehavior -ne 0) } }
ConvertTo-Json -InputObject @($u) -Depth 3 -Compress
"""


def check_updates(system=None):
    updates = _powershell(CHECK_SCRIPT, timeout=600) or []
    for u in updates:
        text = f"{u.get('cls') or ''} {u.get('title') or ''} {u.get('model') or ''}".lower()
        u["is_firmware"] = "firmware" in text or "bios" in text
        u["vendor"] = vendor_of(u.get("mfr"), u.get("title"))
        u["downgrade"] = bool(system) and u["is_firmware"] and is_bios_downgrade(u, system)
    return {"updates": updates, "checked_at": time.time()}


def is_bios_downgrade(update, system):
    """MSI-style BIOS versions: offered 'SBIOS Ver.10D' vs installed 'E16R8IMS.10E' -> older, don't install."""
    m = re.search(r"\bver\.?\s*([0-9a-z]{2,4})\b", f"{update.get('model') or ''} {update.get('title') or ''}", re.I)
    installed = (system.get("bios") or "").rsplit(".", 1)[-1]
    if not m or not installed or len(m.group(1)) != len(installed):
        return False
    try:
        return int(m.group(1), 36) < int(installed, 36)
    except ValueError:
        return False


# ---------------------------------------------------------------- installing (elevated)

INSTALL_SCRIPT = r"""
param([string]$Ids, [string]$Out, [int]$Restore)
function Step($text) { Set-Content -Path "$Out.progress" -Value $text -Encoding UTF8 }
$result = @{ restore_point = $null; updates = @(); reboot = $false; error = $null }
try {
  if ($Restore -eq 1) {
    Step 'Creating a restore point'
    try { Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction SilentlyContinue
          Checkpoint-Computer -Description 'Sekar''s System Utilities - before driver update' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
          $result.restore_point = 'created' }
    catch { $result.restore_point = "not created: $($_.Exception.Message)" }
  }
  Step 'Finding the updates'
  $want = $Ids -split ','
  $s = New-Object -ComObject Microsoft.Update.Session
  $r = $s.CreateUpdateSearcher().Search("IsInstalled=0 and Type='Driver' and IsHidden=0")
  $coll = New-Object -ComObject Microsoft.Update.UpdateColl
  foreach ($x in $r.Updates) {
    if ($want -contains $x.Identity.UpdateID) {
      if ($x.EulaAccepted) { [void]$coll.Add($x) }
      else { $result.updates += @{ id = $x.Identity.UpdateID; title = $x.Title; code = -1; note = 'needs its licence accepted in Windows Update' } }
    }
  }
  if ($coll.Count -gt 0) {
    Step "Downloading $($coll.Count) update(s)"
    $dl = $s.CreateUpdateDownloader(); $dl.Updates = $coll; [void]$dl.Download()
    Step "Installing $($coll.Count) update(s)"
    $in = $s.CreateUpdateInstaller(); $in.Updates = $coll; $ir = $in.Install()
    $result.reboot = [bool]$ir.RebootRequired
    for ($i = 0; $i -lt $coll.Count; $i++) {
      $ur = $ir.GetUpdateResult($i)
      $result.updates += @{ id = $coll.Item($i).Identity.UpdateID; title = $coll.Item($i).Title; code = [int]$ur.ResultCode;
                            hresult = ('0x{0:X8}' -f $ur.HResult) }
    }
  }
} catch { $result.error = $_.Exception.Message }
$result | ConvertTo-Json -Depth 4 | Set-Content -Path $Out -Encoding UTF8
"""
RESULT_CODES = {2: "Installed", 3: "Installed with errors", 4: "Failed", 5: "Cancelled", -1: "Skipped"}


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def run_elevated(exe, params, on_tick=None):
    """Start a process with the UAC prompt and wait for it. Raises PermissionError if the user declines."""
    info = SHELLEXECUTEINFOW(cbSize=ctypes.sizeof(SHELLEXECUTEINFOW), fMask=0x40,   # SEE_MASK_NOCLOSEPROCESS
                             lpVerb="runas", lpFile=exe, lpParameters=params, nShow=0)
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.GetLastError() == 1223:    # ERROR_CANCELLED
            raise PermissionError("Administrator permission was declined, so nothing was installed.")
        raise ctypes.WinError()
    try:
        while ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 500) == 0x102:   # WAIT_TIMEOUT
            if on_tick:
                on_tick()
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)


def install_updates(ids, restore_point=True, progress=None):
    work = tempfile.mkdtemp(prefix="sysutil-drivers-")
    script, out = os.path.join(work, "install.ps1"), os.path.join(work, "result.json")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(INSTALL_SCRIPT)
    params = (f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}" '
              f'-Ids "{",".join(ids)}" -Out "{out}" -Restore {1 if restore_point else 0}')
    last = [None]

    def tick():
        try:
            with open(out + ".progress", encoding="utf-8-sig") as f:
                step = f.read().strip()
        except OSError:
            return
        if step and step != last[0] and progress:
            last[0] = step
            progress(step)

    run_elevated("powershell.exe", params, tick)
    if not os.path.exists(out):
        raise RuntimeError("The installer did not report back - check Windows Update for details.")
    with open(out, encoding="utf-8-sig") as f:
        result = json.load(f)
    for u in result.get("updates") or []:
        u["status"] = RESULT_CODES.get(u.get("code"), f"Result {u.get('code')}")
        u["ok"] = u.get("code") in (2, 3)
    return result


# ---------------------------------------------------------------- vendor tools

def vendor_tools(listing):
    found = {d["vendor"] for d in listing["drivers"] if d["vendor"]}
    system = listing["system"]
    tools = []
    for vendor in ("NVIDIA", "Intel", "AMD"):
        if vendor in found:
            t = VENDOR_TOOLS[vendor]
            exe = next((os.path.expandvars(p) for p in t["exe"] if os.path.exists(os.path.expandvars(p))), None)
            label = os.path.splitext(os.path.basename(exe))[0] if exe else t["label"]   # e.g. GeForce Experience
            tools.append({"vendor": vendor, "label": label, "installed": bool(exe), "target": exe or t["url"]})
    oem = system.get("oem")
    if oem in OEM_SUPPORT:
        model = system.get("model") or ""
        tools.append({"vendor": oem, "label": f"{oem} support for {model}".strip(), "installed": False,
                      "target": OEM_SUPPORT[oem].format(model=quote(model)),
                      "note": "Laptop-specific drivers (incl. Realtek audio & network) and BIOS"})
    return tools


# Intel parts whose generic Intel drivers are safe on any PC; other Intel drivers on laptops (Smart Sound audio,
# Dynamic Tuning, Serial IO...) are tuned by the laptop maker and should come from them.
INTEL_GENERIC = {"DISPLAY", "NET", "BLUETOOTH"}
OEM_TUNED = re.compile(r"realtek|nahimic|smart sound|\bsst\b|dynamic tuning|\bdtt\b|serial io|\bgna\b|"
                       r"management engine|\bmei\b|thunderbolt|card reader|\belan\b|synaptics|precision touchpad", re.I)


def update_source(d, listing, tools):
    """Where a newer version of this driver should come from: {vendor, target, label, why}."""
    by_vendor = {t["vendor"]: t for t in tools}
    oem = by_vendor.get(listing["system"].get("oem"))
    v = d.get("vendor")
    text = f"{d['name']} {d.get('provider') or ''}"
    intel_generic = d["cls"] in INTEL_GENERIC or re.search(r"graphics", d["name"], re.I)
    if d.get("age") is None:         # placeholder date: a driver that ships inside Windows
        return {"vendor": None, "target": None, "label": "Windows Update",
                "why": "This driver comes with Windows and is updated together with Windows itself."}
    if v in ("NVIDIA", "AMD") and v in by_vendor:
        t = by_vendor[v]
        why = f"{v} publishes its own drivers for this part; {t['label']} finds and installs the newest one."
    elif v == "Intel" and intel_generic and "Intel" in by_vendor and not OEM_TUNED.search(text):
        t = by_vendor["Intel"]
        why = "Intel's generic driver is safe here. Intel Driver & Support Assistant detects and installs the newest version."
    elif oem and (OEM_TUNED.search(text) or v in ("Realtek", "MSI", "Intel") or d["cls"] in ("MEDIA", "SYSTEM", "FIRMWARE")):
        t = oem
        why = (f"{oem['vendor']} customises this driver for your {listing['system'].get('model') or 'PC'}. "
               "Install it from their support page - a generic newer version can break audio, the mic, fans or battery features.")
    else:
        return {"vendor": None, "target": None, "label": "Windows Update",
                "why": "Updated through Windows Update. If nothing is offered there, this is the newest version made for your PC."}
    return {"vendor": t["vendor"], "target": t["target"], "label": t["label"], "why": why}


def open_tool(target):
    if not (target.startswith("https://") or (os.path.isfile(target) and target.lower().endswith(".exe"))):
        raise ValueError("Unknown tool.")
    os.startfile(target)
