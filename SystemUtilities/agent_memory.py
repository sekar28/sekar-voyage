"""What the assistant learns on THIS laptop: your answers to its suggestions, which documents you open again,
which programs run and whether you ever use them, and which look suspicious.

Everything lives in %LOCALAPPDATA%\\StorageAnalyzer\\agent\\memory.db - per user, per machine, never synced
(Local, not Roaming), never sent anywhere, and never part of the app folder, so a shipped copy starts blank.
Only a short summary of preferences ("keeps KYC documents") is ever given to the AI.
"""

import ctypes
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from ctypes import wintypes

import quickclean

MEMORY_DIR = os.path.join(quickclean.LOCAL, "StorageAnalyzer", "agent")
DAY = 86400

# Document categories it may suggest deleting before you've taught it anything, and after how many days.
# Everything else (KYC, bank, property...) is only suggested once you've approved deleting it yourself.
DEFAULT_DELETABLE = {"bills": 60, "travel": 90}
LEARNED_AFTER_DAYS = 90          # for categories you approved yourself
KEEP_AFTER_NOS = 2               # say "no" this many times (and never yes) and it stops asking

SYSTEM_NAMES = {"svchost", "lsass", "csrss", "winlogon", "services", "smss", "wininit", "explorer", "dwm",
                "rundll32", "taskhostw", "conhost", "spoolsv", "dllhost", "ctfmon", "sihost", "searchhost"}
RANDOMISH = re.compile(r"^(?=.*\d)[a-z0-9]{8,}$|^[bcdfghjklmnpqrstvwxz]{6,}$|^[0-9a-f]{12,}$", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, ts REAL, kind TEXT, category TEXT, answer TEXT, items INTEGER, detail TEXT);
CREATE TABLE IF NOT EXISTS prefs (key TEXT PRIMARY KEY, value TEXT, source TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, name TEXT, category TEXT, size INTEGER, first_seen REAL, last_opened REAL, gone INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS procs (exe TEXT PRIMARY KEY, name TEXT, publisher TEXT, signed TEXT, first_seen REAL, last_seen REAL,
    days_seen INTEGER DEFAULT 0, last_day TEXT, samples INTEGER DEFAULT 0, fg_samples INTEGER DEFAULT 0, last_fg REAL,
    max_mem INTEGER DEFAULT 0, net INTEGER DEFAULT 0, reasons TEXT, user_tag TEXT);
CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, ts REAL, text TEXT, intent TEXT);
CREATE TABLE IF NOT EXISTS alerts (key TEXT PRIMARY KEY, last_ts REAL);
"""


def _lev1(a, b):
    """True when a and b differ by exactly one edit (svch0st vs svchost)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


