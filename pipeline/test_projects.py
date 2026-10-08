"""Tests for pipeline/regional/_projects.py, the shared shape for association project sources.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "regional"))
import _projects as P  # noqa: E402

ASSOC = {"name": "Test Lookout Association", "url": "https://assoc.example/"}


def docs() -> P.DocSet:
    d = P.DocSet("test_assoc")
    d.add("p2025", "https://assoc.example/2025-projects/", "2025 projects", 2025)
    d.add("pdf2019", "https://assoc.example/2019.pdf", "2019 report (PDF)", 2019)
    return d


def good_record(d: P.DocSet, **kw) -> dict:
    return P.lookout_record(
        source="test_assoc", association=ASSOC, slug="numa-ridge", name="Numa Ridge Lookout", region="mt",
        url=d.url("p2025"), design="14x14-ft house on a 10-ft tower", height_ft=10, staffing="staffed",
        ownership="federal", status="standing",
        events=[d.event(2025, "assessed", "Condition assessment found the exterior needs work.", "p2025"),
                d.event(1934, "built", "Built.", ["p2025", "pdf2019"])],
        extra={"position_note": "test"}, **kw)


class Events(unittest.TestCase):
    def test_event_cites_documents(self):
        d = docs()
        e = d.event(1934, "built", "Built.", ["p2025", "pdf2019"])
        self.assertEqual(e["source_url"], "https://assoc.example/2025-projects/")
        self.assertEqual(e["source_urls"], ["https://assoc.example/2025-projects/", "https://assoc.example/2019.pdf"])
        self.assertEqual(e["from"], "test_assoc")
        one = d.event(2019, "restored", "x", "pdf2019")
        self.assertNotIn("source_urls", one)
        with self.assertRaises(ValueError):
            d.add("p2025", "https://assoc.example/other/", "again")

    def test_record_shape_and_sorted_events(self):
        d = docs()
        r = good_record(d)
        self.assertEqual(r["key"], "test_assoc:mt:numa-ridge")
        self.assertEqual(r["region"], "MT")
        self.assertEqual([e["year"] for e in r["events"]], [1934, 2025])
        ex = r["extra"]
        self.assertEqual(ex["association"], ASSOC)
        self.assertEqual((ex["height_ft"], ex["staffing_hint"], ex["ownership"]), (10, "staffed", "federal"))
        self.assertIsNone(r["lat"])


class Positions(unittest.TestCase):
    def test_position_copied_from_a_source_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "nhlr.json").write_text(json.dumps({"records": [
                {"key": "nhlr:US 38", "lat": 48.884021, "lon": -114.178979},
                {"key": "nhlr:US 99", "lat": None, "lon": None}]}))
            index = P.source_index(Path(tmp))
        self.assertEqual(P.position_from("nhlr:US 38", index), (48.88402, -114.17898))
        with self.assertRaises(KeyError):
            P.position_from("nhlr:US 99", index)
        with self.assertRaises(KeyError):
            P.position_from("nhlr:US 1", index)
        d = docs()
        r = P.lookout_record(source="test_assoc", association=ASSOC, slug="n", name="N", region="MT",
                             url=d.url("p2025"), position_key="nhlr:US 38", index=index)
        self.assertEqual((r["lat"], r["lon"]), (48.88402, -114.17898))
        self.assertEqual(r["extra"]["position_from"], "nhlr:US 38")


class Validation(unittest.TestCase):
    def problems(self, mutate) -> list[str]:
        d = docs()
        r = good_record(d)
        mutate(r, d)
        return P.validate_records([r], source="test_assoc", this_year=2026)

    def test_good_record_passes(self):
        self.assertEqual(self.problems(lambda r, d: None), [])

    def test_catches_the_mistakes_that_would_mangle_a_merge(self):
        def dup(r, d): r["events"].append(d.event(2025, "assessed", "again", "p2025"))
        self.assertTrue(any("same name and year" in p for p in self.problems(dup)))

        def vocab(r, d): r["events"][0]["event"] = "repaired"
        self.assertTrue(any("vocab.event" in p for p in self.problems(vocab)))

        def year(r, d): r["events"][0]["year"] = 2099
        self.assertTrue(any("whole year" in p for p in self.problems(year)))

        def nourl(r, d): r["events"][0].pop("source_url")
        self.assertTrue(any("source_url" in p for p in self.problems(nourl)))

        def other(r, d): r["events"][0].update(event="other", note=None)
        self.assertTrue(any("needs a note" in p or "note" in p for p in self.problems(other)))

        def longnote(r, d): r["events"][0]["note"] = "x" * 300
        self.assertTrue(any("at most" in p for p in self.problems(longnote)))

        def staffing(r, d): r["extra"]["staffing_hint"] = "sometimes"
        self.assertTrue(any("staffing_hint" in p for p in self.problems(staffing)))

        def lonely(r, d): r["lat"] = 48.0
        self.assertTrue(any("both" in p for p in self.problems(lonely)))

        def unsourced(r, d): r.update(lat=48.0, lon=-114.0); r["extra"].pop("position_note")
        self.assertTrue(any("position_from" in p for p in self.problems(unsourced)))

        def noassoc(r, d): r["extra"].pop("association")
        self.assertTrue(any("extra.association" in p for p in self.problems(noassoc)))

        def foreign(r, d): r["events"][0]["from"] = "someone_else"
        self.assertTrue(any("from must be" in p for p in self.problems(foreign)))

    def test_assessed_is_in_the_vocabulary(self):
        self.assertEqual(self.problems(lambda r, d: r["events"][0].update(event="assessed")), [])


class Citations(unittest.TestCase):
    def test_a_report_must_mention_the_lookout_and_the_year(self):
        d = docs()
        d.texts["p2025"] = P.norm("Numa Ridge Lookout was assessed. Built in 1934. 14x14-ft house")
        d.texts["pdf2019"] = P.norm("Another lookout entirely, Swiftcurrent, in 2019")
        r = good_record(d)
        out = P.check_citations([r], {r["key"]: ["Numa Ridge", "Numa"]}, d)
        self.assertEqual(len(out), 2, out)  # no lookout name and no 1934 in the 2019 report
        self.assertTrue(all("never mentions" in o and "pdf2019" in o for o in out), out)
        d.texts["pdf2019"] = P.norm("Numa Ridge, built 1934")
        self.assertEqual(P.check_citations([r], {r["key"]: ["Numa Ridge"]}, d), [])
        # an event of the report's own year needs no year in the text
        r2 = P.lookout_record(source="test_assoc", association=ASSOC, slug="n", name="N", region="MT", url=d.url("p2025"),
                              events=[d.event(2019, "restored", "Repainted.", "pdf2019")], extra={"position_note": "x"})
        d.texts["pdf2019"] = P.norm("Numa Ridge, repainted, no date")
        self.assertEqual(P.check_citations([r2], {r2["key"]: ["Numa Ridge"]}, d), [])

    def test_unread_reports_are_listed_not_failed(self):
        d = docs()
        r = good_record(d)
        out = P.check_citations([r], {r["key"]: ["Numa"]}, d)
        self.assertEqual(len(out), 1)
        self.assertIn("not checked", out[0])


class Writing(unittest.TestCase):
    def test_extract_carries_the_family_marker(self):
        d = docs()
        r = good_record(d)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "test_assoc.json"
            P.write_association_source(out, source="test_assoc", association=ASSOC, url="https://assoc.example/",
                                       retrieved="2026-10-08", license_="Facts only", records=[r])
            data = json.loads(out.read_text())
        self.assertEqual(data["family"], P.FAMILY)
        self.assertEqual(data["association"], ASSOC)
        self.assertEqual(data["source"], "test_assoc")
        self.assertEqual(data["title"], "Test Lookout Association")
        self.assertEqual(data["credit"], "Test Lookout Association")
        self.assertEqual(list(data)[-1], "records")
        self.assertNotIn("_cite", json.dumps(data))

    def test_invalid_records_are_refused(self):
        d = docs()
        r = good_record(d)
        r["events"][0]["event"] = "nonsense"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                P.write_association_source(Path(tmp) / "x.json", source="test_assoc", association=ASSOC,
                                           url="https://assoc.example/", retrieved="2026-10-08", license_="x", records=[r])
            self.assertFalse((Path(tmp) / "x.json").exists())


class Reading(unittest.TestCase):
    PAGE = ('<html><body><nav>skip</nav><article><div class="entry-content">'
            '<h2 class="wp-block-heading">Numa Ridge Lookout Assessment</h2>'
            '<figure><img src="a.jpg"></figure><p>Built in 1934, it is a 14&#215;14-ft house.</p>'
            '<h2>Glacier National Park</h2><h2>Unknown Peak Project</h2><p>Reroofed.</p>'
            '<script>var x=1</script></div></article><footer><p>footer</p></footer></body></html>')

    def test_sections(self):
        s = P.html_sections(self.PAGE)
        self.assertEqual([h for h, _ in s], ["", "Numa Ridge Lookout Assessment", "Glacier National Park", "Unknown Peak Project"])
        self.assertEqual(s[1][1], ["Built in 1934, it is a 14×14-ft house."])
        self.assertNotIn("footer", P.html_text(self.PAGE))
        self.assertEqual(P.unmatched_headings(s, ["Numa Ridge", "Glacier National Park"]), ["Unknown Peak Project"])

    def test_norm_and_squash(self):
        self.assertEqual(P.norm("Numa’s  14×14–ft"), "numa's 14x14-ft")
        self.assertEqual(P.squash_doubles("First First permanent permanent lookout"), "First permanent lookout")


if __name__ == "__main__":
    unittest.main()
