"""Tests for pipeline/designs.py (design-name normalisation). Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import designs


class MatchDesigns(unittest.TestCase):
    def check(self, text: str, expected: list[str]) -> None:
        self.assertEqual(designs.match_designs(text), expected, text)

    def test_bare_codes_in_any_spelling(self) -> None:
        for text in ("L-4", "L4", "l-4", "L 4", "L.4"):
            self.check(text, ["l4"])
        self.check("L-5", ["l5"])
        self.check("L-6 cab with catwalk", ["l6"])
        self.check("D-6", ["d6"])
        self.check("D-6 cupola", ["d6"])
        self.check("Log cabin with a cupola", ["cupola"])
        self.check("Cupola house", ["cupola"])
        self.check("Bus/cupola", [])
        self.check("California Region 5 Plan BC-301 cab on a 10-foot enclosed timber tower", ["bc301"])

    def test_descriptions_that_name_a_design(self) -> None:
        self.check("L-4 ground cab", ["l4"])
        self.check("L-4 cab on a 32-foot timber tower, with catwalk", ["l4"])
        self.check("R-6 flattop cab, 15x15 ft, on a 41-ft timber tower", ["r6"])
        self.check("USFS Region 6 Flat Top cab on an 8-foot concrete block tower", ["r6"])
        self.check("Two-story Region 6 flat cab", ["r6"])

    def test_steel_tower_makers_and_models(self) -> None:
        self.check("Aermotor", ["aermotor"])
        self.check("Aermotor MC-39 steel tower", ["aermotor_mc39", "aermotor"])
        self.check("LS-40", ["aermotor_ls40", "aermotor"])
        self.check("48-49 ft Aermotor LX-24 steel tower", ["aermotor_lx", "aermotor"])
        self.check("McClintic-Marshall tower", ["mcclintic_marshall"])
        self.check("McKlintock-Marshall 86-ft steel tower", ["mcclintic_marshall"])
        self.check("McClintock Marshall", ["mcclintic_marshall"])
        self.check("The 30' Marshall-McClintock tower with a R-8 wooden 14'x 14' cab", ["mcclintic_marshall"])
        self.check("Blaw-Knox", ["blaw_knox"])
        self.check("International Derrick & Equipment Co.", ["ideco"])
        self.check("IDECO tower", ["ideco"])
        self.check("This 74-foot International Stacey tower was built in 1933.", ["other_steel"])
        self.assertEqual(designs.aermotor_models("Aermotor mc39 on an LS-40 base"), ["MC-39", "LS-40"])

    def test_register_and_hobbyist_prose(self) -> None:
        # Real phrasing from the NHLR, FFLOS and firelookout.com descriptions that
        # pipeline/extract_design_mentions.py reads.
        self.check("a vintage USFS 60' CT-2 wooden tower with a L-4 hip roof 14'x 14' cab", ["l4", "r6_timber_towers"])
        self.check("The present standard 53' CT-2 treated timber tower with standard 1936-model L-4 cab", ["l4", "r6_timber_towers"])
        self.check("It is a 31.6' Aermotor MC-24 tower with a 12'x12' wooden R3 low sill cab", ["r3_cab", "aermotor_mc24", "aermotor"])
        self.check("a 48 feet high Aermotor MC-99 type steel tower with a 7X7 foot steel cab", ["l1401", "aermotor"])
        self.check("The 40' Aermotor LL-25 structure with 7' x 7' metal cab", ["aermotor_ll25", "aermotor"])
        self.check("It is a 40' Pacific Coast Steel tower with a modified L-4 live-in cab", ["l4", "pacific_coast_steel"])
        self.check("a CL-100 series 14'x14' live in cab with catwalk on a metal tower", ["cl100"])
        self.check("an L-1600 series 30' steel K-Brace tower with CL-30 13'x13' live in steel cab", ["cl100", "l1600"])
        self.check("The tower is based on the USFS, 1600 series tower plans.", ["l1600"])
        self.check("a California Region 5 Plan BC-301 on a 10 foot enclosed timber tower", ["bc301"])
        self.check("In 1974 existing BC-3 cab was replaced by a 732-6A style cab.", ["bc301", "cdf_732_6a"])
        self.check("The BC-201 was used for sites where visibility was restricted", ["bc201"])
        self.check("The 4A style 14'x 14' lookout was built from 1917 to 1923", ["plan_4a"])
        self.check("California Region 5 Plan 4A or 4AR was constructed on the mountain.", ["plan_4a", "d5"])
        self.check("this \"Supervisor Hall Special\" ground cab, built in 1926", ["d5"])
        self.check("In 1920 a 13X13 D-5 cab was constructed on the site.", ["d5"])
        self.check("It is a C-3 14' x 14' wooden groundhouse with catwalk.", ["c3"])
        self.check("20 foot, H-Beam Steel Tower with a C-3(L)Cab", ["c3"])
        self.check("This 100-foot Wisconsin standard tower features an external protected ladder.", ["wisconsin_standard"])
        self.check("Cold Spring Lookout is a CDF 809R cab with an enclosed 29' steel tower.", ["cdf_809r"])
        self.check("The present 2-story NPS frame cab, built in 1929", ["nps_rustic"])
        self.check("The structure is a NPS standardized fire lookout, drawing PG-3040", ["nps_rustic"])
        self.check("a shake-walled, gable roof L-2 cupola cabin built in 1929", ["l2"])
        self.check("It has a D-1 log cupola cabin.", ["d1"])
        self.check("this 10' treated timber R-6 tower", ["r6"])
        self.check("Plan 80-B (R-6 Flat)", ["r6"])
        self.check("Plan 80 (R-1 L-4)", ["l4"])
        self.check("an R1/L-4 cabin on an enclosed 8 foot tower", ["l4"])

    def test_region_and_plan_numbers_are_not_confused_with_other_numbers(self) -> None:
        # A township, a CDF plan number, a camp, a highway.
        for text in ("IN THE NW 1/4 OF SEC. 11, T-30-N, R-3-W", "The tower is based on CDF Plan Number 1817-4A.",
                     "CCC Camp C-3 built the road", "Highway 4A", "Clinton, Arkansas", "Company 4735-C",
                     "the 1938 Region 6 standard towers",
                     "the signal varying in strength from about R6 to R2"):
            self.check(text, [])
        self.check("Region 1 standard T-30 lookout tower", ["r1_towers"])
        self.assertEqual(designs.variant_codes("r6_timber_towers", "CT-2 tower; later a TT-1"), ["CT-2", "TT-1"])

    def test_nothing_is_guessed(self) -> None:
        for text in ("Tower", "Ground", "Steel tower with 10x10 ft cab", "flat top cab", "CL-4", "L-45", "CL-style cab", "BC-3011", "", None):
            self.check(text, [])  # type: ignore[arg-type]

    def test_a_design_named_only_to_rule_it_out_does_not_count(self) -> None:
        self.check("Grange Hall type ground cab; predates the standard L-4 design", [])
        self.check("Built in 1940, unlike the L-4 cabs nearby", [])
        self.check("Not an R-6", [])
        self.check("Similar to a LS-40 Aermotor tower, it is made of a lighter steel", [])
        self.check("one of the few remaining Blaw-Knox (as compared to the more common Aermotor brand) towers", ["blaw_knox"])
        self.check("one of very few R-5 C-3 cabs in Idaho. The design dates to 1917 and is a precursor to the popular L-4", ["c3"])

    def test_several_designs_are_all_kept(self) -> None:
        # An earlier cab and today's: the guide lists the lookout under both, with this wording.
        self.check("10 ft steel tower (1964); earlier L-4 cab (early 1930s)", ["l4"])
        self.check("R-6 cab that replaced an L-4", ["l4", "r6"])
        self.check("Aermotor tower with an L-6 cab", ["l6", "aermotor"])
        self.assertEqual(designs.tower_designs(["L-4", "Tower", "Aermotor", "L4"]), ["l4", "aermotor"])

    def test_mentions_are_short_terms_that_match_again(self) -> None:
        text = "Started in the 1920's with a D-6 cupola cabin, the present L-4 cab atop a 10' concrete base, a 4A style cab"
        found = designs.find_mentions(text)
        self.assertEqual([d for d, _ in found], ["l4", "d6", "plan_4a"])
        for did, span in found:
            self.assertLess(len(span), 40)
            self.assertIn(did, designs.match_designs(span), span)

    def test_family_and_pairing(self) -> None:
        family = {"aermotor_mc39": "aermotor", "aermotor": "aermotor", "l4": "l4"}
        part = {"aermotor_mc39": "tower", "aermotor": "tower", "l4": "cab", "r6": "cab", "r6_timber_towers": "tower", "plan_86": "whole"}
        self.assertEqual(designs.family_ids(["l4", "aermotor_mc39"], family), ["l4", "aermotor_mc39", "aermotor"])
        self.assertEqual(designs.pair(["l4", "r6_timber_towers"], part), {"cab": "l4", "tower": "r6_timber_towers"})
        self.assertEqual(designs.pair(["aermotor_mc39", "aermotor"], part, family), {"tower": "aermotor_mc39"})
        self.assertEqual(designs.pair(["l4", "aermotor_mc39", "aermotor"], part, family), {"cab": "l4", "tower": "aermotor_mc39"})
        self.assertEqual(designs.pair(["plan_86"], part), {"whole": "plan_86"})
        self.assertEqual(designs.pair(["bc201", "aermotor"], {**part, "bc201": "house"}), {"house": "bc201", "tower": "aermotor"})
        # Two cabs (one replaced the other), or a whole lookout beside a cab: we do not guess.
        self.assertIsNone(designs.pair(["l4", "r6"], part))
        self.assertIsNone(designs.pair(["plan_86", "l4"], part))
        self.assertIsNone(designs.pair([], part))

    def test_accounts_of_several_structures(self) -> None:
        self.assertTrue(designs.describes_several("It is a 14'x14' CL-100 series cab. It replaced an Aermotor fire tower built in 1930."))
        self.assertTrue(designs.describes_several("The original BC-301 cab was replaced by CDF with a 732-6A design."))
        self.assertFalse(designs.describes_several("a vintage USFS 60' CT-2 wooden tower with a L-4 hip roof 14'x 14' cab"))
        # One design only: nothing to pair wrongly, whatever the history.
        self.assertFalse(designs.describes_several("This L-4 cab replaced a tent camp in 1934."))

    def test_every_pattern_has_a_display_name_and_guide_entry(self) -> None:
        guide = json.loads((Path(__file__).resolve().parent.parent / "data" / "designs.json").read_text(encoding="utf-8"))
        ids = {d["id"] for d in guide["designs"]}
        for did, _ in designs.PATTERNS:
            self.assertIn(did, designs.DESIGN_NAMES)
            self.assertIn(did, ids, f"data/designs.json has no entry for {did}")
        for d in guide["designs"]:
            self.assertTrue(d.get("sources"), f"{d['id']} has no sources")
            for src in d["sources"]:
                self.assertTrue(src.get("url", "").startswith(("https://", "http://")), src)


if __name__ == "__main__":
    unittest.main()
