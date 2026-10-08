"""Tests for pipeline/regional/nwmt_projects.py and its curated data (no network).
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "regional"))
import _projects as P  # noqa: E402
import nwmt_projects as N  # noqa: E402
import nwmt_projects_data as D  # noqa: E402

import merge as M  # noqa: E402


def built_records() -> list[dict]:
    docs = P.DocSet(N.SOURCE)
    for d in D.DOCS:
        docs.add(d["id"], d["url"], d["label"], d["year"])
    return N.build_records(docs)


class CuratedData(unittest.TestCase):
    def test_every_cited_document_exists_and_ids_are_unique(self):
        ids = [d["id"] for d in D.DOCS]
        self.assertEqual(len(ids), len(set(ids)))
        for lk in D.LOOKOUTS:
            for e in lk["events"]:
                self.assertTrue(e["cite"], (lk["slug"], e))
                for c in e["cite"]:
                    self.assertIn(c, ids, (lk["slug"], c))

    def test_slugs_and_towers_are_unique(self):
        slugs = [lk["slug"] for lk in D.LOOKOUTS]
        towers = [lk["tower"] for lk in D.LOOKOUTS]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(len(towers), len(set(towers)))

    def test_records_are_valid_in_the_shared_shape(self):
        recs = built_records()
        self.assertEqual(len(recs), len(D.LOOKOUTS))
        problems = [p for p in P.validate_records(recs, source=N.SOURCE)]
        self.assertEqual(problems, [])
        for r in recs:
            self.assertIsNotNone(r["lat"], r["key"])             # every position was copied from a register or list
            self.assertTrue(r["extra"]["position_from"])
            self.assertEqual(r["status"], "standing")

    def test_the_lookout_page_is_the_newest_report_that_mentions_it(self):
        by_slug = {r["key"].split(":")[-1]: r for r in built_records()}
        self.assertEqual(by_slug["numa-ridge"]["url"], "https://nwmt-ffla.org/2025/03/04/2025-projects/")
        self.assertEqual(by_slug["mount-wam"]["url"], "https://nwmt-ffla.org/2026/03/07/2026-projects/")
        # newest report is the 2023 PDF's page, not a post
        self.assertEqual(by_slug["cooney"]["url"], "https://nwmt-ffla.org/2023/09/01/2023-projects/")
        # a newsletter-only lookout falls back to the newsletter page
        self.assertTrue(all(r["url"].startswith("https://nwmt-ffla.org/") for r in by_slug.values()))

    def test_event_links_are_the_documents_cited(self):
        by_slug = {r["key"].split(":")[-1]: r for r in built_records()}
        ev = next(e for e in by_slug["numa-ridge"]["events"] if e["year"] == 2025)
        self.assertEqual(ev["source_urls"], ["https://nwmt-ffla.org/2025/03/04/2025-projects/",
                                             "https://nwmt-ffla.org/wp-content/uploads/2025/11/2025-newsletter-final2.pdf"])
        pdf = next(e for e in by_slug["mud-lake"]["events"] if e["year"] == 2017)
        self.assertEqual(pdf["source_url"], "https://nwmt-ffla.org/wp-content/uploads/2025/09/2017-completed-projects.pdf")

    def test_committed_extract_is_what_the_curated_data_builds(self):
        path = P.SOURCES_DIR / "nwmt_projects.json"
        if not path.exists():
            self.skipTest("extract not written yet")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["family"], P.FAMILY)
        self.assertEqual(data["source"], N.SOURCE)

        def comparable(r: dict) -> dict:
            r = json.loads(json.dumps(r))                                    # a copy
            for e in r["events"]:
                e.pop("_cite", None)                                         # private, not written
            return {k: v for k, v in r.items() if k not in ("lat", "lon")}   # positions follow the registers

        built = {r["key"]: comparable(r) for r in built_records()}
        committed = {r["key"]: comparable(r) for r in data["records"]}
        self.assertEqual(committed, built)

    def test_crawl_patterns(self):
        self.assertTrue(N.PROJECT_POST_RE.match("https://nwmt-ffla.org/2024/09/01/2024-projects/"))
        self.assertTrue(N.PROJECT_POST_RE.match("https://nwmt-ffla.org/2027/03/07/2027-projects/"))
        self.assertFalse(N.PROJECT_POST_RE.match("https://nwmt-ffla.org/2025/11/12/2025-newsletter/"))
        self.assertEqual(N.doc_cache_name({"kind": "post", "year": 2025, "url": "x"}), "2025-projects.html")
        self.assertEqual(N.doc_cache_name({"kind": "pdf", "year": 2019, "url": "https://x/y/2019-completed-projects.pdf"}),
                         "pdf/2019-completed-projects.pdf")


class MergeFamily(unittest.TestCase):
    def test_nwmt_projects_is_a_registered_association(self):
        self.assertIn("nwmt_projects", M.ASSOCIATION_SOURCES)
        # association sources rank after every register and list, in the order ASSOCIATION_SOURCES gives
        self.assertIn("nwmt_projects", M.PRECEDENCE["events"])
        self.assertEqual(M.PRECEDENCE["events"][-len(M.ASSOCIATION_SOURCES):], M.ASSOCIATION_SOURCES)
        self.assertEqual(M.LOCATION_LINEAGE["nwmt_projects"], "registers")


if __name__ == "__main__":
    unittest.main()
