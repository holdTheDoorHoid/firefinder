"""Tests for merge.py and validate.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import contextlib
import io
import json
import random
import tempfile
import unittest
from pathlib import Path

import merge as M
import validate as V

TODAY = "2026-10-04"


def rec(source: str, key: str, name: str | None, lat: float | None, lon: float | None, region: str = "ID", **kw) -> dict:
    r = {
        "key": f"{source}:{key}", "url": f"https://example.org/{source}/{key}", "name": name,
        "country": "US", "region": region, "county": kw.pop("county", None),
        "lat": lat, "lon": lon, "elevation_m": None, "type_raw": None,
        "kind": kw.pop("kind", "tower"), "status_raw": None, "status": kw.pop("status", "standing"),
        "registers": kw.pop("registers", []), "built": kw.pop("built", None), "agency": None,
        "events": [], "photos": kw.pop("photos", []), "links": [], "rental": kw.pop("rental", None),
        "extra": kw.pop("extra", {}),
    }
    r.update(kw)
    return r


def write_sources(folder: Path, by_source: dict[str, list[dict]]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for sid, records in by_source.items():
        (folder / f"{sid}.json").write_text(json.dumps({
            "source": sid, "title": sid, "url": "https://example.org/", "retrieved": TODAY,
            "license": "test", "records": records}), encoding="utf-8")


class Workspace:
    """A temporary sources/towers/report layout for one test."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.sources, self.towers, self.report = root / "sources", root / "towers", root / "report.json"
        self.research = root / "research"

    def run(self, by_source: dict[str, list[dict]] | None = None, photos_manifest: dict | None = None) -> dict:
        if by_source is not None:
            for f in self.sources.glob("*.json"):
                f.unlink()
            write_sources(self.sources, by_source)
        with contextlib.redirect_stdout(io.StringIO()):
            # photos_manifest defaults to {} (not the real data/photos_manifest.json) so tests
            # are hermetic; pass an explicit dict to test the manifest wiring itself.
            return M.run(self.sources, self.towers, self.report, TODAY, log=lambda *a, **k: None,
                         photos_manifest=photos_manifest if photos_manifest is not None else {},
                         research_dir=self.research)

    def write_research(self, data: dict) -> None:
        self.research.mkdir(parents=True, exist_ok=True)
        (self.research / f"{data['id']}.json").write_text(json.dumps(data), encoding="utf-8")

    def towers_by_id(self) -> dict[str, dict]:
        return {p.stem: json.loads(p.read_text()) for p in self.towers.rglob("*.json")}

    def tower_with_key(self, key: str) -> dict:
        hits = [t for t in self.towers_by_id().values() if any(s["key"] == key for s in t["sources"])]
        assert len(hits) == 1, (key, [t["id"] for t in hits])
        return hits[0]

    def close(self) -> None:
        self.tmp.cleanup()


class NameNormalisation(unittest.TestCase):
    def s(self, a: str, b: str):
        return M.name_score(M.name_forms(a), M.name_forms(b))

    def test_clean_name(self):
        self.assertEqual(M.clean_name("Bigelow, Mount"), "Mount Bigelow")
        self.assertEqual(M.clean_name("George, Mount Lookout"), "Mount George Lookout")
        self.assertEqual(M.clean_name("BALD KNOB LOOKOUT"), "Bald Knob Lookout")
        self.assertEqual(M.clean_name("MCGUIRE MTN"), "McGuire Mtn")
        self.assertEqual(M.clean_name("Brownâ\u0080\u0099s Mountain"), "Brown’s Mountain")
        self.assertIsNone(M.clean_name("unnamed"))
        self.assertEqual(M.clean_ridb_name("MCGUIRE MTN. LOOKOUT RENTAL"), "McGuire Mountain Lookout")
        self.assertEqual(M.clean_ridb_name("Cone Peak Lookout - 4E12"), "Cone Peak Lookout")
        self.assertEqual(M.clean_ridb_name("Mt. Harrison Lookout"), "Mt. Harrison Lookout")

    def test_same_lookout_spellings(self):
        self.assertEqual(self.s("Bald Mtn. L.O.", "Bald Mountain Lookout"), 1.0)
        self.assertEqual(self.s("Mt. Tom Fire Lookout", "Tom, Mount"), 1.0)
        self.assertGreaterEqual(self.s("Abbot Butte", "Abbot Butte Lookout"), 0.95)
        self.assertGreaterEqual(self.s("Abbot Butte", "Abbot"), 0.95)
        self.assertGreaterEqual(self.s("Sugarloaf", "Sugar Loaf Fire Tower"), 0.95)
        self.assertGreaterEqual(self.s("Napolean Hill", "Napoleon Hill Lookout"), M.STRONG)
        self.assertGreaterEqual(self.s("Lookout Mountain", "Lookout Mtn."), 0.95)
        self.assertGreaterEqual(self.s("Putnam (Liberty)", "Liberty"), 0.95)

    def test_different_lookouts(self):
        # Peak/Mountain/Butte are stripped, but Knob is not: no strong match
        self.assertLess(self.s("Bald Mountain", "Bald Knob"), M.STRONG)
        self.assertLess(self.s("Crescent Lake North", "Crescent Lake South"), M.PARTIAL)
        self.assertLess(self.s("Chilco Mountain (North)", "Chilco Mountain Lookout – South"), M.PARTIAL)
        self.assertLess(self.s("Valentine NWR 1", "Valentine NWR 2"), M.PARTIAL)
        self.assertLess(self.s("Mineral Mountain", "Mission Mountain"), M.STRONG)
        self.assertLess(self.s("Little Baldy", "Baldy"), M.STRONG)
        # a moved structure's origin is a different place, not another name for this one
        self.assertLess(self.s("Colville Museum (Relocated Graves Mountain)", "Graves Mountain Lookout"), M.PARTIAL)

    def test_generic_names_have_no_score(self):
        self.assertIsNone(self.s("Fire Tower", "Bald Mountain"))
        self.assertIsNone(self.s("Lookout Tower", "Bald Mountain"))
        self.assertTrue(M.name_forms("Lookout Mountain"))

    def test_slug(self):
        self.assertEqual(M.slugify("Dutchman Peak Lookout"), "dutchman-peak")
        self.assertEqual(M.slugify("Hunter Mountain Fire Tower"), "hunter-mountain")
        self.assertEqual(M.slugify("Grandview Lookout Tree"), "grandview-lookout-tree")
        self.assertEqual(M.slugify("Mestaa’ėhehe Mountain Fire Lookout"), "mestaaehehe-mountain")
        self.assertEqual(M.slugify("Lookout"), "lookout")


class RegisterParsing(unittest.TestCase):
    def test_us_numbers(self):
        for raw in ("US 592", "US592", "US #592", "us 592", "592"):
            g = M.normalize_register({"register": "NHLR", "number": raw, "state_number": "OR 23"})
            self.assertEqual(g["number"], "US 592", raw)
            self.assertEqual(g["state_number"], "OR 23")

    def test_register_name_is_part_of_the_key(self):
        nhlr = M.register_keys(M.normalize_register({"register": "NHLR", "number": "US 674"}))
        fflos = M.register_keys(M.normalize_register({"register": "FFLOS", "number": "US 674"}))
        self.assertEqual(nhlr, ["NHLR US 674"])
        self.assertTrue(set(nhlr).isdisjoint(fflos))

    def test_nrhp(self):
        g = M.normalize_register({"register": "NRHP", "number": "1001038"})
        self.assertEqual(g["number"], "01001038")
        self.assertEqual(M.register_keys(g), ["NRHP 1001038"])
        self.assertIn("npgallery", M.register_url(g))

    def test_state_number_only_and_junk(self):
        g = M.normalize_register({"register": "NHLR", "number": "ID 100"})
        self.assertIsNone(g["number"])
        self.assertEqual(g["state_number"], "ID 100")
        self.assertIsNone(M.normalize_register({"register": "NHLR", "number": None}))
        self.assertIsNone(M.normalize_register({"number": "US 5"}))


