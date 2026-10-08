"""Smoke tests for build_site_data.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import build_site_data as bsd

FIXTURES = bsd.FIXTURES


def quiet() -> bsd.Log:
    return bsd.Log(quiet=True)


def tower(rid: str, **extra) -> dict:
    rec = {
        "id": rid,
        "name": rid.split("-", 2)[-1].replace("-", " ").title() + " Lookout",
        "other_names": [],
        "country": "US",
        "region": rid.split("-")[1].upper(),
        "county": None,
        "location": {"lat": 44.123456789, "lon": -121.987654321, "precision": "exact", "from": "ffla"},
        "kind": "tower",
        "status": "standing",
        "registers": [],
        "access": {"level": "public", "note": None},
        "rental": None,
        "events": [],
        "photos": [],
        "links": [],
        "sources": [{"source": "ffla", "key": "ffla:x", "fields": ["location"]}],
        "conflicts": [],
        "verification": "unverified",
        "hidden": False,
    }
    rec.update(extra)
    return rec


class BuildFromFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "data"
        cls.meta = bsd.build(
            FIXTURES / "towers",
            FIXTURES / "stories",
            FIXTURES / "photos",
            Path(cls.tmp.name) / "no-sources",
            bsd.DATA / "vocab.json",
            cls.out,
            fixtures=True,
            log=quiet(),
        )
        cls.geo = json.loads((cls.out / "towers.geojson").read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_every_visible_fixture_is_on_the_map(self) -> None:
        records = [json.loads(p.read_text()) for p in (FIXTURES / "towers").rglob("*.json")]
        visible = {r["id"] for r in records if not r.get("hidden")}
        self.assertTrue(visible, "fixtures are missing")
        self.assertEqual({f["properties"]["i"] for f in self.geo["features"]}, visible)
        self.assertEqual(self.meta["counts"]["total"], len(visible))
        self.assertEqual(self.meta["counts"]["hidden"], len(records) - len(visible))

    def test_hidden_records_are_not_published(self) -> None:
        hidden = [json.loads(p.read_text())["id"] for p in (FIXTURES / "towers").rglob("*.json") if json.loads(p.read_text()).get("hidden")]
        self.assertTrue(hidden)
        for rid in hidden:
            self.assertFalse((self.out / "t" / f"{rid}.json").exists())

    def test_geojson_is_compact_and_follows_the_contract(self) -> None:
        for f in self.geo["features"]:
            p = f["properties"]
            self.assertLessEqual(set(p), set(bsd.GEOJSON_FORMAT))
            for key in ("i", "n", "r", "k", "s", "v", "a"):
                self.assertIn(key, p)
            for key in ("rt", "rg"):
                self.assertIn(p.get(key, 1), (1,))
            for c in f["geometry"]["coordinates"]:
                self.assertEqual(c, round(c, 5))
        self.assertNotIn(b": ", (self.out / "towers.geojson").read_bytes()[:2000])

    def test_tower_files_have_the_full_record_and_story(self) -> None:
        for f in self.geo["features"]:
            rid = f["properties"]["i"]
            rec = json.loads((self.out / "t" / f"{rid}.json").read_text())
            self.assertEqual(rec["id"], rid)
        story = json.loads((self.out / "t" / "us-or-dutchmans-peak.json").read_text())["story_html"]
        self.assertIn('class="footnotes"', story)
        self.assertIn("&quot;the Dutchman&quot; &amp; still do", story)

    def test_meta_lists_sources_with_credit_lines(self) -> None:
        self.assertTrue(self.meta["fixtures"])
        by_id = {s["id"]: s for s in self.meta["sources"]}
        self.assertEqual(by_id["ridb"]["credit"], "Data source: ridb.recreation.gov")
        self.assertIn("OpenStreetMap contributors", by_id["osm"]["credit"])
        self.assertGreater(by_id["nhlr"]["towers"], 0)
        self.assertEqual(self.meta["counts"]["rentable"], sum(1 for f in self.geo["features"] if f["properties"].get("rt")))


def ev(year: int | None, event: str) -> dict:
    return {"year": year, "event": event, "note": None, "from": "nhlr"}


class YearRanges(unittest.TestCase):
    """The owner's rule: a tower counts as standing in a year if it was built on or before
    that year and not yet gone. Unknown stays unknown."""

    def yr(self, status: str, *events: dict) -> tuple:
        return bsd.year_range(tower("us-or-x", status=status, events=list(events)), 2026)

    def test_standing_tower_has_a_start_and_no_end(self) -> None:
        self.assertEqual(self.yr("standing", ev(1933, "built"), ev(1995, "nhlr_registered")), (1933, None))

    def test_earliest_build_year_wins(self) -> None:
        self.assertEqual(self.yr("standing", ev(1935, "built"), ev(1931, "built")), (1931, None))
        self.assertEqual(self.yr("standing", ev(1950, "replaced"), ev(1928, "staffed_first")), (1928, None))

    def test_gone_tower_ends_at_its_first_end_event(self) -> None:
        self.assertEqual(self.yr("gone", ev(1934, "built"), ev(1975, "removed")), (1934, 1975))
        self.assertEqual(self.yr("gone", ev(1934, "built"), ev(1962, "abandoned"), ev(1971, "destroyed")), (1934, 1962))
        self.assertEqual(self.yr("ruins", ev(1920, "built"), ev(1967, "burned")), (1920, 1967))

    def test_an_end_before_a_rebuild_does_not_end_it(self) -> None:
        events = (ev(1922, "built"), ev(1940, "burned"), ev(1942, "rebuilt"), ev(1981, "removed"))
        self.assertEqual(self.yr("gone", *events), (1922, 1981))
        # Burned and rebuilt, still standing: no end at all.
        self.assertEqual(self.yr("standing", ev(1922, "built"), ev(1940, "burned"), ev(1942, "rebuilt")), (1922, None))

    def test_abandoned_but_still_standing_has_not_come_down(self) -> None:
        self.assertEqual(self.yr("standing", ev(1933, "built"), ev(1970, "abandoned")), (1933, None))

    def test_unknown_values_stay_unknown(self) -> None:
        self.assertEqual(self.yr("gone"), (None, None))
        self.assertEqual(self.yr("gone", ev(1934, "built")), (1934, None))
        self.assertEqual(self.yr("gone", ev(1966, "destroyed")), (None, 1966))
        self.assertEqual(self.yr("unknown", ev(1934, "built")), (1934, None))
        self.assertEqual(self.yr("standing", ev(None, "built"), ev(1999, "nhlr_registered")), (None, None))

    def test_moved_structure_ends_the_original_site(self) -> None:
        self.assertEqual(self.yr("relocated", ev(1931, "built"), ev(1984, "relocated")), (1931, 1984))
        # At its new site it stands: the move is not an end.
        self.assertEqual(self.yr("standing", ev(1931, "built"), ev(1984, "relocated")), (1931, None))

    def test_implausible_years_are_ignored(self) -> None:
        self.assertEqual(self.yr("gone", ev(193, "built"), ev(2091, "removed")), (None, None))
        self.assertEqual(self.yr("gone", {"year": True, "event": "built"}), (None, None))

    def test_registration_years_are_not_build_or_end_dates(self) -> None:
        self.assertEqual(self.yr("gone", ev(1998, "fflos_registered")), (None, None))

    def test_counts_say_how_many_cannot_be_placed(self) -> None:
        h = bsd.history_counts([(1933, None, "standing"), (None, None, "standing"), (1934, 1975, "gone"), (1934, None, "gone"), (None, 1960, "gone"), (None, None, "gone"), (None, None, "unknown")], 2026)
        self.assertEqual(h["total"], 7)
        self.assertEqual(h["with_start"], 3)
        self.assertEqual(h["with_end"], 2)
        self.assertEqual(h["standing_now"], 2)
        self.assertEqual(h["complete"], 2)
        self.assertEqual(h["start_no_end"], 1)
        self.assertEqual(h["end_no_start"], 1)
        self.assertEqual(h["standing_no_start"], 1)
        self.assertEqual(h["no_dates"], 3)
        self.assertEqual(h["no_dates_not_standing"], 2)
        self.assertEqual(h["first_year"], 1933)


class RecordHandling(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.towers = self.root / "towers"
        (self.towers / "or").mkdir(parents=True)
        self.out = self.root / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, rec: object) -> None:
        text = rec if isinstance(rec, str) else json.dumps(rec)
        (self.towers / "or" / name).write_text(text)

    def build(self, **kw) -> dict:
        with contextlib.redirect_stderr(io.StringIO()):  # expected warnings
            return bsd.build(self.towers, self.root / "stories", self.root / "photos", self.root / "sources", bsd.DATA / "vocab.json", self.out, log=quiet(), **kw)

    def test_bad_records_are_skipped_not_fatal(self) -> None:
        self.write("good.json", tower("us-or-good", events=[{"year": 1935, "event": "built"}, {"year": 1931, "event": "built"}], rental={"available": True}, registers=[{"register": "NHLR"}], other_names=["Old | Name"]))
        self.write("broken.json", "{not json")
        self.write("traversal.json", {**tower("us-or-x"), "id": "../../etc/passwd"})
        self.write("nocoords.json", {**tower("us-or-nocoords"), "location": {"lat": None, "lon": None}})
        self.write("zz-dupe.json", tower("us-or-good"))  # sorted after good.json, so it is the duplicate
        self.write("hidden.json", tower("us-or-tree", kind="tree", hidden=True))
        meta = self.build()
        self.assertEqual(meta["counts"]["total"], 1)
        self.assertEqual(meta["counts"]["skipped"], 4)
        self.assertEqual(meta["counts"]["hidden"], 1)
        props = json.loads((self.out / "towers.geojson").read_text())["features"][0]["properties"]
        self.assertEqual(props, {"i": "us-or-good", "n": "Good Lookout", "r": "OR", "k": "tower", "s": "standing", "v": "unverified", "a": "public", "b": 1931, "rt": 1, "rg": 1, "o": "Old / Name", "y0": 1931})
        self.assertEqual(sorted(p.name for p in (self.out / "t").iterdir()), ["us-or-good.json"])

    def test_strict_mode_fails_on_bad_records(self) -> None:
        self.write("broken.json", "{not json")
        with self.assertRaises(SystemExit):
            self.build(strict=True)

    def test_unavailable_rental_is_not_rentable(self) -> None:
        self.write("a.json", tower("us-or-a", rental={"available": False}))
        self.build()
        props = json.loads((self.out / "towers.geojson").read_text())["features"][0]["properties"]
        self.assertNotIn("rt", props)

    def test_stale_tower_files_are_removed(self) -> None:
        self.write("a.json", tower("us-or-a"))
        self.build()
        (self.towers / "or" / "a.json").unlink()
        self.write("b.json", tower("us-or-b"))
        self.build()
        self.assertEqual(sorted(p.name for p in (self.out / "t").iterdir()), ["us-or-b.json"])

    def test_refuses_to_clear_a_folder_it_did_not_make(self) -> None:
        self.out.mkdir()
        (self.out / "important.txt").write_text("keep me")
        self.write("a.json", tower("us-or-a"))
        with self.assertRaises(SystemExit):
            self.build()
        self.assertTrue((self.out / "important.txt").exists())

    def test_photo_file_and_thumb_pass_through_unchanged(self) -> None:
        # pipeline/merge.py is what fills in file/thumb from data/photos_manifest.json; this
        # script neither copies photo files nor validates them -- the site resolves file/thumb
        # against site.config.json's photosBase at render time (web/src/render/tower.ts).
        self.write("a.json", tower("us-or-a", photos=[{"file": "bd/bdc82644.webp", "thumb": "bd/bdc82644.t.webp", "url": "https://example.org/1.jpg", "credit": "X"}]))
        self.build()
        rec = json.loads((self.out / "t" / "us-or-a.json").read_text())
        self.assertEqual(rec["photos"][0]["file"], "bd/bdc82644.webp")
        self.assertEqual(rec["photos"][0]["thumb"], "bd/bdc82644.t.webp")
        self.assertEqual(rec["photos"][0]["url"], "https://example.org/1.jpg")


class CommandLine(unittest.TestCase):
    def test_empty_towers_without_fallback_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = bsd.main(["--towers", str(Path(tmp) / "none"), "--out", str(Path(tmp) / "out"), "--quiet"])
            self.assertEqual(code, 2)
            self.assertIn("--fallback-fixtures", err.getvalue())

    def test_empty_towers_with_fallback_uses_fixtures_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = bsd.main(["--towers", str(Path(tmp) / "none"), "--out", str(Path(tmp) / "out"), "--fallback-fixtures", "--quiet"])
            self.assertEqual(code, 0)
            self.assertIn("USING FIXTURE DATA", out.getvalue())
            meta = json.loads((Path(tmp) / "out" / "meta.json").read_text())
            self.assertTrue(meta["fixtures"])
            self.assertGreater(meta["counts"]["total"], 10)


class Markdown(unittest.TestCase):
    def test_research_story_conventions(self):
        md = ("# Hager Mountain Lookout\n\nWatched since 1915.[^1][^2]\n\n"
              "[^1]: Hager Mountain Lookout, NHLR, http://nhlr.org/lookouts/us/or/hager-mountain-lookout/ (accessed 2026-10-04).\n"
              "[^2]: Hager Mtn., firelookout.com, https://www.firelookout.com/or/hagermtn.html (accessed 2026-10-04).\n")
        out = bsd.markdown_to_html(md, title="Hager Mountain Lookout")
        self.assertNotIn("Hager Mountain Lookout</h2>", out)  # the title heading is the page's h1
        self.assertIn("Hager Mountain Lookout</h2>", bsd.markdown_to_html(md, title="Another Lookout"))
        self.assertIn('<sup class="fnsep">,</sup>', out)      # 1,2 not 12
        self.assertIn('<a href="http://nhlr.org/lookouts/us/or/hager-mountain-lookout/" rel="noopener noreferrer">', out)
        self.assertIn("</a> (accessed 2026-10-04).", out)
        self.assertIn('class="fn-back"', out)

    def test_escapes_html_and_unsafe_links(self) -> None:
        out = bsd.markdown_to_html('<script>alert(1)</script> [a](javascript:alert(2)) [b](https://ok.org/?x=1&y=2)\n')
        self.assertNotIn("<script", out)
        self.assertNotIn("javascript:", out)
        self.assertIn('<a href="https://ok.org/?x=1&amp;y=2" rel="noopener noreferrer">b</a>', out)

    def test_structure(self) -> None:
        out = bsd.markdown_to_html("---\ntitle: x\n---\n# Head\n\n> Quoted\n\n- one\n- two\n\nText[^1].\n\n[^1]: Note.\n")
        self.assertNotIn("title: x", out)
        self.assertIn('<h2 id="s-head">Head</h2>', out)
        self.assertIn("<blockquote><p>Quoted</p></blockquote>", out)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)
        self.assertIn('<li id="fn-1">Note. <a href="#fnref-1"', out)

    def test_safe_href(self) -> None:
        for bad in ("javascript:x", "JAVASCRIPT:x", "java\tscript:x", "data:x", "vbscript:x"):
            self.assertIsNone(bsd.safe_href(bad), bad)
        for good in ("https://a.org", "http://a.org", "mailto:a@b.org", "#fn-1", "/firefinder/"):
            self.assertEqual(bsd.safe_href(good), good)


class SiteHistoryAndDesigns(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "towers" / "wa").mkdir(parents=True)
        (self.root / "sources").mkdir()
        self.out = self.root / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_geojson_carries_years_and_designs_and_meta_counts_them(self) -> None:
        recs = [
            tower("us-wa-a", region="WA", design="L-4 ground cab", events=[ev(1935, "built")], sources=[{"source": "ffla", "key": "ffla:wa:a"}]),
            tower("us-wa-b", region="WA", status="gone", events=[ev(1932, "built"), ev(1968, "removed")], sources=[{"source": "fl", "key": "fl:b"}]),
            tower("us-wa-c", region="WA", status="gone", design="Steel tower with 10x10 ft cab"),
        ]
        for r in recs:
            (self.root / "towers" / "wa" / f"{r['id']}.json").write_text(json.dumps(r))
        (self.root / "sources" / "fl.json").write_text(json.dumps({"source": "fl", "records": [{"key": "fl:b", "type_raw": "Tower", "extra": {"design": "Aermotor MC-39"}}]}))
        facts = self.root / "designs.json"
        facts.write_text(json.dumps({"designs": [{"id": "l4", "name": "L-4"}, {"id": "aermotor", "name": "Aermotor", "family": "aermotor"}, {"id": "r6", "name": "R-6"},
                                                 {"id": "aermotor_mc39", "name": "Aermotor MC-39", "family": "aermotor"}]}))
        meta = bsd.build(self.root / "towers", self.root / "stories", self.root / "p", self.root / "sources", bsd.DATA / "vocab.json", self.out, log=quiet(), designs_path=facts, mentions_path=self.root / "none.json", this_year=2026)
        props = {f["properties"]["i"]: f["properties"] for f in json.loads((self.out / "towers.geojson").read_text())["features"]}
        self.assertEqual((props["us-wa-a"]["y0"], props["us-wa-a"].get("y1"), props["us-wa-a"]["d"]), (1935, None, "l4"))
        self.assertEqual((props["us-wa-b"]["y0"], props["us-wa-b"]["y1"], props["us-wa-b"]["d"]), (1932, 1968, "aermotor_mc39|aermotor"))
        self.assertNotIn("y0", props["us-wa-c"])
        self.assertNotIn("d", props["us-wa-c"])
        self.assertEqual(meta["history"]["no_dates"], 1)
        self.assertEqual(meta["designs"], {"total": 3, "with_design_text": 3, "recognised": 2, "by_design": {"l4": 1, "aermotor": 1, "r6": 0, "aermotor_mc39": 1}, "unmatched_text": 1})
        guide = json.loads((self.out / "designs.json").read_text())
        self.assertEqual([d["id"] for d in guide["designs"]], ["l4", "aermotor", "r6", "aermotor_mc39"])
        mc39 = guide["designs"][3]["towers"][0]
        # The source's wording is the design's own name, so it is not repeated.
        self.assertEqual((mc39["i"], mc39.get("w")), ("us-wa-b", None))
        self.assertEqual(guide["designs"][0]["towers"][0]["w"], "L-4 ground cab")
        rec = json.loads((self.out / "t" / "us-wa-b.json").read_text())
        # The page names the model only; the map filter (d above) also carries the family.
        self.assertEqual(rec["design_ids"], ["aermotor_mc39"])

    def test_families_pairs_mentions_and_examples(self) -> None:
        recs = [
            tower("us-or-a", region="OR", sources=[{"source": "nhlr", "key": "nhlr:US 1"}]),
            tower("us-or-b", region="OR", design="Aermotor MC-39 steel tower"),
            tower("us-or-c", region="OR", design="R-6 cab that replaced an L-4"),
            tower("us-or-d", region="OR", status="gone", sources=[{"source": "ridb", "key": "ridb:1"}]),
            tower("us-or-e", region="OR"),
            tower("us-or-f", region="OR", sources=[{"source": "nhlr", "key": "nhlr:US 2"}]),
        ]
        for r in recs:
            (self.root / "towers" / "wa" / f"{r['id']}.json").write_text(json.dumps(r))
        # A prose field in an extract: only the design names count, never the text.
        (self.root / "sources" / "ridb.json").write_text(json.dumps({"source": "ridb", "records": [{"key": "ridb:1", "extra": {"description": "Built in 1933, this Aermotor tower with a 7x7 cab..."}}]}))
        mentions = self.root / "mentions.json"
        mentions.write_text(json.dumps({"mentions": {"nhlr:US 1": ["CT-2", "L-4"], "nhlr:US 2": ["R-6", "Aermotor"]}, "several_structures": ["nhlr:US 2"]}))
        facts = self.root / "designs.json"
        facts.write_text(json.dumps({"designs": [
            {"id": "l4", "name": "L-4", "family": "l4", "part": "cab"},
            {"id": "r6", "name": "R-6", "family": "r6", "part": "cab"},
            {"id": "r6_timber_towers", "name": "Region 6 timber towers", "family": "r6_timber_towers", "part": "tower"},
            {"id": "aermotor", "name": "Aermotor", "family": "aermotor", "part": "tower"},
            {"id": "aermotor_mc39", "name": "Aermotor MC-39", "family": "aermotor", "part": "tower"},
            {"id": "chimney_rock", "name": "Chimney Rock", "family": "chimney_rock", "part": "whole", "examples": [{"id": "us-or-e", "note": "Built to this plan"}]},
        ]}))
        bsd.build(self.root / "towers", self.root / "stories", self.root / "p", self.root / "sources", bsd.DATA / "vocab.json", self.out, log=quiet(), designs_path=facts, mentions_path=mentions, this_year=2026)
        rec = lambda i: json.loads((self.out / "t" / f"{i}.json").read_text())  # noqa: E731
        self.assertEqual((rec("us-or-a")["design_ids"], rec("us-or-a")["design_pair"]), (["r6_timber_towers", "l4"], {"cab": "l4", "tower": "r6_timber_towers"}))
        self.assertEqual(rec("us-or-b")["design_pair"], {"tower": "aermotor_mc39"})
        self.assertNotIn("design_pair", rec("us-or-c"))  # two cabs: an earlier one and today's
        # "An R-6 cab replaced the Aermotor": both named, but not as one lookout.
        self.assertEqual(rec("us-or-f")["design_ids"], ["r6", "aermotor"])
        self.assertNotIn("design_pair", rec("us-or-f"))
        self.assertEqual(rec("us-or-d")["design_ids"], ["aermotor"])
        self.assertEqual((rec("us-or-e")["design_ids"], rec("us-or-e")["design_pair"]), (["chimney_rock"], {"whole": "chimney_rock"}))
        guide = {d["id"]: d for d in json.loads((self.out / "designs.json").read_text())["designs"]}
        # The family head counts both Aermotors but lists only the one with no model recorded.
        aer = guide["aermotor"]
        self.assertEqual((aer["count"], aer["count_unspecified"], [t["i"] for t in aer["towers"]]), (3, 2, ["us-or-d", "us-or-f"]))
        self.assertEqual(aer["members"], [{"id": "aermotor_mc39", "name": "Aermotor MC-39", "count": 1}])
        self.assertEqual(aer["towers"][0].get("w"), None)  # the bare word "Aermotor" says no more than the name
        self.assertEqual(guide["chimney_rock"]["towers"][0]["w"], "Built to this plan")
        self.assertEqual(guide["r6_timber_towers"]["towers"][0]["m"], ["CT-2"])

    def test_sites_with_no_structure_are_shown_but_counted_apart(self) -> None:
        recs = [
            tower("us-wa-a", region="WA", material="steel", material_from="nhlr", events=[ev(1935, "built")]),
            tower("us-wa-b", region="WA", kind="camp", status="gone", events=[ev(1920, "built")]),
            tower("us-wa-c", region="WA", kind="point", status="gone"),
        ]
        for r in recs:
            (self.root / "towers" / "wa" / f"{r['id']}.json").write_text(json.dumps(r))
        (self.root / "sources" / "ffla.json").write_text(json.dumps({"source": "ffla", "records": [
            {"key": "ffla:1", "type_raw": "Firefinder"}, {"key": "ffla:2", "type_raw": "Map Board"}, {"key": "ffla:3", "type_raw": "Map Board"}]}))
        meta = bsd.build(self.root / "towers", self.root / "stories", self.root / "p", self.root / "sources", bsd.DATA / "vocab.json", self.out, log=quiet(), this_year=2026)
        props = {f["properties"]["i"]: f["properties"] for f in json.loads((self.out / "towers.geojson").read_text())["features"]}
        self.assertEqual(set(props), {"us-wa-a", "us-wa-b", "us-wa-c"})
        self.assertEqual(props["us-wa-a"]["m"], "steel")
        self.assertNotIn("m", props["us-wa-b"])
        counts = meta["counts"]
        self.assertEqual((counts["total"], counts["structures"], counts["no_structure"]), (3, 1, 2))
        self.assertEqual(counts["by_material"], {"steel": 1})
        # "Lookouts standing in a year" counts structures only.
        self.assertEqual(meta["history"]["total"], 1)
        guide = json.loads((self.out / "structure_kinds.json").read_text())
        kinds = {k["id"]: k for k in guide["kinds"]}
        self.assertEqual((kinds["camp"]["count"], kinds["point"]["count"], kinds["tower"]["count"]), (1, 1, 1))
        self.assertEqual(kinds["point"]["source_words"], ["Map Board", "Firefinder"])
        self.assertEqual({g["id"]: g["count"] for g in guide["groups"]}, {"structure": 1, "no_structure": 2})
        self.assertEqual(guide["counts"], {"structures": 1, "no_structure": 2, "with_material": 1})


if __name__ == "__main__":
    unittest.main()
