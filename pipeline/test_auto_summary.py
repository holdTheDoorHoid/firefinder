import unittest

import auto_summary as A


class AutoSummary(unittest.TestCase):
    def test_standing_rental_with_registers(self):
        rec = {"name": "McCart Lookout", "region": "MT", "county": "Ravalli", "status": "standing", "kind": "tower",
               "design": "L-4", "elevation_m": 2190.0, "agency": "U.S. Forest Service",
               "events": [{"year": 1939, "event": "built"}],
               "registers": [{"register": "NHLR", "number": "US 85"}, {"register": "NRHP", "number": "96000660"}],
               "rental": {"available": True}}
        s = A.summarize(rec)
        self.assertIn("McCart Lookout is a fire lookout tower (L-4 design) in Ravalli County, Montana, at 7,185 ft", s)
        self.assertIn("It was built in 1939.", s)
        self.assertIn("National Historic Lookout Register (US 85) and the National Register of Historic Places", s)
        self.assertIn("administered by the U.S. Forest Service", s)
        self.assertIn("rented for overnight stays", s)

    def test_gone_with_end_year_and_no_guesses(self):
        rec = {"name": "Abbot Butte", "region": "OR", "county": "Jefferson", "status": "gone", "kind": "tower",
               "events": [{"year": 1933, "event": "built"}, {"year": 1965, "event": "removed"}]}
        s = A.summarize(rec)
        self.assertTrue(s.startswith("Abbot Butte was a fire lookout tower in Jefferson County, Oregon."))
        self.assertIn("It was removed in 1965.", s)
        self.assertNotIn("administered", s)

    def test_long_design_text_is_left_out_and_parish(self):
        rec = {"name": "Mosley Hill Lookout", "region": "LA", "county": "Grant", "status": "unknown", "kind": "tower",
               "design": "All-steel tower with a 13 ft x 13 ft metal cab"}
        s = A.summarize(rec)
        self.assertIn("Grant Parish, Louisiana", s)
        self.assertNotIn("All-steel", s)
        self.assertIn("Whether it still stands is not recorded.", s)


if __name__ == "__main__":
    unittest.main()