class Matching(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_positive_matches(self):
        self.ws.run({
            "ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR", status="gone"),
                     rec("ffla", "b", "Hidden Peak", 46.3712, -114.4634, registers=[{"register": "NHLR", "number": "US 946"}])],
            "firelookout_com": [rec("firelookout_com", "a", "Abbot Butte", 44.5577, -121.7088, "OR", status="gone")],
            "idaho_fl": [rec("idaho_fl", "a", "Abbot Butte Lookout", 44.5600, -121.7150, "OR", status="gone")],
            "osm": [rec("osm", "n1", "Fire Tower", 44.5579, -121.7090, "OR")],
            "nhlr": [rec("nhlr", "US 946", "Hidden Peak Lookout", 46.3800, -114.4700,
                         registers=[{"register": "NHLR", "number": "US 946", "state_number": "ID 100"}])],
        })
        abbot = self.ws.tower_with_key("ffla:a")
        self.assertEqual({s["source"] for s in abbot["sources"]}, {"ffla", "firelookout_com", "idaho_fl", "osm"})
        self.assertEqual(abbot["name"], "Abbot Butte Lookout")  # suffix borrowed from idaho_fl
        hidden = self.ws.tower_with_key("nhlr:US 946")
        self.assertEqual({s["source"] for s in hidden["sources"]}, {"nhlr", "ffla"})
        self.assertEqual(hidden["name"], "Hidden Peak Lookout")
        self.assertEqual(hidden["location"]["from"], "nhlr")

    def test_negative_matches(self):
        self.ws.run({
            # Bald Mountain and Bald Knob 1 km apart: two lookouts
            "ffla": [rec("ffla", "bm", "Bald Mountain", 45.0, -115.0),
                     # two FFLA rows 300 m apart with different names stay apart
                     rec("ffla", "x", "Cougar Point", 46.0, -115.0),
                     rec("ffla", "y", "Elk Point", 46.0027, -115.0),
                     # same register number but different register: different lookouts
                     rec("ffla", "z", "Apache Maid", 34.726, -111.551, "AZ", registers=[{"register": "NHLR", "number": "US 674"}])],
            "osm": [rec("osm", "bk", "Bald Knob", 45.009, -115.0)],
            "fflos": [rec("fflos", "US 674", "Buzzard Butte Lookout Site", 45.278, -123.878, "OR", status="gone",
                          registers=[{"register": "FFLOS", "number": "US 674"}])],
        })
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 6)
        self.assertNotEqual(self.ws.tower_with_key("ffla:bm")["id"], self.ws.tower_with_key("osm:bk")["id"])
        self.assertNotEqual(self.ws.tower_with_key("ffla:x")["id"], self.ws.tower_with_key("ffla:y")["id"])
        self.assertNotEqual(self.ws.tower_with_key("ffla:z")["id"], self.ws.tower_with_key("fflos:US 674")["id"])

    def test_same_source_only_when_double_listed(self):
        self.ws.run({
            # FFLA repeats a row (same name, same place): one lookout
            "ffla": [rec("ffla", "d1", "Dagsboro", 38.5647, -75.2506, "DE"),
                     rec("ffla", "d2", "Dagsboro", 38.5647, -75.2506, "DE")],
            # NHLR never double-lists: two entries at one spot stay two towers
            "nhlr": [rec("nhlr", "US 1", "Flintkote Lookout Tower", 31.0, -89.0, "MS"),
                     rec("nhlr", "US 2", "Flintkote Lookout Tower", 31.0, -89.0, "MS")],
        })
        self.assertEqual(self.ws.tower_with_key("ffla:d1")["id"], self.ws.tower_with_key("ffla:d2")["id"])
        self.assertNotEqual(self.ws.tower_with_key("nhlr:US 1")["id"], self.ws.tower_with_key("nhlr:US 2")["id"])

    def test_near_miss_is_reported_not_merged(self):
        rep = self.ws.run({
            "ffla": [rec("ffla", "a", "Blue Joe", 48.90, -116.50)],
            "idaho_fl": [rec("idaho_fl", "a", "Blue Joe", 48.935, -116.50)],  # ~3.9 km north
        })
        self.assertEqual(len(self.ws.towers_by_id()), 2)
        self.assertEqual(rep["near_misses"]["count"], 1)
        self.assertEqual(rep["near_misses"]["pairs"][0]["type"], "same_name_apart")

    def test_no_coordinates(self):
        rep = self.ws.run({
            "ffla": [rec("ffla", "a", "Spyglass Peak", 47.842, -116.197, county="Kootenai"),
                     rec("ffla", "b", "Nowhere Point", None, None)],
            "ridb": [rec("ridb", "1", "SPYGLASS PEAK LOOKOUT", None, None)],
        })
        self.assertEqual({s["source"] for s in self.ws.tower_with_key("ffla:a")["sources"]}, {"ffla", "ridb"})
        self.assertEqual([u["key"] for u in rep["unplaced"]], ["ffla:b"])

    def test_sites_with_no_structure_are_shown(self):
        # Owner decision 2026-10-08: camps, lookout trees and bare points are shown (the map
        # leaves them off by default); data/structure_kinds.json can hide a kind again.
        self.ws.run({"ffla": [rec("ffla", "t", "Grandview", 35.94, -111.98, "AZ", kind="tree"),
                              rec("ffla", "c", "Bear Point", 45.5, -115.5, kind="camp"),
                              rec("ffla", "p", "Burgard", 44.5, -116.5, type_raw="Firefinder", kind="unknown",
                                  status_raw="Abandoned", status="gone")]})
        tree = self.ws.tower_with_key("ffla:t")
        self.assertFalse(tree["hidden"])
        self.assertEqual(tree["kind"], "tree")
        self.assertFalse(self.ws.tower_with_key("ffla:c")["hidden"])
        point = self.ws.tower_with_key("ffla:p")
        self.assertEqual((point["kind"], point["hidden"], point["material"]), ("point", False, None))

    def test_a_hidden_kind_is_hidden(self):
        saved = dict(M.HIDDEN_KIND_REASON)
        M.HIDDEN_KIND_REASON["tree"] = "Tree platform: out of scope (structures only)"
        try:
            self.ws.run({"ffla": [rec("ffla", "t", "Grandview", 35.94, -111.98, "AZ", kind="tree")]})
        finally:
            M.HIDDEN_KIND_REASON.clear()
            M.HIDDEN_KIND_REASON.update(saved)
        tree = self.ws.tower_with_key("ffla:t")
        self.assertTrue(tree["hidden"])
        self.assertIn("Tree", tree["hidden_reason"])

    def test_a_structure_from_another_source_beats_a_bare_point(self):
        self.ws.run({"ffla": [rec("ffla", "p", "Prairie City", 44.46, -118.7, "OR", type_raw="Firefinder", kind="unknown")],
                     "osm": [rec("osm", "n1", "Prairie City Lookout", 44.4601, -118.7, "OR", kind="ground")]})
        self.assertEqual(self.ws.tower_with_key("ffla:p")["kind"], "ground")

    def test_kind_material_and_roles(self):
        self.ws.run({
            "ffla": [rec("ffla", "a", "Shadow Mtn.", 40.2, -105.8, "CO", type_raw="Stone Tower", kind="tower"),
                     rec("ffla", "b", "Rising Sun AWS", 39.7, -76.06, "MD", type_raw="AWS Tower", kind="tower"),
                     rec("ffla", "c", "Sawtooth Valley", 43.9, -114.9, "ID", type_raw="Rooftop", kind="unknown"),
                     rec("ffla", "d", "Big Butte", 46.1, -117.2, "WA", status_raw="Standing*")],
            "nhlr": [rec("nhlr", "US 9", "Bald Knob", 45.0, -116.0, kind="unknown",
                         extra={"structure_words": ["kind tower", "steel tower"]})],
            "firelookout_com": [rec("firelookout_com", "x", "Bald Knob", 45.0, -116.0, kind="tower", type_raw="Tower",
                                    extra={"design": "L-4"}),
                                rec("firelookout_com", "y", "Hat Point", 45.4, -116.66, "OR", kind="ground", type_raw="Cabin",
                                    extra={"design": "L-4"})],
        })
        shadow = self.ws.tower_with_key("ffla:a")
        self.assertEqual((shadow["kind"], shadow["material"], shadow["material_from"]), ("tower", "stone", "ffla"))
        self.assertEqual(self.ws.tower_with_key("ffla:b")["roles"], ["aws"])
        self.assertEqual(self.ws.tower_with_key("ffla:c")["kind"], "rooftop")
        big = self.ws.tower_with_key("ffla:d")
        self.assertEqual(big["status"], "standing")
        self.assertIn("cab is gone", big["status_note"])
        knob = self.ws.tower_with_key("nhlr:US 9")
        self.assertEqual((knob["kind"], knob["material"], knob["material_from"]), ("tower", "steel", "nhlr"))
        self.assertIn("material", next(s for s in knob["sources"] if s["source"] == "nhlr")["fields"])
        # An L-4 ground cab is wood by its design; an L-4 on a tower says nothing about the tower.
        hat = self.ws.tower_with_key("firelookout_com:y")
        self.assertEqual((hat["material"], hat["material_from"]), ("wood", "design"))

    def test_conflicts_and_verification(self):
        self.ws.run({
            "ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0, status="gone"),
                     rec("ffla", "b", "Iron Mountain", 45.5, -116.0)],
            "firelookout_com": [rec("firelookout_com", "a", "Gold Hill", 45.0, -116.0, status="standing", built=1931),
                                rec("firelookout_com", "b", "Iron Mountain", 45.5, -116.0, built=1930)],
            "idaho_fl": [rec("idaho_fl", "a", "Gold Hill Lookout", 45.006, -116.0, status="gone")],
            "osm": [rec("osm", "b", "Iron Mountain Lookout", 45.5002, -116.0, built=1932)],
        })
        gold = self.ws.tower_with_key("ffla:a")
        fields = {c["field"]: c for c in gold["conflicts"]}
        self.assertIn("status", fields)
        self.assertIn("location", fields)  # idaho_fl is ~670 m off
        self.assertGreater(fields["location"]["distance_m"], 500)
        # FFLA and firelookout.com share lineage; idaho_fl is > 500 m away: not "facts"
        self.assertEqual(gold["verification"], "unverified")
        iron = self.ws.tower_with_key("ffla:b")
        self.assertEqual(iron["verification"], "facts")  # FFLA + OSM, independent, agree
        self.assertEqual({c["field"] for c in iron["conflicts"]}, {"built"})

    def test_output_passes_validation(self):
        self.ws.run({"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0)],
                     "wikidata": [rec("wikidata", "Q1", "Gold Hill Lookout", 45.0001, -116.0,
                                      photos=[{"url": "https://commons.wikimedia.org/wiki/File:X.jpg", "credit": None}])]})
        vocab = json.loads((M.DATA / "vocab.json").read_text())
        for path in self.ws.towers.rglob("*.json"):
            errs, _ = V.check(json.loads(path.read_text()), path, vocab)
            self.assertEqual(errs, [], path)
        t = self.ws.tower_with_key("ffla:a")
        self.assertEqual(set(t["photos"][0]), {"file", "thumb", "url", "source_url", "credit", "license", "caption", "year"})
        self.assertTrue(t["photos"][0]["url"].startswith("https://upload.wikimedia.org/wikipedia/commons/"))

    def test_photographer_hidden_in_a_register_caption_is_credited(self):
        # The DESIGN.md example: a register photo whose caption carries the photographer,
        # while the structured credit field is empty (so photo_entry() falls back to just
        # the site name) until extract_photo_credit() pulls it out of the caption.
        self.ws.run({"nhlr": [rec("nhlr", "US1", "Model Lookout", 45.0, -116.0,
                                  photos=[{"url": "http://nhlr.org/p.jpg", "credit": None,
                                           "caption": "9/10/05--Cabin (Bob Eckler photo-courtesy Bill Starr)",
                                           "year": None}])]})
        photo = self.ws.tower_with_key("nhlr:US1")["photos"][0]
        self.assertEqual(photo["caption"], "9/10/05--Cabin")
        self.assertEqual(photo["credit"],
                         "Bob Eckler (courtesy Bill Starr), via National Historic Lookout Register (nhlr.org)")

    def test_a_caption_with_no_extractable_credit_is_untouched(self):
        self.ws.run({"nhlr": [rec("nhlr", "US1", "Model Lookout", 45.0, -116.0,
                                  photos=[{"url": "http://nhlr.org/p.jpg", "credit": None,
                                           "caption": "Historical Photo", "year": None}])]})
        photo = self.ws.tower_with_key("nhlr:US1")["photos"][0]
        self.assertEqual(photo["caption"], "Historical Photo")
        self.assertEqual(photo["credit"], "National Historic Lookout Register (nhlr.org)")

    def test_an_existing_structured_credit_is_not_reparsed(self):
        # The old (narrower) fetch_registers.py extraction already pulled this one out; the
        # merge-time backfill only runs when the structured credit field is empty.
        self.ws.run({"nhlr": [rec("nhlr", "US1", "Model Lookout", 45.0, -116.0,
                                  photos=[{"url": "http://nhlr.org/p.jpg", "credit": "Jane Smith",
                                           "caption": "1990 photo", "year": None}])]})
        photo = self.ws.tower_with_key("nhlr:US1")["photos"][0]
        self.assertEqual(photo["caption"], "1990 photo")
        self.assertEqual(photo["credit"], "Jane Smith, via National Historic Lookout Register (nhlr.org)")


