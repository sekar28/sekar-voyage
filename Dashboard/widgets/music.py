"""Find YouTube videos for a spoken request. Order of preference: YouTube Data API (needs a free key, most
reliable), yt-dlp if installed, then reading the public results page."""

import json
import re
import urllib.parse

from . import SourceError, fetch, fetch_json

API = "https://www.googleapis.com/youtube/v3/search"


def _via_api(query, key, n):
    params = urllib.parse.urlencode({"part": "snippet", "q": query, "type": "video", "videoEmbeddable": "true",
                                     "maxResults": n, "key": key})
    data = fetch_json(f"{API}?{params}", what="YouTube Data API")
    return [{"id": it["id"]["videoId"], "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"]}
            for it in data.get("items", []) if it.get("id", {}).get("videoId")]


def _via_ytdlp(query, n):
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    return [{"id": e["id"], "title": e.get("title", ""), "channel": e.get("channel") or e.get("uploader", "")}
            for e in info.get("entries", []) if e.get("id")]


def _via_page(query, n):
    page = fetch("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}),
                 what="YouTube", headers={"Accept-Language": "en"}).decode("utf-8", "replace")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    out, seen = [], set()
    if m:
        def walk(node):
            if isinstance(node, dict):
                v = node.get("videoRenderer")
                if v and v.get("videoId") and v["videoId"] not in seen:
                    seen.add(v["videoId"])
                    runs = lambda k: "".join(r.get("text", "") for r in (v.get(k) or {}).get("runs", []))
                    out.append({"id": v["videoId"], "title": runs("title"), "channel": runs("ownerText")})
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(json.loads(m.group(1)))
    if not out:   # page layout changed: fall back to bare ids
        for vid in re.findall(r'"videoId":"([\w-]{11})"', page):
            if vid not in seen:
                seen.add(vid)
                out.append({"id": vid, "title": query, "channel": ""})
    return out[:n]


def _shorts_last(hits):
    """YouTube Shorts are vertical clips, not songs - keep them only as a last resort."""
    is_short = lambda h: "#short" in h["title"].lower() or "#youtubeshort" in h["title"].lower()
    return [h for h in hits if not is_short(h)] + [h for h in hits if is_short(h)]


def search(query, api_key=None, n=8):
    return _shorts_last(_search(query, api_key, n + 4))[:n]


def _search(query, api_key, n):
    query = query.strip()
    if not query:
        raise SourceError("Say what to play.")
    errors = []
    if api_key:
        try:
            hits = _via_api(query, api_key, n)
            if hits:
                return hits
        except SourceError as e:
            errors.append(str(e))
    try:
        hits = _via_ytdlp(query, n)
        if hits:
            return hits
    except ImportError:
        pass
    except Exception as e:      # yt-dlp raises its own error types
        errors.append(f"yt-dlp: {e}")
    try:
        hits = _via_page(query, n)
        if hits:
            return hits
    except (SourceError, ValueError) as e:
        errors.append(str(e))
    raise SourceError("Couldn't search YouTube" + (f" ({'; '.join(errors)})" if errors else "") + ".")
