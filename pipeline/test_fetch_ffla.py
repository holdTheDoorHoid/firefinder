"""Tests for fetch_ffla.py's parsing of FFLA's list views. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import unittest
from collections import Counter

import fetch_ffla as F


def table(*parts: str) -> str:
    return "<figure><table><tbody>" + "".join(parts) + "</tbody></table></figure>"


def heading(text: str, span: int = 7) -> str:
    return f'<tr><td colspan="{span}"><strong>{text}</strong></td></tr>'


def header(*cols: str) -> str:
    return "<tr>" + "".join(f"<td><strong>{c}</strong></td>" for c in cols) + "</tr>"


def row(*cells: str) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


ALPHA_COLS = ("Name", "County", "Lat", "Long", "Type", "Status", "NHLR/FFLOS")
COUNTY_COLS = ("County", "Name", "Lat", "Long", "Type", "Status", "NHLR/FFLOS")


def parse(html: str, view: str = "alpha", abbr: str = "MT") -> list[dict]:
    return F.parse_state_table(html, abbr, f"https://firelookout.org/x/{view}/", Counter(), Counter(), Counter(),
                               groups=(view == "rg"))


class ParseViews(unittest.TestCase):
    def test_county_first_column_order(self) -> None:
        html = table(heading("Lookout Structures and Sites"), header(*COUNTY_COLS),
                     row("Beaverhead", "Bender Point", "45.78200", "-113.71519", "Tower", "Gone", "&nbsp;"),
                     row("Big Horn", "Pryor", "45.28638", "-108.55891", "Tower", "Standing",
                         '<a href="http://nhlr.org/lookouts/us/mt/pryor-lookout/">NHLR US 1534, MT 97</a>'))
        recs = parse(html, "co")
        self.assertEqual([(r["name"], r["county"]) for r in recs], [("Bender Point", "Beaverhead"), ("Pryor", "Big Horn")])
        self.assertEqual(recs[1]["registers"][0]["number"], "US 1534")
        self.assertEqual(recs[0]["key"], "ffla:mt:bender-point:45.7820:-113.7152")

    def test_same_key_whatever_the_column_order(self) -> None:
        a = parse(table(header(*ALPHA_COLS), row("Pryor", "Big Horn", "45.28638", "-108.55891", "Tower", "Standing", "")))
        c = parse(table(header(*COUNTY_COLS), row("Big Horn", "Pryor", "45.28638", "-108.55891", "Tower", "Standing", "")))
        self.assertEqual(a[0]["key"], c[0]["key"])

    def test_by_region_view_names_the_group(self) -> None:
        html = table(heading("Lincoln County"), heading("Lookout Structures and Sites"), header(*ALPHA_COLS),
                     row("Allen Peak", "Lincoln", "47.94165", "-115.40000", "Ground", "Gone", ""),
                     heading("Relocated / Replica Lookouts"), header(*ALPHA_COLS),
                     row("Kellogg Peak (Replica)", "Lincoln", "48.0", "-115.0", "Tower", "Standing", ""),
                     heading("Sanders County"), heading("Lookout Structures and Sites"), header(*ALPHA_COLS),
                     row("Big Hole", "Sanders", "47.60421", "-115.07035", "Ground", "Standing", ""))
        recs = parse(html, "rg")
        self.assertEqual([(r["name"], r["extra"]["group"], r["extra"]["section"]) for r in recs], [
            ("Allen Peak", "Lincoln County", "Lookout Structures and Sites"),
            ("Kellogg Peak (Replica)", "Lincoln County", "Relocated / Replica Lookouts"),
            ("Big Hole", "Sanders County", "Lookout Structures and Sites"),
        ])

    def test_two_headings_in_a_row_in_an_alphabetical_list_are_not_a_group(self) -> None:
        # WV's list: "(Border - see Virginia)" then straight into a section heading
        html = table(heading("(Border – see Virginia)"), heading("Non-lookout Structures"), header(*ALPHA_COLS),
                     row("Coalwood", "McDowell", "37.3789", "-81.6584", "Tower", "Gone", ""))
        r = parse(html, abbr="WV")[0]
        self.assertEqual(r["extra"]["section"], "Non-lookout Structures")
        self.assertNotIn("group", r["extra"])

    def test_alphabetical_list_has_no_group(self) -> None:
        html = table(heading("Lookout Structures"), header(*ALPHA_COLS),
                     row("Allen Peak", "Lincoln", "47.94165", "-115.40000", "Ground", "Gone", ""),
                     heading("Lookout Sites / Non-lookout Structures"), header(*ALPHA_COLS),
                     row("Bear Ridge", "Lincoln", "48.2", "-115.5", "Camp", "Abandoned", ""))
        recs = parse(html)
        self.assertTrue(all("group" not in r["extra"] for r in recs))
        self.assertEqual([r["extra"]["section"] for r in recs],
                         ["Lookout Structures", "Lookout Sites / Non-lookout Structures"])

    def test_undocumented_sites_list_with_notes_and_no_coordinates(self) -> None:
        html = table(heading("Unknown/Undocumented", 9),
                     header("Name", "County", "Lat", "Long", "Type", "Status", "Notes", "Sec/Twp/Rng", "Agency"),
                     row("Alamine", "Shasta", "&nbsp;", "&nbsp;", "Emergency", "NB?", "&nbsp;", "32-32N-1E", "CDF"),
                     row("Baldy", "Modoc", "&nbsp;", "&nbsp;", "Emergency", "NB?", "see map", "xx-xx-xx", "&nbsp;"))
        recs = parse(html, "un", "CA")
        self.assertEqual(len(recs), 2)
        self.assertIsNone(recs[0]["lat"])
        self.assertEqual(recs[0]["extra"]["sec_twp_rng"], "32-32N-1E")
        self.assertEqual(recs[0]["extra"]["agency_raw"], "CDF")
        self.assertNotIn("sec_twp_rng", recs[1]["extra"])   # the "xx-xx-xx" placeholder says nothing
        self.assertEqual(recs[1]["extra"]["notes"], "see map")
        self.assertEqual(recs[0]["key"], "ffla:ca:alamine:null:null")

    def test_a_section_without_its_own_header_row_uses_the_header_above(self) -> None:
        # OR's and WV's "Relocated / Replica Lookouts" start straight after their heading
        html = table(heading("Lookout Structures"), header(*ALPHA_COLS),
                     row("Allen Peak", "Lincoln", "47.94165", "-115.40000", "Ground", "Gone", ""),
                     heading("Relocated / Replica Lookouts"),
                     row("Bly City Park <br>(Relocated Bly Ranger Station)", "Klamath", "42.40715", "-121.04928", "Ground", "Standing", ""),
                     row("Timber Butte<br>(Replica)", "Lane", "43.9253", "-122.57155", "Ground", "Standing", ""))
        recs = parse(html, abbr="OR")
        self.assertEqual([(r["name"], r["extra"]["section"]) for r in recs], [
            ("Allen Peak", "Lookout Structures"),
            ("Bly City Park (Relocated Bly Ranger Station)", "Relocated / Replica Lookouts"),
            ("Timber Butte (Replica)", "Relocated / Replica Lookouts"),
        ])
        self.assertEqual(recs[2]["county"], "Lane")

    def test_a_heading_padded_with_blank_cells_is_not_a_row(self) -> None:
        html = table(header(*ALPHA_COLS),
                     row("Pilot Knob", "Coos", "44.1", "-71.2", "Tower", "Standing", ""),
                     '<tr><td><strong>Non-Wildland Lookouts</strong></td><td>&nbsp;</td><td>&nbsp;</td>'
                     '<td colspan="2">&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>',
                     row("Mount Washington Obs", "Coos", "44.27", "-71.3", "Tower", "Standing", ""))
        recs = parse(html, abbr="NH")
        self.assertEqual([r["name"] for r in recs], ["Pilot Knob", "Mount Washington Obs"])
        self.assertEqual(recs[1]["extra"]["section"], "Non-Wildland Lookouts")

    def test_a_sentence_of_page_text_in_a_row_is_not_a_lookout(self) -> None:
        html = table(header(*ALPHA_COLS),
                     row("Whipple Peak", "Washington", "", "", "", "", ""),
                     row("If evidence or documentation is uncovered showing that any of these were used, "
                         "they will be moved to the lookout lists.", "", "", "", "", "", ""))
        self.assertEqual([r["name"] for r in parse(html, abbr="UT")], ["Whipple Peak"])

    def test_repeated_rows_in_one_view_get_numbered_keys(self) -> None:
        html = table(header(*ALPHA_COLS),
                     row("Bald Mountain", "A", "45.1", "-110.1", "Tower", "Gone", ""),
                     row("Bald Mountain", "A", "45.1", "-110.1", "Tower", "Gone", ""))
        self.assertEqual([r["key"] for r in parse(html)],
                         ["ffla:mt:bald-mountain:45.1000:-110.1000", "ffla:mt:bald-mountain:45.1000:-110.1000:1"])


class Combine(unittest.TestCase):
    def views(self, alpha: str, **others: str) -> list[tuple[str, list[dict]]]:
        out = [("alpha", parse(alpha))]
        out.extend((v, parse(h, v)) for v, h in others.items())
        return out

    def test_a_row_in_two_views_is_one_record_and_keeps_the_alphabetical_key(self) -> None:
        alpha = table(heading("Lookout Structures"), header(*ALPHA_COLS),
                      row("Pryor", "", "45.28638", "-108.55891", "Tower", "Standing", ""))
        co = table(heading("Lookout Structures and Sites"), header(*COUNTY_COLS),
                   row("Big Horn", "Pryor", "45.28638", "-108.55891", "Tower", "Standing", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["key"], "ffla:mt:pryor:45.2864:-108.5589")
        self.assertEqual(r["county"], "Big Horn")                       # enriched from the county view
        self.assertEqual(r["extra"]["section"], "Lookout Structures")  # the primary view's section wins
        self.assertEqual(r["extra"]["views"], ["alpha", "co"])
        self.assertEqual(r["url"], "https://firelookout.org/x/alpha/")

    def test_county_of_the_primary_is_not_overwritten(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Pryor", "Big Horn", "45.28638", "-108.55891", "Tower", "Standing", ""))
        co = table(header(*COUNTY_COLS), row("Yellowstone", "Pryor", "45.28638", "-108.55891", "Tower", "Standing", ""))
        r = F.combine_views(self.views(alpha, co=co))[0]
        self.assertEqual(r["county"], "Big Horn")
        self.assertEqual(r["extra"]["counties"], ["Big Horn", "Yellowstone"])

    def test_a_lookout_listed_under_two_counties_is_still_one_record(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Bassoo Peak", "Sanders/ Flathead", "47.85125", "-114.78813", "2-Story cab", "Standing", ""))
        co = table(header(*COUNTY_COLS),
                   row("Flathead", "Bassoo Peak", "47.85125", "-114.78813", "2-Story cab", "Standing", ""),
                   row("Sanders", "Bassoo Peak", "47.85125", "-114.78813", "2-Story cab", "Standing", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["extra"]["counties"], ["Sanders/ Flathead", "Flathead", "Sanders"])

    def test_two_spellings_of_one_name_at_one_spot_are_one_record(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Roberts (Shorty&#8217;s)", "Lincoln", "48.74143", "-114.93609", "Tower", "Gone", ""))
        co = table(header(*COUNTY_COLS), row("Lincoln", "Roberts (Shortys)", "48.74143", "-114.93609", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["name"], "Roberts (Shorty’s)")
        self.assertEqual(recs[0]["extra"]["views"], ["alpha", "co"])

    def test_a_row_only_a_secondary_view_lists_becomes_its_own_record(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Pryor", "Big Horn", "45.28638", "-108.55891", "Tower", "Standing", ""))
        co = table(header(*COUNTY_COLS),
                   row("Big Horn", "Pryor", "45.28638", "-108.55891", "Tower", "Standing", ""),
                   row("Carbon", "Red Lodge", "45.2", "-109.2", "Tower", "Gone", ""))
        st = table(header(*ALPHA_COLS), row("Red Lodge", "Carbon", "45.2", "-109.2", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co, st=st))
        self.assertEqual([r["name"] for r in recs], ["Pryor", "Red Lodge"])
        self.assertEqual(recs[1]["extra"]["views"], ["co", "st"])
        self.assertEqual(recs[1]["county"], "Carbon")

    def test_repeats_inside_the_primary_stay_separate_records(self) -> None:
        dup = row("Bald Mountain", "A", "45.1", "-110.1", "Tower", "Gone", "")
        alpha = table(header(*ALPHA_COLS), dup, dup)
        co = table(header(*COUNTY_COLS), row("A", "Bald Mountain", "45.1", "-110.1", "Tower", "Gone", ""),
                   row("A", "Bald Mountain", "45.1", "-110.1", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 2)
        self.assertEqual([r["extra"]["views"] for r in recs], [["alpha", "co"], ["alpha", "co"]])


class CombineSpellings(unittest.TestCase):
    """FFLA's views do not always spell a name alike: one lookout, one record."""

    def views(self, alpha: str, **others: str) -> list[tuple[str, list[dict]]]:
        return [("alpha", parse(alpha))] + [(v, parse(h, v)) for v, h in others.items()]

    def test_another_spelling_at_the_same_position_is_the_same_record(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Remer &#8211; first", "Cass", "47.04190", "-93.98610", "Tower", "Gone", ""))
        co = table(header(*COUNTY_COLS), row("Cass", "Remer #1", "47.04190", "-93.98610", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["name"], "Remer – first")
        self.assertEqual(recs[0]["extra"]["also_named"], ["Remer #1"])
        self.assertEqual(recs[0]["extra"]["views"], ["alpha", "co"])

    def test_a_row_already_matched_by_key_is_not_taken_for_the_other_spelling(self) -> None:
        # one position, two lookouts (the old and the new tower); the county view lists both,
        # one of them under another spelling
        alpha = table(header(*ALPHA_COLS),
                      row("Hunter Mountain", "Greene", "42.175", "-74.2288", "Tower", "Standing", ""),
                      row("Hunter Mountain (earlier)", "Greene", "42.175", "-74.2288", "Tower", "Gone", ""))
        co = table(header(*COUNTY_COLS),
                   row("Greene", "Hunter Mountain", "42.175", "-74.2288", "Tower", "Standing", ""),
                   row("Greene", "Hunter Mountain (previous)", "42.175", "-74.2288", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual([r["name"] for r in recs], ["Hunter Mountain", "Hunter Mountain (earlier)"])
        self.assertEqual(recs[1]["extra"]["also_named"], ["Hunter Mountain (previous)"])
        self.assertNotIn("also_named", recs[0]["extra"])

    def test_a_third_name_at_a_position_with_no_unmatched_record_left_is_its_own_record(self) -> None:
        alpha = table(header(*ALPHA_COLS),
                      row("Baldy North", "A", "45.1", "-110.1", "Tower", "Gone", ""),
                      row("Cinder Cone", "A", "45.1", "-110.1", "Tower", "Gone", ""))
        co = table(header(*COUNTY_COLS), row("A", "Baldy Nth", "45.1", "-110.1", "Tower", "Gone", ""),
                   row("A", "Cinder Cone", "45.1", "-110.1", "Tower", "Gone", ""),
                   row("A", "Something Else Entirely", "45.1", "-110.1", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual([r["name"] for r in recs], ["Baldy North", "Cinder Cone", "Something Else Entirely"])
        self.assertEqual(recs[0]["extra"]["also_named"], ["Baldy Nth"])
        self.assertEqual(recs[2]["extra"]["views"], ["co"])

    def test_with_several_unmatched_records_at_a_position_the_closest_name_is_taken(self) -> None:
        alpha = table(header(*ALPHA_COLS),
                      row("Baldy North", "A", "45.1", "-110.1", "Tower", "Gone", ""),
                      row("Cinder Cone", "A", "45.1", "-110.1", "Tower", "Gone", ""))
        co = table(header(*COUNTY_COLS), row("A", "Cinder Cne", "45.1", "-110.1", "Tower", "Gone", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1]["extra"]["also_named"], ["Cinder Cne"])
        self.assertNotIn("also_named", recs[0]["extra"])

    def test_a_secondary_row_with_no_position_joins_the_one_record_of_that_name(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Columbia Mountain", "Ferry", "48.62", "-118.482", "Tower", "Standing*", ""))
        st = table(header(*ALPHA_COLS), row("Columbia Mountain", "Ferry", "", "", "Tower", "Standing*", ""))
        recs = F.combine_views(self.views(alpha, st=st))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["extra"]["views"], ["alpha", "st"])
        self.assertEqual(recs[0]["lat"], 48.62)

    def test_a_secondary_row_with_no_position_and_no_namesake_is_its_own_record(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Columbia Mountain", "Ferry", "48.62", "-118.482", "Tower", "Standing", ""))
        st = table(header(*ALPHA_COLS), row("Kettle Crest", "Ferry", "", "", "Tower", "Standing", ""))
        recs = F.combine_views(self.views(alpha, st=st))
        self.assertEqual([r["name"] for r in recs], ["Columbia Mountain", "Kettle Crest"])
        self.assertIsNone(recs[1]["lat"])


    def test_a_mistyped_position_in_another_view_is_the_same_lookout(self) -> None:
        # WI's by-county list has Collins Marsh at latitude 48.08, a typo for 44.08 (outside Wisconsin)
        alpha = table(header(*ALPHA_COLS), row("Collins Marsh (Relocated Silver Lake, MI)", "Manitowoc", "44.08286", "-87.96828", "Tower", "Standing", ""))
        co = table(header(*COUNTY_COLS), row("Manitowoc", "Collins Marsh (Relocated Silver Lake, MI)", "48.08286", "-87.96828", "Tower", "Standing", ""))
        recs = F.combine_views([("alpha", parse(alpha, abbr="WI")), ("co", parse(co, "co", "WI"))])
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["lat"], 44.08286)
        self.assertEqual(recs[0]["extra"]["views"], ["alpha", "co"])
        self.assertNotIn("coordinate_problem", recs[0]["extra"])

    def test_a_position_only_another_view_has_is_filled_in(self) -> None:
        # WV's alphabetical list leaves Godwin's position out; the by-county list has it
        alpha = table(header(*ALPHA_COLS), row("Godwin (Relocated Parting Springs)", "Randolph", "", "", "Tower", "Standing", ""))
        co = table(header(*COUNTY_COLS), row("Randolph", "Godwin (Relocated Parting Springs)", "38.67295", "-79.97430", "Tower", "Standing", ""))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual((r["lat"], r["lon"]), (38.67295, -79.9743))
        self.assertEqual(r["key"], "ffla:mt:godwin-relocated-parting-springs:null:null")   # the key does not move
        self.assertEqual(r["extra"]["position_from_view"], "co")
        self.assertEqual(r["extra"]["views"], ["alpha", "co"])

    def test_registers_and_links_come_from_the_alphabetical_list_only(self) -> None:
        link = '<a href="http://www.firetower.org/lookouts/us/or/woods-point-lookout-site/">FFLOS US 748, OR 157</a>'
        alpha = table(header(*ALPHA_COLS), row("West Eagle", "Union", "45.10306", "-117.42605", "Unknown", "Abandoned", ""))
        co = table(header(*COUNTY_COLS), row("Union", "West Eagle", "45.10306", "-117.42605", "Unknown", "Abandoned", link))
        recs = F.combine_views(self.views(alpha, co=co))
        self.assertEqual(recs[0]["registers"], [])
        self.assertEqual(recs[0]["links"], [])

    def test_a_secondary_row_with_no_position_does_not_join_a_namesake_in_another_county(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Bear Mountain", "Fresno", "36.7458", "-119.2827", "Tower", "Standing", ""))
        st = table(header(*ALPHA_COLS), row("Bear Mountain", "Siskiyou", "", "", "Tower", "Standing", ""))
        recs = F.combine_views(self.views(alpha, st=st))
        self.assertEqual(len(recs), 2)

    def test_the_undocumented_list_is_never_merged_into_the_lookout_list_by_name(self) -> None:
        alpha = table(header(*ALPHA_COLS), row("Bear Mountain", "Fresno", "36.7458", "-119.2827", "Tower", "Standing", ""))
        un = table(header("Name", "County", "Lat", "Long", "Type", "Status", "Notes", "Sec/Twp/Rng", "Agency"),
                   row("Bear Mountain", "Siskiyou", "", "", "Emergency", "NB?", "", "xx-xx-xx", "CDF"),
                   row("Bunker Hill", "Placer", "39.0494", "-120.3805", "Emergency", "??", "", "", ""))
        recs = F.combine_views([("alpha", parse(alpha, abbr="CA")), ("un", parse(un, "un", "CA"))])
        self.assertEqual([(r["name"], r["extra"]["views"]) for r in recs],
                         [("Bear Mountain", ["alpha"]), ("Bear Mountain", ["un"]), ("Bunker Hill", ["un"])])


class Discovery(unittest.TestCase):
    PAGE = ('<div class="entry-content"><p><a href="https://firelookout.org/lookouts/us/nc/nc-add/">Additional</a></p>'
            '<p>Other sort: <a href="https://firelookout.org/lookouts/us/nc/nc-co/">by County</a><br>'
            'Other sort: <a href="http://firelookout.org/lookouts/us/nc/nc-st">Standing</a></p></div><!-- .entry-content -->'
            '<nav><a href="https://firelookout.org/lookouts/us/nc/nc-menu/">menu</a></nav>')

    def test_other_sorts_are_found_in_the_page_body_only(self) -> None:
        found = F.discover_views(self.PAGE, "NC")
        self.assertEqual({k: v["url"] for k, v in found.items()}, {
            "co": "https://firelookout.org/lookouts/us/nc/nc-co/",
            "st": "https://firelookout.org/lookouts/us/nc/nc-st/",
        })
        self.assertEqual(found["co"]["label"], "by County")

    def test_sitemap_lists_views_by_state_and_skips_add_pages(self) -> None:
        xml = ("<urlset><url><loc>https://firelookout.org/lookouts/us/ca/ca-un/</loc></url>"
               "<url><loc>https://firelookout.org/lookouts/us/ca/ca-add/</loc></url>"
               "<url><loc>https://firelookout.org/lookouts/us/ca/ca-co/</loc></url>"
               "<url><loc>https://firelookout.org/lookouts/us/de/ellendale/</loc></url>"
               "<url><loc>https://firelookout.org/lookouts/us/or/or-rg/</loc></url></urlset>")
        got = F.sitemap_views(xml, ["CA", "DE", "OR"])
        self.assertEqual(got["CA"], {"un": "https://firelookout.org/lookouts/us/ca/ca-un/",
                                     "co": "https://firelookout.org/lookouts/us/ca/ca-co/"})
        self.assertEqual(got["OR"], {"rg": "https://firelookout.org/lookouts/us/or/or-rg/"})
        self.assertNotIn("DE", got)   # a single-lookout page, not a list view

    def test_norm_url(self) -> None:
        self.assertEqual(F.norm_url("http://firelookout.org/lookouts/us/nv//"), "https://firelookout.org/lookouts/us/nv/")
        self.assertEqual(F.norm_url("https://firelookout.org/lookouts/us/id"), "https://firelookout.org/lookouts/us/id/")
        self.assertEqual(F.norm_url("https://firelookout.org/?page_id=156"), "https://firelookout.org/?page_id=156")
        self.assertEqual(F.norm_url("https://firelookout.org/page-sitemap.xml"), "https://firelookout.org/page-sitemap.xml")


if __name__ == "__main__":
    unittest.main()
