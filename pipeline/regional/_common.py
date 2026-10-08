"""Shared helpers for Firefinder regional-source fetchers.

Python 3.12 standard library only. Every fetcher in pipeline/regional/ imports
this module instead of re-implementing HTTP, caching, or rate limiting.

Caching contract: raw responses are cached under the shared, git-ignored
``/home/hoid/Desktop/firefinder/data/raw/<source>/`` directory (or
``$FIREFINDER_RAW_ROOT/<source>/``; see DESIGN.md Sec 2). If a cache file
already exists, ``fetch()`` reads it and makes no network call at all -- this
is what makes every fetcher resumable: re-running a script after a partial
run, a crash, or a rate-limit backoff only fetches what is still missing.

Rate limiting: at most one request every 2 seconds, per host, enforced in
this process. Fetchers that need many requests to one host (e.g. a few
hundred detail pages on firelookout.com) will therefore take a while; run
them with run_in_background or nohup rather than blocking on them.
"""

from __future__ import annotations

import http.client
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

# The shared crawl cache. FIREFINDER_RAW_ROOT overrides the lab machine's path (the same variable
# pipeline/common.py and pipeline/_common.py read), so a CI runner -- which has no /home/hoid --
# can re-read a regional page; see .github/workflows/refresh-rentals.yml.
RAW_ROOT = pathlib.Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw")

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
# Crawl-delay a host's robots.txt asks of us (seconds), by netloc; longer than MIN_INTERVAL_S only.
_crawl_delay: dict[str, float] = {}


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
            # Not rp.read(): it fetches robots.txt with urllib's default,
            # un-headered opener, and some hosts (e.g. Wikipedia, which
            # requires a descriptive User-Agent on every request including
            # this one) answer that with 403. robotparser treats a 401/403
            # fetching robots.txt as "disallow everything", which would then
            # wrongly block a host that is actually fine with our real,
            # identified UA -- so fetch robots.txt ourselves with the same
            # UA we use for every other request, and feed it to the parser.
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=15) as r:
                text = r.read().decode("utf-8", errors="replace")
            rp.parse(text.splitlines())
        except Exception:
            rp = None  # no robots.txt, or unreadable even with our own UA -> treat as allow-all
        _robots_cache[base] = rp
        if rp is not None:
            try:
                delay = rp.crawl_delay(ua)
                if delay and delay > MIN_INTERVAL_S:
                    _crawl_delay[parsed.netloc] = float(delay)
            except Exception:
                pass
    if rp is None:
        return True
    try:
        return rp.can_fetch(ua, url)
    except Exception:
        return True


def _throttle(host: str) -> None:
    now = time.time()
    last = _last_request_at.get(host, 0.0)
    wait = _crawl_delay.get(host, MIN_INTERVAL_S) - (now - last)
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
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        # (http.client.IncompleteRead, a server cutting a response short, is an HTTPException, not an
        # OSError: cherylhill.net did it on 2026-10-08.)
        # A bare TimeoutError/OSError (a slow or flaky host closing the
        # connection mid-read) isn't always wrapped as URLError by urlopen --
        # catch it here too, so one flaky request can't crash an otherwise
        # resumable, hours-long fetcher run. See weebly_lookouts.py's eastern
        # run, 2026-10-04.
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
    header_extra: dict | None = None,
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
    if header_extra:
        # extra top-level keys (e.g. the association-projects family marker), after the
        # standard ones; never overrides them
        for k, v in header_extra.items():
            payload.setdefault(k, v)
        payload["records"] = payload.pop("records")  # records stay last
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")


# ---------------------------------------------------------------------------------------------
# Register pages -> register numbers
# ---------------------------------------------------------------------------------------------

_REGISTER_URLS: dict[str, dict] | None = None


def register_url_key(url: str) -> str:
    """nhlr.org / firetower.org page URL, normalised for lookup: no scheme, no www., lower case,
    no trailing slash ("http://nhlr.org/lookouts/us/or/quail-prairie-lookout/" ->
    "nhlr.org/lookouts/us/or/quail-prairie-lookout")."""
    p = urllib.parse.urlparse(url.strip())
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/").lower())


def register_by_url(sources_dir: pathlib.Path | None = None) -> dict[str, dict]:
    """The committed NHLR and FFLOS extracts as {register_url_key(page url): {"register": {...},
    "name": "Quail Prairie Lookout"}}, so a fetcher that finds a link to a register page on some
    site can name the register number instead of guessing the lookout by name. The register is
    {"register": "NHLR", "number": "US 467", "state_number": "OR 64"}. The name is there so the
    caller can check the link really is about the lookout it thinks (hobby sites' "more
    information" links are often a previous post's, copied over). Empty when the extracts are
    missing."""
    global _REGISTER_URLS
    if _REGISTER_URLS is not None and sources_dir is None:
        return _REGISTER_URLS
    import json

    base = sources_dir or pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "sources"
    out: dict[str, dict] = {}
    for fname in ("nhlr.json", "fflos.json"):
        path = base / fname
        if not path.exists():
            continue
        for rec in json.loads(path.read_text(encoding="utf-8")).get("records", []):
            if rec.get("url") and rec.get("registers"):
                out.setdefault(register_url_key(rec["url"]),
                               {"register": dict(rec["registers"][0]), "name": rec.get("name")})
    if sources_dir is None:
        _REGISTER_URLS = out
    return out


_NAME_NOISE = re.compile(r"\b(?:lookout|lookouts|fire|tower|site|station|cabin|the|mount|mountain|mtn|mt|peak|butte|"
                         r"hill|point|ridge|rock|ranger|guard|national|forest)\b|[^a-z0-9 ]")


def names_agree(a: str | None, b: str | None) -> bool:
    """Loose check that two lookout names are about the same place: their cores (lookout / mountain /
    butte words and punctuation removed) are equal, one holds the other, or are a letter or two apart.
    For vetting a link a page gives, not for matching (the merge does that, properly)."""
    import difflib

    def core(x: str | None) -> str:
        x = re.sub(r"\([^)]*\)", " ", x or "").split(" - ")[0].lower()
        return re.sub(r"\s+", " ", _NAME_NOISE.sub(" ", x)).strip().replace(" ", "")

    ca, cb = core(a), core(b)
    if not ca or not cb:
        return False
    return ca == cb or ca in cb or cb in ca or difflib.SequenceMatcher(None, ca, cb).ratio() >= 0.8
