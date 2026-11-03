"""PC monitor: CPU / memory / battery (sysinfo.live, shared with StorageAnalyzer), NVIDIA GPU via nvidia-smi,
and free space per drive."""

import os
import shutil
import string
import subprocess

import sysinfo

GPU_QUERY = ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"]


def gpu():
    try:
        out = subprocess.run(GPU_QUERY, capture_output=True, text=True, timeout=5,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    name, util, used, total, temp = [x.strip() for x in out.splitlines()[0].split(",")]
    num = lambda v: float(v) if v.replace(".", "", 1).isdigit() else None
    return {"name": name.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", " Laptop"), "util": num(util),
            "mem_used": (num(used) or 0) * 1024 * 1024, "mem_total": (num(total) or 0) * 1024 * 1024, "temp": num(temp)}


def drives():
    out = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            u = shutil.disk_usage(root)
        except OSError:
            continue
        if u.total > 1e9:                     # skip card readers / tiny volumes
            out.append({"drive": letter, "total": u.total, "free": u.free})
    return out


def snapshot():
    live = sysinfo.live()
    return {**live, "gpu": gpu(), "drives": drives()}


def spoken(s):
    gb = lambda b: f"{b / 1024 ** 3:.0f}"
    parts = []
    if s.get("cpu") is not None:
        parts.append(f"CPU {s['cpu']:.0f} percent")
    g = s.get("gpu")
    if g and g.get("util") is not None:
        parts.append(f"GPU {g['util']:.0f} percent" + (f" at {g['temp']:.0f} degrees" if g.get("temp") else ""))
    parts.append(f"{gb(s['mem_used'])} of {gb(s['mem_total'])} gigabytes memory used")
    low = [d for d in s.get("drives", []) if d["free"] / d["total"] < 0.1]
    if low:
        parts.append("low space on " + ", ".join(f"drive {d['drive']}" for d in low))
    if s.get("battery") is not None:
        parts.append(f"battery {s['battery']} percent" + (", charging" if s.get("charging") else ""))
    return ", ".join(parts) + "."
