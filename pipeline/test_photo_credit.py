"""Tests for photo_credit.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import unittest

import photo_credit as pc


class ExtractPhotoCredit(unittest.TestCase):
    def test_the_task_example(self):
        cap, credit = pc.extract_photo_credit("9/10/05--Cabin (Bob Eckler photo-courtesy Bill Starr)")
        self.assertEqual(cap, "9/10/05--Cabin")
        self.assertEqual(credit, "Bob Eckler (courtesy Bill Starr)")

    def test_name_before_photo_no_parens(self):
        self.assertEqual(pc.extract_photo_credit("Andrew Zerbe photo"), (None, "Andrew Zerbe"))
        self.assertEqual(pc.extract_photo_credit("Dick Eckler photo-courtesy Bill Starr"),
                         (None, "Dick Eckler (courtesy Bill Starr)"))

    def test_leading_date_is_absorbed_when_nothing_else_remains(self):
        self.assertEqual(pc.extract_photo_credit("2009 Rod Bacon photo"), (None, "Rod Bacon"))
        self.assertEqual(pc.extract_photo_credit("1974 (Bob Eckler photo-courtesy Bill Starr)"),
                         (None, "Bob Eckler (courtesy Bill Starr)"))

    def test_leading_prose_is_kept_as_the_caption(self):
        self.assertEqual(
            pc.extract_photo_credit("Historical Marker (Andrew Zerbe photo)"),
            ("Historical Marker", "Andrew Zerbe"))
        self.assertEqual(
            pc.extract_photo_credit("Feb. 2004--Tower and Cabin (Warren Johnsen photo-courtesy Bill Starr)"),
            ("Feb. 2004--Tower and Cabin", "Warren Johnsen (courtesy Bill Starr)"))

    def test_photo_courtesy_and_courtesy_of(self):
        self.assertEqual(pc.extract_photo_credit("Photo courtesy Elaine Broskie"), (None, "Elaine Broskie"))
        self.assertEqual(pc.extract_photo_credit("Postcard (courtesy Paul Hartmann)"),
                         ("Postcard", "Paul Hartmann"))
        self.assertEqual(
            pc.extract_photo_credit("May 12, 2008 First day of cab restoration "
                                     "(photo courtesy Judith Myers, City of Hamburg)"),
            ("May 12, 2008 First day of cab restoration", "Judith Myers, City of Hamburg"))

    def test_collection(self):
        self.assertEqual(
            pc.extract_photo_credit("Postcard 1940 (Randy Kneer collection-courtesy Bill Starr)"),
            ("Postcard 1940", "Randy Kneer collection (courtesy Bill Starr)"))

    def test_usfs_photo_is_an_acronym_not_a_name(self):
        self.assertEqual(pc.extract_photo_credit("USFS photo"), (None, "USFS"))
        self.assertEqual(pc.extract_photo_credit("1935 USFS photo"), (None, "USFS"))

    def test_an_earlier_unrelated_parenthetical_is_left_alone(self):
        self.assertEqual(
            pc.extract_photo_credit("Vintage (c 1920) Photo (Bob Eckler Collection-courtesy Bill Starr)"),
            ("Vintage (c 1920) Photo", "Bob Eckler collection (courtesy Bill Starr)"))

    def test_trailing_courtesy_with_no_parens_or_photo_word(self):
        self.assertEqual(
            pc.extract_photo_credit("Hadley Mtn. Observatory Sept. 2003-courtesy Bill Starr"),
            ("Hadley Mtn. Observatory Sept. 2003", "Bill Starr"))

    def test_bare_years_are_not_a_name(self):
        for cap in ("1932 photo", "2010 photo", "1996 photo", "1959 tower photo"):
            self.assertEqual(pc.extract_photo_credit(cap), (cap, None), cap)

    def test_generic_descriptive_words_are_not_a_name(self):
        for cap in ("Historical Photo", "Vintage photo", "Undated Vintage Photo"):
            self.assertEqual(pc.extract_photo_credit(cap), (cap, None), cap)

    def test_a_single_ambiguous_capitalised_word_is_not_a_name(self):
        # Unlike a 2+ word phrase or an ALL-CAPS acronym, one ordinary capitalised word is too
        # likely to be generic vocabulary ("Wikimapia", "TNLandForms.us") to extract blind.
        for cap in ("Wikimapia photo", "TNLandForms.us photo", "KentuckyHiker.com photo",
                    "Foursquare user photo"):
            self.assertEqual(pc.extract_photo_credit(cap), (cap, None), cap)

    def test_photo_colon_description_is_not_a_credit(self):
        cap = "1930 photo: The tin roof from a shack at the old Chesaw was put on this lookout around 1930."
        self.assertEqual(pc.extract_photo_credit(cap), (cap, None))
        cap2 = "1962 photo: 1936 L4 with new R6 under construction"
        self.assertEqual(pc.extract_photo_credit(cap2), (cap2, None))

    def test_descriptive_prose_mentioning_a_name_is_not_a_credit(self):
        cap = "James Nuti photo of Barfoot foundation after its destruction in the 2011 Horseshoe II fire"
        self.assertEqual(pc.extract_photo_credit(cap), (cap, None))
        cap2 = "Former USFS rangers Bill Woodland and Charlie Huppuch at top of High Knob in December 2013"
        self.assertEqual(pc.extract_photo_credit(cap2), (cap2, None))

    def test_a_malformed_unbalanced_caption_is_left_alone(self):
        cap = "4/11/04 Warren Johnsen photo (courtesy Bill Starr"
        self.assertEqual(pc.extract_photo_credit(cap), (cap, None))

    def test_middle_initial_and_suffix(self):
        # "1910s" alone is a bare decade, dropped as a stray date like the rest of the module
        self.assertEqual(pc.extract_photo_credit("1910s (P. Hartmann collection-courtesy Bill Starr)"),
                         (None, "P. Hartmann collection (courtesy Bill Starr)"))
        self.assertEqual(pc.extract_photo_credit("Michael T. Finch, Jr. photo"), (None, "Michael T. Finch, Jr."))

    def test_no_caption_or_empty(self):
        self.assertEqual(pc.extract_photo_credit(None), (None, None))
        self.assertEqual(pc.extract_photo_credit(""), ("", None))


if __name__ == "__main__":
    unittest.main()
