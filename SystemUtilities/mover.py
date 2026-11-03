"""Carry out an organisation plan: match its suggestions to real files, move them, and undo on request.

Only direct children of the analysed folder are moved, only into subfolders of that same folder.
"""

import fnmatch
import json
import os
import re
import time

import quickclean
from organiser import SKIP_DIRS, SYSTEM_FILES

UNDO_DIR = os.path.join(quickclean.LOCAL, "StorageAnalyzer", "undo")
INVALID_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
# Folders Windows, OneDrive or apps rely on by name - moving them breaks things.
SPECIAL_NAMES = {"appdata", "desktop", "documents", "downloads", "pictures", "music", "videos", "onedrive",
                 "favorites", "links", "contacts", "searches", "saved games", "3d objects", "iclouddrive",
                 "icloudphotos", "attachments", "personal vault", "camera roll", "screenshots"}
HIDDEN_OR_SYSTEM = 0x2 | 0x4


def can_organise(folder):
    """Folders the app refuses to rearrange."""
    norm = os.path.normcase(os.path.abspath(folder)).rstrip("\\")
    home = os.path.normcase(os.path.expanduser("~"))
    if len(norm) <= 3:
        return False, "Drive roots can't be organised automatically."
    if norm == home:
        return False, "Your user folder holds system folders - organise a folder inside it instead (e.g. Downloads)."
    if norm.startswith(os.path.join(home, "appdata")):
        return False, "App data folders can't be organised."
    if any(norm == os.path.normcase(r) or norm.startswith(os.path.normcase(r) + "\\") for r in quickclean.PROTECTED_ROOTS):
        return False, "Windows and program folders can't be organised."
    return True, ""


def clean_target(to):
    """Plan target -> safe relative folder (max 2 levels, no '..', no illegal characters)."""
    parts = [INVALID_CHARS.sub("", p).strip(" .") for p in re.split(r"[\\/]+", str(to or ""))]
    parts = [p for p in parts if p and p not in (".", "..")][:2]
    return os.path.join(*parts) if parts else None


def _skip_reason(folder, name, is_dir):
    low = name.lower()
    if low in SYSTEM_FILES:
        return "Windows system file"
    if low.startswith("."):
        return "hidden item"
    if is_dir and (low in SKIP_DIRS or low in SPECIAL_NAMES):
        return "special folder"
    try:
        if os.stat(os.path.join(folder, name), follow_symlinks=False).st_file_attributes & HIDDEN_OR_SYSTEM:
            return "hidden or system item"
    except OSError:
        return "can't be read"
    return None


def _tokens(what):
    what = re.sub(r"\(\s*\d+\s+(files?|items?|folders?)\s*\)", "", str(what), flags=re.I)
    return [t.strip().strip("'\"`") for t in re.split(r",|;|\band\b", what) if t.strip().strip("'\"`")]


