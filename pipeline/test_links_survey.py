"""Tests for the fetchers added from FFLA's links page (docs/sources/links_survey.md):
weebly_lookouts.py's nav fixes, weebly_west.py, cherylhill_oregon.py, trailchick_wa.py, ffla_groups.py,
willhiteweb_wa.py and the register helpers in regional/_common.py.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

REGIONAL = Path(__file__).parent / "regional"


def load_regional(name: str):
    """Loads regional/<name>.py without leaving its bare `_common` (or `weebly_lookouts`) import in
    sys.modules: the regional fetchers each insert their own directory on sys.path and `import _common`,
    which would otherwise collide with pipeline/_common.py in the rest of the test run."""
    saved = {k: sys.modules.pop(k, None) for k in ("_common", "weebly_lookouts")}
    sys.path.insert(0, str(REGIONAL))
    try:
        spec = importlib.util.spec_from_file_location(f"regional_{name}_under_test", REGIONAL / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(REGIONAL))
        for k in saved:
            sys.modules.pop(k, None)
            if saved[k] is not None:
                sys.modules[k] = saved[k]
    return mod


def nav(items: list[tuple[str, str]]) -> str:
    return "<html><body>" + "".join(f'<a href="{h}">{t}</a>' for h, t in items) + "</body></html>"


class WeeblyNavFixes(unittest.TestCase):
    """The eastern / central weebly sites' nav: mislabelled continuation headers, arrow markers."""

    @classmethod
    def setUpClass(cls):
        cls.w = load_regional("weebly_lookouts")

    def test_header_text_key(self):
        k = self.w.header_text_key
        self.assertEqual(k("WEST VIRGINIA\n\t\t&gt;"), "WEST VIRGINIA")
        self.assertEqual(k("MICHIGAN."), "MICHIGAN")
        self.assertEqual(k("PENNSYLVANIA  (A-F)"), "PENNSYLVANIA")

    def test_continuation_headers_go_to_the_right_state(self):
        html = nav([
            ("/indiana.html", "INDIANA"), ("/borden.html", "Borden"),
            ("/georgia1.html", "Georgia"), ("/german-ridge.html", "German Ridge"),   # really Indiana
            ("/kentucky.html", "KENTUCKY"), ("/adaburg.html", "Adaburg"),
            ("/michigan2.html", "MICHIGAN"), ("/alfred.html", "Alfred"),
            ("/delaware1.html", "Delaware"), ("/demond-hill.html", "Demond Hill"),   # really Michigan
            ("/mississippi.html", "MISSISSIPPI"), ("/airey.html", "AIREY"),
        ])
        seg = self.w.nav_segments(html, {"IN", "GA", "KY", "MI", "DE", "MS"})
        self.assertEqual([t for _r, t in seg["IN"]], ["Borden", "German Ridge"])
        self.assertEqual(seg["GA"], [])
        self.assertEqual([t for _r, t in seg["MI"]], ["Alfred", "Demond Hill"])
        self.assertEqual(seg["DE"], [])
        self.assertEqual([t for _r, t in seg["KY"]], ["Adaburg"])

    def test_west_virginia_marker_and_virginia_resuming(self):
        html = nav([
            ("/virginia.html", "VIRGINIA"), ("/alton.html", "Alton"),
            ("/west-virginia.html", "WEST VIRGINIA\n\t\t&gt;"), ("/cabell.html", "Cabell"),
            ("/brushy-mountain2.html", "Brushy Mountain."), ("/buck-knob1.html", "Buck Knob"),
        ])
        seg = self.w.nav_segments(html, {"VA", "WV"})
        self.assertEqual([t for _r, t in seg["VA"]], ["Alton", "Brushy Mountain.", "Buck Knob"])
        self.assertEqual([t for _r, t in seg["WV"]], ["Cabell"])

    def test_unshout(self):
        u = self.w.unshout
        self.assertEqual(u("MCNAB"), "McNab")
        self.assertEqual(u("ALBERT RUSSELL"), "Albert Russell")
        self.assertEqual(u("WILDERNESS (Lampe)"), "Wilderness (Lampe)")
        self.assertEqual(u("O'NEAL HILL"), "O'Neal Hill")
        self.assertEqual(u("Bald Hill"), "Bald Hill")
        self.assertEqual(u("PARKER II"), "Parker II")
        self.assertEqual(u("CCC CAMP"), "CCC Camp")
        self.assertEqual(u("MT. GILBOA"), "Mt. Gilboa")
        self.assertEqual(u("ST. JOHN'S ROCK"), "St. John's Rock")

    def test_declared_state(self):
        d = self.w.declared_state
        self.assertEqual(d(["CABELL", "West Virginia - Cabell County - West Virginia Division of Forestry"]), "WV")
        self.assertEqual(d(["ALTON", "Halifax County", "Virginia Department of Forestry"]), None)
        self.assertEqual(d(["X", "Georgia - Dodge County"]), "GA")


