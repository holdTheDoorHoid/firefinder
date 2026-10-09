"""Approximate positions from USGS GNIS (DESIGN.md 3.5, "Approximate locations").

Run: python3 -m unittest discover -s pipeline
"""

from __future__ import annotations

import json
import unittest

import contextlib
import io

import fetch_gnis_places as F
import merge as M
from test_merge import TODAY, rec, write_sources
from test_merge import Workspace as BaseWorkspace


class Workspace(BaseWorkspace):
    """test_merge's workspace, with a GNIS extract (gnis_file) kept in the sources folder."""

    gnis: dict | None = None

    def run(self, by_source: dict[str, list[dict]] | None = None, photos_manifest: dict | None = None) -> dict:
        if by_source is not None:
            for f in self.sources.glob("*.json"):
                f.unlink()
            write_sources(self.sources, by_source)
        if self.gnis is not None:
            (self.sources / M.GNIS_FILE).write_text(json.dumps(self.gnis), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            return M.run(self.sources, self.towers, self.report, TODAY, log=lambda *a, **k: None,
                         photos_manifest=photos_manifest or {}, research_dir=self.research)


def gnis_file(ws: Workspace, features: dict[str, list[list]], counties: dict[str, list[str]], keys: dict[str, list[str]] | None = None) -> None:
    """A small data/sources/gnis_places.json. `keys` defaults to every feature name, so every
    test record whose name matches is "looked up"."""
    if keys is None:
        keys = {st: sorted({M.gnis_feature_key(r[1]) for r in rows} - {None}) for st, rows in features.items()}
    ws.sources.mkdir(parents=True, exist_ok=True)
    ws.gnis = {"source": "gnis_places", "kind": "reference", "retrieved": TODAY,
               "keys": keys, "counties": counties, "features": features}


AL = {"AL": ["Clay", "Randolph", "St. Clair"]}
# Black Jack Ridge (a ridge in Clay County), a town of Ashland, two Bald Knobs in Randolph County.
FEATURES = {"AL": [
    [100, "Black Jack Ridge", "Ridge", "Clay", 33.30, -85.80],
    [101, "Ashland", "Populated Place", "Clay", 33.27, -85.84],
    [102, "Bald Knob", "Summit", "Randolph", 33.40, -85.50],
    [103, "Bald Knob", "Summit", "Randolph", 33.20, -85.45],
    [104, "Cheaha Range", "Range", "Clay", 33.35, -85.81],
    [105, "Horn Mountain", "Summit", "Clay", 33.10, -85.70],
]}


def weebly(key: str, name: str, county: str | None, lat: float | None = None, lon: float | None = None, **kw) -> dict:
    return rec("eastern_us_lookouts", f"al:{key}", name, lat, lon, "AL", county=county, kind=kw.pop("kind", None), status="unknown", **kw)


class Keys(unittest.TestCase):
    def test_lookout_names_lose_their_lookout_words(self):
        self.assertEqual(M.gnis_lookout_keys("Bald Knob Fire Tower"), ["baldknob"])
        self.assertEqual(M.gnis_lookout_keys("Bald Knob Tower Site"), ["baldknob"])
        self.assertEqual(M.gnis_lookout_keys("Baldknob L.O."), ["baldknob"])
        self.assertEqual(M.gnis_feature_key("Bald Knob"), "baldknob")

    def test_mount_and_mountain(self):
        self.assertEqual(M.gnis_lookout_keys("Mt. Pisgah"), [M.gnis_feature_key("Mount Pisgah")])
        self.assertEqual(M.gnis_lookout_keys("Pisgah Mtn"), [M.gnis_feature_key("Pisgah Mountain")])
        self.assertEqual(M.gnis_lookout_keys("Pisgah Mt."), [M.gnis_feature_key("Pisgah Mountain")])
        self.assertNotEqual(M.gnis_lookout_keys("Mount Pisgah"), [M.gnis_feature_key("Pisgah Mountain")])

    def test_numbers_qualifiers_and_notes(self):
        self.assertEqual(M.gnis_lookout_keys("Bald Knob #2"), ["baldknob2"])           # not Bald Knob
        self.assertEqual(M.gnis_lookout_keys("Mountain Lookout"), [])                  # nothing to look up
        self.assertEqual(M.gnis_lookout_keys("Fork Hill Tower Site (Tioga County)"), ["forkhill"])
        self.assertEqual(M.gnis_lookout_keys("Putnam (Liberty)"), ["putnam", "liberty"])
        self.assertEqual(M.gnis_lookout_keys("Lookout Mountain"), ["lookoutmountain"])
        self.assertEqual(M.gnis_lookout_keys("The Pinnacle"), [M.gnis_feature_key("The Pinnacle")])
        self.assertIsNone(M.gnis_feature_key("Bald Knob (historical)"))

    def test_counties(self):
        self.assertEqual(M.county_key("St. Louis County"), M.county_key("Saint Louis"))
        self.assertEqual(M.county_key("Prince George's"), M.county_key("Prince Georges"))
        self.assertNotEqual(M.county_key("Bedford (city)"), M.county_key("Bedford"))
        self.assertEqual(M.county_keys("Siskiyou/ Trinity"), {"siskiyou", "trinity"})
        self.assertEqual(M.county_keys("King and Queen"), {"kingandqueen"})
        self.assertEqual(M.county_keys("Miami-Dade"), {"miamidade"})


class Lookup(unittest.TestCase):
    def setUp(self):
        keys = {"AL": ["blackjackridge", "ashland", "baldknob", "cheaharange", "hornmountain", "nowhere"]}
        self.g = M.GnisIndex({"keys": keys, "counties": AL, "features": FEATURES})

    def test_outcomes(self):
        self.assertEqual(self.g.lookup("AL", "Clay", ["blackjackridge"])["outcome"], "summit")
        self.assertEqual(self.g.lookup("AL", "Clay County", ["blackjackridge"])["feature"].id, 100)
        town = self.g.lookup("AL", "Clay", ["ashland"])
        self.assertEqual((town["outcome"], town["town"].name), ("town", "Ashland"))
        self.assertEqual(self.g.lookup("AL", "Randolph", ["baldknob"])["outcome"], "ambiguous")
        self.assertEqual(self.g.lookup("AL", "Clay", ["baldknob"])["outcome"], "none")      # other county
        self.assertEqual(self.g.lookup("AL", "Clay", ["cheaharange"])["outcome"], "none")   # Range is not high ground here
        self.assertEqual(self.g.lookup("AL", None, ["blackjackridge"])["outcome"], "no_county")
        self.assertEqual(self.g.lookup("AL", "Clay/Randolph", ["blackjackridge"])["outcome"], "county_unknown")
        self.assertEqual(self.g.lookup("AL", "Clay", ["notinthefile"])["outcome"], "not_looked_up")
        self.assertEqual(self.g.lookup("AL", "Clay", [])["outcome"], "no_name")

    def test_extract_keeps_only_matching_names(self):
        rows = [{"feature_id": "1", "feature_name": "Black Jack Ridge", "feature_class": "Ridge", "state_name": "Alabama",
                 "county_name": "Clay", "prim_lat_dec": "33.3", "prim_long_dec": "-85.8"},
                {"feature_id": "2", "feature_name": "Other Ridge", "feature_class": "Ridge", "state_name": "Alabama",
                 "county_name": "Randolph", "prim_lat_dec": "33.4", "prim_long_dec": "-85.5"},
                {"feature_id": "3", "feature_name": "Black Jack Ridge", "feature_class": "Stream", "state_name": "Alabama",
                 "county_name": "Clay", "prim_lat_dec": "33.3", "prim_long_dec": "-85.8"}]
        features, counties = F.read_gnis(rows, {"AL": {"blackjackridge"}})
        self.assertEqual(features, {"AL": [[1, "Black Jack Ridge", "Ridge", "Clay", 33.3, -85.8]]})
        self.assertEqual(counties, {"AL": {"Clay", "Randolph"}})


class Placement(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        names = sorted({M.gnis_feature_key(r[1]) for r in FEATURES["AL"]} | {"nowhere"})
        gnis_file(self.ws, FEATURES, AL, keys={"AL": names})

    def tearDown(self):
        self.ws.close()

    def test_summit_match_is_placed_approximately_and_unverified(self):
        rep = self.ws.run({"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")]})
        t = self.ws.tower_with_key("eastern_us_lookouts:al:black-jack-ridge")
        loc = t["location"]
        self.assertEqual((loc["lat"], loc["lon"]), (33.3, -85.8))
        self.assertTrue(loc["approximate"])
        self.assertEqual((loc["method"], loc["precision"], loc["from"]), ("gnis_name_match", "approximate", "gnis"))
        self.assertEqual(loc["gnis"], {"id": 100, "name": "Black Jack Ridge", "class": "Ridge", "county": "Clay"})
        self.assertEqual(t["verification"], "unverified")
        self.assertEqual(rep["counts"]["approximate"], 1)
        self.assertEqual(rep["approximate"]["by_class"], {"Ridge": 1})
        self.assertEqual(rep["unplaced"], [])
        self.assertEqual(self.ws.run()["files"]["written"], 0)   # re-run: nothing changes

    def test_town_only_and_no_match_stay_off_the_map(self):
        rep = self.ws.run({"eastern_us_lookouts": [weebly("ashland", "Ashland Fire Tower", "Clay"),
                                                   weebly("nowhere", "Nowhere", "Clay"),
                                                   weebly("bald-knob", "Bald Knob", "Randolph"),
                                                   weebly("no-county", "Black Jack Ridge", None)]})
        self.assertEqual(self.ws.towers_by_id(), {})
        by_key = {u["key"]: u for u in rep["unplaced"]}
        ash = by_key["eastern_us_lookouts:al:ashland"]
        self.assertEqual((ash["gnis"], ash["town"]["name"]), ("town", "Ashland"))
        self.assertEqual(by_key["eastern_us_lookouts:al:nowhere"]["gnis"], "none")
        self.assertEqual(by_key["eastern_us_lookouts:al:bald-knob"]["gnis"], "ambiguous")
        self.assertEqual(len(by_key["eastern_us_lookouts:al:bald-knob"]["candidates"]), 2)
        self.assertEqual(by_key["eastern_us_lookouts:al:no-county"]["gnis"], "no_county")
        rows = {r["name"]: r for r in rep["unplaced_lookouts"]}
        self.assertEqual(rows["Ashland Fire Tower"]["town"]["name"], "Ashland")
        self.assertEqual(rows["Ashland Fire Tower"]["records"][0]["source"], "eastern_us_lookouts")

    def test_two_sources_on_one_feature_are_one_lookout(self):
        ffla = rec("ffla", "al:black-jack:null:null", "Black Jack Ridge", None, None, "AL", county="Clay")
        self.ws.run({"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")], "ffla": [ffla]})
        towers = list(self.ws.towers_by_id().values())
        self.assertEqual(len(towers), 1)
        self.assertEqual({s["source"] for s in towers[0]["sources"]}, {"ffla", "eastern_us_lookouts"})

    def test_a_record_without_a_county_joins_the_lookout_gnis_places(self):
        # The same on the first run as on a later one, when place_without_coords would find the tower.
        ffla = rec("ffla", "al:black-jack-ridge:null:null", "Black Jack Ridge Lookout", None, None, "AL")
        self.ws.run({"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")], "ffla": [ffla]})
        towers = list(self.ws.towers_by_id().values())
        self.assertEqual(len(towers), 1)
        self.assertEqual({s["source"] for s in towers[0]["sources"]}, {"ffla", "eastern_us_lookouts"})
        self.assertEqual(self.ws.run()["files"]["written"], 0)

    def test_a_record_saying_it_was_not_a_lookout_keeps_its_namesake_off_the_map(self):
        ffla = rec("ffla", "al:black-jack-ridge:null:null", "Black Jack Ridge", None, None, "AL",
                   extra={"section": "Sites determined NOT to have been used as wildland fire lookouts"})
        for _ in range(2):
            rep = self.ws.run({"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")], "ffla": [ffla]})
            self.assertEqual(self.ws.towers_by_id(), {})
            self.assertEqual({u["gnis"] for u in rep["unplaced"]}, {"out_of_scope"})
            self.assertTrue(all(u["out_of_scope"].startswith("Not a fire lookout") for u in rep["unplaced_lookouts"]))

    def test_not_placed_on_top_of_a_lookout_already_on_the_map(self):
        osm = rec("osm", "node/1", "Fire Tower", 33.302, -85.801, "AL")   # 230 m from the ridge's GNIS point
        rep = self.ws.run({"osm": [osm], "eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")]})
        self.assertEqual(len(self.ws.towers_by_id()), 1)
        u = rep["unplaced"][0]
        self.assertEqual((u["gnis"], u["near"]), ("near_mapped_lookout", self.ws.tower_with_key("osm:node/1")["id"]))

    def test_out_of_scope_records_are_not_placed(self):
        ffla = rec("ffla", "al:horn:null:null", "Horn Mountain", None, None, "AL", county="Clay", status_raw="Proposed", status="unknown", kind=None)
        rep = self.ws.run({"ffla": [ffla]})
        self.assertEqual(self.ws.towers_by_id(), {})
        self.assertEqual(rep["unplaced"][0]["gnis"], "out_of_scope")

    def test_research_cannot_lift_the_unverified_badge(self):
        self.ws.run({"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")]})
        tid = self.ws.tower_with_key("eastern_us_lookouts:al:black-jack-ridge")["id"]
        self.ws.write_research({"id": tid, "researched": TODAY, "summary": "A ridge tower.", "facts": {},
                                "verification": {"verdict": "pass", "checked": TODAY}, "sources": []})
        self.ws.run()
        self.assertEqual(self.ws.towers_by_id()[tid]["verification"], "unverified")


