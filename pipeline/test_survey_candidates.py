"""Tests for pipeline/regional/survey_candidates.py (the curated_ak extract from the Alaska survey's
hand-compiled candidates) and pipeline/regional/alberta_wildfire.py (Alberta Wildfire's lookout
layer), with small inline fixtures.

Run: python3 -m unittest discover -s pipeline
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGIONAL = HERE / "regional"
sys.path.insert(0, str(HERE))
import structure  # noqa: E402


def load_regional(name: str):
    """regional/<name>.py, without leaving its bare `_common` import (or its sys.path entries) behind
    for the rest of the test run (pipeline/_common.py has the same module name)."""
    saved_path = list(sys.path)
    saved = {k: sys.modules.pop(k, None) for k in ("_common",)}
    sys.path.insert(0, str(REGIONAL))
    try:
        spec = importlib.util.spec_from_file_location(f"regional_{name}_under_test", REGIONAL / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved_path
        for k, v in saved.items():
            sys.modules.pop(k, None)
            if v is not None:
                sys.modules[k] = v
    return mod


sc = load_regional("survey_candidates")
aw = load_regional("alberta_wildfire")
KINDS = {"tower", "ground", "unknown", "tree", "point", "rooftop"}


def cand(**kw) -> dict:
    c = {"name": "Test Fire Tower", "other_names": [], "country": "CA", "region": "SK", "county": None,
         "lat": None, "lon": None, "location_from": None, "kind": "tower", "status": "unknown",
         "built": None, "agency": None, "staffed_now": None, "rental": None, "access_note": None,
         "sources": ["https://www.websiteservice.ca/firetowers_page4.htm"]}
    c.update(kw)
    return c


def one(c: dict, source: str = "curated_ak") -> dict:
    return sc.build_records([c], source, KINDS)[0]


class PositionTest(unittest.TestCase):
    WS = "https://www.websiteservice.ca/firetowers_page4.htm"

    def test_published_position_is_used(self):
        r = one(cand(lat=53.71164, lon=-105.99783, location_from=self.WS))
        self.assertEqual((r["lat"], r["lon"]), (53.71164, -105.99783))

    def test_location_hint_is_never_a_position(self):
        hint = {"lat": 64.8636275, "lon": -147.6432963, "gnis_name": "Birch Hill"}
        r = one(cand(region="AK", country="US", county="Fairbanks North Star", location_hint=hint))
        self.assertIsNone(r["lat"])
        self.assertIsNone(r["lon"])
        self.assertEqual(r["extra"]["location_hint"], hint)   # kept for people only
        # A position with no source URL of its own is not used either.
        r = one(cand(lat=53.7, lon=-106.0, location_from=None))
        self.assertIsNone(r["lat"])
        self.assertIn("position_note", r["extra"])

    def test_alberta_layer_positions_are_dropped(self):
        url = "https://geospatial.alberta.ca/titan/rest/services/friaa/friaa_firesmart_vector_data/MapServer/0"
        r = one(cand(region="AB", lat=55.111111, lon=-115.222222, location_from=url))
        self.assertIsNone(r["lat"])
        self.assertNotIn("55.111111", json.dumps(r))

    def test_flagged_positions_are_dropped(self):
        self.assertIsNone(one(cand(lat=54.7, lon=-105.5, location_from=self.WS,
                                   extra={"coord_problem": "impossible digits"}))["lat"])
        self.assertIsNone(one(cand(lat=53.9523, lon=-102.2624, location_from=self.WS,
                                   extra={"placeholder_position": {"lat": 53.9523, "lon": -102.2624}}))["lat"])
        self.assertIsNone(one(cand(name="Dube Fire Tower", lat=54.77, lon=-105.5, location_from=self.WS))["lat"])
        # outside the record's region (a Saskatchewan record with an Ontario point)
        self.assertIsNone(one(cand(lat=48.6, lon=-93.4, location_from=self.WS))["lat"])


class FieldsTest(unittest.TestCase):
    def test_register_splitting(self):
        r = one(cand(extra={"registers": [{"register": "NHLR", "number": "CAN 2, AB 2"}]}))
        self.assertEqual(r["registers"], [{"register": "NHLR", "number": "CAN 2", "state_number": "AB 2"}])
        r = one(cand(registers=[{"register": "FFLOS", "number": "CAN 1", "state_number": "ON 1"}],
                     extra={"registers": [{"register": "FFLOS", "number": "CAN 1, ON 1"}]}))
        self.assertEqual(r["registers"], [{"register": "FFLOS", "number": "CAN 1", "state_number": "ON 1"}])

    def test_alaska_county_as_gnis_writes_it(self):
        self.assertEqual(one(cand(region="AK", county="Matanuska-Susitna Borough"))["county"], "Matanuska-Susitna")
        self.assertEqual(one(cand(region="AK", county="Yukon-Koyukuk Census Area"))["county"], "Yukon-Koyukuk")
        self.assertEqual(one(cand(county="Division No. 18"))["county"], "Division No. 18")

    def test_names_kind_links(self):
        url2 = "http://nhlr.org/lookouts/can/ab/baseline-lookout/"
        r = one(cand(other_names=["Old Test"], kind="cupola", sources=[url2, url2],
                     evidence=[{"year": 1970, "text": "x", "url": "https://archive.org/details/alaskafirereportunit"}]))
        self.assertEqual(r["extra"]["aliases"], ["Old Test"])
        self.assertEqual(r["kind"], "unknown")                      # not in the vocabulary
        self.assertEqual(r["url"], url2)
        self.assertEqual([l["url"] for l in r["links"]], [url2, "https://archive.org/details/alaskafirereportunit"])
        self.assertTrue(all(l["kind"] == "reference" and l["label"] for l in r["links"]))

    def test_events(self):
        url = "https://archive.org/details/alaskafirereportunit"
        r = one(cand(built=1935, evidence=[
            {"year": 1970, "text": "lookouts 'manned at Bald Mountain' in 1970", "url": url},
            {"year": 1979, "text": "a fire tower is on the summit", "url": url}]))
        self.assertEqual([(e["year"], e["event"]) for e in r["events"]], [(1935, "built"), (1970, "staffed")])
        staffed = r["events"][1]
        self.assertEqual((staffed["from"], staffed["source_url"]), ("curated_ak", url))
        self.assertLessEqual(len(staffed["note"]), 120)


class StatusTest(unittest.TestCase):
    def read(self, value: str) -> dict:
        return structure.read_record("curated_ak", {"status_raw": value, "status": "unknown", "extra": {}})

    def test_survey_status_table(self):
        for value in sc.STATUS_VALUES:
            self.assertEqual(self.read(value)["unmapped"], [], value)
            self.assertEqual(self.read(value)["status"], sc.STATUS_OF[value], value)
        self.assertEqual(self.read("likely gone")["status_note"], "Sources suggest it is gone.")
        self.assertEqual(self.read("unknown")["status"], "unknown")
        # anything outside the closed set is written as "unknown"
        self.assertEqual(one(cand(status="perhaps"))["status_raw"], "unknown")


class KeyTest(unittest.TestCase):
    def test_keys_are_stable(self):
        a = cand(name="Bald Mountain Lookout", region="AK", country="US", nearest_place="Palmer")
        b = cand(name="Bald Mountain Lookout", region="AK", country="US", nearest_place="Talkeetna")
        c = cand(name="Lazy Mountain Lookout", region="AK", country="US")
        k1 = [(r["key"], r["extra"]["nearest_place"] if "nearest_place" in r["extra"] else None)
              for r in sc.build_records([a, b, c], "curated_ak", KINDS)]
        k2 = [(r["key"], r["extra"]["nearest_place"] if "nearest_place" in r["extra"] else None)
              for r in sc.build_records([c, b, a], "curated_ak", KINDS)]
        self.assertEqual(k1, k2)
        self.assertEqual([k for k, _ in k1], ["curated_ak:ak:bald-mountain-lookout",
                                              "curated_ak:ak:bald-mountain-lookout-2",
                                              "curated_ak:ak:lazy-mountain-lookout"])

    def test_source_ids(self):
        self.assertEqual(sc.survey_source_id("ak-hi"), "curated_ak")
        self.assertEqual(sc.survey_source_id("prairies-north"), "survey_prairies_north")


class AlaskaFileTest(unittest.TestCase):
    """The committed extract, when present: six Alaska lookouts, no positions, GNIS county names."""

    def test_committed_extract(self):
        path = HERE.parent / "data" / "sources" / "curated_ak.json"
        if not path.exists():
            self.skipTest("data/sources/curated_ak.json not written")
        data = json.loads(path.read_text(encoding="utf-8"))
        recs = data["records"]
        self.assertEqual(data["source"], "curated_ak")
        self.assertEqual(len(recs), 6)
        self.assertTrue(all(r["lat"] is None and r["lon"] is None for r in recs))
        self.assertNotIn("glacier", json.dumps([r["name"] for r in recs]).lower())
        gnis = HERE.parent / "data" / "sources" / "gnis_places.json"
        if gnis.exists():
            counties = set(json.loads(gnis.read_text(encoding="utf-8"))["counties"]["AK"])
            self.assertEqual([r["county"] for r in recs if r["county"] not in counties], [])


LAYER = {"features": [
    {"attributes": {"ID": 412, "LOOKOUT_ID": "HM", "NAME": "HOUSE MOUNTAIN", "LOOKOUT_TYPE": "Steel",
                    "YEAR_CONSTRUCTED": 2015, "TOWER_HEIGHT": 30.0, "ELEVATION": 1176.34, "MAP_NUMBER": "83O/04",
                    "LOCATION_VERIFIED": "Y", "ACTIVE": "Y", "ACCESS_MODE": "drive", "WEATHER_STATION": "N",
                    "LATITUDE": 55.111111, "LONGITUDE": -115.222222, "LOCATION_VERIFIED_BY": "AC1"}},
    {"attributes": {"ID": 366, "LOOKOUT_ID": "AC", "NAME": "ADAMS CREEK", "LOOKOUT_TYPE": "Cabin",
                    "YEAR_CONSTRUCTED": 2005, "TOWER_HEIGHT": 5.0, "ELEVATION": 2177.6, "MAP_NUMBER": "83E/10",
                    "LOCATION_VERIFIED": "N", "ACTIVE": "N", "ACCESS_MODE": "Fly", "WEATHER_STATION": "Y",
                    "LATITUDE": 53.333333, "LONGITUDE": -118.444444}},
]}


class AlbertaWildfireTest(unittest.TestCase):
    def test_default_writes_no_coordinates(self):
        recs = aw.build_records(LAYER)
        self.assertEqual([(r["lat"], r["lon"]) for r in recs], [(None, None), (None, None)])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "alberta_wildfire.json"
            orig = aw.load
            aw.load = lambda *a, **k: LAYER
            try:
                aw.main(["--out", str(out)])
            finally:
                aw.load = orig
            text = out.read_text(encoding="utf-8")
        self.assertNotIn("55.111111", text)
        self.assertNotIn("-115.222222", text)
        self.assertNotIn("53.333333", text)

    def test_with_positions_switch(self):
        recs = {r["key"]: r for r in aw.build_records(LAYER, with_positions=True)}
        self.assertEqual((recs["alberta_wildfire:HM"]["lat"], recs["alberta_wildfire:HM"]["lon"]), (55.111111, -115.222222))
        self.assertTrue(recs["alberta_wildfire:AC"]["extra"]["position_approximate"])   # Location Verified = N

    def test_fields(self):
        recs = {r["key"]: r for r in aw.build_records(LAYER)}
        hm, ac = recs["alberta_wildfire:HM"], recs["alberta_wildfire:AC"]
        self.assertEqual((hm["name"], hm["region"], hm["country"], hm["agency"]), ("House Mountain", "AB", "CA", "Alberta Wildfire"))
        self.assertEqual((hm["kind"], ac["kind"]), ("tower", "ground"))
        self.assertEqual((hm["built"], hm["events"][0]["event"], hm["events"][0]["year"]), (2015, "built", 2015))
        self.assertEqual((hm["extra"]["height_m"], hm["elevation_m"]), (30.0, 1176.3))
        self.assertEqual(hm["extra"]["staffing_hint"], "staffed")
        self.assertEqual(hm["extra"]["access_level"], "closed")
        self.assertEqual(hm["extra"]["access_note"], aw.ACCESS_NOTE)
        for k in ("staffing_hint", "access_level", "access_note"):
            self.assertNotIn(k, ac["extra"])                      # not active: no staffing, no access
        self.assertEqual(ac["extra"]["access_mode"], "fly")

    def test_structure_reading(self):
        for r in aw.build_records(LAYER):
            got = structure.read_record("alberta_wildfire", r)
            self.assertEqual(got["unmapped"], [])
        hm = structure.read_record("alberta_wildfire", aw.build_records(LAYER)[1])
        self.assertEqual((hm["kind"], hm["material"], hm["status"]), ("tower", "steel", "standing"))
        ac = structure.read_record("alberta_wildfire", aw.build_records(LAYER)[0])
        self.assertEqual((ac["kind"], ac["status"]), ("ground", "unknown"))


if __name__ == "__main__":
    unittest.main()
