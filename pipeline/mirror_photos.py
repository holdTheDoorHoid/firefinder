#!/usr/bin/env python3
"""Mirror the photos the visible towers point at, process them, and write the manifest the
site and pipeline/merge.py read (DESIGN.md "Photos").

Dev-time tool, not part of CI: this is the **one** script in the pipeline allowed to use a
third-party library (Pillow, for image decoding/resizing/WebP encoding). See DESIGN.md.

What it does
------------
1. Collects every `{"file": null, "url": "..."}` photo across the visible towers in
   data/towers/**/*.json, deduplicated by url.
2. Downloads each url politely: one worker per host, at least 2s between requests to the
   same host (nhlr.org and firetower.org count as one host — pipeline/common.py's
   HOST_GROUPS already encodes that), the User-Agent FirefinderBot/0.1. Raw bytes are cached
   under /home/hoid/Desktop/firefinder/data/raw/photos/<host>/<sha1(url)>.bin so a re-run
   never re-fetches a url that already succeeded, and a url is never retried more than twice
   (tracked in data/raw/photos/_logs/attempts.json, outside the committed manifest).
3. Processes each successfully downloaded image: honours EXIF orientation, converts to sRGB,
   strips other metadata, and writes a full-size WebP (long side <= FULL_MAX px, quality
   ~72) and a thumbnail (long side <= 360px, quality ~60), named by the content hash of the
   full-size output so the same photo reused across sources/towers is stored once.
4. Writes data/photos_manifest.json (committed): source url -> {file, thumb, w, h, bytes,
   status, reason}. pipeline/merge.py reads this to fill in each tower's photos.

Usage:
    python3 pipeline/mirror_photos.py                  # run until every url is attempted
    python3 pipeline/mirror_photos.py --limit 40        # smoke-test a handful first
    python3 pipeline/mirror_photos.py --only-host nhlr  # just one host, for testing
    python3 pipeline/mirror_photos.py --report          # print totals from the manifest and exit (no network)

Safe to interrupt (Ctrl-C) and re-run; it flushes the manifest and attempt counts every
MANIFEST_FLUSH_EVERY completions and on exit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    FALLBACK_USER_AGENT,
    RAW_ROOT,
    USER_AGENT,
    RateLimiter,
    RobotsCache,
    _encode_url,
    host_group,
    write_log,
)

try:
    from PIL import Image, ImageCms, ImageOps
except ImportError:  # pragma: no cover - environment problem, not a code path we test
    print(
        "pipeline/mirror_photos.py needs Pillow (the system python3 has it; if this is a "
        "different interpreter, `pip install pillow`). This script is the one exception to "
        "the pipeline's stdlib-only rule (DESIGN.md) because it never runs in CI.",
        file=sys.stderr,
    )
    raise

REPO = Path(__file__).resolve().parent.parent
TOWERS_DIR = REPO / "data" / "towers"
MANIFEST_PATH = REPO / "data" / "photos_manifest.json"

# Output: mirrored images live outside the repo/worktree entirely (DESIGN.md Step 2 / the
# task that wrote this script). Where they get published is still the owner's call.
OUT_ROOT = Path("/home/hoid/Desktop/firefinder-photos/photos")

RAW_PHOTOS_ROOT = RAW_ROOT / "photos"
LOG_PATH = RAW_PHOTOS_ROOT / "_logs" / "mirror_photos.log"
ATTEMPTS_PATH = RAW_PHOTOS_ROOT / "_logs" / "attempts.json"

MIN_SIDE = 120  # below this (long side, px) a decoded image is an icon/spacer, not a photo
# DESIGN.md asks for a full size with the long side <= 1200px, but projected off a sample of
# the real corpus that comes to ~890 MB (plus thumbnails) against an ~800 MB target, so per
# DESIGN.md's own fallback ("if the projection is over, drop the full size to 1024 px and say
# so") this is 1024, not 1200. See the final report for the measured total.
FULL_MAX, FULL_QUALITY = 1024, 72
THUMB_MAX, THUMB_QUALITY = 360, 60
MAX_ATTEMPTS = 3  # first try + up to two retries
MANIFEST_FLUSH_EVERY = 20
REQUEST_TIMEOUT = 30

HTML_SNIFF = (b"<!doctype html", b"<html", b"<?xml")

_SRGB_PROFILE = ImageCms.createProfile("sRGB")


# ---------------------------------------------------------------------------------------
# Collecting urls
# ---------------------------------------------------------------------------------------


def iter_photo_urls() -> dict[str, str]:
    """url -> one tower id it appears on (for logging only). Visible towers, file is null."""
    out: dict[str, str] = {}
    for path in sorted(TOWERS_DIR.glob("*/*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("hidden"):
            continue
        for p in rec.get("photos") or []:
            if not isinstance(p, dict) or p.get("file"):
                continue
            url = p.get("url")
            if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in out:
                out[url] = rec.get("id", path.stem)
    return out


# ---------------------------------------------------------------------------------------
# Raw cache + attempt bookkeeping (gitignored; not the committed manifest)
# ---------------------------------------------------------------------------------------


def raw_cache_path(url: str) -> Path:
    host = urlsplit(url).netloc.lower() or "unknown-host"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return RAW_PHOTOS_ROOT / host / f"{digest}.bin"


class AttemptTracker:
    """How many times each url has been tried, persisted so a terminal-but-still-failing
    url is not retried forever across separate runs of this script."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.counts: dict[str, int] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.counts = {}

    def get(self, url: str) -> int:
        with self.lock:
            return self.counts.get(url, 0)

    def increment(self, url: str) -> int:
        with self.lock:
            self.counts[url] = self.counts.get(url, 0) + 1
            return self.counts[url]

    def flush(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.counts), encoding="utf-8")
            tmp.replace(self.path)


