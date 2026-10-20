#!/usr/bin/env python3
"""Check that every evidence quote in a research file really appears in the source it cites.

  research/check_quotes.py [ID ...] [--all] [--verbose] [--json OUT]

With no ids it checks the research files that git reports as new or modified (a fresh batch).
Source text comes through research/fetch_text.py's cache, so pages the agents read are not
fetched again. A quote counts as found when it appears verbatim after normalising case,
punctuation and whitespace, when every part around an ellipsis appears, or when at least 85%
of its four-word runs appear ("close": usually PDF line breaks or a small slip).
Exit status is 1 when any quote is missing from a source that could be read."""
import argparse, glob, json, os, re, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))
import fetch_text  # noqa: E402

_texts = {}


# Letters Unicode does not decompose into base letter + accent, folded the way people retype them.
_FOLD = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss", "ø": "o", "Ø": "o",
                       "đ": "d", "Đ": "d", "ł": "l", "Ł": "l", "ı": "i", "þ": "th", "ð": "d"})
# Invisible characters that sit inside words in scraped text (soft hyphen, zero-width space and
# joiners, word joiner, byte-order mark, directional marks) are dropped; every dash becomes "-".
_CLEAN = {**dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff\u200e\u200f\u202a\u202b\u202c")),
          **dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")}


def norm(s):
    """Text reduced to lower-case words, so a quote and its page compare equal despite typography:
    curly or straight quotes, « » guillemets, any dash, non-breaking and narrow spaces (French sets
    one before : ; ? ! and inside « »), ligatures (ﬁ, œ), accents (Québec = Quebec, à = a) and
    elision apostrophes (l’église = l'église). Everything that is not a letter or digit becomes a
    single space; the same function runs on both sides, so what matters is that it is consistent."""
    s = unicodedata.normalize("NFKD", s.translate(_CLEAN).lower())  # NFKD: ﬁ -> fi, NBSP -> space, é -> e + accent
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).translate(_FOLD)
    s = re.sub(r"-\s*\n\s*", "", s)  # words hyphenated across PDF lines
    return " ".join(re.sub(r"[\W_]+", " ", s).split())


def source_text(url):
    if url not in _texts:
        try:
            _texts[url] = norm(fetch_text.to_text(*fetch_text.get(url)))
        except Exception as e:  # unreachable, 403, timeout
            _texts[url] = None
            print(f"  (could not read {url}: {e})", file=sys.stderr)
    return _texts[url]


def shingles(words, k=4):
    return {" ".join(words[i:i + k]) for i in range(max(1, len(words) - k + 1))}


def match(quote, text):
    q = norm(quote)
    if not q:
        return "found"
    if q in text:
        return "found"
    parts = [norm(p) for p in re.split(r"\.\.\.|…|\[[^\]]*\]", quote)]
    parts = [p for p in parts if len(p.split()) >= 3]
    if len(parts) > 1 and all(p in text for p in parts):
        return "found"
    words = q.split()
    if len(words) >= 6:
        sh = shingles(words)
        if sum(1 for s in sh if s in text) / len(sh) >= 0.85:
            return "close"
    return "missing"


def cites(e):
    c = e.get("cite")
    if isinstance(c, list):
        return [int(x) for x in c if str(x).isdigit()]
    if c is None:
        return []
    return [int(x) for x in re.findall(r"\d+", str(c))]


def check(rid):
    path = os.path.join(ROOT, "data", "research", f"{rid}.json")
    if not os.path.exists(path):  # not written (the researcher gave up or was blocked): nothing to check
        return {"id": rid, "found": 0, "close": 0, "missing": 0, "unreadable": 0, "no_source": 0, "bad": [], "absent": True}
    r = json.load(open(path, encoding="utf-8"))
    urls = {s.get("n"): s.get("url") for s in r.get("sources") or [] if isinstance(s, dict)}
    out = {"id": rid, "found": 0, "close": 0, "missing": 0, "unreadable": 0, "no_source": 0, "bad": []}
    for e in r.get("evidence") or []:
        if not isinstance(e, dict) or not e.get("quote"):
            continue
        ns = [n for n in cites(e) if urls.get(n)]
        if not ns:
            out["no_source"] += 1
            out["bad"].append({"cite": e.get("cite"), "why": "no source URL", "quote": e["quote"][:160]})
            continue
        texts = [source_text(urls[n]) for n in ns]
        readable = [t for t in texts if t]
        if not readable:
            out["unreadable"] += 1
            continue
        best = "missing"
        for t in readable:
            m = match(e["quote"], t)
            if m == "found":
                best = m
                break
            if m == "close":
                best = m
        out[best] += 1
        if best == "missing":
            out["bad"].append({"cite": e.get("cite"), "url": urls[ns[0]], "quote": e["quote"][:160]})
    return out


def changed_ids():
    # core.quotepath=off: git would otherwise quote any path with a non-ASCII byte
    p = subprocess.run(["git", "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "data/research"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return sorted({os.path.basename(l[3:].strip())[:-5] for l in p.stdout.splitlines() if l.strip().endswith(".json")})


def main():
    if hasattr(sys.stdout, "reconfigure"):  # accented quotes must print whatever the locale
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    ids = a.ids or ([os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(ROOT, "data", "research", "*.json")))]
                    if a.all else changed_ids())
    rows = [check(i) for i in ids]
    tot = {k: sum(r[k] for r in rows) for k in ("found", "close", "missing", "unreadable", "no_source")}
    for r in rows:
        flag = "ABSENT" if r.get("absent") else "MISSING" if r["missing"] or r["no_source"] else "ok"
        print(f"{flag:8} {r['id']}: found {r['found']}, close {r['close']}, missing {r['missing']}, "
              f"unreadable {r['unreadable']}, no source {r['no_source']}")
        if a.verbose:
            for b in r["bad"]:
                print(f"           [{b.get('cite')}] {b.get('url', b.get('why'))}\n             \"{b['quote']}\"")
    print(f"{len(rows)} towers: {tot}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, ensure_ascii=False)
    sys.exit(1 if tot["missing"] or tot["no_source"] else 0)


if __name__ == "__main__":
    main()
