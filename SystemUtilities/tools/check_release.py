"""Release check: fail if personal data would ship with the app.

Usage:  python tools/check_release.py [release_folder]      (default: the app folder itself)

What Jarvis learns, your settings, caches and keys belong in %LOCALAPPDATA%\\StorageAnalyzer on each PC - never in the
folder you package. This exits with code 1 and lists the offending files if any are found.
"""

import fnmatch
import os
import sys

FORBIDDEN = ["memory.db", "memory.db-*", "agent.json", "settings.json", "content_cache.json", "_sigcheck.txt",
             "*.sqlite", "*.sqlite3", "*.key", "secrets*.json", "instance.json", "last_request.wav",
             # model files are downloaded on first use - never shipped (some are research / non-commercial only)
             "*.onnx", "*.onnx.json", "*.tflite"]
FORBIDDEN_DIRS = {"agent", "undo", "webview", "voices",
                  "piper"}   # Piper is GPL-3.0 and optional: users install it themselves


def check(folder):
    problems = []
    for dirpath, dirnames, filenames in os.walk(folder):
        for d in list(dirnames):
            if d.lower() == "webview" and not os.path.isdir(os.path.join(dirpath, d, "EBWebView")):
                continue                     # the bundled pywebview library, not a browser profile with sign-ins
            if d.lower() in FORBIDDEN_DIRS:
                problems.append(os.path.join(dirpath, d) + os.sep)
                dirnames.remove(d)
        for f in filenames:
            if any(fnmatch.fnmatch(f.lower(), pat) for pat in FORBIDDEN):
                problems.append(os.path.join(dirpath, f))
    return problems


def main():
    folder = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
    problems = check(folder)
    if problems:
        print(f"NOT OK - personal data found in {folder}:")
        for p in problems:
            print("  ", p)
        print("Remove these before packaging (they belong in %LOCALAPPDATA%\\StorageAnalyzer on each PC).")
        sys.exit(1)
    print(f"OK - no personal data in {folder}")


if __name__ == "__main__":
    main()