class PhotoManifest(unittest.TestCase):
    """data/photos_manifest.json (pipeline/mirror_photos.py) fills in file/thumb/w/h, and a
    photo the mirror step could not use is dropped rather than kept as a dead link."""

    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def sources(self) -> dict[str, list[dict]]:
        return {"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0, photos=[
            {"url": "http://nhlr.org/photos/ok.jpg", "credit": "A"},
            {"url": "http://nhlr.org/photos/bad.jpg", "credit": "B"},
            {"url": "http://nhlr.org/photos/icon.jpg", "credit": "C"},
            {"url": "http://nhlr.org/photos/unmirrored.jpg", "credit": "D"},
        ])]}

    def test_no_manifest_leaves_file_and_thumb_null(self) -> None:
        self.ws.run(self.sources())
        t = self.ws.tower_with_key("ffla:a")
        self.assertEqual(len(t["photos"]), 4)
        self.assertTrue(all(p["file"] is None and p["thumb"] is None for p in t["photos"]))

    def test_manifest_fills_in_ok_and_drops_failed_and_skipped(self) -> None:
        manifest = {
            "http://nhlr.org/photos/ok.jpg": {"file": "ab/ab12.webp", "thumb": "ab/ab12.t.webp",
                                               "w": 800, "h": 600, "bytes": 1234, "status": "ok", "reason": None},
            "http://nhlr.org/photos/bad.jpg": {"file": None, "thumb": None, "w": None, "h": None,
                                                "bytes": None, "status": "failed", "reason": "http_404"},
            "http://nhlr.org/photos/icon.jpg": {"file": None, "thumb": None, "w": 40, "h": 40,
                                                 "bytes": None, "status": "skipped", "reason": "too small (40x40px)"},
        }
        self.ws.run(self.sources(), photos_manifest=manifest)
        t = self.ws.tower_with_key("ffla:a")
        by_url = {p["url"]: p for p in t["photos"]}
        self.assertEqual(set(by_url), {"http://nhlr.org/photos/ok.jpg", "http://nhlr.org/photos/unmirrored.jpg"})
        ok = by_url["http://nhlr.org/photos/ok.jpg"]
        self.assertEqual((ok["file"], ok["thumb"], ok["w"], ok["h"]), ("ab/ab12.webp", "ab/ab12.t.webp", 800, 600))
        self.assertIsNone(by_url["http://nhlr.org/photos/unmirrored.jpg"]["file"])

    def test_re_merge_with_unchanged_manifest_is_a_no_op(self) -> None:
        manifest = {"http://nhlr.org/photos/ok.jpg": {"file": "ab/ab12.webp", "thumb": "ab/ab12.t.webp",
                                                        "w": 800, "h": 600, "bytes": 1234, "status": "ok", "reason": None}}
        rep1 = self.ws.run(self.sources(), photos_manifest=manifest)
        rep2 = self.ws.run(photos_manifest=manifest)  # re-run, same sources already on disk
        self.assertEqual(rep2["files"]["written"], 0)
        self.assertEqual(rep2["files"]["unchanged"], rep1["files"]["written"])


