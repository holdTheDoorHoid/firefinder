"""Tests for the eastern association-project sources (pipeline/regional/_assoc_east.py and the modules built on
it) and their curated data. No network. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "regional"))
sys.path.insert(0, str(HERE))
import _assoc_east as A  # noqa: E402
import _assoc_site as S  # noqa: E402
import _projects as P  # noqa: E402
import azure_mountain_friends  # noqa: E402
import bald_mountain_friends  # noqa: E402
import bramley_friends  # noqa: E402
import hurricane_friends  # noqa: E402
import mt_arab_friends  # noqa: E402
import nysffla_projects  # noqa: E402
import nysffla_projects_data  # noqa: E402
import smokies_friends  # noqa: E402
import st_regis_friends  # noqa: E402
import ffla_east_reports  # noqa: E402
import kent_conservation_foundation  # noqa: E402
import stillwater_friends  # noqa: E402

import merge as M  # noqa: E402

REPO = HERE.parent

# (module, its LOOKOUTS, its DOCS)
MODULES = [
    (nysffla_projects, nysffla_projects_data.LOOKOUTS, nysffla_projects_data.DOCS),
    (st_regis_friends, st_regis_friends.LOOKOUTS, st_regis_friends.DOCS),
    (hurricane_friends, hurricane_friends.LOOKOUTS, hurricane_friends.DOCS),
    (mt_arab_friends, mt_arab_friends.LOOKOUTS, mt_arab_friends.DOCS),
    (azure_mountain_friends, azure_mountain_friends.LOOKOUTS, azure_mountain_friends.DOCS),
    (bald_mountain_friends, bald_mountain_friends.LOOKOUTS, bald_mountain_friends.DOCS),
    (bramley_friends, bramley_friends.LOOKOUTS, bramley_friends.DOCS),
    (kent_conservation_foundation, kent_conservation_foundation.LOOKOUTS, kent_conservation_foundation.DOCS),
    (stillwater_friends, stillwater_friends.LOOKOUTS, stillwater_friends.DOCS),
    (smokies_friends, smokies_friends.LOOKOUTS, smokies_friends.DOCS),
    (ffla_east_reports, ffla_east_reports.LOOKOUTS, ffla_east_reports.DOCS),
]


def built(mod, lookouts, specs) -> list[dict]:
    docs = P.DocSet(mod.SOURCE)
    for d in specs:
        docs.add(d["id"], d["page"], d["label"], d["year"])
    return S.build_records(mod.SOURCE, mod.ASSOCIATION, specs, lookouts, docs)


class PageText(unittest.TestCase):
    def test_old_hand_made_pages_and_wordpress_pages_read_alike(self):
        page = ("<html><head><style>p{}</style><script>var x=1;</script></head><body><h1>Mount&nbsp;Arab</h1>"
                "<font>Volunteers replaced the steps<br>in September 2006.</font><!-- hidden --><p>Done.</p></body></html>")
        text = S.page_text(page)
        self.assertIn("Volunteers replaced the steps", text)
        self.assertIn("in September 2006.", text)
        self.assertNotIn("var x", text)
        self.assertNotIn("p{}", text)

    def test_doc_defaults(self):
        pdf = A.doc("a", "https://x.org/a.pdf?dl=1", "A", 2020)
        self.assertEqual((pdf["kind"], pdf["page"]), ("pdf", "https://x.org/a.pdf?dl=1"))
        html = A.doc("b", "https://x.org/b/", "B", None, page="https://x.org/b/#2019", cache="b.html")
        self.assertEqual((html["kind"], html["page"]), ("html", "https://x.org/b/#2019"))


class CuratedData(unittest.TestCase):
    def test_every_module_is_valid_in_the_shared_shape(self):
        for mod, lookouts, specs in MODULES:
            with self.subTest(source=mod.SOURCE):
                recs = built(mod, lookouts, specs)
                self.assertEqual(len(recs), len(lookouts))
                self.assertEqual(P.validate_records(recs, source=mod.SOURCE), [])
                for r in recs:
                    self.assertIsNotNone(r["lat"], r["key"])             # position copied from a register or list
                    self.assertTrue(r["extra"]["position_from"], r["key"])
                    self.assertTrue(r["events"], r["key"])

    def test_every_cited_document_exists_and_ids_and_slugs_are_unique(self):
        for mod, lookouts, specs in MODULES:
            with self.subTest(source=mod.SOURCE):
                ids = [d["id"] for d in specs]
                self.assertEqual(len(ids), len(set(ids)))
                slugs = [(lk["region"], lk["slug"]) for lk in lookouts]   # the key carries the state
                self.assertEqual(len(slugs), len(set(slugs)))
                towers = [lk["tower"] for lk in lookouts]
                self.assertEqual(len(towers), len(set(towers)))
                for lk in lookouts:
                    for e in lk["events"]:
                        self.assertTrue(e["cite"], (lk["slug"], e))
                        for c in e["cite"]:
                            self.assertIn(c, ids, (lk["slug"], c))

    def test_each_source_is_registered_for_the_merge(self):
        for mod, _, _ in MODULES:
            self.assertIn(mod.SOURCE, M.ASSOCIATION_SOURCES)

    def test_each_lookout_names_a_tower_that_exists_and_the_position_comes_from_it(self):
        index = P.source_index()
        for mod, lookouts, _ in MODULES:
            for lk in lookouts:
                tid = lk["tower"]
                path = REPO / "data" / "towers" / tid.split("-")[1] / f"{tid}.json"
                self.assertTrue(path.exists(), tid)
                tower = json.loads(path.read_text(encoding="utf-8"))
                keys = {s["key"] for s in tower["sources"]}
                self.assertIn(lk["pos"], keys, f"{tid}: {lk['pos']} is not one of the tower's own source records")
                self.assertIn(lk["pos"], index, lk["pos"])

    def test_cabin_dates_are_not_filed_as_the_towers_build_year(self):
        for _, lookouts, _ in MODULES:
            for lk in lookouts:
                for e in lk["events"]:
                    if e["event"] == "built":
                        self.assertNotIn("observer's cabin", e["note"].lower().split(",")[0][:40], (lk["slug"], e))

    def test_notes_are_short_and_events_do_not_repeat(self):
        for mod, lookouts, _ in MODULES:
            for lk in lookouts:
                seen = set()
                for e in lk["events"]:
                    self.assertLessEqual(len(e["note"]), P.NOTE_MAX, (lk["slug"], e["year"]))
                    k = (e["event"], e["year"])
                    self.assertNotIn(k, seen, (lk["slug"], k))
                    seen.add(k)


class Records(unittest.TestCase):
    def test_lookout_page_is_the_newest_report_unless_the_group_has_its_own_page(self):
        by = {r["key"]: r for r in built(nysffla_projects, nysffla_projects_data.LOOKOUTS, nysffla_projects_data.DOCS)}
        # Pillsbury's newest cited issue is the 2024-06 one, not the 2024-04 where the event is first reported
        pill = by["nysffla_projects:ny:pillsbury-mountain"]
        self.assertTrue(pill["url"].startswith("https://www.nysffla.org/"), pill["url"])
        r = built(st_regis_friends, st_regis_friends.LOOKOUTS, st_regis_friends.DOCS)[0]
        self.assertEqual(r["url"], "http://www.friendsofstregis.org/restoration/")
        self.assertEqual(r["status"], "standing")
        # a record that sets no status makes no claim (a gone tower must not be called standing)
        self.assertEqual(by["nysffla_projects:ny:ampersand-mountain"]["status"], "unknown")

    def test_st_regis_year_links_go_to_the_years_section(self):
        recs = built(st_regis_friends, st_regis_friends.LOOKOUTS, st_regis_friends.DOCS)
        urls = {e["year"]: e["source_url"] for e in recs[0]["events"]}
        self.assertEqual(urls[2016], "http://www.friendsofstregis.org/restoration/#2016")
        self.assertEqual(urls[2026], "http://www.friendsofstregis.org/restoration/#2026")

    def test_mt_arab_waits_the_crawl_delay_robots_txt_asks_for(self):
        self.assertGreaterEqual(mt_arab_friends.CRAWL_DELAY, 10.0)
        self.assertGreaterEqual(smokies_friends.CRAWL_DELAY, 3.0)

    def test_ffla_east_reports_keep_registers_out_and_are_all_pdfs_on_firelookout_org(self):
        for lk in ffla_east_reports.LOOKOUTS:
            for e in lk["events"]:
                self.assertNotEqual(e["event"], "nhlr_registered", (lk["slug"], e))
                self.assertNotRegex(e["note"], r"Historic Lookout Register|NHLR", (lk["slug"], e))
        for d in ffla_east_reports.DOCS:
            self.assertEqual(d["kind"], "pdf")
            self.assertTrue(d["url"].startswith("https://firelookout.org/wp-content/uploads/"), d["url"])
            self.assertEqual(d["cache"], f"pdf/{d['id']}.pdf")
        # a grant is filed as "other" and says so
        for lk in ffla_east_reports.LOOKOUTS:
            for e in lk["events"]:
                if e["note"].startswith("FFLA restoration grant"):
                    self.assertEqual(e["event"], "other", (lk["slug"], e))

    def test_nysffla_issue_ids_match_their_urls(self):
        for d in nysffla_projects_data.DOCS:
            if d["id"] == "projects":
                continue
            ym = d["cache"].split("/")[-1].removesuffix(".pdf")
            self.assertEqual(d["id"], "n" + ym.replace("-", ""))
            self.assertTrue(d["url"].startswith("https://www.nysffla.org/"))
            self.assertEqual(d["year"], int(ym[:4]))
        ids = {d["id"] for d in nysffla_projects_data.DOCS}
        self.assertNotIn("n202603", ids)   # that file repeats April 2026's issue


if __name__ == "__main__":
    unittest.main()