WEST_PAGE = """<html><body><a href="/x.html">nav</a>
<h2 class="wsite-content-title"><strong>QUAIL PRAIRIE MOUNTAIN</strong></h2>
<div class="paragraph"><em>Siskiyou National Forest<br />&#8203;38S-11W-30</em></div>
<div class="paragraph"><strong>July 10, 1963:</strong> "Bids for the new lookout will be let."</div>
<div class="paragraph">Removed</div>
<iframe src="//www.weebly.com/weebly/apps/generateMap.php?map=google&elementid=1&ineditor=0&control=3&width=auto&height=400px&overviewmap=1&scalecontrol=1&typecontrol=1&zoom=14&long=-124.0456&lat=42.2418&domain=www&point=1&align=1&reseller=false"></iframe>
<a href="https://www.firelookout.com/or/quailprairie.html"><span>REX'S FIRE LOOKOUT PAGE</span></a>
</body></html>"""


class WeeblyWest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ww = load_regional("weebly_west")

    def test_nav_entries_county_sites(self):
        html = nav([("/baker-county.html", "BAKER COUNTY"), ("/baker-rs.html", "Baker Ranger Station"),
                    ("/bald-mountain3.html", "Bald Mountain"), ("/benton-county.html", "BENTON COUNTY"),
                    ("/alsea-summit.html", "Alsea Summit"), ("/misc.html", "Misc. Notes - Oregon"),
                    ("/work.html", "Work Party - 2015"), ("/joes.html", "Joe's Lookout"),
                    ("/mhr.html", "Mountain Home Rock")])
        e = self.ww.nav_entries(html, "county", ["OR"])
        self.assertEqual([(x["text"], x["county"], x["state"]) for x in e],
                         [("Baker Ranger Station", "Baker", "OR"), ("Bald Mountain", "Baker", "OR"),
                          ("Alsea Summit", "Benton", "OR"), ("Joe's Lookout", "Benton", "OR"),
                          ("Mountain Home Rock", "Benton", "OR")])

    def test_nav_entries_state_site(self):
        html = nav([("/arizona.html", "ARIZONA"), ("/apache-maid.html", "Apache Maid"),
                    ("/new-mexico.html", "NEW MEXICO"), ("/oso-ridge.html", "Oso Ridge"),
                    ("/misc-nm.html", "General and Misc., New Mexico")])
        e = self.ww.nav_entries(html, "state", ["AZ", "NM"])
        self.assertEqual([(x["text"], x["state"]) for x in e], [("Apache Maid", "AZ"), ("Oso Ridge", "NM")])

    def test_parse_page(self):
        d = self.ww.parse_page(WEST_PAGE, {"county": "Curry", "state": "OR"}, "oregonlookouts.weebly.com")
        self.assertEqual(d["name"], "Quail Prairie Mountain")
        self.assertEqual((d["state"], d["county"]), ("OR", "Curry"))
        self.assertEqual(d["agency"], "Siskiyou National Forest")
        self.assertEqual(d["plss"], "38S-11W-30")
        self.assertEqual((d["lat"], d["lon"]), (42.2418, -124.0456))
        self.assertEqual(d["status"], "gone")
        self.assertEqual([l["url"] for l in d["links"]], ["https://www.firelookout.com/or/quailprairie.html"])

    def test_location_lines(self):
        p = self.ww.parse_location_nodes
        self.assertEqual(p(["WARREN PEAKS", "Crook County - Black Hills National Forest - 52N-63W-20",
                            "May 14, 1938:"])["county"], "Crook")
        r = p(["OSO RIDGE", "New Mexico - Cibola County", "Cibola National Forest", "9N-12W-4", "June 4, 1933:"])
        self.assertEqual((r["state"], r["county"], r["agency"], r["plss"]),
                         ("NM", "Cibola", "Cibola National Forest", "9N-12W-4"))
        r = p(["LOST LAKE", "Columbia > Gifford Pinchot National Forest", "13N-10E-13", "1929:"])
        self.assertEqual((r["agency"], r["plss"]), ("Gifford Pinchot National Forest", "13N-10E-13"))
        self.assertEqual(p(["YOUNGS PEAK", "Del Norte County"])["county"], "Del Norte")
        # a page with no location block at all
        r = p(["WOODS RIDGE", "June 21, 1962:", "\"Mrs. Banghart took a job\""])
        self.assertEqual((r["county"], r["agency"], r["plss"]), (None, None, None))


