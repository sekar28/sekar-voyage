"""Stock and index quotes from Yahoo Finance's public chart endpoint (no key needed)."""

import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from . import SourceError, fetch_json

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval={interval}&includePrePost=false"
RANGES = {"1d": "5m", "5d": "30m", "1mo": "1d", "6mo": "1d", "1y": "1wk", "5y": "1mo"}
CACHE_SECONDS = 60
NAMES = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones", "^NSEI": "Nifty 50", "^BSESN": "Sensex",
         "^FTSE": "FTSE 100", "^N225": "Nikkei 225", "BTC-USD": "Bitcoin"}

_cache = {}


def quote(symbol, rng="1d"):
    symbol = symbol.strip().upper()
    key = (symbol, rng)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    url = CHART.format(symbol=urllib.parse.quote(symbol), range=rng, interval=RANGES.get(rng, "1d"))
    data = fetch_json(url, what=f"Yahoo Finance ({symbol})")
    result = (data.get("chart") or {}).get("result")
    if not result:
        err = ((data.get("chart") or {}).get("error") or {}).get("description")
        raise SourceError(err or f"No data for {symbol}")
    r = result[0]
    meta = r.get("meta", {})
    closes = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    stamps = r.get("timestamp") or []
    points = [[t, c] for t, c in zip(stamps, closes) if c is not None]
    price = meta.get("regularMarketPrice") or (points[-1][1] if points else None)
    # For one day the reference is yesterday's close; for longer ranges, the first point of the range.
    base = meta.get("chartPreviousClose") if rng == "1d" else (points[0][1] if points else None)
    base = base or meta.get("previousClose")
    change = (price - base) if price is not None and base else None
    out = {"symbol": symbol, "name": NAMES.get(symbol) or meta.get("shortName") or meta.get("longName") or symbol,
           "price": price, "change": change, "pct": (change / base * 100) if change is not None else None,
           "currency": meta.get("currency", ""), "state": meta.get("marketState", ""),
           "range": rng, "points": points}
    _cache[key] = (time.time(), out)
    return out


def watchlist(symbols, rng="1d"):
    def one(sym):
        try:
            return quote(sym, rng)
        except SourceError as e:
            return {"symbol": sym.upper(), "name": NAMES.get(sym.upper(), sym.upper()), "error": str(e), "points": []}
    with ThreadPoolExecutor(min(8, max(1, len(symbols)))) as pool:
        return list(pool.map(one, symbols))


def describe(q):
    """One spoken sentence for a quote."""
    if q.get("error") or q.get("price") is None:
        return f"I couldn't get a price for {q['name']}."
    if q["pct"] is None:
        return f"{q['name']} is at {q['price']:,.2f}."
    word = "up" if q["pct"] >= 0 else "down"
    return f"{q['name']} is at {q['price']:,.2f}, {word} {abs(q['pct']):.1f} percent."
