#!/usr/bin/env python3
"""Author and licence for every Wikimedia Commons photo used by Firefinder.

Commons' robots.txt disallows /w/api.php and /wiki/Special:, so this reads each photo's ordinary
file page (/wiki/File:...), which is allowed, and pulls the machine-readable credit fields
(`licensetpl_short`, `licensetpl_link`, the Author row). Polite (2 s gap), cached under
data/raw/commons/, writes data/sources/commons_credits.json keyed by file name (underscored)."""
import glob, hashlib, html, json, os, re, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "raw", "commons")
OUT = os.path.join(ROOT, "data", "sources", "commons_credits.json")
UA = "FirefinderBot/0.1 (+https://github.com/holdTheDoorHoid/firefinder)"


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def file_names():
    d = json.load(open(os.path.join(ROOT, "data", "sources", "wikidata.json")))
    names = set()
    for r in d["records"]:
        for p in r.get("photos") or []:
            u = p.get("url") or ""
            if "/wiki/File:" in u:
                names.add(urllib.parse.unquote(u.split("/wiki/File:", 1)[1]).replace(" ", "_"))
    return sorted(names)


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.sha1(name.encode()).hexdigest() + ".html")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    url = "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(name)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    time.sleep(2)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    open(path, "w", encoding="utf-8").write(body)
    return body


def parse(page):
    page = page.replace("&#95;", "_")  # Commons HTML-escapes the underscores in these class names
    lic = re.search(r'class="licensetpl_short[^"]*"[^>]*>(.*?)</span>', page, re.S)
    link = re.search(r'class="licensetpl_link[^"]*"[^>]*>(.*?)</span>', page, re.S)
    aut = re.search(r'id="fileinfotpl_aut"[^>]*>.*?</td>\s*<td[^>]*>(.*?)</td>', page, re.S)
    author = text(aut.group(1)) if aut else None
    if author:
        author = re.sub(r"\s*\(talk.*?\)$", "", author)[:200] or None
    return {"author": author, "license": text(lic.group(1)) if lic else None,
            "license_url": text(link.group(1)) if link else None}


def main():
    out = {}
    for name in file_names():
        try:
            out[name] = parse(fetch(name))
        except Exception as e:  # keep going; a missing credit falls back to the file page link
            out[name] = {"author": None, "license": None, "license_url": None, "error": str(e)[:200]}
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True, ensure_ascii=False)
    ok = sum(1 for v in out.values() if v.get("license"))
    print(f"{len(out)} Commons files, {ok} with a licence, {sum(1 for v in out.values() if v.get('author'))} with an author")


if __name__ == "__main__":
    main()
