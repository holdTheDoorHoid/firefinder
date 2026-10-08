"""Tests for regional/ffla_rentals.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import io
import json
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent / "regional"))
import ffla_rentals as R  # noqa: E402

PAGE = """<html><body><div class="entry-content">
<p class="wp-block-paragraph">Lookout Rentals are listed below and are grouped by state. The FFLA is NOT involved in management.</p>
<p class="wp-block-paragraph">Unless otherwise noted, these lookout rentals are managed through Recreation.Gov.</p>
<p class="wp-block-paragraph"><strong>California</strong><br><a href="http://www.recreation.gov/camping/campgrounds/234601" target="_blank">Oak Flat Lookout</a> (Currently Unavailable)<br><a href="https://www.recreation.gov/camping/campgrounds/234404">Post Creek Lookout</a></p>
<p class="wp-block-paragraph"><strong>Idaho</strong><br><a href="http://www.recreation.gov/camping/campgrounds/234447">Arid Peak Lookout</a> (Maintenance Closure2026)<br><a href="https://www.airbnb.com/rooms/25687274?source_impression_id=p3_1714456840_q3d">Crystal Peak Relocated Lookout</a> (Managed by private owner)<br><a href="https://www.recreation.gov/camping/campgrounds/234304">Bishop Mountain Lookout Cabin</a> (Administrative Closure 2026)</p>
<p class="wp-block-paragraph"><strong>Montana</strong><br><a href="http://www.recreation.gov/camping/campgrounds/234384">Webb Mountain Lookout<br>&#8203;</a><a href="https://dnrc.mt.gov/TrustLand/public-use/FacilityRentals" target="_blank">Werner Peak Lookout</a>&nbsp;(Managed by MT DNRC)<br><a href="http://www.recreation.gov/camping/campgrounds/234389">West Fork Butte Lookout&nbsp;</a></p>
<p class="wp-block-paragraph"><strong>Washington</strong><br><a href="http://www.recreation.gov/camping/campgrounds/234178">&#8203;Evergreen Mountain Lookout</a> (Maintenance Closure 2026) <a href="http://www.recreation.gov/camping/campgrounds/234178"><br>&#8203;</a><a href="https://www.recreation.gov/camping/campgrounds/269838">Heybrook Lookout<br>&#8203;</a>&#8203;<a href="https://www.airbnb.com/rooms/50778329">North Mountain Lookout</a> (Managed by Friends of North Mountain)</p>
<p class="wp-block-paragraph"><strong>West Virginia</strong><br><a href="https://www.fs.usda.gov/recarea/mbs/recreation/recarea/?recid=17850" target="_blank">&#8203;</a><a href="https://wvstateparks.com/places-to-stay/cabins/seneca-state-forest-cabins/">Thorny Mountain Fire Tower</a>&nbsp;(Managed by WV State Parks)</p>
<p class="wp-block-paragraph"><strong style="color: rgb(51, 51, 51); font-family: &quot;Libre Franklin&quot;;">Wisconsin</strong><a style="color: rgb(34, 34, 34);" href="https://www.fs.usda.gov/recarea/mbs/recreation/recarea/?recid=17850">&#8203;</a><br><a style="color: rgb(34, 34, 34);" href="https://www.airbnb.com/rooms/37930902?source_impression_id=p3_1">Gordon Fire Tower Cabin</a><span style="color: rgb(51, 51, 51);"><span>&nbsp;</span>(Managed by local non-profit group)</span></p>
</div><!-- .entry-content --></body></html>"""


class ParseRentals(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {(r["region"], r["name"]): r for r in R.parse_rentals(PAGE)}

    def test_every_listed_rental_is_found_in_page_order_and_the_intro_text_is_not_a_rental(self) -> None:
        self.assertEqual([(r["region"], r["name"]) for r in R.parse_rentals(PAGE)], [
            ("CA", "Oak Flat Lookout"), ("CA", "Post Creek Lookout"),
            ("ID", "Arid Peak Lookout"), ("ID", "Crystal Peak Relocated Lookout"), ("ID", "Bishop Mountain Lookout Cabin"),
            ("MT", "Webb Mountain Lookout"), ("MT", "Werner Peak Lookout"), ("MT", "West Fork Butte Lookout"),
            ("WA", "Evergreen Mountain Lookout"), ("WA", "Heybrook Lookout"), ("WA", "North Mountain Lookout"),
            ("WV", "Thorny Mountain Fire Tower"), ("WI", "Gordon Fire Tower Cabin"),
        ])

    def test_closure_notes_become_the_status_note(self) -> None:
        self.assertEqual(self.rows[("CA", "Oak Flat Lookout")]["status_note"], "Currently Unavailable")
        self.assertEqual(self.rows[("ID", "Arid Peak Lookout")]["status_note"], "Maintenance Closure 2026")   # "Closure2026" mended
        self.assertEqual(self.rows[("ID", "Bishop Mountain Lookout Cabin")]["status_note"], "Administrative Closure 2026")
        self.assertEqual(self.rows[("WA", "Evergreen Mountain Lookout")]["status_note"], "Maintenance Closure 2026")
        self.assertIsNone(self.rows[("CA", "Post Creek Lookout")]["status_note"])

    def test_managed_by_notes_become_the_manager(self) -> None:
        self.assertEqual(self.rows[("ID", "Crystal Peak Relocated Lookout")]["manager"], "private owner")
        self.assertEqual(self.rows[("MT", "Werner Peak Lookout")]["manager"], "MT DNRC")
        self.assertEqual(self.rows[("WA", "North Mountain Lookout")]["manager"], "Friends of North Mountain")
        self.assertEqual(self.rows[("WV", "Thorny Mountain Fire Tower")]["manager"], "WV State Parks")
        self.assertIsNone(self.rows[("ID", "Arid Peak Lookout")]["manager"])

    def test_a_link_with_a_stray_line_break_inside_does_not_swallow_the_next_rental(self) -> None:
        webb = self.rows[("MT", "Webb Mountain Lookout")]
        werner = self.rows[("MT", "Werner Peak Lookout")]
        self.assertIsNone(webb["manager"])
        self.assertIn("234384", webb["url"])
        self.assertIn("dnrc.mt.gov", werner["url"])

    def test_empty_links_are_skipped_and_inline_styles_are_not_taken_for_notes(self) -> None:
        self.assertEqual(self.rows[("WV", "Thorny Mountain Fire Tower")]["url"],
                         "https://wvstateparks.com/places-to-stay/cabins/seneca-state-forest-cabins/")
        gordon = self.rows[("WI", "Gordon Fire Tower Cabin")]
        self.assertEqual(gordon["notes"], ["Managed by local non-profit group"])    # not "51, 51, 51"

    def test_booking_links_lose_their_tracking_and_use_https(self) -> None:
        self.assertEqual(self.rows[("CA", "Oak Flat Lookout")]["url"], "https://www.recreation.gov/camping/campgrounds/234601")
        self.assertEqual(self.rows[("ID", "Crystal Peak Relocated Lookout")]["url"], "https://www.airbnb.com/rooms/25687274")
        self.assertEqual(self.rows[("WI", "Gordon Fire Tower Cabin")]["url"], "https://www.airbnb.com/rooms/37930902")


class Records(unittest.TestCase):
    def setUp(self) -> None:
        self.recs = {r["name"]: r for r in R.build_records(PAGE, "2026-10-08")}

    def test_recreation_gov_entries_carry_the_facility_number(self) -> None:
        r = self.recs["Arid Peak Lookout"]
        self.assertEqual(r["rental"]["ridb_facility_id"], "234447")
        self.assertEqual(r["rental"]["provider"], "recreation.gov")
        self.assertEqual(r["key"], "ffla_rentals:id:arid-peak-lookout")
        self.assertEqual(R.facility_id("https://www.recreation.gov/camping/campgrounds/10388459"), "10388459")
        self.assertIsNone(R.facility_id("https://www.airbnb.com/rooms/50778329"))

    def test_other_providers_are_named(self) -> None:
        self.assertEqual(self.recs["North Mountain Lookout"]["rental"]["provider"], "Airbnb")
        self.assertEqual(self.recs["Werner Peak Lookout"]["rental"]["provider"], "Montana DNRC")
        self.assertEqual(self.recs["Thorny Mountain Fire Tower"]["rental"]["provider"], "West Virginia State Parks")

    def test_a_record_has_no_position_and_says_nothing_about_the_structure(self) -> None:
        r = self.recs["Oak Flat Lookout"]
        self.assertIsNone(r["lat"])
        self.assertIsNone(r["lon"])
        self.assertEqual((r["kind"], r["status"]), ("unknown", "unknown"))
        self.assertEqual(r["url"], "https://firelookout.org/resources/rentals/")
        self.assertEqual(r["rental"]["status_note"], "Currently Unavailable")
        self.assertTrue(r["rental"]["available"])
        self.assertEqual(r["links"][0]["kind"], "rental")

    def test_a_private_owner_marks_the_ownership(self) -> None:
        self.assertEqual(self.recs["Crystal Peak Relocated Lookout"]["extra"]["ownership"], "private")
        self.assertNotIn("ownership", self.recs["North Mountain Lookout"]["extra"])   # a non-profit on Forest Service land

    def test_keys_are_unique_when_a_name_repeats(self) -> None:
        taken: set[str] = set()
        e1 = {"state": "Idaho", "region": "ID", "name": "Moon Pass", "url": "https://www.airbnb.com/rooms/1", "status_note": None, "manager": None, "notes": []}
        e2 = dict(e1, url="https://www.airbnb.com/rooms/2")
        keys = [R.to_record(e, taken, "2026-10-08")["key"] for e in (e1, e2)]
        self.assertEqual(len(set(keys)), 2)

    def test_the_two_moon_pass_listings_are_given_a_shared_approximate_position(self) -> None:
        taken: set[str] = set()
        out = []
        for unit, rid in (("Half Moon", "1500380336041089909"), ("Full Moon", "1474272441838044176")):
            e = {"state": "Idaho", "region": "ID", "name": f"Moon Pass Replica Lookout ({unit})", "url": f"https://www.airbnb.com/rooms/{rid}",
                 "status_note": None, "manager": "private owner", "notes": ["Managed by private owner"]}
            out.append(R.to_record(e, taken, "2026-10-08"))
        self.assertEqual({r["name"] for r in out}, {"Moon Pass Replica Lookout"})
        self.assertEqual({(r["lat"], r["lon"]) for r in out}, {(47.47, -115.92)})
        self.assertEqual({r["status"] for r in out}, {"replica"})
        self.assertEqual([r["extra"]["listed_as"] for r in out],
                         ["Moon Pass Replica Lookout (Half Moon)", "Moon Pass Replica Lookout (Full Moon)"])


class RefreshGuard(unittest.TestCase):
    """The weekly Action re-reads the page unattended; a page that is not the list must not replace
    the committed extract."""

    def test_a_reread_that_found_nothing_or_under_70_percent_is_refused(self) -> None:
        self.assertTrue(R.too_few(0, 88))
        self.assertTrue(R.too_few(0, 0))
        self.assertTrue(R.too_few(61, 88))        # 70% of 88 is 61.6
        self.assertFalse(R.too_few(62, 88))
        self.assertFalse(R.too_few(88, 88))
        self.assertFalse(R.too_few(95, 88))        # FFLA adding rentals is the normal case
        self.assertFalse(R.too_few(3, 0))          # no extract yet: anything real is fine

    def test_held_count_reads_the_extract_and_tolerates_a_missing_or_broken_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good, broken = Path(tmp) / "good.json", Path(tmp) / "broken.json"
            good.write_text(json.dumps({"records": [{}, {}, {}]}), encoding="utf-8")
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(R.held_count(good), 3)
            self.assertEqual(R.held_count(broken), 0)
            self.assertEqual(R.held_count(Path(tmp) / "missing.json"), 0)

    def run_main(self, root: Path, page: str) -> None:
        with mock.patch.object(R, "REPO_ROOT", root), mock.patch.object(R, "fetch_text", return_value=page), \
                contextlib.redirect_stderr(io.StringIO()):
            R.main([])

    def test_main_writes_the_extract_from_a_good_page_and_keeps_it_when_the_page_goes_bad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "data" / "sources" / "ffla_rentals.json"
            self.run_main(root, PAGE)
            first = out.read_text(encoding="utf-8")
            self.assertEqual(len(json.loads(first)["records"]), 13)
            # an error or challenge page parses to no rentals at all: refused, file untouched
            with self.assertRaises(SystemExit) as stopped:
                self.run_main(root, "<html><body><div class='entry-content'><p>Just a moment...</p></div></body></html>")
            self.assertIn("holds 13", str(stopped.exception))
            self.assertEqual(out.read_text(encoding="utf-8"), first)
            # a page that lost most of its states is refused too
            few = PAGE.replace("Idaho", "Nowhere").replace("Montana", "Nowhere").replace("Washington", "Nowhere")
            with self.assertRaises(SystemExit):
                self.run_main(root, few)
            self.assertEqual(out.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
