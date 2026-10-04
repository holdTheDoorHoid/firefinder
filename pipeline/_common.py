"""Shared helpers for Firefinder's source fetchers.

Python 3.12, standard library only (per DESIGN.md §6 -- the pipeline must run
unattended in GitHub Actions with no installs).

Conventions enforced here so every fetcher behaves the same way:
  - one honest User-Agent, used for every outbound request
  - raw responses are cached under data/raw/<source>/ (git-ignored, shared
    across worktrees) so a re-run never re-fetches unchanged data
  - polite crawling: callers get a RateLimiter to self-throttle
  - source-record JSON (DESIGN §3.2) is written with a stable sort so diffs
    are meaningful and CI output is deterministic given the same input
"""
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import date, timezone, datetime

USER_AGENT = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"

# Shared raw-cache root. Lives outside the worktree (per task instructions) so every agent's
# pipeline hits the same cache instead of re-downloading. That path only exists on the shared
# lab machine, so a CI runner (which has no /home/hoid and may not be able to create it) sets
# FIREFINDER_RAW_ROOT instead -- see .github/workflows/refresh-rentals.yml.
RAW_ROOT = Path(os.environ.get("FIREFINDER_RAW_ROOT") or "/home/hoid/Desktop/firefinder/data/raw")


def today() -> str:
    return date.today().isoformat()


def raw_dir(source: str) -> Path:
    d = RAW_ROOT / source
    d.mkdir(parents=True, exist_ok=True)
    return d


class RateLimiter:
    """Sleeps as needed so calls are spaced >= min_interval_s apart."""

    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        remaining = self.min_interval_s - (now - self._last)
        if remaining > 0:
            time.sleep(remaining)
        self._last = time.monotonic()


def http_get(url: str, *, data: bytes | None = None, headers: dict | None = None,
             timeout: float = 60.0) -> bytes:
    """A GET (or POST, if data is given) with our honest UA, no retries hidden."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_cached(url: str, cache_path: Path, *, data: bytes | None = None,
                  headers: dict | None = None, timeout: float = 60.0,
                  force: bool = False) -> Path:
    """Downloads url to cache_path unless cache_path already exists."""
    if cache_path.exists() and not force:
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    body = http_get(url, data=data, headers=headers, timeout=timeout)
    tmp = cache_path.with_suffix(cache_path.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(cache_path)
    return cache_path


# ---------------------------------------------------------------------------
# HTML -> plain text (RIDB and some regional sources hand us HTML fragments)
# ---------------------------------------------------------------------------

_BLOCK_TAGS = re.compile(
    r"</?(?:p|h[1-6]|div|li|ul|ol|br|tr|table)[^>]*>", re.IGNORECASE
)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\f\v]+")
_BLANKLINES = re.compile(r"\n{3,}")


def html_to_text(fragment: str | None) -> str | None:
    """Strips HTML tags to plain text. Block-level tags become newlines."""
    if not fragment:
        return None
    s = _BLOCK_TAGS.sub("\n", fragment)
    s = _ANY_TAG.sub("", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _BLANKLINES.sub("\n\n", s).strip()
    return s or None


def flatten_text(fragment: str | None) -> str:
    """Like html_to_text but collapsed to one line, for sentence scanning."""
    t = html_to_text(fragment) or ""
    return _WS.sub(" ", t.replace("\n", " ")).strip()


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def ft_to_m(feet: float) -> float:
    return round(feet * 0.3048, 1)


# ---------------------------------------------------------------------------
# US state point-in-polygon, for sources that don't give us a state code
# directly (OSM mostly). Backed by the Census TIGERweb state boundaries,
# cached once as plain GeoJSON (public domain, US Census Bureau).
# ---------------------------------------------------------------------------

CENSUS_STATES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "State_County/MapServer/0/query?where=1%3D1&outFields=STUSAB,STATE,NAME"
    "&outSR=4326&f=geojson&geometryPrecision=3"
)


class StateLookup:
    """Point-in-polygon state lookup over the Census cartographic boundary file."""

    def __init__(self, geojson_path: Path):
        data = json.loads(geojson_path.read_text())
        # Each entry: (STUSAB, [polygon, ...]) where polygon is [ring, ...]
        # and ring is [[lon, lat], ...]. Also keep a bbox per feature so we
        # can skip the expensive ray-cast for most states quickly.
        self.features = []
        for feat in data["features"]:
            props = feat["properties"]
            stusab = props.get("STUSAB")
            geom = feat["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            minx = miny = float("inf")
            maxx = maxy = float("-inf")
            for poly in polys:
                for ring in poly:
                    for lon, lat in ring:
                        minx = min(minx, lon); maxx = max(maxx, lon)
                        miny = min(miny, lat); maxy = max(maxy, lat)
            self.features.append((stusab, polys, (minx, miny, maxx, maxy)))

    @staticmethod
    def _point_in_rings(lon: float, lat: float, polys) -> bool:
        """Even-odd rule across every ring of every polygon (handles holes)."""
        inside = False
        for poly in polys:
            for ring in poly:
                n = len(ring)
                for i in range(n):
                    x1, y1 = ring[i]
                    x2, y2 = ring[(i + 1) % n]
                    if (y1 > lat) != (y2 > lat):
                        x_intersect = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                        if lon < x_intersect:
                            inside = not inside
        return inside

    def state_for(self, lon: float, lat: float) -> str | None:
        for stusab, polys, (minx, miny, maxx, maxy) in self.features:
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                continue
            if self._point_in_rings(lon, lat, polys):
                return stusab
        return None


STATE_NAME_TO_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR", "guam": "GU", "american samoa": "AS",
    "virgin islands": "VI", "northern mariana islands": "MP",
}


def normalize_state(value: str | None) -> str | None:
    """Coerces a state code or full name to a 2-letter USPS code.

    RIDB's address table sometimes spells states out in full instead of
    using the code (e.g. "Wyoming" instead of "WY"); this cleans that up
    without ever guessing a state that wasn't actually given.
    """
    if not value:
        return None
    value = value.strip()
    if len(value) == 2:
        return value.upper()
    return STATE_NAME_TO_ABBR.get(value.lower())


def get_state_lookup() -> StateLookup:
    path = raw_dir("census") / "states.geojson"
    if not path.exists():
        fetch_cached(CENSUS_STATES_URL, path)
    return StateLookup(path)


# ---------------------------------------------------------------------------
# Writing source-record JSON (DESIGN §3.2)
# ---------------------------------------------------------------------------

def write_source_json(path: Path, *, source: str, title: str, url: str,
                       license_text: str, records: list[dict]) -> None:
    records_sorted = sorted(records, key=lambda r: r["key"])
    payload = {
        "source": source,
        "title": title,
        "url": url,
        "retrieved": today(),
        "license": license_text,
        "records": records_sorted,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=False, ensure_ascii=False)
        f.write("\n")
