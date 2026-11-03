"""Calendar from private ICS links (Google: "Secret address in iCal format"; Outlook: "Publish calendar" -> ICS).
No account sign-in. Repeating events are expanded with recurring-ical-events."""

import time
from datetime import date, datetime, timedelta

from . import SourceError, fetch

CACHE_SECONDS = 15 * 60
DAYS_AHEAD = 7

_cache = {"at": 0, "key": None, "data": None}


def _local(dt):
    """Event start/end as a naive local datetime (all-day dates become midnight)."""
    if isinstance(dt, datetime):
        return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    return datetime(dt.year, dt.month, dt.day)


def parse(ics_bytes, start, end, source=""):
    import icalendar
    import recurring_ical_events
    cal = icalendar.Calendar.from_ical(ics_bytes)
    out = []
    for ev in recurring_ical_events.of(cal).between(start, end):
        s, e = ev.get("DTSTART"), ev.get("DTEND")
        if s is None:
            continue
        all_day = not isinstance(s.dt, datetime)
        st = _local(s.dt)
        en = _local(e.dt) if e is not None else st + (timedelta(days=1) if all_day else timedelta(hours=1))
        out.append({"title": str(ev.get("SUMMARY") or "(no title)"), "location": str(ev.get("LOCATION") or ""),
                    "start": st.isoformat(), "end": en.isoformat(), "all_day": all_day, "source": source})
    return out


def events(links, force=False):
    """[(name, url)] -> events from today 00:00 for DAYS_AHEAD days, sorted. Errors per link are reported."""
    key = tuple(links)
    if not force and _cache["key"] == key and _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    today = datetime.combine(date.today(), datetime.min.time())
    start, end = today, today + timedelta(days=DAYS_AHEAD)
    evs, errors = [], []
    for name, url in links:
        try:
            evs += parse(fetch(url.replace("webcal://", "https://"), what=f"calendar {name}", timeout=20), start, end, name)
        except SourceError as e:
            errors.append(str(e))
        except Exception as e:                # malformed calendar
            errors.append(f"calendar {name}: {e}")
    evs.sort(key=lambda e: (e["start"], not e["all_day"]))
    data = {"events": evs, "errors": errors, "fetched": time.time()}
    _cache.update(at=time.time(), key=key, data=data)
    return data


def _when(e):
    st = datetime.fromisoformat(e["start"])
    return "all day" if e["all_day"] else st.strftime("%I:%M %p").lstrip("0")


def spoken_day(evs, day):
    """day: date. One or two sentences."""
    todays = [e for e in evs if datetime.fromisoformat(e["start"]).date() <= day < datetime.fromisoformat(e["end"]).date()
              or datetime.fromisoformat(e["start"]).date() == day]
    label = "today" if day == date.today() else "tomorrow" if day == date.today() + timedelta(days=1) else day.strftime("%A")
    if not todays:
        return f"Nothing on your calendar {label}."
    items = "; ".join(f"{_when(e)}, {e['title']}" for e in todays[:6])
    more = f" And {len(todays) - 6} more." if len(todays) > 6 else ""
    return f"{len(todays)} event{'s' if len(todays) != 1 else ''} {label}: {items}.{more}"


def next_event(evs):
    now = datetime.now()
    upcoming = [e for e in evs if not e["all_day"] and datetime.fromisoformat(e["start"]) >= now]
    return upcoming[0] if upcoming else None


def spoken_next(evs):
    e = next_event(evs)
    if not e:
        return "No more timed events in the next week."
    st = datetime.fromisoformat(e["start"])
    mins = int((st - datetime.now()).total_seconds() // 60)
    rel = f"in {mins} minutes" if mins < 60 else f"at {_when(e)}" + ("" if st.date() == date.today() else st.strftime(" on %A"))
    return f"Next: {e['title']} {rel}" + (f", at {e['location']}" if e["location"] else "") + "."