def preview(node, folder, plan):
    """Resolve plan moves into concrete (name -> target) assignments."""
    ok, why = can_organise(folder)
    if not ok:
        raise PermissionError(why)
    entries = {d.name: ("dir", d.size + d.cloud) for d in node.dirs}
    entries.update({f[0]: ("file", f[1]) for f in node.files})
    by_lower = {n.lower(): n for n in entries}
    targets = {(clean_target(m.get("to")) or "").split(os.sep)[0].lower() for m in plan.get("moves", []) if isinstance(m, dict)}

    assigned, unmatched, skipped = {}, [], {}
    for move in plan.get("moves", []):
        if not isinstance(move, dict):
            continue
        what, target = str(move.get("what", "")), clean_target(move.get("to"))
        if not target:
            unmatched.append(what)
            continue
        hits = []
        for tok in _tokens(what):
            if any(c in tok for c in "*?"):
                found = [n for n in entries if fnmatch.fnmatch(n.lower(), tok.lower())]
                if not found:   # "*.pdf invoices" -> try the wildcard word on its own
                    word = next((w for w in tok.split() if "*" in w or "?" in w), None)
                    found = [n for n in entries if word and fnmatch.fnmatch(n.lower(), word.lower())]
                hits += found
            elif tok.lower() in by_lower:
                hits.append(by_lower[tok.lower()])
        if not hits:
            unmatched.append(what)
        for name in dict.fromkeys(hits):
            kind = entries[name][0]
            if name in assigned or name.lower() in targets:
                continue          # first suggestion wins; never move a target folder itself
            if kind == "dir" and (target.lower() + os.sep).startswith(name.lower() + os.sep):
                continue          # can't move a folder into itself
            reason = _skip_reason(folder, name, kind == "dir")
            if reason:
                skipped[name] = reason
                continue
            assigned[name] = target

    groups = {}
    for name, target in assigned.items():
        g = groups.setdefault(target, {"target": target, "exists": os.path.isdir(os.path.join(folder, target)), "items": []})
        g["items"].append({"name": name, "kind": entries[name][0], "size": entries[name][1]})
    for g in groups.values():
        g["items"].sort(key=lambda i: i["name"].lower())
    return {
        "folder": folder, "assigned": assigned,
        "groups": sorted(groups.values(), key=lambda g: -len(g["items"])),
        "unmatched": unmatched, "skipped": [{"name": n, "reason": r} for n, r in skipped.items()],
    }


def _unique(path):
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem} ({n}){ext}"):
        n += 1
    return f"{stem} ({n}){ext}"


def _inside(path, folder):
    p, f = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    return p.startswith(f + os.sep)


def apply(folder, moves, progress=None):
    """moves: [(name, target)]. Returns a summary and the id of the undo journal."""
    ok, why = can_organise(folder)
    if not ok:
        raise PermissionError(why)
    journal, created, failed = [], [], []
    for n, (name, target) in enumerate(moves):
        if progress:
            progress(n, len(moves))
        src = os.path.join(folder, name)
        dst_dir = os.path.join(folder, clean_target(target) or "")
        if not (_inside(src, folder) and _inside(dst_dir, folder)) or not os.path.exists(src):
            failed.append({"name": name, "error": "no longer there"})
            continue
        try:
            if not os.path.isdir(dst_dir):
                parent = os.path.dirname(dst_dir)
                if not os.path.isdir(parent):
                    os.mkdir(parent)
                    created.append(parent)
                os.mkdir(dst_dir)
                created.append(dst_dir)
            dst = _unique(os.path.join(dst_dir, name))
            os.rename(src, dst)
            journal.append([src, dst])
        except OSError as e:
            failed.append({"name": name, "error": e.strerror or str(e)})

    undo_id = None
    if journal:
        os.makedirs(UNDO_DIR, exist_ok=True)
        undo_id = time.strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(UNDO_DIR, undo_id + ".json"), "w", encoding="utf-8") as f:
            json.dump({"folder": folder, "moves": journal, "created": created}, f, indent=1)
    return {"moved": len(journal), "failed": failed, "created": len(created), "undo_id": undo_id,
            "folders": sorted({os.path.relpath(os.path.dirname(d), folder) for _, d in journal}),
            "done": [{"name": os.path.basename(s), "to": os.path.relpath(os.path.dirname(d), folder)} for s, d in journal]}


def undo(undo_id):
    path = os.path.join(UNDO_DIR, os.path.basename(undo_id) + ".json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    restored, failed = 0, []
    for src, dst in reversed(data["moves"]):
        if not os.path.exists(dst):
            failed.append(os.path.basename(src) + ": was moved or deleted since")
            continue
        try:
            os.rename(dst, _unique(src))
            restored += 1
        except OSError as e:
            failed.append(f"{os.path.basename(src)}: {e.strerror or e}")
    for folder in reversed(data["created"]):     # remove the folders we made, if now empty
        try:
            os.rmdir(folder)
        except OSError:
            pass
    os.remove(path)
    return {"restored": restored, "failed": failed[:5], "folder": data["folder"]}