# ---------------------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------------------


class Fetched:
    __slots__ = ("status", "body", "content_type", "error")

    def __init__(self, status: int, body: bytes, content_type: str, error: str | None):
        self.status = status
        self.body = body
        self.content_type = content_type
        self.error = error


def fetch_binary(url: str, rate_limiter: RateLimiter, robots: RobotsCache) -> Fetched:
    if not robots.allowed(url):
        return Fetched(-1, b"", "", "robots_disallowed")
    rate_limiter.wait(url)
    for ua in (USER_AGENT, FALLBACK_USER_AGENT):
        try:
            req = urllib.request.Request(_encode_url(url), headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "") or ""
                return Fetched(resp.status, body, ctype, None)
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                body = e.read()
            except Exception:
                body = b""
            ctype = (e.headers.get("Content-Type", "") if e.headers else "") or ""
            if status in (403, 406) and ua == USER_AGENT:
                rate_limiter.wait(url)
                continue
            return Fetched(status, body, ctype, None)
        except Exception as e:  # noqa: BLE001 - any network/SSL/timeout failure is a "failure"
            last = e
            continue
    return Fetched(0, b"", "", f"{type(last).__name__}: {last}"[:200])


def looks_like_html(body: bytes, content_type: str) -> bool:
    if "html" in content_type.lower() or "xml" in content_type.lower():
        return True
    head = body[:300].lstrip().lower()
    return any(head.startswith(marker) for marker in HTML_SNIFF)


# ---------------------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------------------


class Unprocessable(Exception):
    pass


def _to_srgb_rgb(im: Image.Image) -> Image.Image:
    """Best-effort convert to sRGB using an embedded ICC profile, honouring it rather than
    just discarding it; falls back to a plain mode convert when there is no profile or the
    conversion fails (most web photos are already sRGB with no embedded profile)."""
    icc = im.info.get("icc_profile")
    if icc:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            return ImageCms.profileToProfile(im.convert("RGB"), src, _SRGB_PROFILE, outputMode="RGB")
        except Exception:
            pass
    return im if im.mode == "RGB" else im.convert("RGB")


def process_image(raw_bytes: bytes) -> tuple[bytes, bytes, int, int]:
    """-> (full_webp_bytes, thumb_webp_bytes, width, height). Raises Unprocessable if the
    bytes are not a decodable image."""
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        im.load()
    except Exception as e:
        raise Unprocessable(f"decode_error: {e}") from e

    im = ImageOps.exif_transpose(im)  # honour orientation, then the tag is gone

    # Flatten transparency onto white before dropping the alpha channel: strips metadata
    # (EXIF/XMP/ICC handled separately) without leaving a black background.
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = _to_srgb_rgb(im)

    width, height = im.size

    def resized(max_side: int) -> Image.Image:
        if max(im.size) <= max_side:
            return im
        ratio = max_side / max(im.size)
        size = (max(1, round(im.width * ratio)), max(1, round(im.height * ratio)))
        return im.resize(size, Image.LANCZOS)

    def encode(image: Image.Image, quality: int) -> bytes:
        buf = io.BytesIO()
        # exif=b"": Pillow would otherwise be able to carry EXIF through; we want none.
        image.save(buf, format="WEBP", quality=quality, method=6)
        return buf.getvalue()

    full_bytes = encode(resized(FULL_MAX), FULL_QUALITY)
    thumb_bytes = encode(resized(THUMB_MAX), THUMB_QUALITY)
    return full_bytes, thumb_bytes, width, height


