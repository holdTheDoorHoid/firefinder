"""Tests for the western association-project modules (pipeline/regional/_assoc_site.py and the
sources built on it). No network: the modules' curated data and the committed extracts only.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "regional"))
sys.path.insert(0, str(HERE))
import _assoc_site as A  # noqa: E402
import _projects as P  # noqa: E402
import merge as M  # noqa: E402

MODULES = ["sand_mountain", "mountaineers_everett", "snoqualmie_lookouts", "buck_rock", "anffla", "scmf_lookouts",
           "ffla_sdrc", "ffla_monterey", "hi_mountain", "mvffla", "historicorps_west", "siskiyou_mountain_club",
           "green_mountain_wa", "ffla_ca_south"]


def load(name):
    return importlib.import_module(name)


class Driver(unittest.TestCase):
    def test_event_and_doc_helpers(self):
        e = A.E(1999, "restored", "Roof.", "a", "b")
        self.assertEqual(e, {"year": 1999, "event": "restored", "note": "Roof.", "cite": ["a", "b"]})
        self.assertEqual(A.E(1999, "restored", "x", "a", inferred="why")["inferred"], "why")
        d = A.doc("x", "https://e.example/p/", "P", 2020, kind="pdf", page="https://e.example/")
        self.assertEqual((d["kind"], d["page"], d["year"]), ("pdf", "https://e.example/", 2020))
        self.assertTrue(A._cache_name(A.doc("y", "https://e.example/a/b/", "Y")).endswith(".html"))
        self.assertTrue(A._cache_name(d).endswith(".pdf"))

    def test_page_text_keeps_table_cells(self):
        html = "<table><tr><td>Year Built</td><td>1934</td></tr></table><script>var x=1999</script><p>Hello&nbsp;world</p>"
        text = A.page_text(html)
        self.assertIn("1934", text)
        self.assertNotIn("1999", text)
        self.assertIn("Hello", text)

    def test_inferred_years_are_not_checked(self):
        lookouts = [dict(slug="s", region="OR", events=[A.E(1968, "burned", "x", "d", inferred="next season"), A.E(1970, "restored", "y", "d")])]
        problems = ["src:or:s burned 1968 cites d: the report never mentions 1968",
                    "src:or:s restored 1970 cites d: the report never mentions 1970"]
        self.assertEqual(A.drop_inferred(problems, "src", lookouts), [problems[1]])

    def test_build_records_and_citation_check(self):
        docs = P.DocSet("t_assoc")
        spec = [A.doc("p", "https://e.example/p/", "P", 2020)]
        docs.add("p", "https://e.example/p/", "P", 2020)
        docs.texts["p"] = P.norm("Numa Ridge was repainted in 2019.")
        index = {"nhlr:US 1": {"lat": 48.1, "lon": -114.2}}
        lookouts = [dict(slug="numa-ridge", name="Numa Ridge Lookout", region="MT", tower="us-mt-numa-ridge", pos="nhlr:US 1",
                         find=["Numa Ridge"], status="standing", events=[A.E(2019, "restored", "Repainted.", "p")])]
        recs = A.build_records("t_assoc", {"name": "T", "url": "https://e.example/"}, spec, lookouts, docs, index=index)
        self.assertEqual(recs[0]["key"], "t_assoc:mt:numa-ridge")
        self.assertEqual((recs[0]["lat"], recs[0]["lon"]), (48.1, -114.2))
        self.assertEqual(recs[0]["url"], "https://e.example/p/")
        self.assertEqual(recs[0]["extra"]["tower_hint"], "us-mt-numa-ridge")
        self.assertEqual(P.check_citations(recs, {recs[0]["key"]: ["Numa Ridge"]}, docs), [])
        docs.texts["p"] = P.norm("Something else entirely.")
        self.assertEqual(len(P.check_citations(recs, {recs[0]["key"]: ["Numa Ridge"]}, docs)), 2)


class CuratedModules(unittest.TestCase):
    def test_cited_documents_exist_and_slugs_are_unique(self):
        for name in MODULES:
            m = load(name)
            ids = [d["id"] for d in m.DOCS]
            self.assertEqual(len(ids), len(set(ids)), name)
            keys = [(lk["region"], lk["slug"]) for lk in m.LOOKOUTS]
            self.assertEqual(len(keys), len(set(keys)), name)
            towers = [lk["tower"] for lk in m.LOOKOUTS]
            self.assertEqual(len(towers), len(set(towers)), name)
            for lk in m.LOOKOUTS:
                self.assertTrue(lk["events"], (name, lk["slug"]))
                self.assertTrue(lk["find"], (name, lk["slug"]))
                for e in lk["events"]:
                    self.assertTrue(e["cite"], (name, lk["slug"], e))
                    for c in e["cite"]:
                        self.assertIn(c, ids, (name, lk["slug"], c))

    def test_one_event_name_and_year_per_lookout(self):
        for name in MODULES:
            for lk in load(name).LOOKOUTS:
                seen = [(e["event"], e["year"]) for e in lk["events"]]
                self.assertEqual(len(seen), len(set(seen)), (name, lk["slug"]))

    def test_committed_extracts_are_valid_and_registered(self):
        for name in MODULES:
            path = HERE.parent / "data" / "sources" / f"{name}.json"
            self.assertTrue(path.exists(), name)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"], name)
            self.assertEqual(data["family"], "association_projects", name)
            self.assertIn(name, M.ASSOCIATION_SOURCES, name)
            self.assertEqual(P.validate_records(data["records"], source=name), [], name)
            # every record gave a position or says why not
            for r in data["records"]:
                self.assertIsNotNone(r["lat"], (name, r["key"]))


if __name__ == "__main__":
    unittest.main()
