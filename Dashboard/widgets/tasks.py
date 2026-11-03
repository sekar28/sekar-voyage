"""Task list with ageing: how long each task has been pending, due dates, complete / delete, and the plain-text
commands accepted over Telegram ("add: ...", "done 2", "delete milk", "list", "snooze 3 2d").
The list itself is kept in settings by app.py; everything here works on that list of dicts."""

import re
import time
import uuid
from datetime import datetime, timedelta

from . import timers

DONE_KEEP_DAYS = 30           # completed tasks are removed after this long
ALERT_DAYS = (1, 3, 7)        # undated tasks nag once at each of these ages, then every 7 days
DEFAULT_REPEAT_HOURS = 12     # overdue tasks nag again after this long, until completed
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HELP = ("Commands:\n"
        "add: buy milk\n"
        "add: pay bill by friday 6 pm\n"
        "list\n"
        "done 2   (or: done milk)\n"
        "delete 2\n"
        "reopen 2\n"
        "snooze 2 3d   (hide alerts for 3 days)\n"
        "The numbers are the ones shown by 'list'.\n\n"
        "/pc how much disk space is free?   (look-ups on your PC, read-only)")


def new(title, due=None, now=None):
    now = now or time.time()
    return {"id": uuid.uuid4().hex[:8], "title": title.strip(), "created": now, "due": due,
            "done_at": None, "alerted_at": 0, "alert_level": 0, "snoozed_until": 0}


def age_text(created, now=None):
    secs = max(0, (now or time.time()) - created)
    if secs < 3600:
        return "just now" if secs < 120 else f"{int(secs // 60)} min"
    if secs < 86400:
        return f"{int(secs // 3600)} h"
    days = int(secs // 86400)
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''}"
    return f"{days // 7} weeks"


def is_overdue(t, now=None):
    return bool(t.get("due")) and not t.get("done_at") and t["due"] < (now or time.time())


def ordered(items, now=None):
    """Pending tasks (overdue first, then oldest first) followed by completed ones (newest first)."""
    now = now or time.time()
    pending = [t for t in items if not t.get("done_at")]
    pending.sort(key=lambda t: (0 if is_overdue(t, now) else 1, t["due"] if is_overdue(t, now) else t["created"]))
    done = sorted((t for t in items if t.get("done_at")), key=lambda t: -t["done_at"])
    return pending + done


def purge(items, now=None):
    """Drop completed tasks older than DONE_KEEP_DAYS; returns the new list."""
    cutoff = (now or time.time()) - DONE_KEEP_DAYS * 86400
    return [t for t in items if not t.get("done_at") or t["done_at"] >= cutoff]


def due_text(due, now=None):
    if not due:
        return ""
    when = datetime.fromtimestamp(due)
    today = datetime.fromtimestamp(now or time.time()).date()
    day = "today" if when.date() == today else "tomorrow" if when.date() == today + timedelta(days=1) \
        else when.strftime("%a %d %b")
    return f"{day} {when.strftime('%I:%M %p').lstrip('0')}"


def added_text(created, now=None):
    """The day a task was added: 'today', 'yesterday', else 'Mon 20 Oct' (with the year when it's an older year)."""
    when = datetime.fromtimestamp(created)
    today = datetime.fromtimestamp(now or time.time()).date()
    if when.date() == today:
        return "today"
    if when.date() == today - timedelta(days=1):
        return "yesterday"
    return when.strftime("%a %d %b" if when.year == today.year else "%a %d %b %Y")


def line(t, n=None, now=None):
    now = now or time.time()
    head = f"{n}. " if n else ""
    if t.get("done_at"):
        return f"{head}✅ {t['title']} (added {added_text(t['created'], now)}, done)"
    bits = [f"pending {age_text(t['created'], now)}, added {added_text(t['created'], now)}"]
    if t.get("due"):
        bits.append(("OVERDUE, was due " if is_overdue(t, now) else "due ") + due_text(t["due"], now))
    return f"{head}{'🔴 ' if is_overdue(t, now) else ''}{t['title']} ({', '.join(bits)})"


