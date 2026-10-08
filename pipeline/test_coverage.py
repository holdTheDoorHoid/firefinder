"""Tests for coverage.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import io
import contextlib
import json
import unittest
from pathlib import Path

import coverage as C
from test_merge import Workspace, rec, write_sources


class CoverageAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def audit(self, **kw) -> dict:
        return C.audit(self.ws.sources, self.ws.towers, self.ws.report, **kw)

    def test_every_placed_record_is_held(self) -> None:
        self.ws.run({
            "ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                     rec("ffla", "b", "Bald Peak", 44.9, -121.2, "OR")],
            "osm": [rec("osm", "a", "Abbot Butte Lookout", 44.5578, -121.7089, "OR")],
        })
        res = self.audit()
        self.assertEqual(res["not_held"], [])
        self.assertEqual(res["per_source"]["ffla"]["held_visible"], 2)
        self.assertEqual(res["per_source"]["osm"]["held_visible"], 1)
        self.assertEqual(res["totals"]["records"], 3)
        self.assertIn("Every record is held", C.format_report(res))

    def test_unplaced_record_without_coordinates_is_listed_with_its_reason(self) -> None:
        # two same-name towers in the state: the position-less record cannot choose between them
        self.ws.run({
            "ffla": [rec("ffla", "a", "Bald Mountain", 44.1, -121.1, "OR"),
                     rec("ffla", "b", "Bald Mountain", 45.1, -122.1, "OR")],
            "eastern_us_lookouts": [rec("eastern_us_lookouts", "bald", "Bald Mountain", None, None, "OR")],
        })
        res = self.audit()
        self.assertEqual([r["key"] for r in res["not_held"]], ["eastern_us_lookouts:bald"])
        self.assertEqual(res["not_held"][0]["reason"], "no_coordinates")
        self.assertIn("several same-name lookouts", res["not_held"][0]["note"])
        self.assertEqual(res["per_source"]["eastern_us_lookouts"]["no_coordinates"], 1)
        self.assertEqual(res["totals"]["unmatched"], 0)

    def test_a_rental_the_name_cannot_place_is_listed(self) -> None:
        self.ws.run({
            "ffla": [rec("ffla", "a", "Bald Mountain", 44.1, -121.1, "OR"),
                     rec("ffla", "b", "Bald Mountain", 45.1, -122.1, "OR")],
            "ffla_rentals": [rec("ffla_rentals", "bald", "Bald Mountain", None, None, "OR"),
                             rec("ffla_rentals", "nowhere", "Nowhere Peak", None, None, "OR")],
        })
        res = self.audit()
        self.assertEqual({r["key"]: r["note"] for r in res["not_held"]},
                         {"ffla_rentals:bald": "several lookouts of that name in the state",
                          "ffla_rentals:nowhere": "no lookout of that name in the state"})

    def test_a_record_added_after_the_last_merge_is_unmatched(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR")]})
        write_sources(self.ws.sources, {"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                                                 rec("ffla", "new", "New Peak", 44.0, -120.0, "OR")]})
        res = self.audit()
        self.assertEqual([(r["key"], r["reason"]) for r in res["not_held"]], [("ffla:new", "unmatched")])
        self.assertEqual(res["totals"]["unmatched"], 1)

    def test_coordinates_outside_the_us(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                              rec("ffla", "swap", "Swapped", -121.7, 44.5, "OR")]})
        res = self.audit()
        self.assertEqual([(r["key"], r["reason"]) for r in res["not_held"]], [("ffla:swap", "coordinates_outside_us")])

    def test_records_on_hidden_towers_count_as_held_but_are_shown_apart(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                              rec("ffla", "t", "Tree Platform", 44.9, -121.2, "OR", kind="tree")]})
        res = self.audit()
        self.assertEqual(res["not_held"], [])
        self.assertEqual(res["per_source"]["ffla"]["held_visible"], 1)
        self.assertEqual(res["per_source"]["ffla"]["held_hidden_only"], 1)

    def test_one_source_only_and_strict_exit_code(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR")],
                     "osm": [rec("osm", "a", "Abbot Butte Lookout", 44.5578, -121.7089, "OR")]})
        write_sources(self.ws.sources, {"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                                                 rec("ffla", "new", "New Peak", 44.0, -120.0, "OR")],
                                        "osm": [rec("osm", "a", "Abbot Butte Lookout", 44.5578, -121.7089, "OR")]})
        res = self.audit(only="osm")
        self.assertEqual(list(res["per_source"]), ["osm"])
        self.assertEqual(res["not_held"], [])
        args = ["--sources", str(self.ws.sources), "--towers", str(self.ws.towers),
                "--report", str(self.ws.report), "--summary"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(C.main(args), 0)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(C.main(args + ["--strict"]), 1)

    def test_json_output(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR")]})
        out = self.ws.tmp.name + "/cov.json"
        with contextlib.redirect_stdout(io.StringIO()):
            C.main(["--sources", str(self.ws.sources), "--towers", str(self.ws.towers), "--json", out])
        data = json.loads(Path(out).read_text())
        self.assertEqual(data["totals"]["records"], 1)


if __name__ == "__main__":
    unittest.main()
