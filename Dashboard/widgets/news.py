"""General news (India + world) from RSS. Uses the same feed reader as the cyber widget."""

import time
from concurrent.futures import ThreadPoolExecutor

from . import SourceError
from .cyber import _dedupe, read_feed

DEFAULT_FEEDS = [
    ["The Hindu", "https://www.thehindu.com/news/national/feeder/default.rss"],
    ["Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"],
    ["NDTV", "https://feeds.feedburner.com/ndtvnews-top-stories"],
    ["BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"],
    ["Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"],
]
CACHE_SECONDS = 15 * 60

_cache = {"at": 0, "key": None, "data": None}


def latest(feeds=None, force=False):
    feeds = [tuple(f) for f in (feeds or DEFAULT_FEEDS)]
    if not force and _cache["key"] == feeds and _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    errors = []

    def one(f):
        try:
            return read_feed(*f)
        except Exception as e:                # SourceError, bad XML
            errors.append(f"{f[0]}: {e}")
            return []

    with ThreadPoolExecutor(len(feeds) or 1) as pool:
        items = [it for got in pool.map(one, feeds) for it in got]
    # Interleave sources (newest of each, then the next of each...) so one busy feed doesn't fill the list
    by_source = {}
    for it in _dedupe(sorted(items, key=lambda it: -it["time"])):
        by_source.setdefault(it["source"], []).append(it)
    items = [lst[i] for i in range(max(map(len, by_source.values()), default=0)) for lst in by_source.values() if i < len(lst)][:60]
    data = {"news": items, "errors": errors, "fetched": time.time()}
    if items or not _cache["data"]:
        _cache.update(at=time.time(), key=feeds, data=data)
        return data
    return {**_cache["data"], "errors": errors}


def spoken(data, n=4):
    top = data["news"][:n]
    if not top:
        raise SourceError("I couldn't load the news.")
    return "Top headlines. " + ". ".join(f"{it['source']}: {it['title']}" for it in top) + "."
