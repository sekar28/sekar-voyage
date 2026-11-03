"""Clean-up mode: rule-based candidates plus AI review of unrecognised large folders."""

import os
import re
import time
from collections import defaultdict

from core import fmt_date, fmt_size, subtree_summary, walk

SAFE, REVIEW, CAUTION, KEEP = "Safe", "Review", "Caution", "Keep"
RISK_ORDER = {SAFE: 0, REVIEW: 1, CAUTION: 2, KEEP: 3}

MB = 1024 ** 2
GB = 1024 ** 3


def _glob_regex(pattern):
    """Path glob: `*` matches within one folder name, `**` matches any number of folders."""
    out = []
    for part in re.split(r"(\*\*|\*|\?)", pattern.lower()):
        out.append({"**": ".*", "*": r"[^\\]*", "?": r"[^\\]"}.get(part, re.escape(part)))
    return re.compile("".join(out) + r"\Z")


def _globs(*patterns):
    return [_glob_regex(p) for p in patterns]


# Folder rules, matched against the path without its drive letter (lower case).
# A matched folder is reported as a whole and not descended into.
DIR_RULES = [
    ("Windows temporary files", _globs(r"windows\temp"), SAFE,
     "Temporary files left behind by Windows and installers. Nothing breaks if removed; files in use are skipped.",
     "Settings > System > Storage > Temporary files, or delete the contents of the folder."),
    ("User temporary files", _globs(r"users\*\appdata\local\temp"), SAFE,
     "Temporary files from apps. Safe to clear; close running apps first so fewer files are locked.",
     "Press Win+R, type %temp%, select all and delete (skip files in use)."),
    ("Windows Update download cache", _globs(r"windows\softwaredistribution\download"), SAFE,
     "Update packages that are already installed. Windows re-downloads anything it still needs.",
     "Disk Cleanup > Clean up system files > Windows Update Cleanup."),
    ("Delivery Optimization cache",
     _globs(r"windows\serviceprofiles\networkservice\appdata\local\microsoft\windows\deliveryoptimization"), SAFE,
     "Update pieces cached to share with other PCs. No impact on your system.",
     "Disk Cleanup > Delivery Optimization Files."),
    ("Recycle Bin", _globs(r"$recycle.bin"), SAFE,
     "Files you already deleted. Emptying the bin makes them unrecoverable.",
     "Right-click Recycle Bin on the desktop > Empty Recycle Bin."),
    ("Crash dumps & error reports",
     _globs(r"windows\minidump", r"users\*\appdata\local\crashdumps", r"programdata\microsoft\windows\wer"), SAFE,
     "Crash reports used for troubleshooting. Safe unless you are diagnosing a crash.",
     "Disk Cleanup > System error memory dump files / Windows error reports."),
    ("Previous Windows installation", _globs(r"windows.old"), CAUTION,
     "Lets you roll back to the previous Windows version. After removal, rollback is impossible.",
     "Disk Cleanup > Clean up system files > Previous Windows installation(s)."),
    ("Browser caches", _globs(
        r"users\*\appdata\local\google\chrome\user data\*\cache",
        r"users\*\appdata\local\google\chrome\user data\*\code cache",
        r"users\*\appdata\local\google\chrome\user data\*\service worker\cachestorage",
        r"users\*\appdata\local\microsoft\edge\user data\*\cache",
        r"users\*\appdata\local\microsoft\edge\user data\*\code cache",
        r"users\*\appdata\local\microsoft\edge\user data\*\service worker\cachestorage",
        r"users\*\appdata\local\bravesoftware\brave-browser\user data\*\cache",
        r"users\*\appdata\local\mozilla\firefox\profiles\*\cache2"), SAFE,
     "Cached web content. Sites load a little slower the first time; logins and bookmarks are kept.",
     "Browser settings > Privacy > Clear browsing data > Cached images and files."),
    ("Developer package caches", _globs(
        r"users\*\appdata\local\npm-cache", r"users\*\appdata\roaming\npm-cache",
        r"users\*\appdata\local\pip\cache", r"users\*\appdata\local\yarn\cache",
        r"users\*\appdata\local\pnpm\store", r"users\*\.gradle\caches",
        r"users\*\.nuget\packages", r"users\*\.cache\huggingface"), CAUTION,
     "Downloaded package caches. Tools re-download what they need, so the next install/build is slower. "
     "Hugging Face caches hold downloaded AI models that would need re-downloading.",
     "npm cache clean --force / pip cache purge / delete the folder."),
    ("GPU shader caches", _globs(
        r"users\*\appdata\local\nvidia\dxcache", r"users\*\appdata\local\nvidia\glcache",
        r"users\*\appdata\local\d3dscache", r"users\*\appdata\local\amd\dxcache",
        r"users\*\appdata\locallow\nvidia\perdriverversion\dxcache"), SAFE,
     "Compiled shaders. Rebuilt automatically; games may stutter briefly on first launch.",
     "Disk Cleanup > DirectX Shader Cache, or delete the folder contents."),
    ("Extracted driver installers", _globs(r"nvidia", r"amd", r"intel"), SAFE,
     "Setup files that graphics/chipset driver installers unpack to the drive root. The installed drivers "
     "do not need them.",
     "Delete the folder (keep it only if you want to reinstall that exact driver offline)."),
    ("Virtual machines", _globs(r"hyper-v images", r"users\*\virtualbox vms", r"users\*\documents\virtual machines",
                                r"programdata\microsoft\windows\virtual hard disks"), CAUTION,
     "Virtual machine disks. Deleting them destroys the VM and everything inside it.",
     "Remove VMs you no longer use from Hyper-V Manager / VirtualBox, or move them to an external drive."),
    ("Installed games", _globs(r"xboxgames\*", r"program files*\steam\steamapps\common\*",
                               r"program files*\epic games\*", r"steamlibrary\steamapps\common\*",
                               r"**\steamlibrary\steamapps\common\*"), KEEP,
     "Game installs. Deleting files manually corrupts the game and leaves it registered as installed.",
     "Uninstall games you no longer play from the Xbox app / Steam / Epic, or Settings > Apps."),
    ("Installed programs", _globs(r"program files\*", r"program files (x86)\*"), KEEP,
     "Installed software. Deleting the folder breaks the program and leaves junk behind.",
     "If you no longer use it, uninstall from Settings > Apps > Installed apps."),
    ("Installed apps (per-user)", _globs(r"users\*\appdata\local\programs\*"), KEEP,
     "Programs installed just for your account (e.g. VS Code, Docker Desktop, Ollama). Deleting the folder "
     "breaks the app and leaves junk behind.",
     "If you no longer use one, uninstall it from Settings > Apps > Installed apps."),
    ("Local AI models (Ollama)", _globs(r"users\*\.ollama\models"), CAUTION,
     "Language models you downloaded for Ollama. Deleting the files breaks those models; they would need "
     "to be downloaded again.",
     "Run `ollama list`, then `ollama rm <model>` for models you no longer use."),
    ("Docker / WSL virtual disks", _globs(r"users\*\appdata\local\docker\wsl", r"users\*\appdata\local\wsl",
                                          r"users\*\appdata\local\packages\canonicalgroup*\localstate",
                                          r"users\*\appdata\local\packages\*linux*\localstate"),
     CAUTION,
     "Virtual disks holding Docker images/containers or a Linux (WSL) install. Deleting the file destroys "
     "everything inside. The disk does not shrink on its own after you delete data inside it.",
     "Run `docker system prune -a` (removes unused images), then Docker Desktop > Troubleshoot > Clean/Purge data, "
     "or compact the .vhdx with `wsl --shutdown` + Optimize-VHD / diskpart."),
    ("Windows component store (WinSxS)", _globs(r"windows\winsxs"), KEEP,
     "Core Windows files. Deleting manually WILL break Windows.",
     "Run as admin: DISM /Online /Cleanup-Image /StartComponentCleanup"),
    ("Windows Installer cache", _globs(r"windows\installer"), KEEP,
     "Needed to repair and uninstall programs. Do not delete manually.",
     "Leave it. Uninstall unused programs instead."),
]

