"""Organiser mode: profile a folder and ask the model for a better structure."""

import os
import re
from collections import Counter, defaultdict
from datetime import datetime

from core import file_type, fmt_size

COPY_PATTERN = re.compile(r"(\(\d+\)|\bcopy\b|- copy|_copy|\bfinal\b|\bnew folder\b|\buntitled\b)", re.I)
# Tool-managed folders: their internal layout is not the user's to organise.
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode", "bin", "obj",
             "dist", "build", ".next", "site-packages"}


def user_walk(node, path):
    """Like core.walk, but does not descend into tool-managed folders."""
    stack = [(node, path)]
    while stack:
        n, p = stack.pop()
        yield n, p
        stack.extend((d, os.path.join(p, d.name)) for d in n.dirs if d.name.lower() not in SKIP_DIRS)


def total_size(node):
    """On-disk plus online-only bytes: what matters when organising, wherever the file lives."""
    return node.size + node.cloud


def profile_folder(node, path):
    """Collect facts about a folder that both the UI and the prompt use."""
    direct_types = Counter()
    direct_size = 0
    years = Counter()
    for name, size, mtime, _ in node.files:
        direct_types[file_type(name)] += 1
        direct_size += size
        years[datetime.fromtimestamp(mtime).year if mtime else 0] += 1

    subfolders = []
    for d in sorted(node.dirs, key=lambda d: -total_size(d)):
        types = Counter()
        for n, _ in user_walk(d, os.path.join(path, d.name)):
            for name, size, _, _ in n.files:
                types[file_type(name)] += size
        main = types.most_common(1)[0][0] if types else "empty"
        subfolders.append({"name": d.name, "size": total_size(d), "files": d.file_count, "main_type": main,
                           "tool": d.name.lower() in SKIP_DIRS})

    # Issues across the whole subtree.
    dupes = defaultdict(list)   # (name, size) -> paths
    copies, empty, deep = [], [], []
    base_depth = path.rstrip("\\").count("\\")
    for n, p in user_walk(node, path):
        if n is not node and n.file_count == 0 and not n.dirs:
            empty.append(p)
        if p.count("\\") - base_depth >= 6 and n.files:
            deep.append(p)
        if COPY_PATTERN.search(n.name):
            copies.append(p)
        for name, size, _, _ in n.files:
            if size >= 100 * 1024:
                dupes[(name.lower(), size)].append(os.path.join(p, name))
            if COPY_PATTERN.search(name):
                copies.append(os.path.join(p, name))
    duplicates = [paths for paths in dupes.values() if len(paths) > 1]
    duplicates.sort(key=len, reverse=True)
    duplicate_waste = sum(size * (len(paths) - 1) for (_, size), paths in dupes.items() if len(paths) > 1)

    biggest = sorted(node.files, key=lambda f: -f[1])[:20]
    newest = sorted(node.files, key=lambda f: -f[2])[:20]
    sample = list({f[0]: f for f in biggest + newest}.values())[:35]

    return {
        "path": path,
        "size": total_size(node),
        "file_count": node.file_count,
        "direct_count": len(node.files),
        "direct_size": direct_size,
        "direct_types": direct_types.most_common(),
        "years": sorted(years.items()),
        "subfolders": subfolders,
        "sample": sample,
        "duplicates": duplicates,
        "duplicate_waste": duplicate_waste,
        "copies": copies,
        "empty": empty,
        "deep": deep,
    }


