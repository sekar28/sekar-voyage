"""Scanning engine and shared helpers."""

import heapq
import os
import subprocess
import threading
import time
from datetime import datetime

TOP_FILES = 200          # entries kept in the "Largest files" tab

FILE_TYPES = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".ppt", ".pptx",
                  ".xls", ".xlsx", ".csv", ".ods", ".epub", ".one"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff",
               ".raw", ".cr2", ".nef", ".svg", ".psd", ".ico"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "Installers": {".exe", ".msi", ".iso", ".img", ".msix", ".appx"},
    "Code": {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".h", ".cs", ".go",
             ".rs", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".ipynb", ".sql", ".sh",
             ".ps1", ".bat"},
}
_EXT_TYPE = {ext: kind for kind, exts in FILE_TYPES.items() for ext in exts}


def file_type(name):
    return _EXT_TYPE.get(os.path.splitext(name)[1].lower(), "Other")


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "unknown"


def reveal_in_explorer(path):
    """Open Explorer with the item selected."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"This item no longer exists:\n{path}")
    subprocess.Popen(f'explorer /select,"{path}"')


def open_path(path):
    os.startfile(path)


# OneDrive / iCloud "online-only" placeholders: listed with their full size but not stored on disk.
CLOUD_ONLY_ATTRS = 0x00400000 | 0x00001000   # RECALL_ON_DATA_ACCESS | OFFLINE


class Node:
    __slots__ = ("name", "parent", "size", "cloud", "dirs", "files", "file_count", "denied")

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.size = 0          # bytes actually stored on this PC (whole subtree)
        self.cloud = 0         # bytes of online-only cloud files (whole subtree)
        self.dirs = []
        self.files = []        # list of (name, size, mtime, cloud_only)
        self.file_count = 0    # files in this whole subtree
        self.denied = False

    @property
    def path(self):
        parts = []
        node = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return os.path.join(*reversed(parts))

    def find(self, path):
        """Return the descendant node for an absolute path, or None."""
        rel = os.path.relpath(path, self.path)
        node = self
        if rel != ".":
            for part in rel.split(os.sep):
                node = next((d for d in node.dirs if d.name.lower() == part.lower()), None)
                if node is None:
                    return None
        return node


def _propagate(node, dsize, dcloud, dfiles):
    while node is not None:
        node.size += dsize
        node.cloud += dcloud
        node.file_count += dfiles
        node = node.parent


def remove_path(root, path):
    """Drop a deleted file or folder from the scanned tree and subtract its size from every parent."""
    try:
        node = root.find(path)
    except ValueError:
        return False
    if node is not None and node.parent is not None:
        node.parent.dirs.remove(node)
        _propagate(node.parent, -node.size, -node.cloud, -node.file_count)
        return True
    parent = root.find(os.path.dirname(path))
    name = os.path.basename(path).lower()
    for f in parent.files if parent else []:
        if f[0].lower() == name:
            parent.files.remove(f)
            _propagate(parent, -(0 if f[3] else f[1]), -(f[1] if f[3] else 0), -1)
            return True
    return False


def refresh_path(root, path):
    """Rescan one folder of the tree in place (after cleaning it) and fix the totals above it."""
    import queue
    try:
        old = root.find(path)
    except ValueError:
        return None
    if old is None:
        return None
    q = queue.Queue()
    Scanner(path, q).run()
    while (msg := q.get())[0] != "done":
        pass
    new = msg[1]
    dsize, dcloud, dfiles = new.size - old.size, new.cloud - old.cloud, new.file_count - old.file_count
    old.dirs, old.files, old.denied = new.dirs, new.files, new.denied
    for d in old.dirs:
        d.parent = old
    old.size, old.cloud, old.file_count = new.size, new.cloud, new.file_count
    _propagate(old.parent, dsize, dcloud, dfiles)
    return old


def walk(node, path=None):
    """Yield (node, path) for a node and all its descendants."""
    stack = [(node, path or node.path)]
    while stack:
        n, p = stack.pop()
        yield n, p
        stack.extend((d, os.path.join(p, d.name)) for d in n.dirs)


def subtree_summary(node, path=None):
    """On-disk size by file type, newest modification time and largest local files of a subtree."""
    by_type = {}
    newest = 0
    biggest = []
    for n, p in walk(node, path):
        for name, size, mtime, cloud in n.files:
            if cloud:
                newest = max(newest, mtime)
                continue
            kind = file_type(name)
            by_type[kind] = by_type.get(kind, 0) + size
            newest = max(newest, mtime)
            if len(biggest) < 5:
                heapq.heappush(biggest, (size, name))
            elif size > biggest[0][0]:
                heapq.heapreplace(biggest, (size, name))
    return {
        "by_type": sorted(by_type.items(), key=lambda kv: -kv[1]),
        "newest": newest,
        "biggest": sorted(biggest, reverse=True),
    }


class Scanner(threading.Thread):
    """Walks a directory tree once and builds an in-memory size tree."""

    def __init__(self, root_path, out_queue):
        super().__init__(daemon=True)
        self.root_path = root_path
        self.q = out_queue
        self.cancelled = False

    def run(self):
        root = Node(self.root_path, None)
        order = [root]
        stack = [(root, self.root_path)]
        top = []  # min-heap of (size, path)
        files_seen = 0
        last_report = time.monotonic()

        while stack and not self.cancelled:
            node, path = stack.pop()
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        try:
                            if entry.is_symlink() or entry.is_junction():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                child = Node(entry.name, node)
                                node.dirs.append(child)
                                order.append(child)
                                stack.append((child, entry.path))
                            else:
                                st = entry.stat(follow_symlinks=False)
                                size = st.st_size
                                cloud = bool(st.st_file_attributes & CLOUD_ONLY_ATTRS)
                                node.files.append((entry.name, size, st.st_mtime, cloud))
                                node.file_count += 1
                                files_seen += 1
                                if cloud:
                                    node.cloud += size
                                    continue
                                node.size += size
                                item = (size, entry.path)
                                if len(top) < TOP_FILES:
                                    heapq.heappush(top, item)
                                elif size > top[0][0]:
                                    heapq.heapreplace(top, item)
                        except OSError:
                            continue
            except OSError:
                node.denied = True

            now = time.monotonic()
            if now - last_report > 0.2:
                last_report = now
                self.q.put(("progress", files_seen, len(order), path))

        if self.cancelled:
            self.q.put(("cancelled",))
            return

        # Children always come after their parent in `order`, so a reverse pass
        # rolls sizes up the tree.
        for node in reversed(order):
            if node.parent is not None:
                node.parent.size += node.size
                node.parent.cloud += node.cloud
                node.parent.file_count += node.file_count

        top.sort(reverse=True)
        self.q.put(("done", root, top, files_seen, len(order)))