class LaterRealPosition(unittest.TestCase):
    """The owner's rule: any real coordinate replaces an approximate pin on a later merge, the
    tower keeps its id, and the approximate position is never used to match anything."""

    def setUp(self):
        self.ws = Workspace()
        gnis_file(self.ws, FEATURES, AL)
        self.first = {"eastern_us_lookouts": [weebly("black-jack-ridge", "Black Jack Ridge", "Clay")]}
        self.ws.run(self.first)
        self.tid = self.ws.tower_with_key("eastern_us_lookouts:al:black-jack-ridge")["id"]
        self.assertTrue(self.ws.towers_by_id()[self.tid]["location"]["approximate"])

    def tearDown(self):
        self.ws.close()

    def test_a_later_record_with_coordinates_joins_by_name_county_and_state(self):
        # FFLA later publishes the lookout with its real position, 6 km from the GNIS point.
        ffla = rec("ffla", "al:black-jack-ridge:33.35:-85.75", "Black Jack Ridge Lookout", 33.35, -85.75, "AL", county="Clay County")
        rep = self.ws.run({**self.first, "ffla": [ffla]})
        towers = self.ws.towers_by_id()
        self.assertEqual(list(towers), [self.tid])                     # no duplicate, same id
        t = towers[self.tid]
        self.assertEqual({s["key"] for s in t["sources"]}, {"eastern_us_lookouts:al:black-jack-ridge", ffla["key"]})
        self.assertEqual((t["location"]["lat"], t["location"]["lon"], t["location"]["from"]), (33.35, -85.75, "ffla"))
        self.assertNotIn("approximate", t["location"])
        self.assertEqual(rep["counts"]["approximate"], 0)
        self.assertIn("approximate_replaced", {r["type"] for r in rep["review"]})
        self.assertEqual(self.ws.run()["files"]["written"], 0)

    def test_the_same_record_gaining_coordinates_replaces_the_pin(self):
        moved = weebly("black-jack-ridge", "Black Jack Ridge", "Clay", lat=33.36, lon=-85.77)
        self.ws.run({"eastern_us_lookouts": [moved]})
        t = self.ws.towers_by_id()[self.tid]
        self.assertEqual((t["location"]["lat"], t["location"]["lon"]), (33.36, -85.77))
        self.assertNotIn("approximate", t["location"])

    def test_a_same_name_record_in_another_county_does_not_join(self):
        other = rec("ffla", "al:black-jack-ridge:33.6:-86.3", "Black Jack Ridge", 33.6, -86.3, "AL", county="St. Clair")
        self.ws.run({**self.first, "ffla": [other]})
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 2)
        self.assertTrue(towers[self.tid]["location"]["approximate"])

    def test_a_record_without_a_county_joins_only_near_the_pin(self):
        near = rec("osm", "node/7", "Black Jack Ridge Lookout", 33.32, -85.82, "AL")   # 3 km from the pin
        far = rec("wikidata", "Q1", "Black Jack Ridge Lookout", 34.6, -86.9, "AL")    # 175 km away
        self.ws.run({**self.first, "osm": [near], "wikidata": [far]})
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 2)
        self.assertEqual({s["key"] for s in towers[self.tid]["sources"]}, {"eastern_us_lookouts:al:black-jack-ridge", "osm:node/7"})

    def test_the_pin_is_never_used_to_match(self):
        # A differently named lookout 20 m from the pin would join a real tower there ("within
        # 100 m whatever the names"); it must not join the approximate one.
        osm = rec("osm", "node/9", "Clay County Fire Tower", 33.3001, -85.8001, "AL")
        self.ws.run({**self.first, "osm": [osm]})
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 2)
        self.assertEqual([s["key"] for s in towers[self.tid]["sources"]], ["eastern_us_lookouts:al:black-jack-ridge"])

    def test_a_from_scratch_run_gives_the_same_id(self):
        for p in self.ws.towers.rglob("*.json"):
            p.unlink()
        self.ws.run(self.first)
        self.assertEqual(list(self.ws.towers_by_id()), [self.tid])


class CountyNames(unittest.TestCase):
    def test_a_record_without_coordinates_joins_a_tower_in_the_same_county_however_spelt(self):
        ws = Workspace()
        try:
            tower = rec("ffla", "ny:catamount:44.3:-75.0", "Catamount Mountain", 44.3, -75.0, "NY", county="St. Lawrence")
            weeb = rec("eastern_us_lookouts", "ny:catamount", "Catamount Mountain", None, None, "NY", county="St Lawrence")
            line = rec("ffla", "ca:cory:41.0:-122.9", "Cory Peak", 41.0, -122.9, "CA", county="Siskiyou/ Trinity")
            west = rec("west_us_lookouts", "ca:cory", "Cory Peak", None, None, "CA", county="Trinity")
            rep = ws.run({"ffla": [tower, line], "eastern_us_lookouts": [weeb], "west_us_lookouts": [west]})
            self.assertEqual(rep["unplaced"], [])
            self.assertEqual(len(ws.towers_by_id()), 2)
        finally:
            ws.close()


if __name__ == "__main__":
    unittest.main()
