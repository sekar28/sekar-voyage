"""The voice assistant behind "Hey Jarvis" for System Utilities: understands a request, runs the same checks the
buttons run, reports in a few spoken sentences and asks before changing anything.

Safety rule: tools only LOOK. Anything that deletes, moves, closes, installs or changes startup is prepared as a
single pending action with the exact items, and runs only after you confirm it (by voice or a click). The AI never
gets a "delete" tool, so whatever it answers, nothing destructive can happen without that confirmation.
"""

import os
import re
import shutil
import sys
import threading
import time
from collections import deque

import agent_memory
import cleanup
import content
import perf
import quickclean
import sysinfo
from llm import LLMError

GB, MB = 1024 ** 3, 1024 ** 2
PENDING_TTL = 300               # a question waits 5 minutes for your answer
SCAN_REUSE = 15 * 60            # reuse a scan of the same folder made in the last 15 minutes
CRIT_PCT = 95                   # CPU / memory / GPU above this for ~a minute = critical alert (bell)
CRIT_DISK = 98                  # any drive more than this % full = critical alert (bell)

YES = re.compile(r"^(yes|yeah|yep|yup|sure|ok(ay)?|go ahead|do it|please do|confirm(ed)?|proceed|clean (it|them)( up)?|"
                 r"delete (it|them)|remove (it|them)|go for it|sounds good|alright|of course|right|correct)\b", re.I)
NO = re.compile(r"^(no|nope|nah|don'?t|do not|cancel|stop|never ?mind|not now|leave (it|them)|skip( it)?|keep (it|them))\b", re.I)
REVIEW = re.compile(r"^(show( me)?|review|let me (see|check|look)|open( it)?|details|which (ones|files)|what are they)\b", re.I)


def fmt(n):
    if n >= GB:
        return f"{n / GB:.1f} GB"
    if n >= MB:
        return f"{n / MB:.0f} MB"
    return f"{max(1, n // 1024)} KB" if n else "0 KB"


def plural(n, word):
    if n == 1:
        return f"{n} {word}"
    head, _, last = word.rpartition(" ")
    last = last[:-1] + "ies" if re.search(r"[^aeiou]y$", last) else last + "s"
    return f"{n} {head + ' ' if head else ''}{last}"


class Reply:
    def __init__(self, say, pending=None):
        self.say, self.pending = say, pending


class Pending:
    """One prepared change, waiting for yes / no / review."""

    def __init__(self, kind, question, run, items=(), category="", review=None, categories=None):
        self.kind, self.question, self.run = kind, question, run
        self.items = list(items)
        self.category, self.categories = category, categories or ([category] if category else [""])
        self.review = review or {}
        self.created = time.time()

    def expired(self):
        return time.time() - self.created > PENDING_TTL

    def public(self):
        return {"kind": self.kind, "question": self.question, "count": len(self.items),
                "items": [str(i)[:200] for i in self.items[:40]], "review": self.review}


# ---------------------------------------------------------------- understanding requests

INTENTS = [   # (intent, pattern) - matched before the AI, so common requests are instant and work with AI off
    ("boost", r"\b(boost|speed (it |things |my pc |the pc )?up|make (it|my pc|the pc) faster|(pc|computer|laptop) is slow|free (up )?(some )?(ram|memory))\b"),
    ("clean_ram", r"\b(clean|clear|trim|flush) (the |my )?(ram|memory)\b"),
    ("junk", r"\b(junk|temp(orary)? files|cache|quick clean|clean (up )?(my |the )?(pc|computer|laptop|system|disk|drive)|free (up )?(disk )?space)\b"),
    ("old_docs", r"\b(old|unused|unneeded) (documents|docs|files|bills|invoices|pdfs)|\b(bills|invoices|statements) .*(delete|remove|clean)|documents .*(delete|don.t need)"),
    ("duplicates", r"\b(duplicates?|copies|same files?|versions)\b"),
    ("organise", r"\b(organi[sz]e|sort|tidy|arrange|clean up the mess in)\b"),
    ("undo", r"\bundo\b"),
    ("deletable", r"\b(what|anything) (can|could|should) (i|we|be) (delete|remove|clean|throw away)|\b(scan|check|analy[sz]e) (my |the )?(downloads|documents|desktop|pictures|videos|music|[a-z] drive|folder)|\bwhat.s (taking|using) (up )?(space|storage)"),
    ("suspicious", r"\b(suspicious|virus|malware|hack(ed|er)?|safe|legit|dodgy|strange|unknown) (process|program|app)s?|\bprocess(es)? .*(suspicious|safe|legit)|\bscan .* defender\b"),
    ("startup", r"\bstart ?up\b|\b(starts|launch(es)?) (with|when) (windows|i (log|sign) in)"),
    ("orphans", r"\b(orphan(ed|s)?|left ?over|zombie|stray|abandoned)\b"),
    ("performance", r"\b(process(es)?|what( i|.)s running|running (apps|programs|applications)|background (apps|processes)|"
                    r"task manager|cpu|memory usage|ram usage|performance)\b"),
    ("drivers", r"\bdrivers?\b"),
    ("health", r"\b(how is|how.s|check|status of|health of) (my |the )?(pc|computer|laptop|system)|\b(check.?up|health check|full check)\b"),
    ("learned", r"\bwhat (have you|did you) learn|\bwhat do you know about (me|my)"),
    ("status", r"\b(are you (done|finished)|what are you doing|progress|still (working|scanning))\b"),
]

DOC_WORDS = {"bills": "bills", "bill": "bills", "invoices": "bills", "invoice": "bills", "receipts": "bills",
             "kyc": "kyc", "identity": "kyc", "id cards": "kyc", "passport": "kyc", "aadhaar": "kyc", "pan card": "kyc",
             "bank": "bank", "tax": "bank", "statements": "bank", "insurance": "insurance", "medical": "insurance",
             "tickets": "travel", "travel": "travel", "boarding passes": "travel", "work": "work", "certificates": "education",
             "manuals": "manuals", "property": "property", "legal": "property"}