def render_list(items, now=None):
    now = now or time.time()
    order = ordered(items, now)
    if not order:
        return "No tasks. Add one with: add: buy milk"
    pending = [t for t in order if not t.get("done_at")]
    out = [f"{len(pending)} pending:" if pending else "Nothing pending."]
    out += [line(t, i + 1, now) for i, t in enumerate(order)]
    return "\n".join(out)


def spoken(items, now=None):
    pending = [t for t in ordered(items, now) if not t.get("done_at")]
    if not pending:
        return "You have no pending tasks."
    over = [t for t in pending if is_overdue(t, now)]
    first = ", ".join(t["title"] for t in pending[:3])
    return f"{len(pending)} pending task{'s' if len(pending) != 1 else ''}" + \
        (f", {len(over)} overdue" if over else "") + f": {first}."


# ---------------------------------------------------------------- dates
def parse_when(text, now=None):
    """'tomorrow', 'friday 6 pm', 'today at 17:30', 'in 3 days', 'in 2 hours', 'at 6 pm' -> epoch seconds or None.
    A day with no time means 6 pm that day."""
    now_dt = datetime.fromtimestamp(now) if now else datetime.now()
    t = text.lower().strip().rstrip(".")
    m = re.match(r"in\s+(\d+)\s*(days?|d|weeks?|w)\b", t)
    if m:
        n = int(m.group(1)) * (7 if m.group(2).startswith("w") else 1)
        return (now_dt + timedelta(days=n)).replace(hour=18, minute=0, second=0, microsecond=0).timestamp()
    if t.startswith("in "):
        secs = timers.parse_duration(t[3:])
        return (now_dt + timedelta(seconds=secs)).timestamp() if secs else None
    day = None
    if "tomorrow" in t:
        day = now_dt.date() + timedelta(days=1)
    elif "today" in t or "tonight" in t:
        day = now_dt.date()
    else:
        for i, name in enumerate(WEEKDAYS):
            if re.search(rf"\b({name}|{name[:3]})\b", t):
                day = now_dt.date() + timedelta(days=(i - now_dt.weekday()) % 7 or 7)
                break
    h, mi = 18, 0
    tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a m|p m)\b", t) or re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b()", t)
    if tm:
        h, mi = int(tm.group(1)), int(tm.group(2) or 0)
        ap = (tm.group(3) or "").replace(" ", "")
        if h > 23 or mi > 59:
            return None
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
    elif day is None:
        return None
    if day is None:                                   # only a time: today if still ahead, else tomorrow
        day = now_dt.date()
        if now_dt.replace(hour=h, minute=mi, second=0, microsecond=0) <= now_dt:
            day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, h, mi).timestamp()


def split_title_due(text, now=None):
    """'pay bill by friday 6 pm' -> ('pay bill', epoch). If the date part isn't understood it stays in the title."""
    m = re.match(r"(.+?)\s+(?:by|due|on|before)\s+(.+)$", text.strip(), re.I)
    if m:
        due = parse_when(m.group(2), now)
        if due:
            return m.group(1).strip(), due
    return text.strip(), None


# ---------------------------------------------------------------- finding a task by number or words
def find(items, ref, now=None):
    """'2' -> the 2nd task in list order; words -> the one task whose title contains them. Returns (task, error)."""
    order = ordered(items, now)
    ref = ref.strip()
    if not ref:
        return None, "Which task? Send 'list' to see the numbers."
    if re.fullmatch(r"\d+", ref):
        n = int(ref)
        if 1 <= n <= len(order):
            return order[n - 1], None
        return None, f"There's no task {n}. Send 'list' to see them."
    hits = [t for t in order if ref.lower() in t["title"].lower()]
    pending = [t for t in hits if not t.get("done_at")]
    hits = pending or hits
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, f"No task matches '{ref}'."
    return None, f"'{ref}' matches {len(hits)} tasks - use its number from 'list'."