def rule_issues(p):
    """Plain-language issues found without AI."""
    issues = []
    if p["direct_count"] >= 25:
        kinds = ", ".join(f"{n} {k}" for k, n in p["direct_types"][:4])
        issues.append(f"{p['direct_count']} loose files sit directly in this folder ({kinds}). "
                      "Group them into subfolders by type, project or year.")
    if len(p["direct_types"]) >= 4 and p["direct_count"] >= 10:
        issues.append("Many different file types are mixed together at the top level.")
    if p["duplicates"]:
        issues.append(f"{len(p['duplicates'])} file(s) appear more than once (same name & size), wasting "
                      f"{fmt_size(p['duplicate_waste'])}, e.g. {os.path.basename(p['duplicates'][0][0])}.")
    if p["copies"]:
        issues.append(f"{len(p['copies'])} item(s) have names like 'copy', '(1)', 'final' or 'New folder' - "
                      "signs of ad-hoc versions. Rename or remove the old ones.")
    if p["empty"]:
        issues.append(f"{len(p['empty'])} empty folder(s) can be removed.")
    if p["deep"]:
        issues.append(f"{len(p['deep'])} folder(s) are nested 6+ levels deep - consider flattening.")
    small = [s for s in p["subfolders"] if s["files"] <= 2 and s["main_type"] != "empty"]
    if len(small) >= 5:
        issues.append(f"{len(small)} subfolders hold only 1-2 files - consider merging them.")
    return issues


ORGANISE_SYSTEM = """You are a professional digital organiser helping a Windows user tidy one folder.
Using the facts provided, propose a clear, practical folder structure (at most 8 top-level folders,
max 2 levels deep) that fits the actual content, and say which existing files/folders should move where.
Rules:
- Organise by PURPOSE or topic inferred from the names (e.g. "Finance", "Certificates", "Work/AWS",
  "Projects/<name>", "Photos/<event>"), not by file type alone. Do not create bare year folders at the top level;
  years are fine inside Photos or Archive.
- Keep existing subfolders that already make sense, and mention them in "structure".
- Group similar files into ONE move using a name pattern (e.g. "img2024*.jpg", "signed_*.pdf"),
  at most 12 moves. Never list the same file twice.
- Only call something old/archive if its year is at least 2 years ago.
- Do not invent files that are not listed. Folders marked [tool] are managed by software: never move their contents.
Respond with JSON only, exactly in this shape:
{"summary":"2-3 sentences on the current state",
 "structure":[{"folder":"Name or Name/Sub","purpose":"what belongs here"}],
 "moves":[{"what":"existing file, folder or pattern","to":"target folder","why":"short reason"}],
 "issues":[{"problem":"...","fix":"..."}],
 "tips":["naming or maintenance tip"]}"""


def build_prompt(p):
    lines = [
        f"Folder: {p['path']}",
        f"Total: {fmt_size(p['size'])}, {p['file_count']:,} files in subtree; "
        f"{p['direct_count']} files directly inside ({fmt_size(p['direct_size'])}).",
        "Direct file types: " + (", ".join(f"{k}: {n}" for k, n in p["direct_types"]) or "none"),
        "Direct files by year modified: " + (", ".join(f"{y}: {n}" for y, n in p["years"] if y) or "n/a"),
        "Subfolders (name | size | files | main content):",
    ]
    lines += [f"- {s['name']}{' [tool]' if s['tool'] else ''} | {fmt_size(s['size'])} | {s['files']} | {s['main_type']}"
              for s in p["subfolders"][:40]]
    if len(p["subfolders"]) > 40:
        lines.append(f"- ... and {len(p['subfolders']) - 40} more subfolders")
    lines.append(f"Today is {datetime.now():%Y-%m-%d}. Sample of files directly inside (name | size | modified):")
    lines += [f"- {n} | {fmt_size(s)} | {datetime.fromtimestamp(m):%Y-%m}" for n, s, m, _ in p["sample"]]
    issues = rule_issues(p)
    if issues:
        lines.append("Detected issues:")
        lines += [f"- {i}" for i in issues]
    return "\n".join(lines)


PLAN_MAX_TOKENS = 2500


def plan_prompt(profile):
    return ORGANISE_SYSTEM, build_prompt(profile)


def ai_organise(llm, profile):
    data = llm.chat_json(*plan_prompt(profile), max_tokens=PLAN_MAX_TOKENS)
    if not isinstance(data, dict):
        data = {}
    for key in ("structure", "moves", "issues", "tips"):
        if not isinstance(data.get(key), list):
            data[key] = []
    data["summary"] = str(data.get("summary", ""))
    return data


