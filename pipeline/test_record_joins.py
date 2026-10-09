"""Tests for RECORD_JOINS moving records between towers and retiring the tower left empty, for
LOCATION_PICKS, and for validate.py's checks of a retired tower. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import merge as M
import record_joins
import validate as V
from test_merge import Workspace, rec


def pair(**kw) -> dict:
    """Two sources' records for one lookout 4 km apart (past the 1.5 km a strong name may span), as the
    western weebly sites and FFLA give Cable Mountain, MT."""
    return {
        "ffla": [rec("ffla", "cable", "Cable Mountain", 46.2177, -113.2213, "MT", status="gone")],
        "west_us_lookouts": [rec("west_us_lookouts", "mt:cable-mountain", "Cable Mountain", 46.2527, -113.1934, "MT", status="unknown", **kw)],
    }


class MovingRecords(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()
        self.saved = dict(M.RECORD_JOINS)
        M.RECORD_JOINS.clear()

    def tearDown(self) -> None:
        M.RECORD_JOINS.clear()
        M.RECORD_JOINS.update(self.saved)
        self.ws.close()

    def two_towers(self) -> tuple[str, str]:
        self.ws.run(pair())
        keep = self.ws.tower_with_key("ffla:cable")["id"]
        gone = self.ws.tower_with_key("west_us_lookouts:mt:cable-mountain")["id"]
        self.assertNotEqual(keep, gone)
        return keep, gone

    def test_a_pin_moves_a_record_out_of_a_tower_of_its_own_and_the_empty_tower_is_retired(self) -> None:
        keep, gone = self.two_towers()
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        rep = self.ws.run()
        towers = self.ws.towers_by_id()
        self.assertEqual({s["key"] for s in towers[keep]["sources"]}, {"ffla:cable", "west_us_lookouts:mt:cable-mountain"})
        old = towers[gone]                       # the file, and its id, stay
        self.assertTrue(old["hidden"])
        self.assertEqual(old["merged_into"], keep)
        self.assertEqual(old["sources"], [])
        self.assertIn(keep, old["hidden_reason"])
        self.assertEqual(rep["merged_towers"], [{"id": gone, "into": keep, "name": "Cable Mountain",
                                                 "moved_records": ["west_us_lookouts:mt:cable-mountain"]}])
        self.assertEqual((rep["counts"]["towers"], rep["counts"]["merged_away"], rep["counts"]["visible"]), (1, 1, 1))
        self.assertEqual(rep["near_misses"]["count"], 0)

    def test_a_join_a_human_pinned_is_not_flagged_for_its_different_names(self) -> None:
        records = {"ffla": [rec("ffla", "cable", "Cable Mountain", 46.2177, -113.2213, "MT")],
                   "osm": [rec("osm", "n1", "Georgetown Lake Lookout", 46.2527, -113.1934, "MT")]}
        self.ws.run(records)
        M.RECORD_JOINS["osm:n1"] = "ffla:cable"
        rep = self.ws.run()
        self.assertEqual(len(self.ws.towers_by_id()), 2)       # one retired
        self.assertEqual([r for r in rep["review"] if r["type"] == "matched_different_names"], [])

    def test_a_second_run_changes_nothing(self) -> None:
        keep, gone = self.two_towers()
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        self.ws.run()
        before = {p.name: p.read_text() for p in self.ws.towers.rglob("*.json")}
        rep = self.ws.run()
        self.assertEqual(rep["files"]["written"], 0)
        self.assertEqual({p.name: p.read_text() for p in self.ws.towers.rglob("*.json")}, before)
        self.assertEqual(rep["matching"]["by_source"]["west_us_lookouts"], {"key": 1})

    def test_nothing_matches_a_retired_tower_afterwards(self) -> None:
        keep, gone = self.two_towers()
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        self.ws.run()
        # a new record right on the retired tower's old spot starts a tower of its own; it does not revive it
        records = pair()
        records["osm"] = [rec("osm", "n1", "Cable Mountain Lookout", 46.2527, -113.1934, "MT")]
        self.ws.run(records)
        towers = self.ws.towers_by_id()
        self.assertEqual(towers[gone]["sources"], [])
        self.assertNotIn(self.ws.tower_with_key("osm:n1")["id"], (gone,))

    def test_a_pin_to_a_tower_id_that_was_retired_follows_it_on(self) -> None:
        keep, gone = self.two_towers()
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        self.ws.run()
        records = pair()
        records["osm"] = [rec("osm", "n9", "Cable Mtn", 46.9, -113.9, "MT")]
        M.RECORD_JOINS["osm:n9"] = gone          # the old id still works as a target
        self.ws.run(records)
        self.assertEqual(self.ws.tower_with_key("osm:n9")["id"], keep)

    def test_a_tower_that_keeps_other_records_is_not_retired(self) -> None:
        records = pair()
        records["osm"] = [rec("osm", "n1", "Cable Mountain Lookout", 46.2528, -113.1935, "MT")]   # joins the weebly tower
        self.ws.run(records)
        keep = self.ws.tower_with_key("ffla:cable")["id"]
        other = self.ws.tower_with_key("west_us_lookouts:mt:cable-mountain")["id"]
        self.assertEqual(other, self.ws.tower_with_key("osm:n1")["id"])
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        rep = self.ws.run()
        towers = self.ws.towers_by_id()
        self.assertEqual({s["key"] for s in towers[other]["sources"]}, {"osm:n1"})
        self.assertFalse(towers[other]["hidden"])
        self.assertNotIn("merged_into", towers[other])
        self.assertEqual(rep["merged_towers"], [])
        self.assertIn({"type": "record_join_moved", "key": "west_us_lookouts:mt:cable-mountain", "towers": [other, keep]}, rep["review"])

    def test_from_scratch_the_pin_joins_at_once_and_no_second_tower_is_made(self) -> None:
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = "ffla:cable"
        rep = self.ws.run(pair())
        self.assertEqual(len(self.ws.towers_by_id()), 1)
        self.assertEqual(rep["merged_towers"], [])

    def test_towers_pinned_onto_each_other_are_left_for_a_human(self) -> None:
        keep, gone = self.two_towers()
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        M.RECORD_JOINS["ffla:cable"] = gone
        rep = self.ws.run()
        self.assertEqual(len(self.ws.towers_by_id()), 2)
        self.assertTrue(any(r["type"] == "record_join_chain" for r in rep["review"]))

    def test_a_research_file_under_a_retired_id_is_reported(self) -> None:
        keep, gone = self.two_towers()
        self.ws.write_research({"id": gone, "researched": "2026-10-08", "summary": "x", "facts": {}, "events": [], "sources": []})
        M.RECORD_JOINS["west_us_lookouts:mt:cable-mountain"] = keep
        rep = self.ws.run()
        self.assertTrue(any(p["file"] == f"{gone}.json" and "merged into" in p["problem"] for p in rep["research"]["problems"]))


class LocationPicks(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()
        self.saved = dict(M.LOCATION_PICKS)
        M.LOCATION_PICKS.clear()

    def tearDown(self) -> None:
        M.LOCATION_PICKS.clear()
        M.LOCATION_PICKS.update(self.saved)
        self.ws.close()

    def records(self) -> dict:
        # NHLR's pin 400 m from OSM's: the same tower, NHLR (the better source) shown
        return {"nhlr": [rec("nhlr", "US 1", "Sandwich Fire Tower", 41.6778, -70.4283, "MA", registers=[{"register": "NHLR", "number": "US 1"}])],
                "osm": [rec("osm", "n1", "Sandwich Fire Tower", 41.6780, -70.4284, "MA")]}

    def test_the_default_shows_the_best_source(self) -> None:
        self.ws.run(self.records())
        self.assertEqual(self.ws.tower_with_key("nhlr:US 1")["location"]["from"], "nhlr")

    def test_a_pick_shows_the_record_a_human_checked(self) -> None:
        M.LOCATION_PICKS["nhlr:US 1"] = "osm:n1"
        self.ws.run(self.records())
        loc = self.ws.tower_with_key("nhlr:US 1")["location"]
        self.assertEqual((loc["from"], loc["lat"]), ("osm", 41.678))

    def test_a_pick_of_a_record_the_tower_does_not_hold_is_ignored(self) -> None:
        M.LOCATION_PICKS["nhlr:US 1"] = "osm:not-there"
        self.ws.run(self.records())
        self.assertEqual(self.ws.tower_with_key("nhlr:US 1")["location"]["from"], "nhlr")


class TheTable(unittest.TestCase):
    def test_every_entry_names_a_record_and_a_target(self) -> None:
        for key, target in record_joins.RECORD_JOINS.items():
            self.assertRegex(key, r"^[a-z_]+:\S+", key)
            self.assertTrue(target.startswith("us-") or ":" in target, (key, target))
            self.assertNotEqual(key, target)

    def test_a_key_target_comes_from_a_source_matched_before_the_record_it_receives(self) -> None:
        order = {s: i for i, s in enumerate(M.SOURCE_ORDER)}
        for key, target in record_joins.RECORD_JOINS.items():
            if target.startswith("us-"):
                continue
            self.assertLess(order[target.split(":")[0]], order[key.split(":")[0]], (key, target))

    def test_picks_name_records(self) -> None:
        for key, pick in record_joins.LOCATION_PICKS.items():
            self.assertRegex(key, r"^[a-z_]+:\S+")
            self.assertRegex(pick, r"^[a-z_]+:\S+")


class ValidateRetired(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.towers = Path(self.tmp.name) / "towers"
        (self.towers / "or").mkdir(parents=True)
        self.vocab = json.loads(V.DATA.joinpath("vocab.json").read_text())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def tower(self, rid: str, **kw) -> dict:
        r = {
            "id": rid, "name": rid, "other_names": [], "country": "US", "region": "OR", "county": None,
            "location": {"lat": 44.5, "lon": -122.5, "precision": "exact", "from": "ffla"}, "elevation_m": None,
            "kind": "tower", "design": None, "height_m": None, "status": "gone", "registers": [], "agency": None,
            "ownership": "unknown", "access": {"level": "unknown", "note": None}, "staffing": {"status": "unknown"},
            "visit": {}, "rental": None, "events": [], "photos": [], "links": [],
            "sources": [{"source": "ffla", "key": f"ffla:{rid}", "fields": []}], "conflicts": [],
            "verification": "unverified", "locked": [], "hidden": False, "hidden_reason": None, "updated": "2026-10-08",
        }
        r.update(kw)
        return r

    def errors(self, *records: dict) -> list[str]:
        for r in records:
            (self.towers / "or" / f"{r['id']}.json").write_text(json.dumps(r))
        lines: list[str] = []
        V.validate(self.towers, V.DATA / "vocab.json", log=lines.append, research_dir=Path(self.tmp.name) / "r", stories_dir=Path(self.tmp.name) / "s")
        return [x for x in lines if x.startswith("ERROR")]

    def retired(self, into: str = "us-or-b", **kw) -> dict:
        fields = {"hidden": True, "hidden_reason": "Merged", "merged_into": into, "sources": [], **kw}
        return self.tower("us-or-a", **fields)

    def test_a_good_retired_tower_passes(self) -> None:
        self.assertEqual(self.errors(self.retired(), self.tower("us-or-b")), [])

    def test_a_retired_tower_must_be_hidden_have_no_sources_and_name_a_visible_tower(self) -> None:
        self.assertTrue(any("not hidden" in e for e in self.errors(self.retired(hidden=False, hidden_reason=None), self.tower("us-or-b"))))
        self.assertTrue(any("still lists sources" in e for e in self.errors(
            self.retired(sources=[{"source": "ffla", "key": "ffla:x", "fields": []}]), self.tower("us-or-b"))))
        self.assertTrue(any("does not exist" in e for e in self.errors(self.retired(into="us-or-nowhere"))))
        self.assertTrue(any("itself merged away" in e for e in self.errors(
            self.retired(), self.tower("us-or-b", hidden=True, hidden_reason="m", merged_into="us-or-c", sources=[]), self.tower("us-or-c"))))
        self.assertTrue(any("is hidden" in e for e in self.errors(
            self.retired(), self.tower("us-or-b", hidden=True, hidden_reason="Never built"))))

    def test_an_ordinary_tower_still_needs_sources(self) -> None:
        self.assertTrue(any("sources is empty" in e for e in self.errors(self.tower("us-or-b", sources=[]))))

    def test_research_under_a_retired_id_is_an_error(self) -> None:
        research = Path(self.tmp.name) / "r"
        research.mkdir()
        (research / "us-or-a.json").write_text("{}")
        errs = self.errors(self.retired(), self.tower("us-or-b"))
        self.assertTrue(any("merged into us-or-b" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