BRAIN = """You are Jarvis, the voice assistant inside "Sekar's System Utilities", a Windows PC care app. Pick ONE tool for the
user's request and reply with ONE JSON object only: {"tool": "<name>", "args": {...}} or {"say": "<short spoken answer>"}.

Tools (they only look and report; anything that changes the PC is offered afterwards and needs the user's yes):
- health {}                         full check-up: memory, disk, junk, loose files, drivers
- junk {}                           measure junk files (temp, caches, logs, installers) and offer to clean
- deletable {"folder": "<name>"}    scan a folder/drive (downloads, documents, desktop, pictures, C drive, a path) for things to delete
- old_docs {"folder": "<name>"}     find documents (bills, tickets...) you no longer open, using what you've learned
- organise {"folder": "<name>", "deep": false}   plan how to sort a folder's loose files ("deep": also read unclear documents)
- duplicates {"folder": "<name>"}   find duplicate files and versions
- undo {}                           offer to undo the last organise
- performance {}                    memory, CPU, what's running, background helpers
- boost {}                          offer to close safe background helpers and clean RAM
- clean_ram {}                      trim memory now (closes nothing)
- orphans {}                        leftover background processes whose app has closed (offers to close them)
- suspicious {}                     programs that look suspicious, with reasons
- startup {}                        startup apps, and ones you never use
- drivers {}                        check Windows Update for driver updates
- open_screen {"screen": "home|cleanup|quick|organiser|drivers|performance|assistant"}
- remember {"category": "<bills|kyc|bank|insurance|travel|work|education|property|manuals|personal|other>", "choice": "keep|delete"}
- mark_process {"name": "<program name>", "verdict": "ok|suspicious"}
- learned {}                        what you have learned about this user
- status {}                         what you're working on

What you know about this user (learned on this PC):
{rules}

Speech-to-text may mishear words. Use "say" for greetings or questions you can answer without a tool (1-2 sentences).
Never claim to have deleted or changed anything yourself."""


