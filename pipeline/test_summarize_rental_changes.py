"""Tests for summarize_rental_changes.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import unittest

import summarize_rental_changes as S


class DiffRental(unittest.TestCase):
    def test_no_change(self):
        rental = {"available": True, "season": "Year-round"}
        self.assertIsNone(S.diff_rental(rental, dict(rental), "Flag Point"))

    def test_new_listing(self):
        self.assertEqual(S.diff_rental(None, {"available": True}, "Flag Point"),
                         "Flag Point: new rental listing")

    def test_listing_removed(self):
        self.assertEqual(S.diff_rental({"available": True}, None, "Flag Point"),
                         "Flag Point: rental listing removed from the record")

    def test_field_change_is_named(self):
        old = {"available": True, "season": "May-Oct", "fee": "$75/night"}
        new = {"available": True, "season": "June-Sept", "fee": "$75/night"}
        self.assertEqual(S.diff_rental(old, new, "Hager Mountain"), "Hager Mountain: season changed")

    def test_several_fields_change(self):
        old = {"available": True, "season": "May-Oct", "rules": []}
        new = {"available": False, "season": "May-Oct", "rules": ["Pack out all trash"]}
        self.assertEqual(S.diff_rental(old, new, "X"), "X: available, rules changed")

    def test_checked_and_description_alone_are_not_reported(self):
        # "checked" moves on every reconfirmation and "description" is often just RIDB's prose
        # reformatted -- neither is worth a line in a weekly commit message on its own.
        old = {"available": True, "checked": "2026-09-01", "description": "Overview\n\nOld text."}
        new = {"available": True, "checked": "2026-10-04", "description": "Overview\n\nNew text."}
        self.assertIsNone(S.diff_rental(old, new, "X"))

    def test_an_ffla_closure_note_appearing_or_lifting_is_reported(self):
        # the Action re-reads FFLA's rentals page, whose closure notes live in rental.status_note
        old = {"available": True, "status_note": None}
        new = {"available": True, "status_note": "Maintenance Closure 2026"}
        self.assertEqual(S.diff_rental(old, new, "Arid Peak"), "Arid Peak: status_note changed")
        self.assertEqual(S.diff_rental(new, old, "Arid Peak"), "Arid Peak: status_note changed")
        self.assertEqual(S.diff_rental({"manager": "MT DNRC"}, {"manager": "MT DNRC"}, "Werner Peak"), None)


class BuildMessage(unittest.TestCase):
    def test_no_changes(self):
        self.assertIn("no rental field changes", S.build_message([]))

    def test_lists_changes_with_a_count_title(self):
        msg = S.build_message(["Flag Point: season changed", "Hager Mountain: fee changed"])
        self.assertTrue(msg.startswith("Weekly RIDB refresh: 2 rental listing(s) changed"))
        self.assertIn("- Flag Point: season changed", msg)
        self.assertIn("- Hager Mountain: fee changed", msg)

    def test_truncates_past_fifty(self):
        lines = [f"Tower {i}: fee changed" for i in range(60)]
        msg = S.build_message(lines)
        self.assertIn("...and 10 more", msg)
        self.assertEqual(msg.count("fee changed"), 50)


if __name__ == "__main__":
    unittest.main()