# ---------------------------------------------------------------------------------------
# Manifest + stats
# ---------------------------------------------------------------------------------------


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        try:
            self.data: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def get(self, url: str) -> dict | None:
        with self.lock:
            return self.data.get(url)

    def set(self, url: str, entry: dict) -> None:
        with self.lock:
            self.data[url] = entry

    def flush(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self.path)


_write_lock = threading.Lock()  # guards writing content-addressed files (dedup check+write)


def write_once(path: Path, data: bytes) -> None:
    with _write_lock:
        if path.exists() and path.stat().st_size == len(data):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)


# ---------------------------------------------------------------------------------------
# Per-url worker logic
# ---------------------------------------------------------------------------------------


def handle_url(
    url: str,
    rate_limiter: RateLimiter,
    robots: RobotsCache,
    manifest: Manifest,
    attempts: AttemptTracker,
    stats: Counter,
    stats_lock: threading.Lock,
    stop: threading.Event,
) -> None:
    """Brings one url to a terminal manifest state (ok/failed/skipped) before returning,
    retrying a failure immediately (up to MAX_ATTEMPTS total tries, each still paced by
    rate_limiter) rather than requiring a separate script invocation per retry. The only way
    this returns without a terminal state is a shutdown request (`stop`) mid-retry, which is
    fine: the next run resumes it exactly where this one left off."""
    if manifest.get(url) is not None:
        return  # already terminal from a previous run

    def fail(reason: str) -> None:
        manifest.set(url, {"file": None, "thumb": None, "w": None, "h": None, "bytes": None,
                            "status": "failed", "reason": reason})
        with stats_lock:
            stats["failed"] += 1

    cache_path = raw_cache_path(url)
    last_reason = "unknown"
    while True:
        if stop.is_set():
            return

        body: bytes | None = None
        if cache_path.exists():
            try:
                body = cache_path.read_bytes()
            except OSError:
                body = None

        if body is None:
            if attempts.get(url) >= MAX_ATTEMPTS:
                return fail(last_reason)
            n = attempts.increment(url)
            fetched = fetch_binary(url, rate_limiter, robots)
            if fetched.error == "robots_disallowed":
                write_log(LOG_PATH, f"ROBOTS {url}")
                return fail("robots_disallowed")
            if fetched.status != 200 or fetched.error:
                last_reason = fetched.error or f"http_{fetched.status}"
                write_log(LOG_PATH, f"FETCH-FAIL ({n}/{MAX_ATTEMPTS}) {last_reason} {url}")
                if n >= MAX_ATTEMPTS:
                    return fail(last_reason)
                continue  # retry
            if looks_like_html(fetched.body, fetched.content_type):
                last_reason = "html_response"
                write_log(LOG_PATH, f"HTML-NOT-IMAGE ({n}/{MAX_ATTEMPTS}) {url}")
                if n >= MAX_ATTEMPTS:
                    return fail(last_reason)
                continue  # retry
            body = fetched.body
            write_once(cache_path, body)

        try:
            full_bytes, thumb_bytes, width, height = process_image(body)
        except Unprocessable as e:
            n = attempts.increment(url)
            last_reason = str(e)[:200]
            write_log(LOG_PATH, f"DECODE-FAIL ({n}/{MAX_ATTEMPTS}) {e} {url}")
            try:
                cache_path.unlink()  # don't keep unusable bytes around; re-download on retry
            except OSError:
                pass
            if n >= MAX_ATTEMPTS:
                return fail(last_reason)
            continue  # retry (re-downloads, since the cached bytes were just removed)

        if max(width, height) < MIN_SIDE:
            manifest.set(url, {"file": None, "thumb": None, "w": width, "h": height, "bytes": None,
                                "status": "skipped", "reason": f"too small ({width}x{height}px)"})
            with stats_lock:
                stats["skipped"] += 1
            return

        sha1 = hashlib.sha1(full_bytes).hexdigest()
        hh = sha1[:2]
        full_rel = f"{hh}/{sha1}.webp"
        thumb_rel = f"{hh}/{sha1}.t.webp"
        write_once(OUT_ROOT / full_rel, full_bytes)
        write_once(OUT_ROOT / thumb_rel, thumb_bytes)
        manifest.set(url, {"file": full_rel, "thumb": thumb_rel, "w": width, "h": height,
                            "bytes": len(full_bytes), "status": "ok", "reason": None})
        with stats_lock:
            stats["ok"] += 1
            stats["bytes_full"] += len(full_bytes)
            stats["bytes_thumb"] += len(thumb_bytes)
        return


