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

    def run(self, by_source: dict[str, list[dict]] | None = None) -> dict:
        if by_source is not None:
            for f in self.sources.glob("*.json"):
                f.unlink()
            write_sources(self.sources, by_source)
        with contextlib.redirect_stdout(io.StringIO()):
            return M.run(self.sources, self.towers, self.report, TODAY, log=lambda *a, **k: None)

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
        self.assertGreaterEqual(self.s("Colville Museum (Relocated Graves Mountain)", "Graves Mountain Lookout"), 0.95)
        self.assertGreaterEqual(self.s("Putnam (Liberty)", "Liberty"), 0.95)

    def test_different_lookouts(self):
        # Peak/Mountain/Butte are stripped, but Knob is not: no strong match
        self.assertLess(self.s("Bald Mountain", "Bald Knob"), M.STRONG)
        self.assertLess(self.s("Crescent Lake North", "Crescent Lake South"), M.PARTIAL)
        self.assertLess(self.s("Chilco Mountain (North)", "Chilco Mountain Lookout – South"), M.PARTIAL)
        self.assertLess(self.s("Valentine NWR 1", "Valentine NWR 2"), M.PARTIAL)
        self.assertLess(self.s("Mineral Mountain", "Mission Mountain"), M.STRONG)
        self.assertLess(self.s("Little Baldy", "Baldy"), M.STRONG)

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

    def test_out_of_scope_hidden(self):
        self.ws.run({"ffla": [rec("ffla", "t", "Grandview", 35.94, -111.98, "AZ", kind="tree"),
                              rec("ffla", "c", "Bear Point", 45.5, -115.5, kind="camp")]})
        tree = self.ws.tower_with_key("ffla:t")
        self.assertTrue(tree["hidden"])
        self.assertIn("Tree", tree["hidden_reason"])
        self.assertTrue(self.ws.tower_with_key("ffla:c")["hidden"])

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
        self.assertTrue(t["photos"][0]["url"].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/"))


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


if __name__ == "__main__":
    unittest.main()