class Agent:
    def __init__(self, api, memory=None):
        self.api = api
        self.mem = memory or agent_memory.Memory()
        self.pending = None
        self.job = None                       # label of the long task running, if any
        self.events = deque(maxlen=200)
        self.listeners = []                   # callables(event) told about every pushed event
        self._eid = 0
        self._lock = threading.Lock()
        self._ask_lock = threading.Lock()
        self.history = deque(maxlen=8)
        self.transcript = deque(maxlen=100)
        self._scanned = {}                    # folder -> time of the agent's last scan
        self.last_undo = None                 # (undo_id, folder, count)
        self._stop = threading.Event()
        self._last_check = {}
        self._mem_high_since = None
        self._high = {}                       # resource -> readings in a row above CRIT_PCT
        sysinfo.live()                        # prime the CPU reading (the first one is always empty)

    # ------------------------------------------------------------ plumbing
    def call(self, name, *args):
        r = getattr(self.api, name)(*args)
        if isinstance(r, dict) and "__error__" in r:
            raise RuntimeError(r["__error__"])
        return r

    def _ui(self, event, data):
        try:
            self.api._emit(event, data)
        except Exception:
            pass

    def _line(self, who, text, **extra):
        if not text:
            return
        entry = {"who": who, "text": text, "ts": time.time(), **extra}
        self.transcript.append(entry)
        self._ui("agent_line", {**entry, "pending": self.pending.public() if self.pending else None, "job": self.job})

    def push(self, say, kind="report", expect_reply=None, critical=False):
        """A message for the Dashboard to speak (and for the Assistant panel). critical: the Dashboard rings its bell once."""
        with self._lock:
            self._eid += 1
            ev = {"id": self._eid, "say": say, "kind": kind, "ts": time.time(), "critical": critical,
                  "expect_reply": bool(self.pending) if expect_reply is None else expect_reply}
            self.events.append(ev)
        self._line("jarvis", say, kind="critical" if critical else kind)
        for listener in list(self.listeners):     # e.g. System Utilities' own voice, when the Dashboard is closed
            try:
                listener(ev)
            except Exception:
                pass
        return ev

    def events_since(self, since=0):
        with self._lock:
            return {"events": [e for e in self.events if e["id"] > since], "last": self._eid}

    def state(self):
        return {"pending": self.pending.public() if self.pending else None, "job": self.job,
                "transcript": list(self.transcript), "monitor": self.monitor_on()}

    def monitor_on(self):
        return bool(self.api._settings.get("agent_monitor", True))

    def _set_pending(self, p):
        self.pending = p
        self._ui("agent_pending", p.public() if p else None)

    # ------------------------------------------------------------ asking
    def ask(self, text, source="panel"):
        text = (text or "").strip()
        text = re.sub(r"^(hey |ok |okay )?(jarvis|computer)[,.! ]*", "", text, flags=re.I).strip()
        if not text:
            return {"say": "Yes?", "expect_reply": True, "busy": bool(self.job)}
        self._line("you", text, source=source)
        with self._ask_lock:
            try:
                reply = self._answer(text)
            except (LLMError, RuntimeError, ValueError, FileNotFoundError, PermissionError) as e:
                reply = Reply(f"Sorry, {str(e).rstrip('.')}.")
        if reply.pending is not None:
            self._set_pending(reply.pending)
        self.history.append(("user", text))
        self.history.append(("jarvis", reply.say))
        self._line("jarvis", reply.say)
        return {"say": reply.say, "expect_reply": bool(self.pending and reply.pending is not None), "busy": bool(self.job)}

    def _answer(self, text):
        p = self.pending
        if p and p.expired():
            self._set_pending(None)
            p = None
        if p:
            if YES.search(text):
                return self.confirm(source="voice")
            if NO.search(text):
                return self.decline()
            if REVIEW.search(text):
                return self.review()
        elif YES.fullmatch(text.strip(" .!")) or NO.fullmatch(text.strip(" .!")):
            return Reply("There's nothing waiting for an answer right now.")
        intent, args = self._intent(text)
        self.mem.log_request(text, intent)
        return self.run_tool(intent, args)

    def _intent(self, text):
        low = text.lower()
        for intent, pattern in INTENTS:
            if re.search(pattern, low):
                return intent, {"folder": self._folder_word(text), "deep": bool(re.search(r"\b(deep|read|contents?)\b", low)),
                                "text": text}
        client = self._ai()
        if client is None:
            return "help", {}
        rules = "\n".join(f"- {r}" for r in self.mem.rules_summary()) or "- nothing learned yet"
        convo = "\n".join(f"{who}: {t}" for who, t in list(self.history)[-6:])
        state = f"Task running: {self.job or 'none'}. Waiting for an answer to: {self.pending.question if self.pending else 'nothing'}."
        out = client.chat_json(BRAIN.replace("{rules}", rules), f"{state}\nRecent conversation:\n{convo}\n\nRequest: {text}",
                               timeout=60, max_tokens=300)
        if isinstance(out, dict) and out.get("say") and not out.get("tool"):
            return "say", {"text": str(out["say"])}
        if isinstance(out, dict) and out.get("tool"):
            return str(out["tool"]), dict(out.get("args") or {})
        return "help", {}

    @staticmethod
    def _folder_word(text):
        """The folder a request is about: an explicit path first, then a known folder, then 'C drive'."""
        m = re.search(r"[a-zA-Z]:\\[^\"'?]*", text)
        if m and len(m.group(0).rstrip("\\ .")) > 2:
            return m.group(0).rstrip(" .")
        low = text.lower()
        for word in ("downloads", "documents", "desktop", "pictures", "videos", "music"):
            if word in low or word.rstrip("s") + " folder" in low:
                return word
        m = re.search(r"\b([a-z]) drive\b|\b([a-z]):\\?(?=\s|$)", low)
        letter = m and (m.group(1) or m.group(2))
        if letter and letter not in ("a", "i"):
            return f"{letter} drive"
        return None

    def _ai(self):
        if not self.api._ai_enabled:
            return None
        return self.api._llm

    def folder(self, name, default="downloads"):
        name = (name or default or "").strip()
        folders = self.api.known_folders()
        known = {f["name"].lower(): f["path"] for f in folders} if isinstance(folders, list) else {}
        low = name.lower()
        for label, path in known.items():
            if label in low or label.rstrip("s") in low:
                return path
        m = re.fullmatch(r"([a-z])( drive|:\\?|:)", low)
        if m:
            path = f"{m.group(1).upper()}:\\"
            if os.path.isdir(path):
                return path
        if os.path.isdir(name):
            return name
        raise ValueError(f"I couldn't find a folder called {name}")

    # ------------------------------------------------------------ tools
    def run_tool(self, intent, args):
        tools = {
            "health": (self.t_health, False, "Checking your PC"),
            "junk": (self.t_junk, False, None),
            "deletable": (self.t_deletable, True, "Scanning {folder}"),
            "old_docs": (self.t_old_docs, True, "Looking through the documents in {folder}"),
            "organise": (self.t_organise, True, "Working out how to organise {folder}"),
            "duplicates": (self.t_duplicates, True, "Looking for duplicates in {folder}"),
            "undo": (self.t_undo, False, None),
            "performance": (self.t_performance, False, None),
            "boost": (self.t_boost, False, None),
            "clean_ram": (self.t_clean_ram, False, None),
            "suspicious": (self.t_suspicious, False, None),
            "orphans": (self.t_orphans, False, None),
            "startup": (self.t_startup, False, None),
            "drivers": (self.t_drivers, True, "Asking Windows Update for driver updates"),
            "open_screen": (self.t_open_screen, False, None),
            "remember": (self.t_remember, False, None),
            "mark_process": (self.t_mark_process, False, None),
            "learned": (self.t_learned, False, None),
            "status": (self.t_status, False, None),
            "say": (lambda a: Reply(a.get("text", "")), False, None),
            "help": (self.t_help, False, None),
        }
        if intent not in tools:
            return self.t_help(args)
        fn, slow, label = tools[intent]
        if not slow:
            return fn(args)
        if self.job:
            return Reply(f"I'm still busy: {self.job.lower()}. I'll tell you when it's done.")
        folder_name = args.get("folder") or "your Downloads folder"
        if ":\\" in folder_name:
            folder_name = os.path.basename(folder_name.rstrip("\\")) or folder_name
        elif "folder" not in folder_name and "drive" not in folder_name:
            folder_name = f"your {folder_name}"
        label = label.format(folder=folder_name)
        self.job = label

        def work():
            try:
                r = fn(args)
            except Exception as e:
                r = Reply(f"Sorry, that didn't work: {str(e).rstrip('.')}.")
            self.job = None
            if r.pending is not None:
                self._set_pending(r.pending)
            self.push(r.say, "report", expect_reply=r.pending is not None)
        threading.Thread(target=work, daemon=True).start()
        self._ui("agent_job", {"job": label})
        return Reply(f"{label}. I'll tell you when it's done.")

    def t_help(self, args):
        return Reply("I can check your PC, clean junk, find files you can delete, organise a folder, find duplicates, "
                     "boost performance, review startup apps and check drivers. What would you like?")

    def t_status(self, args):
        if self.job:
            return Reply(f"I'm {self.job[0].lower() + self.job[1:]}.")
        if self.pending:
            return Reply(f"I'm waiting for your answer: {self.pending.question}")
        return Reply("Nothing running right now.")

    # ---- junk
    def _junk(self):
        targets = [t for t in quickclean.TARGETS if t["default"] and t["kind"] not in ("recycle", "cleanmgr")]
        sizes = {t["id"]: quickclean.measure(t) for t in targets}
        admin = quickclean.is_admin()
        usable = [t for t in targets if sizes[t["id"]]["size"] > 0 and not (t.get("admin") and not admin)]
        return sorted(usable, key=lambda t: -sizes[t["id"]]["size"]), sizes

    def t_junk(self, args):
        usable, sizes = self._junk()
        total = sum(sizes[t["id"]]["size"] for t in usable)
        if total < 20 * MB:
            return Reply("Your PC is already clean - there's less than 20 MB of junk.")
        top = ", ".join(f"{t['name'].lower()} {fmt(sizes[t['id']]['size'])}" for t in usable[:3])
        ids = [t["id"] for t in usable]
        habit = " You usually say yes to this." if self.mem.policy("junk", "") == "usual" else ""

        def run():
            r = self.call("quick_clean", ids)
            return f"Done. Freed {fmt(r['freed'])}" + (f"; {plural(r['skipped'], 'file')} in use were skipped." if r["skipped"] else ".")
        q = f"You can free {fmt(total)} of junk: {top}.{habit} Shall I clean it?"
        return Reply(q, Pending("junk", q, run, [f"{t['name']} ({fmt(sizes[t['id']]['size'])})" for t in usable],
                                review={"view": "quick"}))

    # ---- scanning a folder
    def _scan(self, path):
        key = os.path.normcase(path)
        try:
            mtime = os.stat(path).st_mtime       # changes when files are added to / removed from the folder
        except OSError:
            mtime = None
        last = self._scanned.get(key)
        root = self.api._root
        if (last and time.time() - last[0] < SCAN_REUSE and last[1] == mtime and root is not None
                and os.path.normcase(root.path) == key):
            return root
        self.call("start_scan", path)
        deadline = time.time() + 3600
        while time.time() < deadline:
            sc = self.api._scanner
            if sc is not None and not sc.is_alive() and self.api._root is not None:
                break
            if sc is not None and not sc.is_alive() and getattr(sc, "cancelled", False):
                raise RuntimeError("the scan was cancelled")
            time.sleep(0.5)
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            pass
        self._scanned[key] = (time.time(), mtime)
        return self.api._root

    def t_deletable(self, args):
        path = self.folder(args.get("folder"))
        self._scan(path)
        self.call("find_candidates")
        if self._ai() is not None:
            try:
                self.call("ai_review")
            except RuntimeError:
                pass
        picks, by_cat = [], {}
        for cat in list(self.api._cats) + ([self.api._ai_cat] if self.api._ai_cat else []):
            source_cat = None if cat.source == "ai" else cat
            if self.mem.policy("files", cat.name) == "never":
                continue
            for item in cat.items:
                risk = item.get("risk", cat.risk)
                act = sys.modules[type(self.api).__module__].action_for(item, source_cat)
                if risk == cleanup.SAFE and act in ("clean", "recycle"):
                    picks.append((item, cat))
                    by_cat[cat.name] = by_cat.get(cat.name, 0) + item.get("reclaim", item["size"])
        name = os.path.basename(path.rstrip("\\")) or path
        if not picks:
            review = sum(c.total for c in self.api._cats if c.risk != cleanup.SAFE)
            return Reply(f"Nothing in {name} is safe to delete without a look." +
                         (f" {fmt(review)} is worth reviewing - open Clean-up to see it." if review > 50 * MB else ""))
        total = sum(by_cat.values())
        top = ", ".join(f"{k.lower()} {fmt(v)}" for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])[:3])
        paths = [i["path"] for i, _ in picks]

        def run():
            freed = failed = 0
            for p in paths:
                r = self.api.clean_item(p)
                if isinstance(r, dict) and "__error__" not in r:
                    freed += r.get("freed", 0)
                else:
                    failed += 1
            return f"Done. Freed {fmt(freed)}" + (f"; {plural(failed, 'item')} couldn't be removed." if failed else ".")
        q = f"In {name}, {fmt(total)} is safe to delete: {top}. Deleted folders' contents go away, files go to the Recycle Bin. Shall I clean them?"
        return Reply(q, Pending("files", q, run, paths, categories=list(by_cat), review={"view": "cleanup", "path": path}))

    # ---- old documents (learned)
    def t_old_docs(self, args):
        path = self.folder(args.get("folder"))
        self._scan(path)
        self.mem.observe_files(path)
        self.mem.observe_opens()
        client = self._ai()
        mode = "full" if client is not None and getattr(client, "is_local", False) else "names_only"
        res = self.call("classify_run", path, mode)
        now = time.time()
        picks, kept, by_cat = [], set(), {}
        for g in res["groups"]:
            cat = g["key"]
            policy = self.mem.policy("docs", cat)
            if policy in ("never", "ask"):
                word = g["label"].split(" &")[0]
                kept.add(word if word.isupper() else word.lower())
                continue
            limit = self.mem.doc_age_limit(cat)
            for f in g["files"]:
                self.mem.set_file_category(f["path"], cat)
                info = self.mem.file_info(f["path"])
                try:
                    st = os.stat(f["path"])
                except OSError:
                    continue
                last_touch = max(x for x in (info["last_opened"], info["first_seen"], st.st_mtime) if x)
                if now - last_touch >= limit * agent_memory.DAY:
                    picks.append(f)
                    by_cat.setdefault(cat, []).append(f)
        name = os.path.basename(path.rstrip("\\")) or path
        if not picks:
            return Reply(f"I didn't find documents in {name} that you're done with." +
                         (f" I left your {', '.join(sorted(kept))} documents alone." if kept else ""))
        parts = []
        for cat, files in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
            usual = self.mem.policy("docs", cat) == "usual"
            parts.append(f"{plural(len(files), content.CATEGORIES[cat][0].split(' &')[0].lower().rstrip('s'))} not opened for "
                         f"over {self.mem.doc_age_limit(cat)} days{' - you usually delete these' if usual else ''}")
        size = sum(f["size"] for f in picks)
        files = [f["path"] for f in picks]

        def run():
            done = failed = 0
            for p in files:
                try:
                    if quickclean.send_to_recycle_bin(p):
                        done += 1
                        continue
                except Exception:
                    pass
                failed += 1
            return f"Moved {plural(done, 'document')} to the Recycle Bin." + (f" {failed} couldn't be moved." if failed else "")
        keep_note = f" Your {', '.join(sorted(kept))} documents stay." if kept else ""
        q = f"In {name}: {'; '.join(parts)} ({fmt(size)}).{keep_note} Move them to the Recycle Bin?"
        return Reply(q, Pending("docs", q, run, files, categories=list(by_cat), review={"view": "explorer", "path": path}))

    # ---- organising
    def t_organise(self, args):
        path = self.folder(args.get("folder"))
        self._scan(path)
        self.call("analyse_folder", path)
        deep = bool(args.get("deep"))
        if self._ai() is not None:
            self.call("ai_plan", path, deep, "names_only" if not getattr(self._ai(), "is_local", False) else "full")
        else:
            self.call("rule_plan", path, deep, "full")
        prev = self.call("preview_organise", path)
        groups = prev["groups"]
        names = [i["name"] for g in groups for i in g["items"]]
        name = os.path.basename(path.rstrip("\\")) or path
        if not names:
            return Reply(f"{name} already looks organised - I have nothing to move.")
        top = ", ".join(f"{g['target']} {len(g['items'])}" for g in groups[:4])

        def run():
            r = self.call("apply_organise", path, names)
            self.last_undo = (r.get("undo_id"), path, r.get("moved", 0))
            left = len(r.get("left", []))
            return (f"Organised {plural(r.get('moved', 0), 'item')} into {plural(len(r.get('achieved', [])), 'folder')}."
                    + (f" {plural(left, 'file')} stayed - open Organiser to see why." if left else "")
                    + " Say undo if you want it back as it was.")
        q = f"I can sort {plural(len(names), 'item')} in {name} into {plural(len(groups), 'folder')}: {top}. You can undo it. Shall I go ahead?"
        return Reply(q, Pending("organise", q, run, names, review={"view": "organiser", "path": path}))

    def t_undo(self, args):
        if not self.last_undo or not self.last_undo[0]:
            return Reply("There's nothing of mine to undo.")
        undo_id, path, count = self.last_undo

        def run():
            r = self.call("undo_organise", undo_id)
            self.last_undo = None
            return f"Put back {plural(r['restored'], 'item')}."
        q = f"Undo organising {os.path.basename(path.rstrip(chr(92)))} - put {plural(count, 'item')} back where they were?"
        return Reply(q, Pending("undo", q, run, [path]))

    # ---- duplicates
    def t_duplicates(self, args):
        path = self.folder(args.get("folder"))
        self._scan(path)
        r = self.call("find_version_dupes", path)
        appdata = os.path.normcase(os.path.dirname(quickclean.LOCAL)) + "\\"   # apps manage their own files there
        dupes = [d["path"] for g in r["groups"] for d in g["dupes"]
                 if quickclean.is_deletable(d["path"])[0] and not os.path.normcase(d["path"]).startswith(appdata)]
        waste = sum(g["size"] for g in r["groups"] for d in g["dupes"] if d["path"] in dupes)
        name = os.path.basename(path.rstrip("\\")) or path
        if not dupes:
            return Reply(f"No duplicate copies in {name}.")

        def run():
            res = self.call("remove_version_dupes", dupes)
            return f"Moved {plural(res['removed'], 'copy')} to the Recycle Bin, freeing {fmt(res['freed'])}." + \
                (f" {len(res['failed'])} were skipped." if res["failed"] else "")
        q = (f"{name} has {plural(len(dupes), 'extra copy')} of files like name(1), identical to the original, "
             f"using {fmt(waste)}. Move the copies to the Recycle Bin and keep the originals?")
        return Reply(q, Pending("dupes", q, run, dupes, review={"view": "cleanup", "path": path}))

    # ---- performance
    def t_performance(self, args):
        snap = self.call("perf_snapshot")
        live = snap["live"]
        apps = [g for g in snap["groups"] if g["cat"] in ("app", "safe", "review")][:3]
        safe = [g for g in snap["groups"] if g["cat"] == "safe"]
        sus = self.mem.suspicious()
        say = (f"Memory is at {live['mem_pct']}% and the processor at {round(live['cpu'] or 0)}%. "
               f"Biggest: {', '.join(f'{(g['desc'] or g['name'])} {fmt(g['mem'])}' for g in apps)}.")
        if sus:
            say += f" {plural(len(sus), 'program')} look{'s' if len(sus) == 1 else ''} suspicious - ask me about suspicious programs."
        if safe:
            r = self._boost_pending(snap)
            return Reply(f"{say} {r.say}", r.pending)
        return Reply(say + " Nothing unnecessary is running.")

    def _boost_pending(self, snap=None):
        snap = snap or self.call("perf_snapshot")
        safe = [g for g in snap["groups"] if g["cat"] == "safe"]
        keys = [g["key"] for g in safe]
        mem = sum(g["mem"] for g in safe)
        before = snap["live"]["mem_pct"]

        def run():
            closed = 0
            if keys:
                r = self.call("perf_end", keys, False)
                closed = len(r["closed"])
            t = self.call("perf_trim")
            return f"Done. Closed {plural(closed, 'background helper')} and cleaned RAM: memory {before}% to {t['after']['mem_pct']}%."
        what = f"close {plural(len(safe), 'background helper')} using {fmt(mem)} and clean RAM" if safe else "clean RAM"
        q = f"I can {what}. Open apps are left alone. Go ahead?"
        return Reply(q, Pending("boost", q, run, [g["desc"] or g["name"] for g in safe], review={"view": "perf"}))

    def t_boost(self, args):
        return self._boost_pending()

    def t_clean_ram(self, args):
        t = self.call("perf_trim")
        return Reply(f"Cleaned RAM: memory went from {t['before']['mem_pct']}% to {t['after']['mem_pct']}%, about {fmt(t['freed'])} freed.")

    def t_orphans(self, args):
        """Background processes (not Windows, no window) whose parent app has exited - often leftovers of a closed app."""
        snap = self.call("perf_snapshot")
        startup = {os.path.normcase(agent_memory.quickclean_exe(i["command"])) for i in snap.get("startup") or []}
        left = [g for g in snap["groups"] if g["cat"] in ("safe", "review") and g.get("orphans") and not g["title"]
                and os.path.normcase(g["path"]) not in startup]     # startup apps are meant to run on their own
        full = [g for g in left if g["orphans"] == g["count"]]          # every process of it is orphaned
        total = sum(g["count"] for g in snap["groups"])
        if not left:
            return Reply(f"{total} processes are running and none of them is an orphan - every background process "
                         "still belongs to an app or to Windows.")
        names = ", ".join(f"{g['desc'] or g['name']} ({fmt(g['mem'])})" for g in full[:4])
        partial = [g for g in left if g not in full]
        extra = (f" {plural(len(partial), 'other program')} {'has' if len(partial) == 1 else 'have'} some orphaned processes too, "
                 "but also live ones, so I'd leave them." if partial else "")
        if not full:
            return Reply(f"{total} processes are running. No app is fully orphaned.{extra}")
        keys = [g["key"] for g in full]
        mem = sum(g["mem"] for g in full)

        def run():
            r = self.call("perf_end", keys, False)
            failed = len(r["failed"])
            return f"Closed {plural(len(r['closed']), 'leftover program')}, freeing about {fmt(r['freed'])}." + \
                (f" {failed} wouldn't close." if failed else "")
        q = (f"{total} processes are running. {plural(len(full), 'program')} {'is' if len(full) == 1 else 'are'} left over "
             f"from apps that have closed: {names}{f', {fmt(mem)} in all' if len(full) > 1 else ''}.{extra} "
             f"{'None has' if len(full) > 1 else 'It has no'} window, so no work is lost. Close {'them' if len(full) > 1 else 'it'}?")
        return Reply(q, Pending("orphans", q, run, [g["desc"] or g["name"] for g in full], review={"view": "perf"}))

    def t_suspicious(self, args):
        try:
            snap = self.call("perf_snapshot")
            self.mem.sample_processes(snap["groups"], agent_memory.foreground_exe(), agent_memory.internet_pids())
        except RuntimeError:
            pass
        self.mem.check_signatures()
        sus = self.mem.suspicious()
        if not sus:
            return Reply("Nothing running looks suspicious. Every program I've seen is signed or comes from a normal place.")
        first = sus[0]
        names = ", ".join(s["name"] for s in sus[:3])
        exe = first["exe"]

        def run():
            ok, msg = agent_memory.defender_scan(exe)
            if ok:
                self.mem.tag_process(exe, "ok")
            return f"{first['name']}: {msg}"
        q = (f"{plural(len(sus), 'program')} look{'s' if len(sus) == 1 else ''} suspicious: {names}. {first['name']}: "
             f"{'; '.join(first['reasons'][:3])}. That doesn't mean it's harmful. Shall I scan it with Microsoft Defender?")
        return Reply(q, Pending("defender", q, run, [s["exe"] for s in sus], category="process", review={"view": "perf"}))

    def t_startup(self, args):
        snap = self.call("perf_snapshot")
        items = snap.get("startup") or []
        on = [i for i in items if i["enabled"]]
        unused = self.mem.unused_startup(on)
        if not unused:
            learning = self.mem._q("SELECT MIN(first_seen) FROM procs", one=True)[0]
            days = int((time.time() - learning) / agent_memory.DAY) if learning else 0
            extra = (f" I've only been watching for {plural(days, 'day')}; give me a week to see which ones you never use."
                     if days < 7 else " You use all of them.")
            return Reply(f"{plural(len(on), 'app')} start with Windows.{extra}")
        names = [u["name"] for u in unused]
        ids = [u["id"] for u in unused]

        def run():
            done = 0
            for i in ids:
                r = self.api.perf_set_startup(i, False)
                done += isinstance(r, dict) and "__error__" not in r
            return f"Turned off {plural(done, 'startup app')}. They're still installed, and you can switch them back on in Performance."
        detail = "; ".join(f"{u['name']} runs most days but you haven't opened it "
                           f"{'at all' if u['never_used'] else f'for {u['idle_days']} days'}" for u in unused[:3])
        q = f"{detail}. Stop {'them' if len(unused) > 1 else 'it'} starting with Windows?"
        return Reply(q, Pending("startup", q, run, names, review={"view": "perf"}))

    def t_drivers(self, args):
        r = self.call("drivers_check", True)
        ups = [u for u in r["updates"] if not u["downgrade"] and not u["is_firmware"]]
        if not ups:
            return Reply("Your drivers are up to date with Windows Update. Intel, NVIDIA and MSI's own tools may still "
                         "have newer ones - say open drivers to see them.")
        ids = [u["id"] for u in ups]

        def run():
            res = self.call("drivers_install", ids, True)
            good = sum(1 for u in res.get("updates", []) if u.get("ok"))
            return f"Installed {good} of {plural(len(ids), 'driver update')}." + (" Restart Windows to finish." if res.get("reboot") else "")
        q = (f"Windows Update has {plural(len(ups), 'driver update')}: {', '.join(u['title'] for u in ups[:2])}. "
             "Install with a restore point first? Windows will ask for permission.")
        return Reply(q, Pending("drivers", q, run, [u["title"] for u in ups], review={"view": "drivers"}))

    def t_open_screen(self, args):
        screen = str(args.get("screen") or "home").lower()
        self._ui("agent_show", {"view": screen})
        return Reply("Opening it.")

    def t_remember(self, args):
        cat = str(args.get("category") or "").lower()
        cat = DOC_WORDS.get(cat, cat)
        choice = "keep" if str(args.get("choice", "keep")).lower() in ("keep", "never") else "delete"
        if cat not in content.CATEGORIES:
            return Reply("Which kind of documents - bills, tickets, KYC, bank, insurance...?")
        self.mem.set_pref(f"docs.{cat}", choice)
        label = content.CATEGORIES[cat][0].lower()
        return Reply(f"Got it - I'll never suggest deleting {label}." if choice == "keep"
                     else f"Got it - I'll suggest deleting old {label} when you haven't opened them for a while.")

    def t_mark_process(self, args):
        name = str(args.get("name") or "").lower()
        rows = self.mem._q("SELECT exe, name FROM procs")
        hit = next(((e, n) for e, n in rows if name and (name in n.lower() or name in os.path.basename(e))), None)
        if not hit:
            return Reply(f"I haven't seen a program called {name} running.")
        verdict = "ok" if str(args.get("verdict", "ok")).lower() in ("ok", "safe", "fine", "legit") else "suspicious"
        self.mem.tag_process(hit[0], verdict)
        return Reply(f"OK, I'll {'stop flagging' if verdict == 'ok' else 'keep an eye on'} {hit[1]}.")

    def t_learned(self, args):
        rules = self.mem.rules_summary()
        L = self.mem.learned()
        base = f"I've seen {plural(L['counts']['procs'], 'program')} and you've answered {plural(L['counts']['decisions'], 'suggestion')}."
        self._ui("agent_show", {"view": "learned"})
        if not rules:
            return Reply(base + " I haven't learned any preferences yet - they build up as you say yes or no.")
        return Reply(base + " " + "; ".join(rules[:4]) + ".")

    def t_health(self, args):
        live = sysinfo.live()
        usable, sizes = self._junk()
        junk = sum(sizes[t["id"]]["size"] for t in usable)
        du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        loose = {f["name"]: f["loose"] for f in self.api.known_folders() if isinstance(f, dict)}
        drv = self.api._drv_updates
        parts = [f"Memory {live['mem_pct']}%, processor {round(live['cpu'] or 0)}%",
                 f"C drive has {fmt(du.free)} free ({round(du.free / du.total * 100)}%)",
                 f"{fmt(junk)} of junk can be cleared" if junk >= 50 * MB else "hardly any junk",
                 f"Downloads has {plural(loose.get('Downloads', 0), 'loose file')}"]
        if drv is not None:
            n = sum(1 for u in drv["updates"] if not u["downgrade"])
            parts.append(f"{plural(n, 'driver update')} waiting" if n else "drivers up to date")
        days = live["uptime"] // agent_memory.DAY
        if days >= 7:
            parts.append(f"not restarted for {days} days")
        say = ". ".join(p[0].upper() + p[1:] for p in parts) + "."
        if junk >= 200 * MB:
            r = self.t_junk({})
            return Reply(f"{say} Want me to clear the junk?", r.pending)
        return Reply(say)

    # ------------------------------------------------------------ confirming
    def confirm(self, source="click"):
        p = self.pending
        if not p or p.expired():
            self._set_pending(None)
            return Reply("There's nothing waiting for a yes right now.")
        self._set_pending(None)
        for cat in p.categories:
            self.mem.record(p.kind, cat, "yes", len(p.items), p.question)
        if self.job:
            return Reply(f"I'm still busy: {self.job.lower()}. Ask me again when it's done.")
        self.job = "Carrying that out"

        def work():
            try:
                say = p.run()
            except Exception as e:
                say = f"That didn't fully work: {str(e).rstrip('.')}."
            self.job = None
            self.push(say, "report", expect_reply=False)
        threading.Thread(target=work, daemon=True).start()
        return Reply("On it.")

    def decline(self):
        p = self.pending
        self._set_pending(None)
        if p:
            for cat in p.categories:
                self.mem.record(p.kind, cat, "no", len(p.items), p.question)
            if p.kind == "docs" and len(p.categories) == 1 and self.mem.policy("docs", p.categories[0]) == "never":
                return Reply(f"OK, I'll leave them. I won't suggest deleting {content.CATEGORIES[p.categories[0]][0].lower()} again.")
        return Reply("OK, I'll leave everything as it is.")

    def review(self):
        p = self.pending
        if not p:
            return Reply("There's nothing to review right now.")
        for cat in p.categories:
            self.mem.record(p.kind, cat, "review", len(p.items), p.question)
        self._ui("agent_show", {**p.review, "items": p.items[:300], "kind": p.kind})
        self._set_pending(None)
        return Reply("I've opened it in Sekar's System Utilities so you can check and choose.")

    # ------------------------------------------------------------ background monitor
    def start_monitor(self):
        threading.Thread(target=self._monitor, daemon=True, name="agent-monitor").start()

    def stop(self):
        self._stop.set()

    def _due(self, key, every):
        last = self._last_check.get(key, 0)
        if time.time() - last >= every:
            self._last_check[key] = time.time()
            return True
        return False

    def _alert(self, key, headline, pending=None, hint="", every=agent_memory.DAY):
        """Speak an alert once per `every`. With a prepared action it asks the question (so "yes" works), unless you're
        already answering another question - then it just says what to ask for."""
        if not self.mem.alert_due(key, every):
            return False
        if pending is not None and (self.pending is None or self.pending.expired()):
            self._set_pending(pending)
            self.push(f"{headline} {pending.question}", "alert", expect_reply=True)
        else:
            self.push(f"{headline} {hint}".strip(), "alert", expect_reply=False)
        return True

    def _monitor(self):
        self._stop.wait(60)                    # let the app settle first
        while not self._stop.is_set():
            try:
                if self.monitor_on():
                    self._tick()
            except Exception:
                pass
            self._stop.wait(30)

    def _critical(self, key, active, headline, pending=None, hint=""):
        """Critical alert (the Dashboard rings its bell): once per occurrence. It re-arms only when `active` turns
        False (None = no change), and the state is kept in memory.db, so a restart doesn't ring again."""
        row_key = f"crit:{key}"
        fired = self.mem._q("SELECT 1 FROM alerts WHERE key=?", (row_key,), one=True)
        if active is False and fired:
            self.mem._q("DELETE FROM alerts WHERE key=?", (row_key,))
        if not active or fired:
            return False
        self.mem._q("INSERT OR REPLACE INTO alerts VALUES (?,?)", (row_key, time.time()))
        if pending is not None and (self.pending is None or self.pending.expired()):
            self._set_pending(pending)
            self.push(f"{headline} {pending.question}", "alert", expect_reply=True, critical=True)
        else:
            self.push(f"{headline} {hint}".strip(), "alert", expect_reply=False, critical=True)
        return True

    def _critical_checks(self):
        """CPU, memory or GPU above 95% for about a minute (two readings in a row); any drive over 98% full."""
        live = sysinfo.live()                # CPU is the average since the previous tick (~30 s)
        gpus = live.get("gpus") or []          # Windows GPU counters - don't wake a sleeping laptop GPU
        readings = {"cpu": live["cpu"], "memory": live["mem_pct"], "gpu": max((g["pct"] for g in gpus), default=None)}
        for res, value in readings.items():
            if value is None:
                continue
            high = self._high.get(res, 0) + 1 if value > CRIT_PCT else 0
            self._high[res] = high
            active = True if high >= 2 else (False if value < CRIT_PCT - 5 else None)
            if not active:
                self._critical(res, active, "")
                continue
            if res == "memory":
                self._critical(res, True, f"Critical: memory is {value}% full.", self._boost_pending().pending,
                               "Say 'boost my PC' to free some.")
            elif res == "cpu":
                top = max((g for g in perf.snapshot(0.5)["groups"] if g["cat"] != "self"), key=lambda g: g["cpu"], default=None)
                who = f" {top['desc'] or top['name']} is using {round(top['cpu'])}% of it." if top and top["cpu"] >= 10 else ""
                self._critical(res, True, f"Critical: the processor has been above 95% for a minute (now {round(value)}%).{who}",
                               hint="Say 'what's running' to see more.")
            else:
                self._critical(res, True, f"Critical: the graphics card has been above 95% busy for a minute (now {round(value)}%).",
                               hint="A game or video app may be working it hard.")
        if self._due("crit-disk", 300):
            drives = self.api.list_drives()
            for d in drives if isinstance(drives, list) else []:
                if not d.get("total"):
                    continue
                pct = d["used"] / d["total"] * 100
                letter = d["letter"].rstrip(":\\")
                active = True if pct > CRIT_DISK else (False if pct < CRIT_DISK - 1 else None)
                self._critical(f"disk-{letter}", active,
                               f"Critical: drive {letter} is {pct:.1f}% full, only {fmt(d['free'])} left.",
                               self.t_junk({}).pending if letter.upper() == os.environ.get("SystemDrive", "C:")[0] and active else None,
                               "Say 'what can I delete' to free some space.")

    def _tick(self):
        now = time.time()
        self._critical_checks()
        if self._due("fg", 60):
            exe = agent_memory.foreground_exe()
            if exe:
                self.mem.note_foreground(exe)
        boosted = False
        crit_mem = self.mem._q("SELECT 1 FROM alerts WHERE key='crit:memory'", one=True)
        if self._due("mem", 120) and not crit_mem:   # the critical memory alert already covers it
            live = sysinfo.live()
            if live["mem_pct"] >= 85:
                self._mem_high_since = self._mem_high_since or now
                if now - self._mem_high_since >= 600:
                    boosted = self._alert("mem", f"Heads up: memory has been over 85% for ten minutes (now {live['mem_pct']}%).",
                                          self._boost_pending().pending, "Say 'boost my PC' when you want me to free some.",
                                          every=6 * 3600)
            else:
                self._mem_high_since = None
        if self._due("procs", 900):
            snap = perf.snapshot()
            self.api._perf = snap
            self.mem.sample_processes(snap["groups"], agent_memory.foreground_exe(), agent_memory.internet_pids())
            self.mem.check_signatures()
            for s in self.mem.suspicious():         # critical, once per program (until you mark it OK)
                self._critical(f"sus-{s['exe']}", True, f"Critical: a program looks suspicious: {s['name']} - "
                               f"{'; '.join(s['reasons'][:2])}.", hint="Ask me about suspicious programs and I'll scan it with Microsoft Defender.")
            heavy = sum(g["mem"] for g in snap["groups"] if g["cat"] == "safe")
            mem_alert = self.mem._q("SELECT last_ts FROM alerts WHERE key='mem'", one=True)
            recently_offered = boosted or (mem_alert and now - mem_alert[0] < 12 * 3600)
            if heavy >= GB and not recently_offered:
                self._alert("helpers", f"Background helpers are using {fmt(heavy)} of memory.",
                            self._boost_pending(snap).pending, "Say 'boost my PC' to close them.", every=12 * 3600)
        if self._due("disk", 3600):
            du = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
            if du.free / du.total < 0.10:
                self._alert("disk", f"Your C drive is almost full: only {fmt(du.free)} left.",
                            hint="Say 'clean my PC' and I'll find junk to clear.")
        if self._due("files", 6 * 3600):
            for f in self.api.known_folders():
                if isinstance(f, dict) and f["name"] in ("Downloads", "Desktop", "Documents"):
                    self.mem.observe_files(f["path"])
                    if f["name"] != "Documents" and f["loose"] >= 30:
                        self._alert(f"loose-{f['name']}", f"Your {f['name']} folder has {f['loose']} loose files.",
                                    hint=f"Say 'organise my {f['name'].lower()}' and I'll suggest where they go.")
            self.mem.observe_opens()
            usable, sizes = self._junk()
            junk = sum(sizes[t["id"]]["size"] for t in usable)
            if junk >= GB:
                self._alert("junk", f"Over {fmt(junk)} of junk has built up.", self.t_junk({}).pending,
                            "Say 'clean my junk' to review it.")
        if self._due("daily", agent_memory.DAY):
            live = sysinfo.live()
            if live["uptime"] >= 7 * agent_memory.DAY:
                self._alert("restart", f"Your PC hasn't restarted for {live['uptime'] // agent_memory.DAY} days.",
                            hint="A restart clears memory leaks and finishes updates.", every=3 * agent_memory.DAY)
            try:
                upd = self.call("drivers_check", True)
                n = sum(1 for u in upd["updates"] if not u["downgrade"] and not u["is_firmware"])
                if n:
                    self._alert("drivers", f"Windows Update has {plural(n, 'driver update')} for your PC.",
                                hint="Say 'update my drivers' to review them.")
            except RuntimeError:
                pass
            day = time.localtime().tm_wday
            if self.mem.habit("junk") == day:
                usable, sizes = self._junk()
                junk = sum(sizes[t["id"]]["size"] for t in usable)
                if junk >= 200 * MB:
                    self._alert("habit-junk", f"You usually clean up on {time.strftime('%A')}s.", self.t_junk({}).pending,
                                "Say 'clean my junk' to review it.")