# Folder names matched anywhere (outside protected locations).
NAME_RULES = {
    "node_modules": ("node_modules folders", REVIEW,
                     "JavaScript project dependencies. Restored with `npm install`; remove only for projects "
                     "you are not actively working on.",
                     "Delete the folder; run npm install when you return to the project."),
    "__pycache__": ("Python bytecode caches", SAFE,
                    "Recreated automatically the next time Python runs.",
                    "Delete the folder."),
}

ROOT_SYSTEM_FILES = {
    "hiberfil.sys": ("Hibernation file", KEEP,
                     "Used for hibernation and Fast Startup. Cannot be deleted directly.",
                     "To reclaim it, run as admin: powercfg /h off (disables hibernation/Fast Startup)."),
    "pagefile.sys": ("Page file (virtual memory)", KEEP,
                     "Virtual memory. Removing it can cause crashes when RAM runs out.",
                     "Can be resized in System > Advanced system settings > Performance > Virtual memory."),
    "swapfile.sys": ("Swap file", KEEP, "Used by Store apps. Managed by Windows.", "Leave it."),
}

PROTECTED_PREFIXES = ("windows", "program files", "program files (x86)", "programdata", "$recycle.bin",
                      "recovery", "system volume information")
APPDATA_PROGRAMS = _globs(r"users\*\appdata", r"users\*\appdata\**")
DOWNLOADS = _globs(r"users\*\downloads", r"users\*\downloads\**",
                   r"users\*\onedrive\downloads", r"users\*\onedrive\downloads\**")
