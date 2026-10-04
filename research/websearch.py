#!/usr/bin/env python3
"""Web search from the shell, for research agents when the WebSearch tool is unavailable.

  scripts/websearch.py "LayerOne 2019 badge" [-n 10]

Uses DuckDuckGo's lite endpoint (POST, text-browser user agent; the html endpoint and Bing/Google
block or garble scripted queries). Prints one result per line: title | url | snippet.
Polite: one request per call, ~1.5 s pause, retries once on 429/403."""
import argparse, fcntl, html, os, re, sys, time, urllib.parse, urllib.request

LOCK = os.environ.get("WEBSEARCH_LOCK", "/home/hoid/Desktop/firefinder/data/raw/_locks/ddg.lock")
MIN_GAP = float(os.environ.get("WEBSEARCH_GAP", "4.5"))  # seconds between requests, machine-wide (DDG lite 403s on faster bursts)

class Throttle:
    """Serialise all callers on this machine and keep MIN_GAP between requests; holds the lock for the request itself."""
    def __enter__(self):
        os.makedirs(os.path.dirname(LOCK), exist_ok=True)
        self.f = open(LOCK, "a+"); fcntl.flock(self.f, fcntl.LOCK_EX)
        self.f.seek(0); last = float((self.f.read() or "0").strip() or 0)
        wait = last + MIN_GAP - time.time()
        if wait > 0: time.sleep(wait)
        return self
    def __exit__(self, *a):
        self.f.seek(0); self.f.truncate(); self.f.write(str(time.time())); self.f.flush()
        fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()

UA = "Lynx/2.8.9rel.1 libwww-FM/2.14 SSL-MM/1.4.1 OpenSSL/1.1.1"

def clean(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()

def ddg_lite(q, n):
    data = urllib.parse.urlencode({"q": q, "kl": "us-en"}).encode()
    req = urllib.request.Request("https://lite.duckduckgo.com/lite/", data=data, headers={"User-Agent": UA, "Referer": "https://lite.duckduckgo.com/"})
    for attempt in range(3):
        try:
            with Throttle():
                with urllib.request.urlopen(req, timeout=25) as r: txt = r.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2: time.sleep(20 * (attempt + 1)); continue
            raise
    out = []
    for m in re.finditer(r'<a rel="nofollow" href="([^"]+)" class=.result-link.>(.*?)</a>(.*?)(?=<a rel="nofollow" href=|$)', txt, re.S):
        url = html.unescape(m.group(1))
        if url.startswith("//duckduckgo.com/l/?uddg="): url = urllib.parse.unquote(url.split("uddg=")[1].split("&")[0])
        sn = re.search(r'<td class=.result-snippet.>(.*?)</td>', m.group(3), re.S)
        out.append((clean(m.group(2)), url, clean(sn.group(1)) if sn else ""))
        if len(out) >= n: break
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("query"); ap.add_argument("-n", type=int, default=10); a = ap.parse_args()
    try: res = ddg_lite(a.query, a.n)
    except Exception as e: print(f"# search failed: {e}"); return
    if not res: print("# no results"); return
    for t, u, d in res: print(f"{t} | {u} | {d[:220]}")

if __name__ == "__main__":
    main()
