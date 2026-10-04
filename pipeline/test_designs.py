"""Tests for pipeline/designs.py (design-name normalisation). Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import unittest

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

    def test_descriptions_that_name_a_design(self) -> None:
        self.check("L-4 ground cab", ["l4"])
        self.check("L-4 cab on a 32-foot timber tower, with catwalk", ["l4"])
        self.check("R-6 flattop cab, 15x15 ft, on a 41-ft timber tower", ["r6"])
        self.check("USFS Region 6 Flat Top cab on an 8-foot concrete block tower", ["r6"])

    def test_steel_tower_makers_and_models(self) -> None:
        self.check("Aermotor", ["aermotor"])
        self.check("Aermotor MC-39 steel tower", ["aermotor"])
        self.check("LS-40", ["aermotor"])
        self.check("48-49 ft Aermotor LX-24 steel tower", ["aermotor"])
        self.check("McClintic-Marshall tower", ["mcclintic_marshall"])
        self.check("McKlintock-Marshall 86-ft steel tower", ["mcclintic_marshall"])
        self.check("McClintock Marshall", ["mcclintic_marshall"])
        self.check("Blaw-Knox", ["blaw_knox"])
        self.check("International Derrick & Equipment Co.", ["ideco"])
        self.check("IDECO tower", ["ideco"])
        self.assertEqual(designs.aermotor_models("Aermotor mc39 on an LS-40 base"), ["MC-39", "LS-40"])

    def test_nothing_is_guessed(self) -> None:
        for text in ("Tower", "Ground", "Steel tower with 10x10 ft cab", "flat top cab", "CL-4", "L-45", "BC-301", "", None):
            self.check(text, [])  # type: ignore[arg-type]

    def test_a_design_named_only_to_rule_it_out_does_not_count(self) -> None:
        self.check("Grange Hall type ground cab; predates the standard L-4 design", [])
        self.check("Built in 1940, unlike the L-4 cabs nearby", [])
        self.check("Not an R-6", [])

    def test_several_designs_are_all_kept(self) -> None:
        # An earlier cab and today's: the guide lists the lookout under both, with this wording.
        self.check("10 ft steel tower (1964); earlier L-4 cab (early 1930s)", ["l4"])
        self.check("R-6 cab that replaced an L-4", ["l4", "r6"])
        self.assertEqual(designs.tower_designs(["L-4", "Tower", "Aermotor", "L4"]), ["l4", "aermotor"])

    def test_every_pattern_has_a_display_name(self) -> None:
        for did, _ in designs.PATTERNS:
            self.assertIn(did, designs.DESIGN_NAMES)


if __name__ == "__main__":
    unittest.main()
