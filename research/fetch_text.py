#!/usr/bin/env python3
"""Read a web page or PDF as plain text, cheaply, for research agents.

  research/fetch_text.py URL [--grep REGEX] [--context 1] [--max 6000]

- nhlr.org / firetower.org pages are read from the crawl cache (data/raw/nhlr, data/raw/fflos);
  everything else is fetched once and cached under data/raw/web/ (polite: 2 s per host, honest UA).
- HTML is reduced to text (scripts, styles and navigation dropped); PDFs go through pdftotext.
- --grep prints only the lines matching REGEX (case-insensitive) with --context lines around them,
  so a 40-page NRHP nomination costs a few hundred words instead of thousands.
- Output is capped at --max characters; the first line says how long the full text was."""
import argparse, fcntl, hashlib, html, os, re, subprocess, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
UA = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"
LOCKDIR = os.path.join(RAW, "_locks")


def cached_register(url):
    u = urllib.parse.urlsplit(url)
    host = u.netloc.lower().removeprefix("www.")
    src = {"nhlr.org": "nhlr", "firetower.org": "fflos"}.get(host)
    if not src:
        return None
    path = os.path.join(RAW, src, host, u.path.strip("/"), "index.html")
    return path if os.path.exists(path) else None


def polite_get(url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    os.makedirs(LOCKDIR, exist_ok=True)
    with open(os.path.join(LOCKDIR, "web-" + re.sub(r"[^a-z0-9.]", "_", host)), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        last = float((f.read() or "0").strip() or 0)
        wait = last + 2.0 - time.time()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/pdf,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body, ctype = r.read(), r.headers.get("Content-Type", "")
        finally:
            f.seek(0); f.truncate(); f.write(str(time.time())); f.flush()
    return body, ctype


def get(url):
    reg = cached_register(url)
    if reg:
        return open(reg, "rb").read(), "text/html"
    os.makedirs(os.path.join(RAW, "web"), exist_ok=True)
    key = os.path.join(RAW, "web", hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(key + ".bin"):
        return open(key + ".bin", "rb").read(), open(key + ".type").read()
    body, ctype = polite_get(url)
    open(key + ".bin", "wb").write(body)
    open(key + ".type", "w").write(ctype)
    return body, ctype


def to_text(body, ctype):
    if body[:5] == b"%PDF-" or "pdf" in ctype:
        p = subprocess.run(["pdftotext", "-layout", "-", "-"], input=body, capture_output=True, timeout=120)
        return p.stdout.decode("utf-8", "replace")
    s = body.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|table|section|article)>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in s.splitlines()]
    return "\n".join(l for l in lines if l)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--grep")
    ap.add_argument("--context", type=int, default=1)
    ap.add_argument("--max", type=int, default=6000)
    a = ap.parse_args()
    try:
        text = to_text(*get(a.url))
    except Exception as e:
        print(f"ERROR fetching {a.url}: {e}")
        sys.exit(1)
    out = text
    if a.grep:
        lines = text.splitlines()
        rx = re.compile(a.grep, re.I)
        keep = set()
        for i, l in enumerate(lines):
            if rx.search(l):
                keep.update(range(max(0, i - a.context), min(len(lines), i + a.context + 1)))
        out = "\n".join(("..." if i - 1 not in keep and i else "") + lines[i] for i in sorted(keep)) or "(no matching lines)"
    print(f"[{len(text)} chars of text; showing {min(len(out), a.max)}]")
    print(out[: a.max])


if __name__ == "__main__":
    main()