class Memory:
    def __init__(self, folder=MEMORY_DIR):
        os.makedirs(folder, exist_ok=True)
        self.path = os.path.join(folder, "memory.db")
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)

    def _q(self, sql, args=(), one=False):
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
        return (rows[0] if rows else None) if one else rows

    def forget_all(self):
        with self._lock:
            for table in ("decisions", "prefs", "files", "procs", "requests", "alerts"):
                self._db.execute(f"DELETE FROM {table}")
            self._db.commit()

    # ------------------------------------------------------------ preferences and decisions
    def set_pref(self, key, value, source="you"):
        if value is None:
            self._q("DELETE FROM prefs WHERE key=?", (key,))
        else:
            self._q("INSERT OR REPLACE INTO prefs VALUES (?,?,?,?)", (key, json.dumps(value), source, time.time()))

    def pref(self, key, default=None):
        row = self._q("SELECT value FROM prefs WHERE key=?", (key,), one=True)
        return json.loads(row[0]) if row else default

    def record(self, kind, category, answer, items=0, detail=""):
        """Your answer to a suggestion: yes / no / review."""
        self._q("INSERT INTO decisions (ts, kind, category, answer, items, detail) VALUES (?,?,?,?,?,?)",
                (time.time(), kind, category or "", answer, items, detail[:300]))

    def stats(self, kind, category):
        rows = self._q("SELECT answer, COUNT(*) FROM decisions WHERE kind=? AND category=? GROUP BY answer",
                       (kind, category or ""))
        d = dict(rows)
        return d.get("yes", 0), d.get("no", 0)

    def policy(self, kind, category):
        """'never' (you keep these), 'usual' (you usually say yes), 'default' (allowed, not learned yet) or 'ask'."""
        tag = self.pref(f"{kind}.{category}")
        if tag in ("keep", "never"):
            return "never"
        if tag == "delete":
            return "usual"
        yes, no = self.stats(kind, category)
        if no >= KEEP_AFTER_NOS and yes == 0:
            return "never"
        if yes >= 2 and yes > no * 2:
            return "usual"
        if kind == "docs" and category in DEFAULT_DELETABLE:
            return "default"
        return "usual" if yes > no else "ask"

    def doc_age_limit(self, category):
        return self.pref(f"docs_after.{category}") or DEFAULT_DELETABLE.get(category, LEARNED_AFTER_DAYS)

    def log_request(self, text, intent):
        self._q("INSERT INTO requests (ts, text, intent) VALUES (?,?,?)", (time.time(), text[:300], intent or ""))

    def habit(self, intent, min_times=3):
        """Weekday you most often ask for this (e.g. clean junk on Mondays), if it's a clear habit."""
        rows = self._q("SELECT ts FROM requests WHERE intent=? AND ts>?", (intent, time.time() - 90 * DAY))
        if len(rows) < min_times:
            return None
        days = [time.localtime(r[0]).tm_wday for r in rows]
        best = max(set(days), key=days.count)
        return best if days.count(best) >= min_times and days.count(best) / len(days) >= 0.6 else None

    def alert_due(self, key, every=DAY):
        row = self._q("SELECT last_ts FROM alerts WHERE key=?", (key,), one=True)
        if row and time.time() - row[0] < every:
            return False
        self._q("INSERT OR REPLACE INTO alerts VALUES (?,?)", (key, time.time()))
        return True

    def rules_summary(self):
        """Short plain rules for the AI prompt - learned preferences only, never history or file lists."""
        out = []
        cats = {r[0] for r in self._q("SELECT DISTINCT category FROM decisions WHERE kind='docs'")} | set(DEFAULT_DELETABLE)
        for cat in sorted(c for c in cats if c):
            p = self.policy("docs", cat)
            if p == "never":
                out.append(f"user keeps {cat} documents - never suggest deleting them")
            elif p == "usual":
                out.append(f"user usually deletes {cat} documents older than {self.doc_age_limit(cat)} days")
        for kind in ("junk", "startup", "process"):
            yes, no = self.stats(kind, "")
            if yes + no >= 3:
                out.append(f"user {'usually accepts' if yes > no else 'usually declines'} {kind} suggestions")
        return out

    # ------------------------------------------------------------ documents: arrival and opens
    def observe_files(self, folder):
        """Note new loose documents in a folder (arrival time) and ones that disappeared (moved/deleted)."""
        now = time.time()
        seen = set()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            return
        for e in entries:
            if not e.is_file(follow_symlinks=False):
                continue
            seen.add(os.path.normcase(e.path))
            try:
                st = e.stat()
            except OSError:
                continue
            arrived = min(getattr(st, "st_birthtime", st.st_ctime), st.st_mtime)
            self._q("INSERT OR IGNORE INTO files (path, name, size, first_seen) VALUES (?,?,?,?)",
                    (os.path.normcase(e.path), e.name, st.st_size, arrived or now))
        prefix = os.path.normcase(folder).rstrip("\\") + "\\"
        for (path,) in self._q("SELECT path FROM files WHERE path LIKE ? AND gone=0", (prefix + "%",)):
            if path not in seen and "\\" not in path[len(prefix):]:
                self._q("UPDATE files SET gone=1 WHERE path=?", (path,))

    def observe_opens(self):
        """Files you opened, from Windows' Recent items (each shortcut's time = when you last opened it)."""
        script = (r"[Console]::OutputEncoding=[Text.Encoding]::UTF8; $s=New-Object -ComObject WScript.Shell; "
                  r"$r=[Environment]::GetFolderPath('Recent'); "
                  r"$o=Get-ChildItem -LiteralPath $r -Filter *.lnk -File -ErrorAction SilentlyContinue | ForEach-Object { "
                  r"try { [pscustomobject]@{t=$s.CreateShortcut($_.FullName).TargetPath; w=[int64](($_.LastWriteTimeUtc - [datetime]'1970-01-01').TotalSeconds)} } catch {} }; "
                  r"ConvertTo-Json -InputObject @($o) -Compress")
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=60,
                                 creationflags=subprocess.CREATE_NO_WINDOW).stdout
            items = json.loads(out or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return 0
        n = 0
        for it in items:
            if it.get("t"):
                path = os.path.normcase(it["t"])
                self._q("INSERT OR IGNORE INTO files (path, name, first_seen) VALUES (?,?,?)",
                        (path, os.path.basename(path), it["w"]))
                self._q("UPDATE files SET last_opened=MAX(COALESCE(last_opened,0),?) WHERE path=?", (it["w"], path))
                n += 1
        return n

    def file_info(self, path):
        row = self._q("SELECT first_seen, last_opened FROM files WHERE path=?", (os.path.normcase(path),), one=True)
        return {"first_seen": row[0], "last_opened": row[1]} if row else {"first_seen": None, "last_opened": None}

    def set_file_category(self, path, category):
        self._q("UPDATE files SET category=? WHERE path=?", (category, os.path.normcase(path)))

    # ------------------------------------------------------------ processes: usage and suspicion
    def sample_processes(self, groups, foreground_exe=None, net_pids=()):
        """One background sample from perf.snapshot() groups."""
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        net_pids = set(net_pids)
        for g in groups:
            if g["cat"] in ("windows", "self") or not g["path"]:
                continue
            exe = os.path.normcase(g["path"])
            row = self._q("SELECT last_day FROM procs WHERE exe=?", (exe,), one=True)
            on_net = any(p[0] in net_pids for p in g["procs"])
            if row is None:
                self._q("INSERT INTO procs (exe, name, publisher, first_seen, last_seen, days_seen, last_day, samples, max_mem, net) "
                        "VALUES (?,?,?,?,?,1,?,1,?,?)", (exe, g["name"], g.get("company") or "", now, now, today, g["mem"], int(on_net)))
            else:
                self._q("UPDATE procs SET last_seen=?, samples=samples+1, max_mem=MAX(max_mem,?), net=MAX(net,?), "
                        "days_seen=days_seen+(CASE WHEN last_day=? THEN 0 ELSE 1 END), last_day=? WHERE exe=?",
                        (now, g["mem"], int(on_net), today, today, exe))
        if foreground_exe:
            self.note_foreground(foreground_exe)

    def note_foreground(self, exe):
        self._q("UPDATE procs SET fg_samples=fg_samples+1, last_fg=? WHERE exe=?", (time.time(), os.path.normcase(exe)))

    def proc(self, exe):
        row = self._q("SELECT name, publisher, signed, first_seen, days_seen, fg_samples, last_fg, max_mem, net, reasons, user_tag "
                      "FROM procs WHERE exe=?", (os.path.normcase(exe),), one=True)
        keys = ("name", "publisher", "signed", "first_seen", "days_seen", "fg_samples", "last_fg", "max_mem", "net", "reasons", "user_tag")
        return dict(zip(keys, row)) if row else None

    def tag_process(self, exe, tag):
        """Your verdict: 'ok' (stop flagging it) or 'suspicious'."""
        self._q("UPDATE procs SET user_tag=? WHERE exe=?", (tag, os.path.normcase(exe)))

    def check_signatures(self, limit=40):
        """Authenticode status for programs not checked yet (one PowerShell call for the batch)."""
        rows = self._q("SELECT exe FROM procs WHERE signed IS NULL LIMIT ?", (limit,))
        paths = [r[0] for r in rows if os.path.exists(r[0])]
        if not paths:
            return 0
        listing = os.path.join(os.path.dirname(self.path), "_sigcheck.txt")
        with open(listing, "w", encoding="utf-8") as f:
            f.write("\n".join(paths))
        script = (r"[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                  f"$o = Get-Content -LiteralPath '{listing}' -Encoding UTF8 | ForEach-Object {{ "
                  r"$s = Get-AuthenticodeSignature -LiteralPath $_ -ErrorAction SilentlyContinue; "
                  r"[pscustomobject]@{p=$_; s=\"$($s.Status)\"; n=$(if ($s.SignerCertificate) { $s.SignerCertificate.GetNameInfo('SimpleName', $false) } else { '' })} }; "
                  r"ConvertTo-Json -InputObject @($o) -Compress")
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=120,
                                 creationflags=subprocess.CREATE_NO_WINDOW).stdout
            items = json.loads(out or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return 0
        finally:
            try:
                os.remove(listing)
            except OSError:
                pass
        for it in items:
            status = "valid" if it.get("s") == "Valid" else ("unsigned" if it.get("s") == "NotSigned" else (it.get("s") or "unknown").lower())
            self._q("UPDATE procs SET signed=?, publisher=CASE WHEN publisher='' THEN ? ELSE publisher END WHERE exe=?",
                    (status, it.get("n") or "", os.path.normcase(it["p"])))
        for (p,) in rows:
            if p not in [os.path.normcase(i["p"]) for i in items]:
                self._q("UPDATE procs SET signed='missing' WHERE exe=? AND signed IS NULL", (p,))
        return len(items)

    @staticmethod
    def suspicion_reasons(exe, name, signed, publisher, fg_samples, net, days_seen):
        """Plain reasons a program looks suspicious; [] when nothing stands out. One weak sign alone is not enough."""
        low = os.path.normcase(exe)
        stem = os.path.splitext(os.path.basename(low))[0]
        windir = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows")) + "\\"
        strong, weak = [], []
        if stem in SYSTEM_NAMES and not low.startswith(windir):
            strong.append(f"named like the Windows program {stem}.exe but runs from outside Windows")
        elif any(_lev1(stem, s) for s in SYSTEM_NAMES if len(s) > 4):
            strong.append(f"its name imitates a Windows program ({stem}.exe)")
        if signed == "unsigned":
            weak.append("it isn't digitally signed")
        elif signed not in (None, "valid", "missing", "unknown"):
            strong.append(f"its digital signature is {signed}")
        temp = os.path.normcase(os.environ.get("TEMP", ""))
        if temp and low.startswith(temp + "\\"):
            strong.append("it runs from the Temp folder")
        elif low.startswith(os.path.normcase(os.environ.get("APPDATA", "_")) + "\\") or "\\appdata\\local\\temp\\" in low:
            folder = os.path.basename(os.path.dirname(low))
            if RANDOMISH.match(folder) or RANDOMISH.match(stem):
                strong.append("it runs from a random-looking folder in AppData")
        if not publisher:
            weak.append("no publisher is named")
        if fg_samples == 0 and days_seen >= 2:
            weak.append("it runs hidden - you've never had its window open")
        if net:
            weak.append("it connects to the internet")
        return strong + weak if strong or len(weak) >= 3 and signed == "unsigned" else []

    def suspicious(self):
        rows = self._q("SELECT exe, name, signed, publisher, fg_samples, net, days_seen, user_tag FROM procs "
                       "WHERE COALESCE(user_tag,'') != 'ok'")
        out = []
        for exe, name, signed, publisher, fg, net, days, tag in rows:
            reasons = self.suspicion_reasons(exe, name, signed, publisher, fg, net, days)
            if reasons or tag == "suspicious":
                out.append({"exe": exe, "name": name, "reasons": reasons or ["you marked it suspicious"], "tagged": tag})
        return out

    def unused_startup(self, startup_items, min_days=7, idle_days=14):
        """Startup apps that run on most days you use the PC, but whose window you haven't used for idle_days."""
        out = []
        for item in startup_items:
            if not item["enabled"]:
                continue
            exe = os.path.normcase(quickclean_exe(item["command"]))
            info = self.proc(exe) if exe else None
            if not info or info["days_seen"] < min_days:
                continue
            last_used = info["last_fg"]
            if last_used is None or time.time() - last_used > idle_days * DAY:
                days = int((time.time() - (last_used or info["first_seen"])) / DAY)
                out.append({**item, "exe": exe, "days_seen": info["days_seen"], "idle_days": days, "never_used": last_used is None})
        return out

    # ------------------------------------------------------------ "What Jarvis has learned"
    def learned(self):
        decisions = self._q("SELECT kind, category, answer, COUNT(*) FROM decisions GROUP BY kind, category, answer")
        by = {}
        for kind, cat, answer, n in decisions:
            by.setdefault((kind, cat), {"kind": kind, "category": cat, "yes": 0, "no": 0, "review": 0})[answer] = n
        patterns = []
        for (kind, cat), d in by.items():
            patterns.append({**d, "policy": self.policy(kind, cat) if cat else None})
        for cat in DEFAULT_DELETABLE:
            if ("docs", cat) not in by:
                patterns.append({"kind": "docs", "category": cat, "yes": 0, "no": 0, "review": 0, "policy": self.policy("docs", cat)})
        prefs = [{"key": k, "value": json.loads(v), "source": s} for k, v, s, _ in self._q("SELECT * FROM prefs")]
        counts = {t: self._q(f"SELECT COUNT(*) FROM {t}", one=True)[0] for t in ("decisions", "files", "procs", "requests")}
        opened = self._q("SELECT COUNT(*) FROM files WHERE last_opened IS NOT NULL", one=True)[0]
        tagged = [{"exe": e, "name": n, "tag": t} for e, n, t in self._q("SELECT exe, name, user_tag FROM procs WHERE user_tag IS NOT NULL")]
        return {"patterns": patterns, "prefs": prefs, "counts": counts, "opened": opened, "tagged": tagged,
                "suspicious": self.suspicious(), "rules": self.rules_summary(), "folder": os.path.dirname(self.path)}


def quickclean_exe(command):
    command = os.path.expandvars(command or "").strip()
    m = re.match(r'"([^"]+)"', command) or re.match(r"(.+?\.exe)\b", command, re.I)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- live signals

def foreground_exe():
    """Path of the program whose window you're using right now."""
    user32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return None
    try:
        buf, n = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
    finally:
        k32.CloseHandle(h)


def internet_pids():
    """Processes with an established connection to a non-local address (netstat)."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=20,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 5 and parts[3] == "ESTABLISHED":
            remote = parts[2].rsplit(":", 1)[0]
            if not remote.startswith(("127.", "[::1]", "0.0.0.0", "[::]")):
                pids.add(int(parts[4]))
    return pids


def defender_scan(path):
    """Microsoft Defender custom scan of one file. Returns (clean?, message)."""
    exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"Windows Defender\MpCmdRun.exe")
    if not os.path.exists(exe):
        raise RuntimeError("Microsoft Defender isn't available on this PC.")
    r = subprocess.run([exe, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"], capture_output=True,
                       text=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode == 0:
        return True, "Microsoft Defender found no threats in it."
    if r.returncode == 2:
        return False, "Microsoft Defender found a threat in it. Open Windows Security to deal with it."
    return None, f"Microsoft Defender couldn't scan it (code {r.returncode})."