TABLE_HTML = """<table id="tablepress-4"><thead><tr class="row-1"><th>NAME</th></tr></thead><tbody>
<tr class="row-2"><td class="column-1"><a href="https://cherylhill.net/firelookouts/2015/07/03/acker-rock/">Acker Rock</a></td><td>Umpqua National Forest</td><td>Area 3</td><td>4,112'</td><td>1964</td><td><a href="http://www.recreation.gov/camping/acker-rock-lookout/r/campgroundDetails.do?contractCode=NRSO&amp;parkId=72346">Rental</a></td><td>Yes</td></tr>
<tr class="row-3"><td class="column-1">Big Rock / Green Mountain</td><td>Linn Forest Protective Association</td><td>Area 4</td><td>4,509'</td><td>1950</td><td>Abandoned</td><td>No</td></tr>
<tr class="row-4"><td class="column-1"><a href="http://cherylhill.net/firelookouts/2016/06/15/black-butte/">Black Butte</a>*</td><td>Deschutes National Forest</td><td>Area 1</td><td>6,436</td><td>1995</td><td>Staffed</td><td>Yes</td></tr>
</tbody></table>"""

POST_HTML = """<html><body><article><h1>Quail Prairie</h1>
<p>Posted on July 4, 2014</p><p>Type: 41&prime; R-6 tower</p><p>Status: Abandoned</p><p>Elevation: 3,030 feet</p>
<p>Visited: June 29, 2014</p><p>More information</p>
<a href="http://nhlr.org/lookouts/us/or/quail-prairie-lookout/">National Historic Lookout Register</a>
</article></body></html>"""


class CherylHill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ch = load_regional("cherylhill_oregon")

    def test_table_rows(self):
        rows = self.ch.table_rows(TABLE_HTML)
        self.assertEqual([r["name"] for r in rows], ["Acker Rock", "Big Rock / Green Mountain", "Black Butte"])
        self.assertEqual(rows[0]["post"], "https://cherylhill.net/firelookouts/2015/07/03/acker-rock/")
        self.assertTrue(rows[0]["rental"].startswith("http://www.recreation.gov/"))
        self.assertIsNone(rows[1]["post"])
        self.assertTrue(rows[2]["multiple"])      # the asterisk: more than one structure
        self.assertEqual(self.ch.elevation_ft(rows[0]["elevation_raw"]), 4112)
        self.assertEqual(self.ch.elevation_ft("6,436"), 6436)

    def test_post_facts_register_is_vetted(self):
        # stand-in for the committed NHLR extract
        fake = {self.ch.register_url_key("http://nhlr.org/lookouts/us/or/quail-prairie-lookout/"):
                {"register": {"register": "NHLR", "number": "US 467", "state_number": "OR 64"},
                 "name": "Quail Prairie Lookout"}}
        self.ch.register_by_url = lambda *a, **k: fake
        f = self.ch.post_facts(POST_HTML, "Quail Prairie")
        self.assertEqual(f["design"], "R-6")
        self.assertEqual(f["height_ft"], 41)
        self.assertEqual(f["nhlr"]["number"], "US 467")
        # the same link on a post about another lookout (copied-over "more information") is dropped
        f = self.ch.post_facts(POST_HTML, "Bald Butte")
        self.assertIsNone(f["nhlr"])
        self.assertEqual(f["rejected_register"], "Quail Prairie Lookout")

    def test_destroyed_titles(self):
        html = ('<article><h2><a href="https://x/flag/">Flag Point Lookout Has Burned in the Grasshopper Fire</a></h2>'
                '<span>Posted on August 1, 2026</span></article>'
                '<article><h2><a href="https://x/silver/">Silver Butte lookout gone</a></h2>'
                '<span>Posted on June 14, 2013</span></article>')
        got = self.ch.destroyed_posts(html)
        self.assertEqual([(g["name"], g["year"], g["event"]) for g in got],
                         [("Flag Point", 2026, "burned"), ("Silver Butte", None, None)])


