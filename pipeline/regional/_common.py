"""Shared helpers for Firefinder regional-source fetchers.

Python 3.12 standard library only. Every fetcher in pipeline/regional/ imports
this module instead of re-implementing HTTP, caching, or rate limiting.

Caching contract: raw responses are cached under the shared, git-ignored
``/home/hoid/Desktop/firefinder/data/raw/<source>/`` directory (see DESIGN.md
Sec 2). If a cache file already exists, ``fetch()`` reads it and makes no
network call at all -- this is what makes every fetcher resumable: re-running
a script after a partial run, a crash, or a rate-limit backoff only fetches
what is still missing.

Rate limiting: at most one request every 2 seconds, per host, enforced in
this process. Fetchers that need many requests to one host (e.g. a few
hundred detail pages on firelookout.com) will therefore take a while; run
them with run_in_background or nohup rather than blocking on them.
"""

from __future__ import annotations

import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

RAW_ROOT = pathlib.Path("/home/hoid/Desktop/firefinder/data/raw")

UA_BOT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"
# Fallback only when a host outright refuses the bot UA (e.g. a WAF that
# blocks on UA string alone). Document every use of this in the fetcher and
# in the final report -- see andyarthur_ny.py.
UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MIN_INTERVAL_S = 2.0

_last_request_at: dict[str, float] = {}
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class FetchError(RuntimeError):
    pass


def cache_path(source: str, *parts: str) -> pathlib.Path:
    p = RAW_ROOT / source / pathlib.Path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _robots_allows(url: str, ua: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(base)
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None  # no robots.txt, or unreadable -> treat as allow-all
        _robots_cache[base] = rp
    if rp is None:
        return True
    try:
        return rp.can_fetch(ua, url)
    except Exception:
        return True


def _throttle(host: str) -> None:
    now = time.time()
    last = _last_request_at.get(host, 0.0)
    wait = MIN_INTERVAL_S - (now - last)
    if wait > 0:
        time.sleep(wait)


def fetch(
    url: str,
    source: str,
    cache_rel_path: str,
    *,
    use_browser_ua: bool = False,
    timeout: float = 20.0,
    encoding: str | None = None,
) -> bytes:
    """Fetch ``url``, transparently cached at data/raw/<source>/<cache_rel_path>.

    If the cache file exists already, returns it with no network activity
    (this is the resumability contract). Otherwise honours robots.txt, waits
    out the per-host rate limit, fetches, writes the cache file, and returns
    the bytes.
    """
    path = cache_path(source, cache_rel_path)
    if path.exists():
        return path.read_bytes()

    ua = UA_BROWSER if use_browser_ua else UA_BOT
    if not _robots_allows(url, ua):
        raise FetchError(f"robots.txt disallows fetching {url}")

    host = urllib.parse.urlparse(url).netloc
    _throttle(host)
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        _last_request_at[host] = time.time()
        raise FetchError(f"HTTP {e.code} fetching {url}") from e
    except urllib.error.URLError as e:
        _last_request_at[host] = time.time()
        raise FetchError(f"error fetching {url}: {e}") from e
    _last_request_at[host] = time.time()

    path.write_bytes(data)
    return data


def fetch_text(
    url: str,
    source: str,
    cache_rel_path: str,
    *,
    use_browser_ua: bool = False,
    timeout: float = 20.0,
    encoding: str = "latin-1",
) -> str:
    """Like fetch(), decoded to text. firelookout.com and friends are old
    sites with no charset header worth trusting; latin-1 never raises and is
    byte-preserving for the ASCII-heavy markup these sites use."""
    return fetch(
        url, source, cache_rel_path, use_browser_ua=use_browser_ua, timeout=timeout
    ).decode(encoding, errors="replace")


FEET_TO_M = 0.3048


def ft_to_m(feet: float | int | None) -> float | None:
    if feet is None:
        return None
    return round(feet * FEET_TO_M, 2)


def slugify(name: str) -> str:
    out = []
    prev_dash = False
    for ch in name.lower().strip():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    s = "".join(out).strip("-")
    return s or "unnamed"


def write_source_json(
    out_path: pathlib.Path,
    *,
    source: str,
    title: str,
    url: str,
    retrieved: str,
    license_: str,
    records: list[dict],
) -> None:
    import json

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source,
        "title": title,
        "url": url,
        "retrieved": retrieved,
        "license": license_,
        "records": records,
    }
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")
