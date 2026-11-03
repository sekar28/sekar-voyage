"""Data sources behind the dashboard tiles. Each module only fetches and shapes data - no UI, no AI."""

import json
import urllib.error
import urllib.request

# Some news sites and Yahoo refuse the default Python user agent.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class SourceError(Exception):
    pass


def fetch(url, timeout=12, headers=None, what=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise SourceError(f"{what or url} returned HTTP {e.code}") from e
    except OSError as e:
        raise SourceError(f"Cannot reach {what or url} - offline?") from e


def fetch_json(url, **kwargs):
    try:
        return json.loads(fetch(url, **kwargs).decode("utf-8"))
    except ValueError as e:
        raise SourceError(f"{kwargs.get('what') or url} sent something that wasn't JSON") from e