INSTALLER_EXTS = {".exe", ".msi", ".iso", ".zip", ".rar", ".7z", ".msix"}
LOG_EXTS = {".log", ".etl", ".dmp"}


CLOUD_ROOTS = _globs(r"users\*\onedrive", r"users\*\onedrive - *", r"users\*\iclouddrive",
                     r"users\*\icloudphotos", r"users\*\dropbox", r"users\*\google drive")
CLOUD_NOTE = ("This is inside a cloud-synced folder: deleting it here also deletes it from the cloud and your "
              "other devices. To free space on this PC but keep it online, right-click it in Explorer > "
              "'Free up space' (OneDrive) or 'Remove download' (iCloud).")


def rel_path(path):
    return os.path.splitdrive(path)[1].strip("\\").lower()


def is_cloud_synced(path):
    rel = rel_path(path)
    parts = rel.split("\\")
    return any(g.match("\\".join(parts[:i])) for i in range(2, min(len(parts), 3) + 1) for g in CLOUD_ROOTS)


def is_protected(rel):
    """System or program locations where generic rules must not suggest deletions."""
    first = rel.split("\\", 1)[0]
    return first in PROTECTED_PREFIXES or any(g.match(rel) for g in APPDATA_PROGRAMS)


class Category:
    def __init__(self, name, risk, impact, how, source="rule"):
        self.name = name
        self.risk = risk
        self.impact = impact
        self.how = how
        self.source = source
        self.items = []   # dicts: path, size, kind ("dir"/"file"), note, reclaim

    @property
    def total(self):
        return sum(i.get("reclaim", i["size"]) for i in self.items)


