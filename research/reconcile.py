#!/usr/bin/env python3
"""Tidy a batch of research output before the merge.

- `cite` values written as a bare number become a list (events, corrections, resolved_conflicts).
- A story footnote whose number is missing from the research file's `sources` gets a source entry
  built from the footnote text itself (title, URL, accessed date), so the two stay in step.
Reports what it changed; run it after every story batch, then `pipeline/validate.py`."""
import glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF = re.compile(r"^\[\^(\d+)\]:\s*(.+)$", re.M)


def from_footnote(n, text):
    url = re.search(r"https?://\S+?(?=[\s)]|\.?\s|$)", text)
    url = url.group(0).rstrip(".,;)") if url else None
    acc = re.search(r"accessed (\d{4}-\d{2}-\d{2})", text)
    title = text.split(", http")[0].split(" http")[0].strip().rstrip(",")
    parts = [p.strip() for p in title.split(",")]
    src = {"n": n, "title": parts[0] if parts else title}
    if len(parts) > 1:
        src["publisher"] = ", ".join(parts[1:])
    if url:
        src["url"] = url
    if acc:
        src["accessed"] = acc.group(1)
    return src


def main():
    fixed_cites = added = 0
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "research", "*.json"))):
        rid = os.path.basename(p)[:-5]
        r = json.load(open(p, encoding="utf-8"))
        changed = False
        for k in ("corrections", "events", "resolved_conflicts"):
            for c in r.get(k) or []:
                if isinstance(c, dict) and isinstance(c.get("cite"), int):
                    c["cite"] = [c["cite"]]; changed = True; fixed_cites += 1
        story = os.path.join(ROOT, "data", "stories", f"{rid}.md")
        if os.path.exists(story):
            have = {s.get("n") for s in r.get("sources") or [] if isinstance(s, dict)}
            for n, text in DEF.findall(open(story, encoding="utf-8").read()):
                if int(n) not in have:
                    r.setdefault("sources", []).append(from_footnote(int(n), text))
                    r["sources"].sort(key=lambda s: s.get("n") or 0)
                    changed = True; added += 1
                    print(f"{rid}: added source {n} from its footnote")
        if changed:
            json.dump(r, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"cites normalised: {fixed_cites}; sources added from footnotes: {added}")


if __name__ == "__main__":
    main()
