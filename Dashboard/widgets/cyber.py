"""Latest cyber-attack news (security news RSS feeds) and CISA's Known Exploited Vulnerabilities catalog."""

import email.utils
import html
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import SourceError, fetch, fetch_json

FEEDS = [
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("SecurityWeek", "https://www.securityweek.com/feed/"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("The Record", "https://therecord.media/feed/"),
]
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CACHE_SECONDS = 15 * 60
PER_FEED = 15
ATOM = "{http://www.w3.org/2005/Atom}"

_cache = {"at": 0, "data": None}


def _text(el, *tags):
    for tag in tags:
        found = el.find(tag)
        if found is not None:
            if found.text and found.text.strip():
                return found.text.strip()
            if found.get("href"):
                return found.get("href")
    return ""


def _when(raw):
    if not raw:
        return 0
    try:
        return email.utils.parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _plain(raw, limit=280):
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def read_feed(source, url):
    root = ET.fromstring(fetch(url, what=source))
    entries = root.findall("./channel/item") or root.findall(f"{ATOM}entry")
    out = []
    for e in entries[:PER_FEED]:
        title = _plain(_text(e, "title", f"{ATOM}title"), 200)
        if not title:
            continue
        out.append({"source": source, "title": title,
                    "link": _text(e, "link", f"{ATOM}link"),
                    "summary": _plain(_text(e, "description", f"{ATOM}summary", f"{ATOM}content")),
                    "time": _when(_text(e, "pubDate", f"{ATOM}updated", f"{ATOM}published"))})
    return out


def read_kev(limit=8):
    data = fetch_json(KEV_URL, what="CISA KEV", timeout=20)
    vulns = sorted(data.get("vulnerabilities", []), key=lambda v: v.get("dateAdded", ""), reverse=True)
    return [{"cve": v.get("cveID"), "vendor": v.get("vendorProject"), "product": v.get("product"),
             "name": v.get("vulnerabilityName"), "added": v.get("dateAdded"),
             "ransomware": v.get("knownRansomwareCampaignUse") == "Known",
             "link": f"https://nvd.nist.gov/vuln/detail/{v.get('cveID')}"} for v in vulns[:limit]]


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def latest(force=False):
    if not force and _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    errors = []

    def safe(fn, *args):
        try:
            return fn(*args)
        except (SourceError, ET.ParseError) as e:
            errors.append(str(e))
            return []

    with ThreadPoolExecutor(len(FEEDS) + 1) as pool:
        feeds = [pool.submit(safe, read_feed, name, url) for name, url in FEEDS]
        kev = pool.submit(safe, read_kev)
        news = [it for f in feeds for it in f.result()]
    news = _dedupe(sorted(news, key=lambda it: -it["time"]))[:60]
    data = {"news": news, "kev": kev.result(), "errors": errors, "fetched": time.time()}
    if news or not _cache["data"]:
        _cache.update(at=time.time(), data=data)
    return data if news or not _cache["data"] else {**_cache["data"], "errors": errors}


def article_text(url, limit=8000):
    """The readable paragraphs of a news article ('' if the page can't be read)."""
    page = fetch(url, what="the article", timeout=15).decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style|nav|footer|aside|header|form|noscript|svg|figure)\b.*?</\1>", " ", page)
    def paragraphs(html_part):
        paras = [_plain(p, 2000) for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", html_part)]
        return [p for p in paras if len(p) > 40 and not re.search(r"(?i)subscribe|newsletter|cookie|sign up|follow us", p)]
    m = re.search(r"(?is)<article\b.*?</article>", page)
    paras = paragraphs(m.group(0)) if m else []
    if sum(map(len, paras)) < 400:           # no <article>, or it only wraps a teaser: use the whole page
        paras = paragraphs(page)
    return "\n".join(paras)[:limit]


def headlines_for_ai(data, n=25):
    lines = [f"- [{it['source']}] {it['title']}: {it['summary'][:160]}" for it in data["news"][:n]]
    lines += [f"- CISA added {k['cve']} ({k['vendor']} {k['product']}) to known-exploited list on {k['added']}"
              + (" - used in ransomware" if k["ransomware"] else "") for k in data["kev"][:5]]
    return "\n".join(lines)