def find_candidates(root, root_path=None, large_old_bytes=500 * MB, old_days=365, dup_min=10 * MB):
    cats = {}

    def add(name, risk, impact, how, **item):
        cat = cats.get(name)
        if cat is None:
            cat = cats[name] = Category(name, risk, impact, how)
        cat.items.append(item)

    cutoff = time.time() - old_days * 86400
    dupes = defaultdict(list)
    stack = [(root, root_path or root.path)]
    while stack:
        node, path = stack.pop()
        rel = rel_path(path)

        rule = next((r for r in DIR_RULES if any(g.match(rel) for g in r[1])), None)
        if rule:
            name, _, risk, impact, how = rule
            if node.size >= (100 * MB if risk == KEEP else MB):
                add(name, risk, impact, how, path=path, size=node.size, kind="dir",
                    note=f"{node.file_count:,} files")
            continue

        protected = is_protected(rel)
        if not protected and node.name.lower() in NAME_RULES and node.size >= MB:
            add(*NAME_RULES[node.name.lower()], path=path, size=node.size, kind="dir",
                note=f"{node.file_count:,} files")
            continue

        if any(g.match(rel) for g in CLOUD_ROOTS):
            for d in node.dirs:
                if d.size >= 100 * MB:
                    add("Cloud files kept on this PC", SAFE,
                        "These files are already in the cloud but also stored locally. Freeing them keeps them "
                        "online and on your other devices; they download again when you open them (needs internet).",
                        "Right-click the folder in Explorer > 'Free up space' (OneDrive) / 'Remove download' "
                        "(iCloud). Do NOT delete them - that deletes them from the cloud too.",
                        path=os.path.join(path, d.name), size=d.size, kind="dir",
                        note=f"{fmt_size(d.cloud)} already online-only")

        in_downloads = any(g.match(rel) for g in DOWNLOADS)
        for fname, size, mtime, cloud in node.files:
            if cloud:
                continue   # takes no space on this PC
            fpath = os.path.join(path, fname)
            low = fname.lower()
            ext = os.path.splitext(low)[1]
            if rel == "" and low in ROOT_SYSTEM_FILES:
                add(*ROOT_SYSTEM_FILES[low], path=fpath, size=size, kind="file", note="system file")
            elif rel == "windows" and low == "memory.dmp":
                crash = next(r for r in DIR_RULES if r[0] == "Crash dumps & error reports")
                add(crash[0], *crash[2:], path=fpath, size=size, kind="file", note="full memory dump")
            elif in_downloads and ext in INSTALLER_EXTS and size >= MB:
                add("Installers & archives in Downloads", REVIEW,
                    "Setup files and archives are usually not needed once installed or extracted.",
                    "Delete the ones you no longer need, or move archives you want to keep to backup storage.",
                    path=fpath, size=size, kind="file", note=f"modified {fmt_date(mtime)}")
            elif ext in LOG_EXTS and size >= 50 * MB:
                add("Large log & dump files", REVIEW,
                    "Logs and dumps from apps. Usually only useful for troubleshooting.",
                    "Delete if the app is closed; it will start a fresh log.",
                    path=fpath, size=size, kind="file", note=f"modified {fmt_date(mtime)}")
            elif not protected and size >= large_old_bytes and mtime < cutoff:
                add(f"Large files untouched for {old_days // 365}+ year(s)", REVIEW,
                    "Big files you have not modified in a long time. Often old videos, backups or disk images.",
                    "Move to an external drive / cloud, or delete if no longer needed.",
                    path=fpath, size=size, kind="file", note=f"last modified {fmt_date(mtime)}")
            if not protected and size >= dup_min:
                dupes[(low, size)].append(fpath)

        stack.extend((d, os.path.join(path, d.name)) for d in node.dirs)

    for (fname, size), paths in dupes.items():
        if len(paths) > 1:
            for p in paths:
                add("Likely duplicate files (same name & size)", REVIEW,
                    "The same file appears in several places. Keep one copy; the others are wasted space. "
                    "Verify the contents match before deleting.",
                    "Open each location in Explorer, keep the copy in the best place, delete the rest.",
                    path=p, size=size, kind="file", note=f"{len(paths)} copies",
                    reclaim=size * (len(paths) - 1) // len(paths))

    result = sorted(cats.values(), key=lambda c: (RISK_ORDER[c.risk], -c.total))
    for c in result:
        c.items.sort(key=lambda i: -i["size"])
    return result


# ---------------------------------------------------------------- AI review

def covered_paths(categories):
    # "Cloud files kept on this PC" only says how to free the local copy; the AI can still explain those folders.
    return {rel_path(i["path"]) for c in categories for i in c.items
            if i["kind"] == "dir" and c.name != "Cloud files kept on this PC"}


def unknown_big_folders(root, categories, limit=18):
    """Large folders not explained by rules: the biggest folders that have no big subfolder of their own,
    plus folders holding a lot of loose files directly."""
    covered = covered_paths(categories)
    threshold = max(100 * MB, root.size // 200)
    picked = []
    stack = [(root, root.path, 0)]
    while stack:
        node, path, depth = stack.pop()
        rel = rel_path(path)
        if rel.split("\\", 1)[0] == "windows" or any(rel == c or rel.startswith(c + "\\") for c in covered):
            continue   # Windows itself is never a deletion candidate
        big_children = [d for d in node.dirs if d.size >= threshold]
        if depth > 0 and (not big_children or depth >= 8):
            picked.append((node, path))
            continue
        if depth > 0 and sum(f[1] for f in node.files if not f[3]) >= threshold:
            picked.append((node, path))
        stack.extend((d, os.path.join(path, d.name), depth + 1) for d in big_children)
    picked.sort(key=lambda np: -np[0].size)
    return picked[:limit]


def describe_folder(node, path):
    s = subtree_summary(node, path)
    children = sorted(node.dirs, key=lambda d: -d.size)[:6]
    lines = [
        f"path: {path}",
        f"size on disk: {fmt_size(node.size)}, files: {node.file_count:,}, last modified: {fmt_date(s['newest'])}"
        + (f", plus {fmt_size(node.cloud)} of online-only cloud files" if node.cloud else "")
        + (" (cloud-synced folder)" if is_cloud_synced(path) else ""),
        "content by type: " + ", ".join(f"{k} {fmt_size(v)}" for k, v in s["by_type"][:5]),
        "largest subfolders: " + (", ".join(f"{d.name} ({fmt_size(d.size)})" for d in children) or "none"),
        "largest files: " + (", ".join(f"{n} ({fmt_size(sz)})" for sz, n in s["biggest"]) or "none"),
    ]
    return "\n".join(lines)


REVIEW_SYSTEM = """You are a careful Windows storage expert helping a user free disk space.
For each folder, identify what it most likely is (which app, game, tool or user data) and whether the
user can reclaim the space. Be conservative:
- Windows system folders and anything required by installed software: verdict "keep" or advise uninstalling.
- Installed programs and games: never say delete the folder; say "uninstall via Settings > Apps" if unused.
- Caches, temp data, old downloads, build output: usually "safe".
- Personal files (photos, documents, videos, projects): "review" - the user must decide; suggest archiving.
Respond with JSON only, exactly in this shape:
{"items":[{"id":1,"what":"short description","verdict":"safe|review|keep","action":"how to free the space safely","impact":"what happens if removed"}]}"""


CACHE_WORDS = re.compile(r"cache|temp|tmp|crash|logs?\b", re.I)


REVIEW_MAX_TOKENS = 1500     # per batch of folders
EXPLAIN_MAX_TOKENS = 600


def review_prompt(chunk):
    """(system, user) for one batch of (node, path) folders - also used to estimate tokens before sending."""
    return REVIEW_SYSTEM, "\n\n".join(f"Folder id {i + 1}:\n{describe_folder(n, p)}" for i, (n, p) in enumerate(chunk))


def ai_review_folders(llm, folders, progress=None, batch=5):
    """Ask the model about each (node, path). Returns a Category of AI suggestions."""
    cat = Category("AI review of large folders", REVIEW,
                   "Suggestions generated by AI. AI can be wrong - check before deleting.",
                   "See each item's action.", source="ai")
    for start in range(0, len(folders), batch):
        chunk = folders[start:start + batch]
        if progress:
            progress(f"Asking {llm.model} about folders {start + 1}-{start + len(chunk)} of {len(folders)}...")
        data = llm.chat_json(*review_prompt(chunk), max_tokens=REVIEW_MAX_TOKENS)
        answers = {}
        for item in data.get("items", []) if isinstance(data, dict) else []:
            try:
                answers[int(item.get("id"))] = item
            except (TypeError, ValueError):
                continue
        for i, (node, path) in enumerate(chunk):
            a = answers.get(i + 1, {})
            verdict = str(a.get("verdict", "review")).lower()
            risk = {"safe": SAFE, "keep": KEEP}.get(verdict, REVIEW)
            action = a.get("action", "")
            rel = rel_path(path)
            # Guardrails: never let the model recommend deleting system or program folders.
            if rel.split("\\", 1)[0] == "windows":
                risk, action = KEEP, "Windows system folder - do not delete manually."
            elif rel.startswith(("program files", "programdata")) and risk == SAFE:
                risk = REVIEW
                action = (action + " " if action else "") + "(Uninstall via Settings > Apps rather than deleting.)"
            elif is_cloud_synced(path):
                if risk == SAFE:
                    risk = REVIEW
                action = (action + " " if action else "") + CLOUD_NOTE
            elif risk == SAFE and "\\appdata\\" in rel and not CACHE_WORDS.search(rel):
                # App data the model calls safe may hold settings, databases or virtual disks.
                risk = REVIEW
                action = (action + " " if action else "") + \
                    "(App data: close the app first, and prefer its own 'clear cache' option.)"
            cat.items.append({
                "path": path, "size": node.size, "kind": "dir",
                "note": a.get("what", "no answer from model"),
                "risk": risk, "action": action, "impact": a.get("impact", ""),
            })
    cat.items.sort(key=lambda i: (RISK_ORDER[i["risk"]], -i["size"]))
    return cat


EXPLAIN_SYSTEM = """You are a careful Windows storage expert. The user asks about one file or folder on their PC.
In at most 6 short sentences explain: what it most likely is, whether it is safe to delete,
the impact of deleting it, and the safest way to reclaim the space (e.g. uninstall, app setting, Disk Cleanup).
Never encourage deleting Windows system files or folders of installed programs."""


def explain_prompt(node=None, path=None, size=None, mtime=None):
    if node is not None:
        info = describe_folder(node, path)
    else:
        info = f"file: {path}\nsize: {fmt_size(size)}\nlast modified: {fmt_date(mtime)}"
    if is_cloud_synced(path):
        info += ("\nNote: this is in a cloud-synced folder (OneDrive/iCloud); deleting it also deletes the cloud copy, "
                 "while 'Free up space' keeps it online and frees local disk.")
    return EXPLAIN_SYSTEM, info


def ai_explain(llm, node=None, path=None, size=None, mtime=None):
    return llm.chat(*explain_prompt(node, path, size, mtime), max_tokens=EXPLAIN_MAX_TOKENS)
