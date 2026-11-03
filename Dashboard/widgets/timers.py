"""Timers and reminders: parsing spoken durations / times, and the running list (kept in settings by app.py)."""

import re
import time
import uuid
from datetime import datetime, timedelta

WORD_NUMS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
             "forty": 40, "forty five": 45, "fifty": 50, "sixty": 60, "ninety": 90}
UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1, "m": 60, "min": 60, "mins": 60, "minute": 60,
         "minutes": 60, "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}


def _num(tok):
    tok = tok.strip()
    if re.fullmatch(r"\d+(\.\d+)?", tok):
        return float(tok)
    return WORD_NUMS.get(tok)


def parse_duration(text):
    """'10 minutes', '1 hour 30', 'an hour and a half', '90 seconds', 'half an hour', '1h 20m' -> seconds or None."""
    t = text.lower().replace("-", " ")
    t = re.sub(r"\bforty five\b", "45", t)
    if re.search(r"\bhalf an hour\b", t):
        return 1800
    total, found = 0.0, False
    for m in re.finditer(r"(\d+(?:\.\d+)?|an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                         r"fifteen|twenty|thirty|forty|fifty|sixty|ninety)\s*(hours?|hrs?|h|minutes?|mins?|m|"
                         r"seconds?|secs?|s)\b(\s+and\s+a\s+half)?", t):
        n, unit = _num(m.group(1)), UNITS[m.group(2)]
        total += n * unit + (unit / 2 if m.group(3) else 0)
        found = True
        rest = t[m.end():]
        # "1 hour 30" -> 30 minutes after an hour
        trail = re.match(r"\s*(?:and\s*)?(\d+)\s*$", rest)
        if unit == 3600 and trail:
            total += int(trail.group(1)) * 60
    return int(total) if found and total > 0 else None


def parse_time(text, now=None):
    """'at 6', 'at 6 pm', 'at 6:30', 'at 18:45', 'at noon', 'tomorrow at 7 am' -> datetime in the future, or None."""
    now = now or datetime.now()
    t = text.lower().replace(".", "")
    if re.search(r"\bnoon\b", t):
        h, mi, ampm = 12, 0, None
    elif re.search(r"\bmidnight\b", t):
        h, mi, ampm = 0, 0, None
    else:
        m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2})|\s+(\d{2})(?!\s*(?:min|sec|hour)))?\s*(am|pm|a m|p m)?\b", t)
        if not m:
            return None
        h, mi = int(m.group(1)), int(m.group(2) or m.group(3) or 0)
        ampm = (m.group(4) or "").replace(" ", "") or None
    if h > 23 or mi > 59:
        return None
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if "tomorrow" in t:
        target += timedelta(days=1)
    elif target <= now:
        if ampm is None and h < 12 and target + timedelta(hours=12) > now:
            target += timedelta(hours=12)    # "at 6" said at 2 pm means 6 pm
        else:
            target += timedelta(days=1)
    return target


def parse_command(text):
    """A timer / reminder request -> {'action': 'timer'|'reminder', 'at': epoch, 'label': ...} or None."""
    t = text.strip().rstrip(".!?")             # keep the case: labels are read back ("call Amma")
    m = re.match(r"(?:please )?(?:set |start )?(?:a |an )?timer (?:for )?(.+?)(?: (?:called|named|for|to) (.+))?$", t, re.I) or \
        re.match(r"(?:please )?(?:set |start )?(?:a |an )?(.+?) timer(?: (?:called|named|for|to) (.+))?$", t, re.I)
    if m:
        secs = parse_duration(m.group(1))
        if secs:
            return {"action": "timer", "at": time.time() + secs, "label": (m.group(2) or "").strip() or _fmt_dur(secs) + " timer"}
    # "remind me at 6 to X" / "remind me tomorrow at 7 to X" (time first), else "remind me to X at 6 / in 20 minutes"
    m = re.match(r"remind me ((?:tomorrow )?at .+?|in .+?) (?:to |that |about )(.+)$", t, re.I)
    if m:
        when_txt, label = m.group(1), m.group(2)
    else:
        m = re.match(r"remind me (?:to )?(.+?) ((?:tomorrow )?at .+|in .+)$", t, re.I)
        if not m:
            return None
        label, when_txt = m.group(1), m.group(2)
    when_txt = when_txt.lower()
    if when_txt.startswith("in "):
        secs = parse_duration(when_txt[3:])
        return {"action": "reminder", "at": time.time() + secs, "label": label} if secs else None
    dt = parse_time(when_txt)
    return {"action": "reminder", "at": dt.timestamp(), "label": label} if dt else None


def _fmt_dur(secs):
    secs = int(round(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{h} hour{'s' if h != 1 else ''}" if h else "", f"{m} minute{'s' if m != 1 else ''}" if m else "",
             f"{s} second{'s' if s != 1 else ''}" if s and not h else ""]
    return " ".join(p for p in parts if p) or "0 seconds"


def new(kind, at, label):
    return {"id": uuid.uuid4().hex[:8], "kind": kind, "at": float(at), "label": label, "created": time.time()}


def confirm(t):
    if t["kind"] == "timer":
        return f"Timer set for {_fmt_dur(t['at'] - time.time())}."
    when = datetime.fromtimestamp(t["at"])
    day = "" if when.date() == datetime.now().date() else " tomorrow" if when.date() == (datetime.now() + timedelta(days=1)).date() else when.strftime(" on %A")
    return f"OK, I'll remind you{day} at {when.strftime('%I:%M %p').lstrip('0')} to {t['label']}."


def spoken_list(items):
    if not items:
        return "No timers or reminders running."
    now = time.time()
    parts = [f"{t['label']}, {_fmt_dur(t['at'] - now)} left" if t["kind"] == "timer"
             else f"{t['label']} at {datetime.fromtimestamp(t['at']).strftime('%I:%M %p').lstrip('0')}" for t in items]
    return "; ".join(parts) + "."