class TrailChick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tc = load_regional("trailchick_wa")

    def test_fact_block_and_parse(self):
        page = ("<html><body><h1>Winchester Mountain</h1><p>Last Updated: November 25, 2023</p>"
                "<p>Location : 48.956472, -121.643167</p><p>Summit Elevation : 6,510'</p>"
                "<p>Lookout Type: 14'x14' L-4 groundhouse</p><p>Site Established: 1931</p>"
                "<p>Current Structure Built: 1935</p><p>Date Visited: 8/28/17</p></body></html>")
        facts = self.tc.fact_block(page)
        self.assertEqual(facts["Location"], "48.956472, -121.643167")
        self.assertEqual(facts["Current Structure Built"], "1935")
        f = self.tc.parse_lookout({"title": "Winchester Mountain", "elevation": "6,510'",
                                   "lookout_type": ["L-4"]}, facts)
        self.assertEqual((f["lat"], f["lon"]), (48.956472, -121.643167))
        self.assertEqual((f["elev_ft"], f["design"], f["built"], f["established"]), (6510, "L-4", 1935, 1931))
        self.assertEqual(self.tc.kind_of(facts["Lookout Type"]), "ground")

    def test_bad_coordinates_are_dropped(self):
        f = self.tc.parse_lookout({"title": "X", "lookout_type": []}, {"Location": "12.5, -121.6"})
        self.assertIsNone(f["lat"])      # not in Washington

    def test_title_cleaning_and_kind(self):
        self.assertEqual(self.tc.clean_title("Slate Peak - RIP"), ("Slate Peak", True))
        self.assertEqual(self.tc.clean_title("Whitmore Mountain L-4 Cab"), ("Whitmore Mountain", False))
        self.assertEqual(self.tc.clean_title("Goat Peak"), ("Goat Peak", False))
        self.assertEqual(self.tc.kind_of("53' steel tower with live-in cab"), "tower")
        self.assertEqual(self.tc.kind_of("Crows nest"), "platform")
        self.assertEqual(self.tc.kind_of("14'x14' L-4 cab"), "unknown")
        self.assertEqual(self.tc.kind_of("86' tree cab"), "tree")


SOCAL_HTML = """<html><body><p>Click Tower Name for more info</p>
<p>Tower Name</p><p>County</p><p>NHLR#</p><p>Operator</p><p>Status</p>
<p><a href="http://nhlr.org/lookouts/us/ca/black-mountain-lookout-san-bernadino-nf/">Black Mountain</a></p><p>San Bernardino</p><p>289</p><p>SBNF</p><p>Closed</p>
<p><a href="http://nhlr.org/lookouts/us/ca/keller-peak-lookout/">Keller Peak</a></p><p>San Bernardino</p><p>28</p><p>SBNF</p><p>Destroyed in 2024 Line Fire</p>
<p>Estelle Mtn - no link</p><p>Riverside</p><p>752</p><p>Cal Fire</p><p>Airport Control Tower</p>
<p>Contact:</p></body></html>"""