# ---------------------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------------------


def worker_loop(
    group: str,
    urls: list[str],
    rate_limiter: RateLimiter,
    robots: RobotsCache,
    manifest: Manifest,
    attempts: AttemptTracker,
    stats: Counter,
    stats_lock: threading.Lock,
    stop: threading.Event,
    progress: dict,
    progress_lock: threading.Lock,
) -> None:
    done = 0
    for url in urls:
        if stop.is_set():
            break
        try:
            handle_url(url, rate_limiter, robots, manifest, attempts, stats, stats_lock, stop)
        except Exception as e:  # noqa: BLE001 - one bad url must never kill the worker
            write_log(LOG_PATH, f"UNEXPECTED {type(e).__name__}: {e} {url}")
        done += 1
        with progress_lock:
            progress[group] = done
            total_done = sum(progress.values())
        if total_done % MANIFEST_FLUSH_EVERY == 0:
            manifest.flush()
            attempts.flush()
        if done % 100 == 0 or done == len(urls):
            write_log(LOG_PATH, f"[{group}] {done}/{len(urls)} done")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="process at most N urls total (smoke test)")
    ap.add_argument("--only-host", default=None, help="only urls whose host contains this substring")
    ap.add_argument("--report", action="store_true", help="print totals from the manifest and exit; no network")
    args = ap.parse_args()

    if args.report:
        print_report()
        return 0

    urls_by_tower = iter_photo_urls()
    urls = list(urls_by_tower.keys())
    if args.only_host:
        urls = [u for u in urls if args.only_host.lower() in urlsplit(u).netloc.lower()]
    if args.limit:
        urls = urls[: args.limit]

    groups: dict[str, list[str]] = defaultdict(list)
    for u in urls:
        groups[host_group(u)].append(u)

    print(f"mirror_photos: {len(urls)} urls across {len(groups)} host group(s):")
    for g, us in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"  {g}: {len(us)}")

    manifest = Manifest(MANIFEST_PATH)
    attempts = AttemptTracker(ATTEMPTS_PATH)
    rate_limiter = RateLimiter()
    robots = RobotsCache(rate_limiter)
    stats: Counter = Counter()
    stats_lock = threading.Lock()
    progress: dict[str, int] = {}
    progress_lock = threading.Lock()
    stop = threading.Event()

    def handle_signal(signum, frame):
        write_log(LOG_PATH, f"signal {signum} received, finishing in-flight requests and flushing...")
        stop.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    write_log(LOG_PATH, f"START {len(urls)} urls, {len(groups)} host groups")
    t0 = time.time()
    threads = [
        threading.Thread(
            target=worker_loop,
            args=(g, us, rate_limiter, robots, manifest, attempts, stats, stats_lock, stop, progress, progress_lock),
            name=f"mirror-{g}",
            daemon=True,
        )
        for g, us in groups.items()
    ]
    for t in threads:
        t.start()
    try:
        for t in threads:
            while t.is_alive():
                t.join(timeout=5)
    finally:
        manifest.flush()
        attempts.flush()

    elapsed = time.time() - t0
    write_log(
        LOG_PATH,
        f"DONE in {elapsed/60:.1f} min: ok={stats['ok']} failed={stats['failed']} skipped={stats['skipped']} "
        f"bytes_full={stats['bytes_full']} bytes_thumb={stats['bytes_thumb']}",
    )
    print(f"mirror_photos: ok={stats['ok']} failed={stats['failed']} skipped={stats['skipped']} in {elapsed/60:.1f} min")
    return 0


def print_report() -> None:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("no manifest yet")
        return
    by_status = Counter(e.get("status") for e in data.values())
    total_full = sum(e.get("bytes") or 0 for e in data.values() if e.get("status") == "ok")
    reasons = Counter(e.get("reason") for e in data.values() if e.get("status") in ("failed", "skipped"))
    print(f"manifest entries: {len(data)}")
    for status, n in by_status.most_common():
        print(f"  {status}: {n}")
    print(f"total full-size bytes (ok only): {total_full / 1_000_000:.1f} MB")
    print("top reasons (failed/skipped):")
    for reason, n in reasons.most_common(15):
        print(f"  {n:5d}  {reason}")


if __name__ == "__main__":
    raise SystemExit(main())
