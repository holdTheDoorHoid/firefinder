"""Tests for pipeline/structure.py: kinds, materials and statuses, and the guard that every type
and status value in data/sources has a deliberate mapping.

Run: python3 -m unittest discover -s pipeline
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import structure as st  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class GuardTest(unittest.TestCase):
    def test_every_source_value_has_a_mapping(self):
        """A new Type or Status wording from a crawl must be mapped in structure.py, not become
        "unknown" quietly. Add it to the table for its source (FFLA_TYPES, FFLA_STATUS, ...)."""
        bad = st.unmapped_values(REPO / "data" / "sources")
        lines = [f"{sid}: {k} ({n} records)" for sid, vals in bad.items() for k, n in sorted(vals.items())]
        self.assertEqual(lines, [], "values with no mapping in pipeline/structure.py:\n" + "\n".join(lines))

    def test_guard_notices_a_new_value(self):
        raw = {"key": "ffla:x", "type_raw": "Hot Air Balloon", "status_raw": "Floating away", "extra": {}}
        self.assertEqual(st.read_record("ffla", raw)["unmapped"],
                         [("type", "Hot Air Balloon"), ("status", "Floating away")])
        self.assertEqual(st.read_record("newsource", {"type_raw": "Tower"})["unmapped"], [("type", "Tower")])
        self.assertEqual(st.read_record("osm", {"extra": {"tower_construction": "bamboo"}})["unmapped"],
                         [("osm_tag", "tower_construction=bamboo")])

    def test_tables_use_the_vocabulary(self):
        vocab = json.loads((REPO / "data" / "vocab.json").read_text())
        kinds, statuses = set(vocab["kind"]), set(vocab["status"])
        self.assertEqual(kinds, set(st.kind_ids()), "data/vocab.json and data/structure_kinds.json list the same kinds")
        self.assertEqual(set(vocab["material"]), set(st.material_ids()))
        self.assertEqual(set(vocab["material"]), set(st.MATERIALS))
        self.assertEqual(set(vocab["role"]), set(st.role_ids()))
        for table in st.SIMPLE_TYPES.values():
            for info in table.values():
                self.assertIn(info.kind or "unknown", kinds)
                self.assertTrue(info.material is None or info.material in st.MATERIALS)
                self.assertTrue(info.role is None or info.role in vocab["role"])
        for table in [*st.SIMPLE_STATUS.values(), st.FFLA_STATUS_YEAR]:
            for info in table.values():
                self.assertIn(info.status or "unknown", statuses)
                self.assertTrue(info.event is None or info.event in vocab["event"])
        for k in st.WORD_KINDS:
            self.assertIn(k, kinds)

    def test_scope_table(self):
        self.assertEqual(st.no_structure_kinds(), {"camp", "tree", "point"})
        self.assertEqual(st.hidden_kind_reasons(), {}, "owner decision 2026-10-08: no kind is hidden")
        groups = {g["id"] for g in st.load_vocab()["groups"]}
        self.assertEqual(set(st.kind_group().values()), groups)


class TypeTest(unittest.TestCase):
    def kind(self, source, value):
        return st.read_record(source, {"type_raw": value, "kind": "unknown"})["kind"]

    def test_ffla_types(self):
        self.assertEqual(self.kind("ffla", "Tower"), "tower")
        self.assertEqual(self.kind("ffla", "2-StoryCab"), "two_story")
        self.assertEqual(self.kind("ffla", "Tower/Ground*"), "tower")
        self.assertEqual(self.kind("ffla", "Rooftop Cab"), "rooftop")
        self.assertEqual(self.kind("ffla", "Grain Elevator"), "rooftop")
        self.assertEqual(self.kind("ffla", "Trailer"), "mobile")
        self.assertEqual(self.kind("ffla", "Bus/cupola"), "mobile")
        self.assertEqual(self.kind("ffla", "Firefinder"), "point")
        self.assertEqual(self.kind("ffla", "Map Board (cabin)"), "ground")
        self.assertEqual(self.kind("ffla", "Crowsnest"), "platform")
        self.assertEqual(self.kind("ffla", "Unk"), "unknown")

    def test_aws_is_a_role_not_a_kind(self):
        r = st.read_record("ffla", {"type_raw": "AWS", "kind": "unknown"})
        self.assertEqual((r["kind"], r["roles"]), ("unknown", ["aws"]))
        r = st.read_record("ffla", {"type_raw": "AWS Tower", "kind": "tower"})
        self.assertEqual((r["kind"], r["roles"]), ("tower", ["aws"]))

    def test_material_from_type(self):
        self.assertEqual(st.read_record("ffla", {"type_raw": "Stone Tower"})["material"], "stone")
        self.assertEqual(st.read_record("ffla", {"type_raw": "Log Crib"})["kind"], "tower")
        self.assertEqual(st.read_record("ffla", {"type_raw": "Log Crib"})["material"], "log")
        self.assertEqual(st.read_record("ffla", {"type_raw": "Wooden Tower"})["material"], "wood")
        r = st.read_record("ffla", {"type_raw": "Stone", "kind": "tower"})
        self.assertEqual((r["kind"], r["material"]), ("unknown", "stone"))

    def test_status_in_the_type_column(self):
        r = st.read_record("ffla", {"type_raw": "Gone", "status_raw": None, "status": "unknown"})
        self.assertEqual(r["status"], "gone")

    def test_wikidata_and_osm(self):
        self.assertEqual(self.kind("wikidata", "lookout tree"), "tree")
        self.assertEqual(self.kind("wikidata", "ranger station; fire lookout tower"), "tower")
        # OSM: the fetcher's reading of the full tags stands.
        r = st.read_record("osm", {"type_raw": "building=fire_lookout", "kind": "two_story", "extra": {"building_material": "wood"}})
        self.assertEqual((r["kind"], r["material"]), ("two_story", "wood"))
        r = st.read_record("osm", {"type_raw": "man_made=tower;tower:type=observation", "kind": "tower",
                                   "extra": {"tower_construction": "lattice"}})
        self.assertIsNone(r["material"])


class StatusTest(unittest.TestCase):
    def read(self, source, value, status="unknown"):
        return st.read_record(source, {"status_raw": value, "status": status, "events": []})

    def test_ffla_statuses(self):
        self.assertEqual(self.read("ffla", "Abandoned")["status"], "gone")
        self.assertEqual(self.read("ffla", "Collapsed")["status"], "ruins")
        self.assertEqual(self.read("ffla", "Standing (Ruins)")["status"], "ruins")
        self.assertEqual(self.read("ffla", "Gone**")["status"], "gone")
        self.assertEqual(self.read("ffla", "Private", "standing")["status"], "unknown")
        self.assertIn("private", self.read("ffla", "Private")["flags"])
        self.assertIn("never_built", self.read("ffla", "Never Built")["flags"])

    def test_standing_star_keeps_its_meaning(self):
        r = self.read("ffla", "Standing*")
        self.assertEqual(r["status"], "standing")
        self.assertIn("cab is gone", r["status_note"])
        self.assertIsNone(self.read("ffla", "Standing")["status_note"])

    def test_years_in_a_status_become_events(self):
        r = self.read("ffla", "Burned 2026")
        self.assertEqual(r["status"], "gone")
        self.assertEqual([(e["event"], e["year"]) for e in r["events"]], [("burned", 2026)])
        r = self.read("ffla", "New 2026")
        self.assertEqual((r["status"], r["events"][0]["event"]), ("standing", "rebuilt"))
        self.assertEqual(self.read("ffla", "Removed 2026")["events"][0]["event"], "removed")

    def test_apply_does_not_repeat_an_event_the_fetcher_added(self):
        ev = {"year": 2026, "event": "burned", "note": "From FFLA status column value 'Burned 2026'", "from": "ffla"}
        raw = {"status_raw": "Burned 2026", "status": "gone", "events": [ev]}
        new, _ = st.apply("ffla", raw)
        self.assertEqual(new["events"], [ev])
        self.assertEqual(raw["events"], [ev])  # the source record is not changed

    def test_other_sources(self):
        self.assertEqual(self.read("nj_forest_fire_towers", "Not in service or no longer standing", "gone")["status"], "unknown")
        self.assertEqual(self.read("wikipedia_lookout_lists", "Torn down?", "gone")["status"], "unknown")
        self.assertEqual(self.read("tnlandforms", "moved")["status"], "relocated")
        self.assertEqual(self.read("eastern_us_lookouts", "razed")["status"], "gone")
        # OSM and Wikidata: understood, the fetcher decides.
        self.assertEqual(self.read("osm", "abandoned=yes; ruins=yes", "ruins")["status"], "ruins")
        self.assertEqual(self.read("wikidata", "P576 dissolved/abandoned/demolished date: 2003", "gone")["status"], "gone")


class WordsTest(unittest.TestCase):
    def test_material_and_kind_words(self):
        w = st.structure_words("This 100' Aermotor MC-39 steel tower with 7'x7' steel cab was erected in 1948.")
        self.assertIn("steel tower", w)
        self.assertIn("kind tower", w)
        self.assertEqual(st.words_material(w, "tower"), "steel")
        self.assertEqual(st.words_kind(w), "tower")
        self.assertEqual(st.structure_words("Built in 1932, this 40' timber L-4 tower was abandoned."), ["wood tower", "kind tower"])

    def test_earlier_structures_do_not_count(self):
        w = st.structure_words("The first lookout was a wooden tower. It was replaced in 1950 by a 100-foot steel tower.")
        self.assertEqual(st.words_material(w, "tower"), "steel")
        w = st.structure_words("This steel tower replaced an earlier wooden tower in 1940.")
        self.assertEqual(st.words_material(w, "tower"), "steel")
        w = st.structure_words("A 2 story log cabin was built in 1923, replaced in 1933 by a cab on a log crib.")
        self.assertNotIn("kind two_story", w)
        self.assertEqual(st.structure_words("A watchman's ground cabin sits near the tower."), [])

    def test_present_structure_decides(self):
        w = st.structure_words("A camp was set up in 1923, followed by a log cabin in 1925. The present R-6 flat cab, built in 1962, is staffed.")
        self.assertIsNone(st.words_material(w, "ground"))

    def test_cab_material_is_not_the_towers(self):
        w = st.structure_words("The 14' x 14' wooden cab sits on a tower.")
        self.assertIsNone(st.words_material(w, "tower"))
        self.assertEqual(st.words_material(w, "ground"), "wood")
        self.assertIsNone(st.words_material(["wood tower"], "camp"))

    def test_mixed_and_names(self):
        self.assertEqual(st.words_material(st.structure_words("A unique stone and wood structure."), "ground"), "mixed")
        self.assertEqual(st.structure_words("S-Tree Lookout was built by the U.S. Forest Service."), [])
        self.assertEqual(st.structure_words("Table Rock Lookout is a fine place."), [])
        self.assertEqual(st.words_kind(st.structure_words("The two story ground house with a 12' x 12' cab.")), "two_story")

    def test_trailers_and_roofs(self):
        self.assertEqual(st.words_kind(st.structure_words("In 1957 a trailer was set up on this site.")), "mobile")
        self.assertEqual(st.structure_words("A cab and trailer quarters were erected in 1963."), [])
        self.assertNotIn("kind rooftop", st.structure_words("The only lookout in Alabama with a rooftop observation platform."))

    def test_aws_role(self):
        self.assertIn("role aws", st.structure_words("During 1942-43 it was staffed as an Aircraft Warning Station."))

    def test_words_are_a_closed_vocabulary(self):
        texts = ["This 100' steel tower with a 7'x7' metal cab.", "A log and stone cabin.", "Built of native stone.",
                 "A ground cabin.", "This 10' concrete block tower."]
        for t in texts:
            for w in st.structure_words(t):
                self.assertIn(w, st.STRUCTURE_WORDS)


class DesignTest(unittest.TestCase):
    def test_design_fallback(self):
        self.assertEqual(st.design_material(["aermotor"], "tower"), ("steel", "aermotor"))
        self.assertEqual(st.design_material(["l4", "aermotor"], "tower"), ("steel", "aermotor"))
        self.assertEqual(st.design_material(["l4"], "ground"), ("wood", "l4"))
        # An L-4 cab says nothing about what the tower under it was made of.
        self.assertEqual(st.design_material(["l4"], "tower"), (None, None))
        self.assertEqual(st.design_material(["l5"], "ground"), (None, None))
        self.assertEqual(st.design_material(["aermotor"], "camp"), (None, None))

    def test_designs_json_material_wins(self):
        facts = [{"id": "l5", "kind": "cab", "material": "log"}, {"id": "l4", "kind": "cab", "material": "wood"}]
        self.assertEqual(st.design_material(["l5"], "ground", facts), ("log", "l5"))
        self.assertEqual(st.design_material(["l4", "l5"], "ground", facts), (None, None))

    def test_design_is_tower(self):
        self.assertEqual(st.design_is_tower(["l4", "ideco"]), "ideco")
        self.assertIsNone(st.design_is_tower(["r6"]))


if __name__ == "__main__":
    unittest.main()