class FflaGroups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_regional("ffla_groups")

    def test_parse_socal(self):
        rows = self.g.parse_socal(SOCAL_HTML)
        self.assertEqual([r["name"] for r in rows], ["Black Mountain", "Keller Peak", "Estelle Mtn"])
        self.assertEqual(rows[0]["register_url"], "http://nhlr.org/lookouts/us/ca/black-mountain-lookout-san-bernadino-nf/")
        # a row with no link of its own gets the register page the module knows it belongs to
        self.assertEqual(rows[2]["register_url"], "http://nhlr.org/lookouts/us/ca/estelle-mountain-lookout/")
        self.assertEqual((rows[1]["operator"], rows[1]["condition"]), ("SBNF", "Destroyed in 2024 Line Fire"))

    def test_condition_status(self):
        c = self.g.condition_status
        self.assertEqual(c("Destroyed in 2024 Line Fire"), ("gone", 2024))
        self.assertEqual(c("Destroyed by fire 2022"), ("gone", 2022))
        self.assertEqual(c("Steel legs only"), ("ruins", None))
        self.assertEqual(c("Operational-rebuilt 2020"), ("standing", None))
        self.assertEqual(c("Private Property, no access"), ("standing", None))

    def test_every_group_page_names_a_known_group(self):
        for group, state, name, county, url, row in self.g.GROUP_PAGES:
            self.assertIn(group, self.g.GROUPS, name)
            self.assertTrue(url.startswith(("http://", "https://")), url)


class WillhiteWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wh = load_regional("willhiteweb_wa")

    def test_list_entries(self):
        html = ('<a href="olympics/mount_steel_187.htm">Mount Steel</a>'
                '<a href="http://willhiteweb.com/fire_lookouts/twin_lakes/dosewallips_river_014.htm">Twin Lakes</a>'
                '<a href="/washington/fire_lookouts/olympics/list_460.htm">All Olympic Sites</a>'
                '<a href="/info/maps/north-cascades-drawn.jpg">Early Drawing</a>'
                '<a href="http://willhiteweb.com/info/maps_050.htm">1936 Chelan Recreation Map</a>'
                '<a href="http://willhiteweb.com/a/b/lookouts_061.htm">The Cascades Former Lookouts</a>'
                '<a href="http://willhiteweb.com/a/c/x_062.htm">Purcell Mountain\\Trails End</a>')
        got = self.wh.list_entries(html, "http://www.willhiteweb.com/washington/fire_lookouts/olympics/list_460.htm")
        self.assertEqual([n for n, _u in got], ["Mount Steel", "Twin Lakes", "Purcell Mountain/Trails End"])


class RegisterHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_regional("cherylhill_oregon")   # re-exports the regional helpers

    def test_register_url_key(self):
        k = self.c.register_url_key
        self.assertEqual(k("http://www.nhlr.org/lookouts/us/or/Quail-Prairie-Lookout/"),
                         k("https://nhlr.org/lookouts/us/or/quail-prairie-lookout"))

    def test_names_agree(self):
        a = self.c.names_agree
        self.assertTrue(a("Mt. Ireland", "Mount Ireland Lookout"))
        self.assertTrue(a("Red Mtn - Riverside", "Red Mountain Lookout (San Bernadino NF)"))
        self.assertTrue(a("Sid Ormsby", "Sid Ormsbee Lookout"))
        self.assertFalse(a("Bald Butte", "Sugarpine Mountain Lookout"))
        self.assertFalse(a("Cinnamon Butte", "Pig Iron Lookout"))
        self.assertFalse(a(None, "Pig Iron Lookout"))


NEW_SOURCES = ["west_us_lookouts", "trailchick_wa", "cherylhill_oregon", "ffla_groups", "willhiteweb_wa"]


class Registration(unittest.TestCase):
    """The five sources are wired into merge.py and the credits table."""

    def test_registered_everywhere(self):
        import build_site_data as bsd
        import merge as M

        for sid in NEW_SOURCES:
            self.assertIn(sid, M.SOURCE_ORDER, sid)
            self.assertIn(sid, M.SOURCE_SITE, sid)
            self.assertIn(sid, bsd.KNOWN_SOURCES, sid)
            self.assertTrue(bsd.KNOWN_SOURCES[sid]["credit"], sid)
        # every source named in a precedence list is a source the matcher knows
        for field, order in M.PRECEDENCE.items():
            for sid in order:
                self.assertIn(sid, M.SOURCE_ORDER + ["research"], f"{field}: {sid}")
        self.assertEqual(M.STRONG_RADIUS_BY_SOURCE["west_us_lookouts"], 3000)