class IdStability(unittest.TestCase):
    SOURCES = {
        "ffla": [rec("ffla", "a", "Bald Mountain", 45.0, -115.0), rec("ffla", "b", "Bald Mountain", 46.0, -115.0),
                 rec("ffla", "c", "Bald Mountain", 47.0, -115.0), rec("ffla", "d", "Indian Hill", 45.5, -116.5)],
        "osm": [rec("osm", "x", "Bald Mountain Lookout", 46.0001, -115.0)],
    }

    def ids(self, ws: Workspace) -> dict[str, str]:
        return {s["key"]: t["id"] for t in ws.towers_by_id().values() for s in t["sources"]}

    def test_rerun_and_fresh_run_give_same_ids(self):
        a, b = Workspace(), Workspace()
        try:
            a.run(self.SOURCES)
            first = self.ids(a)
            rep = a.run()
            self.assertEqual(rep["files"]["written"], 0)
            self.assertEqual(self.ids(a), first)
            shuffled = {k: random.Random(7).sample(v, len(v)) for k, v in self.SOURCES.items()}
            b.run(shuffled)
            self.assertEqual(self.ids(b), first)
            self.assertEqual(sorted(set(first.values()))[:3], ["us-id-bald-mountain", "us-id-bald-mountain-2", "us-id-bald-mountain-3"])
        finally:
            a.close()
            b.close()

    def test_new_records_never_rename_existing(self):
        ws = Workspace()
        try:
            ws.run(self.SOURCES)
            before = self.ids(ws)
            more = {k: list(v) for k, v in self.SOURCES.items()}
            # a new Bald Mountain that sorts first (furthest north) must not take an existing id
            more["ffla"].append(rec("ffla", "e", "Bald Mountain", 48.5, -116.0))
            ws.run(more)
            after = self.ids(ws)
            for key, tid in before.items():
                self.assertEqual(after[key], tid)
            self.assertEqual(after["ffla:e"], "us-id-bald-mountain-4")
            # a record that vanishes from its source leaves its tower in place
            fewer = {"ffla": [r for r in more["ffla"] if r["key"] != "ffla:d"], "osm": more["osm"]}
            ws.run(fewer)
            self.assertIn("us-id-indian-hill", ws.towers_by_id())
        finally:
            ws.close()


