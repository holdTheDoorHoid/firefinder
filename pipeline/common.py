"""Shared fetch/cache/rate-limit helpers for the data-registers pipeline.

Python 3.12 standard library only. See DESIGN.md section 2 for crawl etiquette:
at most one request every 2s per host, an honest User-Agent, honour robots.txt,
cache every raw response under RAW_ROOT/<source>/ (by default the shared
/home/hoid/Desktop/firefinder/data/raw/) so a re-run never refetches.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

USER_AGENT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"
FALLBACK_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Shared raw-cache root. Lives outside the worktree so every agent's crawl hits the same cache
# instead of re-downloading. That path only exists on the shared lab machine, so a CI runner (which
# has no /home/hoid and may not be able to create it) sets FIREFINDER_RAW_ROOT instead -- the same
# override pipeline/_common.py honours (see .github/workflows/refresh-rentals.yml).
RAW_ROOT = Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw")

# Hosts that are operated by the same party and must be rate-limited together
# (DESIGN.md: "treat nhlr.org and firetower.org as ONE host").
HOST_GROUPS = {
    "nhlr.org": "nhlr-firetower",
    "www.nhlr.org": "nhlr-firetower",
    "firetower.org": "nhlr-firetower",
    "www.firetower.org": "nhlr-firetower",
}

MIN_INTERVAL = 2.0  # seconds, per host group


def host_group(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return HOST_GROUPS.get(host, host)


class RateLimiter:
    """Enforces a minimum interval between requests to the same host group."""

    def __init__(self, min_interval: float = MIN_INTERVAL):
        self.min_interval = min_interval
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        grp = host_group(url)
        last = self._last.get(grp)
        if last is not None:
            elapsed = time.monotonic() - last
            remaining = self.min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last[grp] = time.monotonic()


class RobotsCache:
    """Caches robots.txt parsers per host; treats a missing robots.txt as allow-all."""

    def __init__(self, rate_limiter: RateLimiter, user_agent: str = USER_AGENT):
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._rl = rate_limiter
        self._ua = user_agent

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._parsers.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = base + "/robots.txt"
            self._rl.wait(robots_url)
            try:
                req = urllib.request.Request(
                    robots_url, headers={"User-Agent": self._ua}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                rp.parse(raw.splitlines())
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    rp.parse([])  # no robots.txt -> allow all
                else:
                    rp.parse([])
            except Exception:
                rp.parse([])  # unreachable robots.txt -> don't block the crawl
            self._parsers[base] = rp
        return rp.can_fetch(self._ua, url)


def _encode_url(url: str) -> str:
    """Percent-encode non-ASCII characters in the path (e.g. accented letters in a
    slug) so urllib can send the request line; urlopen does not do this itself."""
    parts = urlsplit(url)
    path = quote(parts.path, safe="/%")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _cache_path(source: str, url: str) -> Path:
    parts = urlsplit(url)
    path = parts.path
    if not path or path == "/":
        path = "/index.html"
    elif path.endswith("/"):
        path = path + "index.html"
    elif "." not in path.rsplit("/", 1)[-1]:
        path = path + "/index.html"
    path = path.lstrip("/")
    if parts.query:
        # sanitize query into the filename rather than hashing, these URLs are rare
        safe_q = re.sub(r"[^A-Za-z0-9_=-]", "_", parts.query)[:100]
        stem, _, ext = path.rpartition(".")
        if stem:
            path = f"{stem}__{safe_q}.{ext}"
        else:
            path = f"{path}__{safe_q}"
    return RAW_ROOT / source / parts.netloc / path


def cached_body(source: str, url: str) -> str | None:
    """Returns the cached body text if present (regardless of original status), else None."""
    p = _cache_path(source, url)
    meta_p = p.with_suffix(p.suffix + ".meta.json")
    if meta_p.exists():
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
        return ""  # cached as a non-2xx response with no useful body
    return None


def cached_meta(source: str, url: str) -> dict | None:
    p = _cache_path(source, url)
    meta_p = p.with_suffix(p.suffix + ".meta.json")
    if meta_p.exists():
        return json.loads(meta_p.read_text(encoding="utf-8"))
    return None


def fetch(
    source: str,
    url: str,
    rate_limiter: RateLimiter,
    robots: RobotsCache | None = None,
    user_agent: str = USER_AGENT,
    force: bool = False,
    log=None,
) -> tuple[int, str, bool]:
    """Fetch `url`, using and populating the shared raw cache.

    Returns (status_code, body_text, was_cached). A cached entry (status != 2xx included)
    is returned without making a network request unless `force` is True.
    """
    p = _cache_path(source, url)
    meta_p = p.with_suffix(p.suffix + ".meta.json")

    if not force and meta_p.exists():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        body = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        return meta.get("status", 0), body, True

    if robots is not None and not robots.allowed(url):
        if log:
            log(f"BLOCKED by robots.txt: {url}")
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        meta_p.write_text(
            json.dumps({"url": url, "status": -1, "error": "robots_disallowed"}),
            encoding="utf-8",
        )
        return -1, "", False

    rate_limiter.wait(url)
    ua = user_agent
    status = 0
    body = ""
    err = None
    for attempt_ua in (ua, FALLBACK_USER_AGENT):
        try:
            req = urllib.request.Request(_encode_url(url), headers={"User-Agent": attempt_ua})
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                raw = resp.read()
            try:
                body = raw.decode("utf-8")
            except UnicodeDecodeError:
                body = raw.decode("iso-8859-1", errors="replace")
            err = None
            break
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            err = None
            if status in (403, 406) and attempt_ua is ua:
                if log:
                    log(f"UA rejected (status {status}), retrying with browser UA: {url}")
                rate_limiter.wait(url)
                continue
            break
        except Exception as e:
            err = e
            status = 0
            body = ""
            break

    p.parent.mkdir(parents=True, exist_ok=True)
    if err is not None:
        if log:
            log(f"FETCH ERROR {url}: {err!r}")
        return 0, "", False

    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(p)
    meta_p.write_text(
        json.dumps({"url": url, "status": status, "fetched": time.time()}),
        encoding="utf-8",
    )
    if log:
        log(f"FETCHED {status} {url}")
    return status, body, False


def write_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI",
    "Wyoming": "WY",
}


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"&amp;", "and", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