# ---------------------------------------------------------------- commands
def handle(text, items, now=None):
    """Run one text command on `items` (changed in place). Returns (reply, changed)."""
    now = now or time.time()
    raw = text.strip()
    if raw.startswith("+"):
        raw = "add " + raw[1:]
    m = re.match(r"^/?(add|new|todo|task|done|complete|finish|finished|delete|del|remove|rm|reopen|undo|snooze|"
                 r"list|ls|tasks|pending|help|start)\b\s*:?\s*(.*)$", raw, re.I | re.S)
    if not m:
        return "I didn't understand that.\n" + HELP, False
    cmd, rest = m.group(1).lower(), m.group(2).strip()
    if cmd in ("list", "ls", "tasks", "pending"):
        return render_list(items, now), False
    if cmd in ("help", "start"):
        return HELP, False
    if cmd in ("add", "new", "todo", "task"):
        if not rest:
            return "What should I add? Example: add: buy milk by friday", False
        title, due = split_title_due(rest, now)
        t = new(title, due, now)
        items.append(t)
        return "Added: " + line(t, now=now), True
    t, err = find(items, rest.split(" ")[0] if cmd == "snooze" else rest, now)
    if err:
        return err, False
    if cmd in ("done", "complete", "finish", "finished"):
        if t.get("done_at"):
            return f"Already done: {t['title']}", False
        t["done_at"] = now
        return f"Done: {t['title']} (was pending {age_text(t['created'], now)})", True
    if cmd in ("delete", "del", "remove", "rm"):
        items.remove(t)
        return f"Deleted: {t['title']}", True
    if cmd in ("reopen", "undo"):
        t["done_at"], t["alerted_at"], t["alert_level"] = None, 0, 0
        return f"Reopened: {t['title']}", True
    if cmd == "snooze":
        sm = re.search(r"(\d+)\s*(h|hr|hours?|d|days?)?\b", rest.split(" ", 1)[1] if " " in rest else "")
        n = int(sm.group(1)) if sm else 1
        unit = 3600 if sm and (sm.group(2) or "d").startswith("h") else 86400
        t["snoozed_until"] = now + n * unit
        return f"Snoozed until {due_text(t['snoozed_until'], now)}: {t['title']}", True
    return HELP, False


# ---------------------------------------------------------------- alerts
def pending_alerts(items, now=None, repeat_hours=DEFAULT_REPEAT_HOURS):
    """Tasks that need a nudge now: [(task, reason)]. Marks them as alerted so each fires once per step.
    Overdue: again every `repeat_hours`. Undated: at 1, 3 and 7 days old, then weekly."""
    now = now or time.time()
    out = []
    for t in items:
        if t.get("done_at") or t.get("snoozed_until", 0) > now:
            continue
        if is_overdue(t, now):
            if now - t.get("alerted_at", 0) >= repeat_hours * 3600:
                out.append((t, "overdue"))
                t["alerted_at"] = now
            continue
        if t.get("due"):
            continue
        days = (now - t["created"]) / 86400
        level = sum(1 for d in ALERT_DAYS if days >= d)
        if days >= ALERT_DAYS[-1]:
            level += int((days - ALERT_DAYS[-1]) // 7)
        if level > t.get("alert_level", 0):
            t["alert_level"], t["alerted_at"] = level, now
            out.append((t, "aging"))
    return out


def alert_text(t, reason, now=None):
    now = now or time.time()
    if reason == "overdue":
        return f"🔴 Overdue: {t['title']} (was due {due_text(t['due'], now)}, pending {age_text(t['created'], now)})\nReply: done {t['title'][:24]}"
    return f"⏳ Still pending after {age_text(t['created'], now)}: {t['title']}\nReply: done {t['title'][:24]}"


def digest_text(items, now=None):
    pending = [t for t in ordered(items, now) if not t.get("done_at")]
    if not pending:
        return "☀️ No pending tasks today."
    return "☀️ Your pending tasks:\n" + "\n".join(line(t, i + 1, now) for i, t in enumerate(pending))