# ---------------------------------------------------------------- plan without AI

TYPE_HOMES = {
    "Documents": ("Documents", "PDFs, Word, Excel, PowerPoint and text files"),
    "Images": ("Pictures", "Photos, screenshots and other images"),
    "Videos": ("Videos", "Video files"),
    "Audio": ("Music", "Music and recordings"),
    "Archives": ("Archives", "Zip / RAR / 7z files - extract what you need, keep the rest as backup or delete"),
    "Installers": ("Installers", "Setup files (.exe, .msi, .iso) - usually safe to delete once installed"),
    "Code": ("Code", "Scripts, notebooks and config files"),
    "Other": ("Misc", "Everything else - review these by hand"),
}


NOUNS = {"Documents": "document", "Images": "image", "Videos": "video", "Audio": "audio file", "Archives": "archive",
         "Installers": "installer", "Code": "code file", "Other": "other file"}
SYSTEM_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}


def rule_plan(node, profile):
    """Same shape as ai_organise(), built from file types and dates only (works with AI turned off)."""
    loose = defaultdict(list)            # type -> [(name, mtime)]
    for name, _, mtime, _ in node.files:
        if name.lower() not in SYSTEM_FILES:
            loose[file_type(name)].append((name, mtime))
    existing = {d.name.lower(): d.name for d in node.dirs}

    structure, moves = [], []
    for kind, files in sorted(loose.items(), key=lambda kv: -len(kv[1])):
        if kind == "Other" and len(files) < 3:
            continue
        home, purpose = TYPE_HOMES[kind]
        target = existing.get(home.lower(), home)
        years = sorted({datetime.fromtimestamp(m).year for _, m in files if m})
        if kind in ("Images", "Videos") and len(years) >= 3:
            purpose += f" - sorted into one subfolder per year ({years[0]}-{years[-1]})"
        structure.append({"folder": target, "purpose": purpose + (" (already exists)" if target.lower() in existing else "")})
        exts = Counter(os.path.splitext(n)[1].lower() or "(no extension)" for n, _ in files)
        pattern = ", ".join(f"*{e}" if e.startswith(".") else e for e, _ in exts.most_common(4))
        plural = "s" if len(files) != 1 else ""
        moves.append({"what": f"{pattern} ({len(files)} file{plural})", "to": target,
                      "why": f"{len(files)} loose {NOUNS[kind]}{plural} at the top level"})

    issues = []
    if profile["duplicates"]:
        issues.append({"problem": f"{len(profile['duplicates'])} duplicate file(s)",
                       "fix": f"keep one copy of each to free {fmt_size(profile['duplicate_waste'])}"})
    if profile["copies"]:
        issues.append({"problem": f"{len(profile['copies'])} 'copy' / '(1)' / 'final' versions",
                       "fix": "keep the latest version, delete or archive the rest"})
    if profile["empty"]:
        issues.append({"problem": f"{len(profile['empty'])} empty folder(s)", "fix": "delete them"})
    if profile["deep"]:
        issues.append({"problem": f"{len(profile['deep'])} folder(s) nested 6+ levels deep",
                       "fix": "move them up so nothing is more than 3-4 levels deep"})

    if moves:
        summary = (f"{profile['direct_count']} loose files sit directly in this folder. Grouping them by type into "
                   f"{len(structure)} folder{'s' if len(structure) != 1 else ''} makes them much easier to find.")
    else:
        summary = "There are no loose files to sort here - the top level is already organised into folders."
    return {
        "summary": summary, "structure": structure, "moves": moves, "issues": issues,
        "tips": ["Name files with a date first (2025-03-14 Invoice ACME.pdf) so they sort in order.",
                 "Keep the top level to a handful of folders; put finished work into an Archive folder each year."],
        "model": "Rules (no AI)",
    }