class LockedFields(unittest.TestCase):
    def test_locked_fields_are_kept(self):
        ws = Workspace()
        try:
            src = {"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0, status="gone")]}
            ws.run(src)
            path = next(ws.towers.rglob("*.json"))
            t = json.loads(path.read_text())
            t["name"] = "Gold Hill Lookout (researched name)"
            t["status"] = "standing"
            t["location"] = {"lat": 45.001, "lon": -116.001, "precision": "exact", "from": "research"}
            t["locked"] = ["name", "location"]
            path.write_text(json.dumps(t))
            src["ffla"][0]["county"] = "Idaho"
            ws.run(src)
            t2 = json.loads(path.read_text())
            self.assertEqual(t2["name"], "Gold Hill Lookout (researched name)")
            self.assertEqual(t2["location"]["from"], "research")
            self.assertEqual(t2["status"], "gone")        # not locked: refreshed from the source
            self.assertEqual(t2["county"], "Idaho")
            self.assertEqual(t2["id"], t["id"])
        finally:
            ws.close()


class MovedStructures(unittest.TestCase):
    def test_parse_annotation(self):
        site, ann = M.parse_annotation("State Fair (Relocated Padlock Hill)")
        self.assertEqual((site, ann["kind"], ann["origin"]), ("State Fair", "relocated", "Padlock Hill"))
        site, ann = M.parse_annotation("Crystal Ridge (Relocated Stranger Mtn, WA)")
        self.assertEqual((ann["origin"], ann["origin_region"]), ("Stranger Mountain", "WA"))
        _, ann = M.parse_annotation("Trout Mountain (Relocated from Alabama)")
        self.assertEqual((ann["origin"], ann["origin_region"]), (None, "AL"))
        _, ann = M.parse_annotation("Missoula Aerial Fire Depot (Hornet Peak Replica)")
        self.assertEqual((ann["kind"], ann["replica_of"]), ("replica", "Hornet Peak"))
        _, ann = M.parse_annotation("Wilson Hill WMA #1 (Parts from Whites Hill)")
        self.assertEqual((ann["kind"], ann["origin"]), ("parts", "Whites Hill"))
        _, ann = M.parse_annotation("Sounding Knob (Relocated on same mountain)")
        self.assertTrue(ann["same_place"])
        _, ann = M.parse_annotation("Rugby (Relocated Salyer NWR \u2013 HQ)")
        self.assertEqual(ann["origin"], "Salyer NWR \u2013 HQ")
        self.assertEqual(M.parse_annotation("Putnam (Liberty)"), ("Putnam (Liberty)", None))
        # the note is not an alternate name to match on
        self.assertEqual(M.name_variants("State Fair (Relocated Padlock Hill)"), ["State Fair"])

    def test_moved_lookout_is_named_and_linked(self):
        ws = Workspace()
        try:
            ws.run({"ffla": [
                rec("ffla", "o", "Padlock Hill", 42.3646, -76.2699, "NY", status="gone"),
                rec("ffla", "n", "State Fair (Relocated Padlock Hill)", 43.0705, -76.2185, "NY"),
                rec("ffla", "r", "Missoula Aerial Fire Depot (Hornet Peak Replica)", 46.92, -114.09, "MT"),
            ], "osm": [rec("osm", "x", "Padlock Hill Fire Tower", 43.0706, -76.2186, "NY")]})
            towers = ws.towers_by_id()
            new, old = towers["us-ny-padlock-hill-at-state-fair"], towers["us-ny-padlock-hill"]
            self.assertEqual(new["name"], "Padlock Hill Fire Tower (now at the State Fair)")
            self.assertEqual(new["status"], "standing")
            self.assertEqual(old["status"], "relocated")
            ev = [e for e in new["events"] if e["event"] == "relocated"][0]
            self.assertEqual((ev["moved_from"], ev["moved_to"]), ("Padlock Hill", "State Fair"))
            self.assertIn({"label": "Original site: Padlock Hill", "url": "../us-ny-padlock-hill/",
                           "kind": "relocated_from", "id": "us-ny-padlock-hill"}, new["links"])
            self.assertTrue(any(l.get("kind") == "relocated_to" and l["id"] == new["id"] for l in old["links"]))
            self.assertEqual(towers["us-mt-hornet-peak-replica"]["status"], "replica")
            # re-running changes nothing, and the two-way links survive
            self.assertEqual(ws.run()["files"]["written"], 0)
            vocab = json.loads((M.DATA / "vocab.json").read_text())
            for path in ws.towers.rglob("*.json"):
                self.assertEqual(V.check(json.loads(path.read_text()), path, vocab)[0], [], path)
        finally:
            ws.close()


class ReassignSameSpot(unittest.TestCase):
    """DESIGN.md §3.5: within 100 m, a record with a clearly different name is reassigned to a
    tower it strongly and uniquely names elsewhere in the region, instead of joining the near
    one -- but only for RIDB/idahofirelookouts.com, whose pins are already known to be rougher
    (see the Black Butte / Lookout Butte, ID story: recreation.gov's "Lookout Butte Lookout"
    facility sits 45 m from Black Butte but is really Lookout Butte's listing, 64 km away)."""

    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_ridb_coordinate_error_is_reassigned(self):
        rep = self.ws.run({
            "nhlr": [rec("nhlr", "US1", "Black Butte Lookout", 45.0, -115.0, "ID"),
                     rec("nhlr", "US2", "Lookout Butte Lookout", 45.577, -115.0, "ID")],
            "ridb": [rec("ridb", "1", "LOOKOUT BUTTE LOOKOUT", 45.0004, -115.0, "ID",
                         rental={"available": True, "provider": "recreation.gov",
                                 "url": "https://www.recreation.gov/camping/campgrounds/1"})],
        })
        black_butte = self.ws.tower_with_key("nhlr:US1")
        lookout_butte = self.ws.tower_with_key("nhlr:US2")
        ridb_tower = self.ws.tower_with_key("ridb:1")
        self.assertEqual(ridb_tower["id"], lookout_butte["id"])
        self.assertNotEqual(ridb_tower["id"], black_butte["id"])
        self.assertIsNone(black_butte["rental"])
        self.assertIsNotNone(lookout_butte["rental"])
        items = [r for r in rep["review"] if r["type"] == "reassigned_same_spot"]
        self.assertEqual([i["key"] for i in items], ["ridb:1"])
        self.assertEqual(items[0]["tower"], lookout_butte["id"])
        self.assertEqual(items[0]["nearby_tower"], black_butte["id"])

    def test_other_sources_keep_the_near_match(self):
        # Same shape, but FFLA (not RIDB/idahofirelookouts.com): a same-spot, different-named
        # record is a common real alternate name (Pequawket = Kearsarge North) far more often
        # than a coordinate bug, so it stays with the near tower.
        self.ws.run({
            "nhlr": [rec("nhlr", "US1", "Black Butte Lookout", 45.0, -115.0, "ID"),
                     rec("nhlr", "US2", "Lookout Butte Lookout", 45.577, -115.0, "ID")],
            "ffla": [rec("ffla", "x", "Lookout Butte Lookout", 45.0004, -115.0, "ID")],
        })
        self.assertEqual(self.ws.tower_with_key("ffla:x")["id"], self.ws.tower_with_key("nhlr:US1")["id"])

    def test_relocated_structure_site_is_not_treated_as_a_coordinate_error(self):
        # The near tower's different name is already explained by the move: it is "<original
        # name> (now at <Y>)"'s display site, not a RIDB pin that landed on the wrong tower.
        rep = self.ws.run({
            "ffla": [rec("ffla", "orig", "Sliderock", 46.9, -114.0, "MT", status="gone"),
                     rec("ffla", "museum", "Fort Missoula Historical Museum (Relocated Sliderock)",
                         46.87, -114.03, "MT")],
            "ridb": [rec("ridb", "2", "Sliderock Lookout", 46.87, -114.03, "MT")],
        })
        museum = self.ws.tower_with_key("ffla:museum")
        self.assertEqual(self.ws.tower_with_key("ridb:2")["id"], museum["id"])
        self.assertFalse(any(r["type"] == "reassigned_same_spot" and r["key"] == "ridb:2" for r in rep["review"]))

    def test_ambiguous_far_matches_are_left_for_a_human(self):
        rep = self.ws.run({
            "nhlr": [rec("nhlr", "US1", "Near Tower", 45.0, -115.0, "ID"),
                     rec("nhlr", "US2", "Twin Peak", 45.3, -115.0, "ID"),
                     rec("nhlr", "US3", "Twin Peak", 45.5, -115.2, "ID")],
            "ridb": [rec("ridb", "3", "TWIN PEAK LOOKOUT", 45.0004, -115.0, "ID")],
        })
        near_tower = self.ws.tower_with_key("nhlr:US1")
        self.assertEqual(self.ws.tower_with_key("ridb:3")["id"], near_tower["id"])
        items = [r for r in rep["review"] if r["type"] == "reassign_same_spot_ambiguous"]
        self.assertEqual([i["key"] for i in items], ["ridb:3"])
        self.assertEqual(items[0]["nearby_tower"], near_tower["id"])
        self.assertEqual(set(items[0]["towers"]),
                         {self.ws.tower_with_key("nhlr:US2")["id"], self.ws.tower_with_key("nhlr:US3")["id"]})


class SmallRules(unittest.TestCase):
    def test_one_year_build_difference_is_not_a_conflict(self):
        ws = Workspace()
        try:
            ws.run({"ffla": [rec("ffla", "a", "Iron Mountain", 45.5, -116.0), rec("ffla", "b", "Gold Hill", 45.0, -116.0)],
                    "firelookout_com": [rec("firelookout_com", "a", "Iron Mountain", 45.5, -116.0, built=1930),
                                        rec("firelookout_com", "b", "Gold Hill", 45.0, -116.0, built=1930)],
                    "osm": [rec("osm", "a", "Iron Mountain Lookout", 45.5001, -116.0, built=1931),
                            rec("osm", "b", "Gold Hill Lookout", 45.0001, -116.0, built=1932)]})
            self.assertEqual(ws.tower_with_key("ffla:a")["conflicts"], [])
            self.assertEqual([c["field"] for c in ws.tower_with_key("ffla:b")["conflicts"]], ["built"])
        finally:
            ws.close()

    def test_hide_keys(self):
        ws = Workspace()
        try:
            key = next(iter(M.HIDE_KEYS))
            src, _, rest = key.partition(":")
            ws.run({src: [rec(src, rest, "East Lookout Tower", 13.3865, 144.722, "GU")]})
            t = ws.tower_with_key(key)
            self.assertTrue(t["hidden"])
            self.assertEqual(t["hidden_reason"], M.HIDE_KEYS[key])
        finally:
            ws.close()

    def test_rental_on_a_burned_lookout_warns(self):
        ws = Workspace()
        try:
            ffla = rec("ffla", "f", "Flag Point", 45.3179, -121.4666, "OR", status="gone")
            ffla["events"] = [{"year": 2026, "event": "burned", "note": None, "from": "ffla"}]
            ridb = rec("ridb", "1", "Flag Point Lookout", 45.318, -121.467, "OR", agency=None,
                       rental={"available": True, "provider": "recreation.gov", "url": "https://www.recreation.gov/x"})
            ridb["agency"] = "USDA Forest Service"
            ws.run({"ffla": [ffla], "ridb": [ridb]})
            rental = ws.tower_with_key("ffla:f")["rental"]
            self.assertIs(rental["available"], False)
            self.assertEqual(rental["warning"], "FFLA reports this lookout burned in 2026, but recreation.gov "
                                                "still lists it. Check with the forest before booking.")
            self.assertEqual(rental["url"], "https://www.recreation.gov/x")
        finally:
            ws.close()

    def test_osm_unknown_access_does_not_block_the_ridb_fallback(self):
        # us-mt-mccart: OSM's access=permit tag describes the structure, not the land, so
        # record_access() gives it level "unknown" -- that must not out-rank the public access a
        # recreation.gov rental itself implies, just because it is the only source with any
        # access value at all.
        ws = Workspace()
        try:
            ws.run({
                "nhlr": [rec("nhlr", "1", "McCart Lookout", 45.6, -113.8, "MT")],
                "ridb": [rec("ridb", "1", "McCart Lookout", 45.6001, -113.8, "MT",
                             rental={"available": True, "provider": "recreation.gov",
                                     "url": "https://www.recreation.gov/x"})],
                "osm": [rec("osm", "n1", "McCart Lookout", 45.6002, -113.8, "MT",
                            extra={"access": "permit"})],
            })
            access = ws.tower_with_key("nhlr:1")["access"]
            self.assertEqual(access["level"], "public")
            self.assertIn("recreation.gov", access["note"])
        finally:
            ws.close()

    def test_osm_unknown_access_is_kept_as_a_last_resort(self):
        # No tribal ownership and no RIDB rental to fall back to: OSM's structure-only note is
        # still better than nothing.
        ws = Workspace()
        try:
            ws.run({
                "nhlr": [rec("nhlr", "1", "Solo Lookout", 45.6, -113.8, "MT")],
                "osm": [rec("osm", "n1", "Solo Lookout", 45.6001, -113.8, "MT",
                            extra={"access": "permit"})],
            })
            access = ws.tower_with_key("nhlr:1")["access"]
            self.assertEqual(access, {"level": "unknown", "note": "OpenStreetMap tags the structure access=permit."})
        finally:
            ws.close()

    def test_rental_vanished_from_ridb_gets_a_warning_not_removal(self):
        ws = Workspace()
        try:
            ffla = rec("ffla", "f", "Flag Point", 45.3179, -121.4666, "OR")
            ridb = rec("ridb", "1", "Flag Point Lookout", 45.318, -121.467, "OR",
                       rental={"available": True, "provider": "recreation.gov",
                               "url": "https://www.recreation.gov/x", "checked": "2026-09-01"})
            ws.run({"ffla": [ffla], "ridb": [ridb]})
            before = ws.tower_with_key("ffla:f")["rental"]
            self.assertIs(before["available"], True)
            self.assertEqual(before["checked"], "2026-09-01")

            # The next weekly refresh reads RIDB's export successfully, but it no longer has
            # this facility (removed or renumbered) -- a real absence, not a skipped fetch.
            ws.run({"ffla": [ffla], "ridb": []})
            after = ws.tower_with_key("ffla:f")["rental"]
            self.assertEqual(after["url"], "https://www.recreation.gov/x")  # kept, not removed
            self.assertEqual(after["checked"], "2026-09-01")  # left as is, not bumped to today
            self.assertIs(after["available"], False)
            self.assertIn("no longer finds", after["warning"])
            self.assertIn("2026-09-01", after["warning"])
        finally:
            ws.close()

    def test_skipped_ridb_fetch_does_not_warn(self):
        ws = Workspace()
        try:
            ffla = rec("ffla", "f", "Flag Point", 45.3179, -121.4666, "OR")
            ridb = rec("ridb", "1", "Flag Point Lookout", 45.318, -121.467, "OR",
                       rental={"available": True, "provider": "recreation.gov",
                               "url": "https://www.recreation.gov/x", "checked": "2026-09-01"})
            ws.run({"ffla": [ffla], "ridb": [ridb]})
            # A local run that never re-fetched RIDB at all (no data/sources/ridb.json this
            # time) must not be mistaken for every rental having vanished.
            ws.run({"ffla": [ffla]})
            rental = ws.tower_with_key("ffla:f")["rental"]
            self.assertIs(rental["available"], True)
            self.assertNotIn("warning", rental)
        finally:
            ws.close()


class StatusNotes(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(M.parse_status_note("Buffalo Lookout Tower (Demolished)")[1]["status"], "gone")
        name, info = M.parse_status_note("Muzette Lookout Tower (likely gone)")
        self.assertEqual((name, info["status"], info["note"]), ("Muzette Lookout Tower", "unknown", "Sources suggest it is gone."))
        self.assertIn("hidden_reason", M.parse_status_note("Slide Mountain (Non-fire Tower)")[1])
        self.assertEqual(M.parse_status_note("Orchard Point (unknown)")[0], "Orchard Point")
        for keep in ("Barnum (Loc 2)", "Putnam (Liberty)", "South Rim TT-8 (Name Unknown)"):
            self.assertEqual(M.parse_status_note(keep), (keep, None))

    def test_merge(self):
        ws = Workspace()
        try:
            ws.run({"osm": [rec("osm", "b", "Buffalo Lookout Tower (Demolished)", 34.7, -81.6, "SC"),
                            rec("osm", "m", "Muzette Lookout Tower (likely gone)", 41.5, -78.0, "PA")],
                    "ffla": [rec("ffla", "s", "Slide Mountain (Non-fire Tower)", 41.9991, -74.3859, "NY", status="gone"),
                             rec("ffla", "o", "Orchard Point (unknown)", 39.0, -76.4, "MD")]})
            t = ws.towers_by_id()
            self.assertEqual((t["us-sc-buffalo"]["name"], t["us-sc-buffalo"]["status"]), ("Buffalo Lookout Tower", "gone"))
            self.assertIn("Buffalo Lookout Tower (Demolished)", t["us-sc-buffalo"]["other_names"])
            self.assertEqual((t["us-pa-muzette"]["status"], t["us-pa-muzette"]["status_note"]), ("unknown", "Sources suggest it is gone."))
            self.assertEqual(t["us-ny-slide-mountain"]["hidden_reason"], "Not a fire lookout (FFLA lists it as a non-fire tower)")
            self.assertEqual(t["us-md-orchard-point"]["name"], "Orchard Point")
        finally:
            ws.close()


def research_file(rid: str, **kw) -> dict:
    data = {
        "id": rid, "researched": "2026-10-04",
        "summary": "A cab on a summit watched for smoke since 1915.",
        "facts": {"design": "R-6 flat top", "status": "standing", "agency": "Fremont National Forest",
                  "staffing": {"status": "staffed", "as_of": "2026"},
                  "access": {"level": "public", "note": "Foot access in winter."},
                  "visit": {"climbable": None, "drive_up": False}},
        "events": [{"year": 1967, "event": "built", "note": "Current R-6 cab", "cite": [1]},
                   {"year": 1936, "event": "replaced", "note": "L-4 cab", "cite": [2]},
                   {"year": 1992, "event": "fire_spotted", "note": "Hip roof", "cite": [1]},
                   {"year": 1980, "event": "unstaffed", "note": "Staffing ended", "cite": [2]}],
        "corrections": [{"field": "location", "current": "45.0, -116.0", "proposed": "45.1, -116.1",
                         "evidence": "Register page", "cite": [1]}],
        "sources": [{"n": 1, "title": "Gold Hill Lookout", "publisher": "NHLR", "url": "http://nhlr.org/lookouts/us/id/gold-hill/", "accessed": "2026-10-04"},
                    {"n": 2, "title": "Gold Hill", "publisher": "firelookout.com", "url": "https://example.org/firelookout_com/a", "accessed": "2026-10-04"}],
        "photos": [{"url": "https://example.org/p.jpg", "source_url": "https://example.org/p", "credit": "USFS", "license": "Public domain", "caption": "1938", "year": 1938}],
        "confidence": "medium",
        "notes_for_editor": "Check the 1936 date.",
    }
    data.update(kw)
    return data


class ResearchOverlay(unittest.TestCase):
    SOURCES = {"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0, status="gone", built=1967)],
               "firelookout_com": [rec("firelookout_com", "a", "Gold Hill", 45.0, -116.0, status="gone", built=1967)]}

    def setUp(self):
        self.ws = Workspace()
        self.ws.run(self.SOURCES)
        self.tid = self.ws.tower_with_key("ffla:a")["id"]

    def tearDown(self):
        self.ws.close()

    def tower(self) -> dict:
        return self.ws.towers_by_id()[self.tid]

    def test_facts_events_photos_links_and_provenance(self):
        self.ws.write_research(research_file(self.tid))
        rep = self.ws.run()
        t = self.tower()
        self.assertEqual((t["design"], t["status"], t["agency"]), ("R-6 flat top", "standing", "Fremont National Forest"))
        self.assertEqual(t["summary"], "A cab on a summit watched for smoke since 1915.")
        self.assertEqual(t["staffing"], {"status": "staffed", "as_of": "2026"})
        self.assertIs(t["visit"]["drive_up"], False)
        self.assertIsNone(t["visit"]["climbable"])
        # research changed the status against the sources: the disagreement stays visible
        c = next(c for c in t["conflicts"] if c["field"] == "status")
        self.assertEqual(c["values"][0], {"source": "research", "value": "standing"})
        self.assertIn({"source": "ffla", "value": "gone"}, c["values"])
        # events: same year+event once (research's, with its citation); unknown names left out; aliases mapped
        built = [e for e in t["events"] if e["event"] == "built"]
        self.assertEqual(len(built), 1)
        self.assertEqual((built[0]["from"], built[0]["source_url"]), ("research", "http://nhlr.org/lookouts/us/id/gold-hill/"))
        self.assertFalse(any(e["event"] == "fire_spotted" for e in t["events"]))
        self.assertTrue(any(e["event"] == "staffed_last" and e["year"] == 1980 for e in t["events"]))
        self.assertEqual(t["photos"][-1]["url"], "https://example.org/p.jpg")
        self.assertEqual(t["photos"][-1]["license"], "Public domain")
        refs = [l for l in t["links"] if l["kind"] == "reference"]
        self.assertEqual([l["url"] for l in refs], ["http://nhlr.org/lookouts/us/id/gold-hill/"])  # firelookout.com page already linked
        src = next(s_ for s_ in t["sources"] if s_["source"] == "research")
        self.assertEqual(src["key"], f"research:{self.tid}")
        self.assertIn("status", src["fields"])
        self.assertEqual(t["research"]["researched"], "2026-10-04")
        # corrections are reported, never applied
        self.assertEqual(t["location"]["lat"], 45.0)
        self.assertEqual(rep["research_corrections"][0]["proposed"], "45.1, -116.1")
        self.assertEqual(rep["research"]["notes_for_editor"][0]["note"], "Check the 1936 date.")
        self.assertTrue(any("fire_spotted" in p_["problem"] for p_ in rep["research"]["problems"]))

    def test_status_note_only_qualifies_a_status(self):
        facts = {"status": "standing", "status_note": "Hip roof replaced the original flat roof in 1992."}
        self.ws.write_research(research_file(self.tid, facts=facts))
        self.ws.run()
        self.assertIsNone(self.tower()["status_note"])
        facts = {"status": "ruins", "status_note": "Only the footings remain."}
        self.ws.write_research(research_file(self.tid, facts=facts))
        self.ws.run()
        self.assertEqual(self.tower()["status_note"], "Only the footings remain.")

    def test_verification_mapping(self):
        for verdict, expected in (("pass", "verified"), ("fixed", "verified"), ("fail", "researched"), (None, "researched")):
            extra = {"verification": {"checked": "2026-10-05", "claims_checked": 12, "unsupported_removed": 0,
                                      "errors_fixed": 0, "verdict": verdict}} if verdict else {}
            self.ws.write_research(research_file(self.tid, **extra))
            self.ws.run()
            self.assertEqual(self.tower()["verification"], expected, verdict)

    def test_locked_fields_win(self):
        path = next(p for p in self.ws.towers.rglob(f"{self.tid}.json"))
        t = json.loads(path.read_text())
        t["design"] = "Hand-checked design"
        t["locked"] = ["design", "status"]
        path.write_text(json.dumps(t))
        self.ws.write_research(research_file(self.tid))
        self.ws.run()
        t = self.tower()
        self.assertEqual(t["design"], "Hand-checked design")
        self.assertEqual(t["status"], "gone")
        self.assertFalse(any(c["field"] == "status" and c["values"][0]["source"] == "research" for c in t["conflicts"]))
        self.assertEqual(t["agency"], "Fremont National Forest")  # not locked: research applies

    def test_rerun_is_idempotent(self):
        self.ws.write_research(research_file(self.tid))
        self.ws.run()
        first = self.tower()
        rep = self.ws.run()
        self.assertEqual(rep["files"]["written"], 0)
        self.assertEqual(self.tower(), first)
        self.assertEqual(sum(1 for s_ in first["sources"] if s_["source"] == "research"), 1)

    def test_research_for_an_unknown_tower_is_reported(self):
        self.ws.write_research(research_file("us-id-nowhere"))
        rep = self.ws.run()
        self.assertTrue(any("no tower" in p_["problem"] for p_ in rep["research"]["problems"]))

    def test_validator(self):
        vocab = json.loads((M.DATA / "vocab.json").read_text())
        data = research_file(self.tid)
        path = Path(f"{self.tid}.json")
        errs, warns = V.check_research(data, path, vocab, {self.tid})
        self.assertEqual(errs, [])
        self.assertTrue(any("fire_spotted" in w for w in warns))
        bad = research_file(self.tid, events=[{"year": 1967, "event": "built", "cite": [9]}])
        self.assertTrue(any("not in sources" in e for e in V.check_research(bad, path, vocab, {self.tid})[0]))
        story = "Built in 1967.[^1] Rebuilt.[^3]\n\n[^1]: NHLR, http://nhlr.org/x (accessed 2026-10-04).\n"
        errs, _ = V.check_story(story, data)
        self.assertTrue(any("[^3] has no definition" in e for e in errs))
        self.assertTrue(any("[^3] has no matching source" in e for e in errs))
        self.assertEqual(V.check_story("Built.[^1]\n\n[^1]: NHLR, http://nhlr.org/x/.\n", data)[0], [])


class PackedDMS(unittest.TestCase):
    def test_fire_lookouts_org_coordinates(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("flo", Path(__file__).parent / "regional" / "fire_lookouts_org.py")
        flo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flo)
        lat, lon, fmt = flo.parse_gps("37.2235", "119.1048")  # Mt. Tom: 37 22' 35", 119 10' 48"
        self.assertEqual(fmt, "packed_dms")
        self.assertAlmostEqual(lat, 37 + 22 / 60 + 35 / 3600, places=6)
        self.assertAlmostEqual(lon, -(119 + 10 / 60 + 48 / 3600), places=6)
        self.assertEqual(flo.parse_gps("35.85278", "118.5025"), (35.85278, -118.5025, "decimal"))  # 85 > 59
        self.assertEqual(flo.parse_gps("37.27212", "119.54944")[2], "decimal")  # 94 > 59 in the longitude
        self.assertEqual(flo.parse_gps("36.020", "118.253")[2], "decimal")      # too few digits


class RemovedField(unittest.TestCase):
    """NHLR/FFLOS's "Removed" table field -> an event (pipeline/fetch_registers.py)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fetch_registers_under_test", Path(__file__).parent / "fetch_registers.py")
        cls.fr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.fr)

    def parse(self, text):
        return self.fr.parse_removed_field(text, "fflos")

    def test_bare_year(self):
        ev = self.parse("1984")
        self.assertEqual((ev["year"], ev["event"]), (1984, "removed"))
        self.assertIn('"1984"', ev["note"])
        self.assertNotIn("about", ev["note"])

    def test_fire_mentions_are_burned(self):
        for text, year in [("2002 - Wildfire", 2002), ("1968 Arson Fire", 1968),
                            ("1969 (Burned)", 1969), ("1914 Volcanic Eruption", 1914)]:
            ev = self.parse(text)
            self.assertEqual(ev["year"], year, text)
        self.assertEqual(self.parse("2002 - Wildfire")["event"], "burned")
        self.assertEqual(self.parse("1968 Arson Fire")["event"], "burned")
        self.assertEqual(self.parse("1969 (Burned)")["event"], "burned")
        self.assertEqual(self.parse("1914 Volcanic Eruption")["event"], "destroyed")

    def test_circa_keeps_the_year_and_says_about(self):
        ev = self.parse("circa 2010")
        self.assertEqual(ev["year"], 2010)
        self.assertEqual(ev["event"], "removed")
        self.assertIn("about 2010", ev["note"])
        self.assertIn('"circa 2010"', ev["note"])

    def test_bare_decade_is_also_approximate(self):
        ev = self.parse("late 1970s")
        self.assertEqual(ev["year"], 1970)
        self.assertIn("about 1970", ev["note"])
        ev2 = self.parse("1930's")
        self.assertEqual(ev2["year"], 1930)
        self.assertIn("about 1930", ev2["note"])

    def test_range_uses_the_later_year(self):
        self.assertEqual(self.parse("1957-1958")["year"], 1958)
        self.assertEqual(self.parse("between 1966 and 1979")["year"], 1979)
        self.assertEqual(self.parse("1940s or 1950s")["year"], 1950)

    def test_qualifiers_keep_their_year(self):
        self.assertEqual(self.parse("after 1943")["year"], 1943)
        self.assertEqual(self.parse("before 1970")["year"], 1970)
        self.assertEqual(self.parse("by 2018")["year"], 2018)
        self.assertEqual(self.parse("Prior to 1986")["year"], 1986)

    def test_no_usable_year_is_skipped(self):
        for text in ("Standing", "Unknown", "Relocation Date Unknown",
                     "Collapsed structure remains", "Cabin gone, tower remains"):
            self.assertIsNone(self.parse(text), text)

    def test_note_names_the_source(self):
        self.assertIn("NHLR", self.fr.parse_removed_field("1984", "nhlr")["note"])
        self.assertIn("FFLOS", self.fr.parse_removed_field("1984", "fflos")["note"])


class Validation(unittest.TestCase):
    def test_validator_catches_errors(self):
        ws = Workspace()
        try:
            ws.run({"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0)]})
            path = next(ws.towers.rglob("*.json"))
            vocab = json.loads((M.DATA / "vocab.json").read_text())
            t = json.loads(path.read_text())
            self.assertEqual(V.check(t, path, vocab)[0], [])
            bad = dict(t, status="burnt", location={"lat": 70.8, "lon": -70.8})
            errs, _ = V.check(bad, path, vocab)
            self.assertTrue(any("status" in e for e in errs))
            self.assertTrue(any("outside the United States" in e for e in errs))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(V.validate(ws.towers, M.DATA / "vocab.json"), 0)
                (path.parent / "us-id-copy.json").write_text(json.dumps(dict(t, id="us-id-copy")))
                (path.parent / "us-id-dupe.json").write_text(json.dumps(dict(t, id="us-id-copy")))
                self.assertEqual(V.validate(ws.towers, M.DATA / "vocab.json"), 1)
        finally:
            ws.close()


class AssociationProjects(unittest.TestCase):
    """The association-project source family (merge.py ASSOCIATION_SOURCES, DESIGN.md 3.7)."""

    SRC = "test_assoc"

    def setUp(self):
        import copy
        self.saved = (list(M.SOURCE_ORDER), copy.deepcopy(M.PRECEDENCE), dict(M.LOCATION_LINEAGE), list(M.ASSOCIATION_SOURCES))
        M.ASSOCIATION_SOURCES.append(self.SRC)
        M.register_associations(M.ASSOCIATION_SOURCES)
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()
        order, prec, lineage, assoc = self.saved
        M.SOURCE_ORDER[:] = order
        M.PRECEDENCE.clear(); M.PRECEDENCE.update(prec)
        M.LOCATION_LINEAGE.clear(); M.LOCATION_LINEAGE.update(lineage)
        M.ASSOCIATION_SOURCES[:] = assoc

    def assoc_rec(self, key: str, name: str, lat, lon, **kw) -> dict:
        r = rec(self.SRC, key, name, lat, lon, region="MT", kind="unknown", status=kw.pop("status", "standing"),
                extra={"association": {"name": "Test Lookout Association", "url": "https://assoc.example/"},
                       "position_from": "nhlr:US 1", **kw.pop("extra", {})}, **kw)
        r["url"] = "https://assoc.example/2025-projects/"
        return r

    def ev(self, year, event, note, urls=("https://assoc.example/2025-projects/",)):
        e = {"year": year, "event": event, "note": note, "from": self.SRC, "source_url": urls[0]}
        if len(urls) > 1:
            e["source_urls"] = list(urls)
        return e

    def test_registration_puts_the_family_after_the_registers(self):
        self.assertIn(self.SRC, M.SOURCE_ORDER)
        self.assertLess(M.SOURCE_ORDER.index("michigan_fire_tower"), M.SOURCE_ORDER.index(self.SRC))
        self.assertLess(M.SOURCE_ORDER.index(self.SRC), M.SOURCE_ORDER.index("wikidata"))
        for f in ("design", "height_m", "agency", "staffing", "events", "status", "name"):
            self.assertEqual(M.PRECEDENCE[f][-1], self.SRC, f)
        self.assertEqual(M.LOCATION_LINEAGE[self.SRC], "registers")
        M.register_associations(M.ASSOCIATION_SOURCES)  # idempotent
        self.assertEqual(M.PRECEDENCE["design"].count(self.SRC), 1)
        self.assertEqual(M.SOURCE_ORDER.count(self.SRC), 1)

    def test_events_links_and_facts_join_the_register_tower(self):
        nhlr = rec("nhlr", "US 1", "Numa Ridge Lookout", 48.884, -114.179, "MT", built=1934,
                   registers=[{"register": "NHLR", "number": "US 1"}])
        nhlr["agency"] = "National Park Service"
        a = self.assoc_rec("numa", "Numa Ridge", 48.884, -114.179, extra={
            "design": "14x14-ft house on a 10-ft tower", "height_ft": 10, "staffing_hint": "staffed", "ownership": "federal"})
        a["agency"] = "Glacier National Park"
        a["events"] = [self.ev(1934, "built", "Built; the report gives the year."),
                       self.ev(2019, "assessed", "Condition assessment by volunteers.", ("https://assoc.example/2019.pdf", "https://assoc.example/news.pdf")),
                       self.ev(2025, "restored", "Repainted the exterior.")]
        self.ws.run({"nhlr": [nhlr], self.SRC: [a]})
        t = self.ws.tower_with_key(f"{self.SRC}:numa")
        self.assertEqual({s["source"] for s in t["sources"]}, {"nhlr", self.SRC})
        self.assertEqual(t["agency"], "National Park Service")          # the register outranks the association
        self.assertEqual(t["design"], "14x14-ft house on a 10-ft tower")  # the association fills a gap
        self.assertEqual(t["height_m"], 3.0)
        self.assertEqual(t["staffing"]["status"], "staffed")
        self.assertEqual(t["ownership"], "federal")
        ev = {(e["year"], e["event"]): e for e in t["events"]}
        self.assertEqual(ev[(2025, "restored")]["source_url"], "https://assoc.example/2025-projects/")
        self.assertEqual(ev[(2025, "restored")]["from"], self.SRC)
        self.assertEqual(ev[(2019, "assessed")]["source_urls"], ["https://assoc.example/2019.pdf", "https://assoc.example/news.pdf"])
        self.assertNotIn(1934, [e["year"] for e in t["events"] if e["from"] == self.SRC])  # the register's build year wins
        link = next(l for l in t["links"] if l["url"] == "https://assoc.example/2025-projects/")
        self.assertEqual(link["kind"], "association")
        self.assertIn("Test Lookout Association", link["label"])
        self.assertEqual(t["location"]["from"], "nhlr")
        # same position, same lineage: the association does not make it "facts"-verified
        self.assertEqual(t["verification"], "unverified")

    def test_the_family_never_overrides_a_register_and_a_report_only_tower_is_made(self):
        a = self.assoc_rec("solo", "Solo Peak Lookout", 47.0, -113.0)
        a["extra"].pop("position_from")
        a["extra"]["position_note"] = "given by the association"
        a["events"] = [self.ev(2020, "restored", "Reroofed.")]
        self.ws.run({self.SRC: [a]})
        t = self.ws.tower_with_key(f"{self.SRC}:solo")
        self.assertEqual(t["name"], "Solo Peak Lookout")
        self.assertEqual(t["status"], "standing")
        self.assertEqual(t["events"][0]["source_url"], "https://assoc.example/2025-projects/")

    def test_family_marker_and_the_list_must_agree(self):
        msgs: list[str] = []
        write_sources(self.ws.sources, {self.SRC: [self.assoc_rec("a", "A Peak", 47.0, -113.0)],
                                        "other_assoc": [rec("other_assoc", "b", "B Peak", 47.5, -113.0)]})
        p = self.ws.sources / f"{self.SRC}.json"
        d = json.loads(p.read_text()); p.write_text(json.dumps(d))                      # no family marker
        q = self.ws.sources / "other_assoc.json"
        d = json.loads(q.read_text()); d["family"] = M.ASSOCIATION_FAMILY; q.write_text(json.dumps(d))  # not in the list
        M.load_sources(self.ws.sources, log=msgs.append)
        self.assertTrue(any(self.SRC in m and "no \"family\"" in m for m in msgs), msgs)
        self.assertTrue(any("other_assoc" in m and "ASSOCIATION_SOURCES" in m for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
