"""Duplicate versions: files like setup.exe / setup(1).exe / setup (2).exe / setup - Copy.exe that are byte-for-byte
identical. Names only nominate candidates; a SHA-256 hash of the content decides."""

import hashlib
import os
import re
from collections import Counter, defaultdict

from organiser import user_walk

# "name(1)", "name (12)", "name - Copy", "name - Copy (3)"
VERSION_RE = re.compile(r"^(?P<base>.*?)(?:\s*\((?P<n>\d{1,3})\)|\s+-\s+copy(?:\s*\((?P<c>\d{1,3})\))?)$", re.I)


def split_version(name):
    """'claude (2).exe' -> ('claude', '.exe', 2); 'claude.exe' -> ('claude', '.exe', 0)."""
    stem, ext = os.path.splitext(name)
    m = VERSION_RE.match(stem)
    if m and m.group("base").strip():
        if m.group("n"):
            return m.group("base").strip(), ext, int(m.group("n"))
        return m.group("base").strip(), ext, 1000 + int(m.group("c") or 1)   # copies rank after numbered versions
    return stem.strip(), ext, 0


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _public(x):
    return {"name": x["name"], "path": x["path"], "size": x["size"], "mtime": x["mtime"]}


def find(node, folder, progress=None):
    families = defaultdict(list)          # (dir, base, ext) -> files
    for n, path in user_walk(node, folder):
        for name, size, mtime, cloud in n.files:
            base, ext, ver = split_version(name)
            families[(path, base.lower(), ext.lower())].append(
                {"name": name, "path": os.path.join(path, name), "size": size, "mtime": mtime, "cloud": cloud, "ver": ver})
    families = {k: v for k, v in families.items() if len(v) >= 2 and any(x["ver"] for x in v)}

    # Only files that share their size with another local member of the family can be identical.
    todo, skipped_cloud = [], 0
    for fam in families.values():
        sizes = Counter(x["size"] for x in fam if not x["cloud"])
        for x in fam:
            if x["cloud"]:
                skipped_cloud += 1      # hashing would download it from the cloud
            elif x["size"] > 0 and sizes[x["size"]] > 1:
                todo.append(x)
    for i, x in enumerate(todo):
        if progress:
            progress(i, len(todo), x["name"])
        try:
            x["hash"] = file_hash(x["path"])
        except OSError:
            x["hash"] = None

    groups, different = [], 0
    for (path, _, _), fam in families.items():
        clusters = defaultdict(list)
        for x in fam:
            if x.get("hash"):
                clusters[(x["size"], x["hash"])].append(x)
        found = False
        for (size, digest), members in clusters.items():
            if len(members) < 2:
                continue
            members.sort(key=lambda x: (x["ver"], x["mtime"]))   # keep the original name, else the oldest
            groups.append({"dir": path, "keep": _public(members[0]), "dupes": [_public(x) for x in members[1:]],
                           "size": size, "hash": digest[:16]})
            found = True
        if not found and sum(1 for x in fam if x.get("hash")) >= 2:
            different += 1      # compared, and the contents really differ
    groups.sort(key=lambda g: -g["size"] * len(g["dupes"]))
    return summarise({"folder": folder, "groups": groups, "different": different,
                      "skipped_cloud": skipped_cloud, "hashed": len(todo)})


def summarise(result):
    result["waste"] = sum(g["size"] * len(g["dupes"]) for g in result["groups"])
    result["copies"] = sum(len(g["dupes"]) for g in result["groups"])
    return result
