"""Photo slideshow: every image under the chosen folders, shuffled.

Photos are shown from a cache of screen-sized JPEGs, which also covers iPhone HEIC files (the WebView can't show
them). Online-only OneDrive photos are downloaded once to make the cached copy, then freed again ("Free up space"),
so the slideshow doesn't slowly fill the disk with full-size originals."""

import hashlib
import os
import random
import stat
import subprocess
import threading
import winreg

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic", ".heif"}
MAX_PHOTOS = 30000
MIN_BYTES = 40_000      # skip icons and thumbnails
MAX_SIDE = 1920         # the 16" screen is 1920 px wide at most
# Files that exist only in the cloud (OneDrive "online-only"): opening them downloads them.
CLOUD_ONLY = getattr(stat, "FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS", 0x400000) | stat.FILE_ATTRIBUTE_OFFLINE
SKIP_DIRS = {"$recycle.bin", "node_modules", ".git", "appdata", "screenshot", "screenshots"}
NO_WINDOW = 0x08000000

_locks = {}
_locks_guard = threading.Lock()


def default_folders():
    """The Pictures folder, following OneDrive / custom redirection."""
    path = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            path = os.path.expandvars(winreg.QueryValueEx(key, "My Pictures")[0])
    except OSError:
        pass
    path = path or os.path.join(os.path.expanduser("~"), "Pictures")
    return [path] if os.path.isdir(path) else []


def is_cloud_only(path):
    try:
        return bool(getattr(os.stat(path), "st_file_attributes", 0) & CLOUD_ONLY)
    except OSError:
        return False


def scan(folders, include_cloud=True):
    found = []
    for root in folders:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                if os.path.splitext(name)[1].lower() not in EXTS:
                    continue
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if st.st_size < MIN_BYTES:
                    continue
                if not include_cloud and getattr(st, "st_file_attributes", 0) & CLOUD_ONLY:
                    continue
                found.append(path)
                if len(found) >= MAX_PHOTOS:
                    break
    random.shuffle(found)
    return found


def _cache_name(path):
    st = os.stat(path)
    return hashlib.sha1(f"{path}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest() + ".jpg"


def _lock_for(path):
    with _locks_guard:
        return _locks.setdefault(path, threading.Lock())


def free_up(path):
    """Same as OneDrive's "Free up space" on one file: keep it in the cloud, drop the local copy."""
    subprocess.run(["attrib", "+U", "-P", path], capture_output=True, creationflags=NO_WINDOW, timeout=30)


def render(path, cache_dir):
    """Path of a screen-sized JPEG of the photo, making it on first use."""
    from PIL import Image, ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener()

    os.makedirs(cache_dir, exist_ok=True)
    out = os.path.join(cache_dir, _cache_name(path))
    with _lock_for(path):
        if os.path.exists(out):
            os.utime(out)          # mark as recently used for pruning
            return out
        was_cloud = is_cloud_only(path)
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((MAX_SIDE, MAX_SIDE))
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                tmp = out + ".part"
                im.save(tmp, "JPEG", quality=85, optimize=True)
                os.replace(tmp, out)
        finally:
            if was_cloud:
                free_up(path)
    return out


def prune(cache_dir, max_bytes):
    """Delete the least recently shown cached JPEGs beyond max_bytes (only our own cache files)."""
    try:
        files = [e for e in os.scandir(cache_dir) if e.is_file() and e.name.endswith(".jpg")]
    except OSError:
        return
    files.sort(key=lambda e: e.stat().st_mtime, reverse=True)
    total = 0
    for e in files:
        total += e.stat().st_size
        if total > max_bytes:
            try:
                os.remove(e.path)
            except OSError:
                pass