class MergeBehaviour(unittest.TestCase):
    """What the merge does with records shaped like the new fetchers' (see test_merge.py's Workspace)."""

    def setUp(self):
        try:
            from test_merge import Workspace, rec
        except ImportError:                      # run as pipeline.test_links_survey
            from pipeline.test_merge import Workspace, rec
        self.rec = rec
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def link_labels(self, tower: dict) -> list[str]:
        return [l["label"] for l in tower["links"]]

    def test_oregon_row_joins_by_register_and_adds_its_link(self):
        r = self.rec
        post = r("cherylhill_oregon", "or:quail-prairie", "Quail Prairie", None, None, "OR",
                 registers=[{"register": "NHLR", "number": "US 467", "state_number": "OR 64"}])
        post["url"] = "https://cherylhill.net/firelookouts/2014/07/04/quail-prairie/"
        self.ws.run({"nhlr": [r("nhlr", "US 467", "Quail Prairie Lookout", 42.2418, -124.0456, "OR",
                                registers=[{"register": "NHLR", "number": "US 467", "state_number": "OR 64"}])],
                     "cherylhill_oregon": [post]})
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 1)
        t = self.ws.tower_with_key("cherylhill_oregon:or:quail-prairie")
        self.assertIn("Quail Prairie on Every Lookout in Oregon (Cheryl Hill)", self.link_labels(t))

    def test_name_only_link_needs_a_unique_name(self):
        r = self.rec
        a = r("ffla_groups", "ca:buck-rock", "Buck Rock", None, None, "CA")
        a["links"] = [{"label": "Buck Rock lookout: Buck Rock Foundation", "url": "https://buckrock.org/buck-rock-lookout/",
                       "kind": "association"}]
        a["url"] = None
        b = r("ffla_groups", "ca:bald", "Bald Mountain", None, None, "CA")
        b["links"] = [{"label": "Bald Mountain lookout: X", "url": "https://example.org/bald", "kind": "association"}]
        b["url"] = None
        self.ws.run({"ffla": [r("ffla", "1", "Buck Rock", 36.7893, -118.6, "CA"),
                              r("ffla", "2", "Bald Mountain", 37.0, -119.0, "CA"),
                              r("ffla", "3", "Bald Mountain", 38.0, -120.0, "CA")],
                     "ffla_groups": [a, b]})
        buck = self.ws.tower_with_key("ffla:1")
        self.assertIn("Buck Rock lookout: Buck Rock Foundation", self.link_labels(buck))
        self.assertIn("association", [l["kind"] for l in buck["links"] if l["label"].startswith("Buck Rock lookout")])
        report = json.loads(self.ws.report.read_text())
        self.assertEqual([u["key"] for u in report["unplaced"]], ["ffla_groups:ca:bald"])   # two Bald Mountains

    def test_western_weebly_pin_within_3_km_is_the_same_lookout(self):
        r = self.rec
        self.ws.run({"ffla": [r("ffla", "1", "Lost Lake", 46.6116, -121.5068, "WA")],
                     "west_us_lookouts": [r("west_us_lookouts", "wa:lost-lake", "Lost Lake", 46.6330, -121.5068, "WA", kind="unknown")]})
        self.assertEqual(len(self.ws.towers_by_id()), 1)    # 2.4 km apart
        self.ws.run({"ffla": [r("ffla", "1", "Lost Lake", 46.6116, -121.5068, "WA")],
                     "eastern_us_lookouts": [r("eastern_us_lookouts", "wa:lost-lake", "Lost Lake", 46.6330, -121.5068, "WA")]})
        self.assertEqual(len(self.ws.towers_by_id()), 2)    # the 1.5 km default still applies elsewhere

    def test_trailchick_rip_is_gone_and_new_tower_keeps_its_photo(self):
        r = self.rec
        t = r("trailchick_wa", "wa:aeneas-mountain", "Aeneas Mountain", 47.81203, -120.868, "WA", status="gone", kind="tower")
        t["photos"] = [{"url": "https://trailchick-media.s3.us-west-2.amazonaws.com/IMG_1.jpg",
                        "credit": None, "caption": None, "year": None}]
        self.ws.run({"trailchick_wa": [t]})
        tower = self.ws.tower_with_key("trailchick_wa:wa:aeneas-mountain")
        self.assertEqual(tower["status"], "gone")
        self.assertEqual(tower["photos"][0]["credit"], "TrailChick Washington lookout guide (trailchick.com)")
        self.assertEqual(tower["verification"], "unverified")


if __name__ == "__main__":
    unittest.main()
