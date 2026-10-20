"""Tests for the follow-up Canadian round (2026-10-20): Canada's local units (pipeline/ca_units.py), the
CGNDB gazetteer in the merge, Ron Kemnow's Canadian site (regional/canada_lookouts_weebly.py),
websiteservice.ca (regional/websiteservice_sk.py), the BC Geographic Warehouse layers
(regional/bc_geowarehouse.py), the Canadian survey rules (regional/survey_candidates.py), and the merge
rules they brought (no joins across the border, STATUS_PICKS, copied positions, unplaced grouping).

Run: python3 -m unittest discover -s pipeline
"""

from __future__ import annotations

import json
import unittest

import ca_units as U
import merge as M
import structure
from test_merge import rec
from test_approx_pins import Workspace
from test_survey_candidates import KINDS, cand, load_regional

clw = load_regional("canada_lookouts_weebly")
ws_sk = load_regional("websiteservice_sk")
bcgw = load_regional("bc_geowarehouse")
sc = load_regional("survey_candidates")


def ca(source: str, key: str, name: str | None, lat, lon, region: str = "ON", **kw) -> dict:
    r = rec(source, key, name, lat, lon, region, **kw)
    r["country"] = "CA"
    return r


# ---------------------------------------------------------------------------------------------
# Local units
# ---------------------------------------------------------------------------------------------

class Units(unittest.TestCase):
    def test_unit_spellings_compare_equal(self):
        self.assertEqual(U.unit_key("Regional District of Central Kootenay"), U.unit_key("Central Kootenay"))
        self.assertEqual(U.unit_key("Thompson - Nicola"), U.unit_key("Thompson-Nicola Regional District"))
        self.assertEqual(U.unit_key("Sudbury District"), "sudbury")
        self.assertEqual(U.unit_key("Les Collines-de-l'Outaouais"), "lescollinesdeloutaouais")
        # the merge drops the same words
        self.assertEqual(M.county_key("Regional District of Central Kootenay"), M.county_key("Central Kootenay"))
        self.assertEqual(M.county_key("Sudbury District"), M.county_key("Sudbury"))
        self.assertEqual(M.county_key("Jefferson County"), "jefferson")   # US unchanged

    def test_old_bc_districts_map_to_todays(self):
        self.assertEqual(U.bc_current_districts("Fraser - Cheam"), ["Fraser Valley"])
        self.assertEqual(U.bc_current_districts("Comox - Strathcona"), ["Comox Valley", "Strathcona"])
        self.assertEqual(U.bc_current_districts("Okanogan - Similkameen"), ["Okanagan-Similkameen"])
        self.assertEqual(U.bc_current_districts("Edson Forest"), [])

    def test_named_unit_only_for_real_units(self):
        self.assertEqual(U.named_unit("BC", "Thompson - Nicola"), "Thompson-Nicola")
        self.assertEqual(U.named_unit("ON", "Parry Sound District"), "Parry Sound District")
        self.assertEqual(U.named_unit("ON", "Haliburton County"), "Haliburton County")
        self.assertIsNone(U.named_unit("ON", "Sioux Lookout District"))     # a Ministry fire district
        self.assertIsNone(U.named_unit("ON", "Pembrooke District"))
        self.assertEqual(U.named_unit("NB", "Gloucester County"), "Gloucester County")
        self.assertEqual(U.named_unit("NS", "CBRM"), "CBRM")
        self.assertIsNone(U.named_unit("AB", "Edson Forest"))
        self.assertIsNone(U.named_unit("QC", "The Laurentian Forest Protective Association"))


# ---------------------------------------------------------------------------------------------
# The CGNDB gazetteer in the merge
# ---------------------------------------------------------------------------------------------

class CgndbWorkspace(Workspace):
    """The approximate-pin workspace, with a CGNDB extract (cgndb) written after the sources."""

    cgndb: dict | None = None

    def run(self, by_source=None, photos_manifest=None):
        if by_source is not None:
            for f in self.sources.glob("*.json"):
                f.unlink()
            from test_merge import write_sources
            write_sources(self.sources, by_source)
        if self.cgndb is not None:
            (self.sources / M.CGNDB_FILE).write_text(json.dumps(self.cgndb), encoding="utf-8")
        return super().run(None, photos_manifest)


def cgndb_file(ws: CgndbWorkspace, features: dict, units: dict, keys: dict | None = None) -> None:
    if keys is None:
        keys = {r: sorted({M.gnis_feature_key(f[1]) for f in rows} - {None}) for r, rows in features.items()}
    ws.sources.mkdir(parents=True, exist_ok=True)
    ws.cgndb = {"source": "cgndb_places", "kind": "reference", "retrieved": "2026-10-20",
                "keys": keys, "units": units, "features": features}


NB_FEATURES = {"NB": [
    ["DAAAA", "Ashton Hill", "Hill", ["Northumberland"], 47.0989, -65.7318],
    ["DAAAB", "Blue Mountain", "Mountain", ["Restigouche"], 47.50, -66.80],
    ["DAAAC", "Blue Mountain", "Mountain", ["York"], 46.10, -66.90],
    ["DAAAD", "Lone Peak", "Peak", ["Victoria"], 46.90, -67.10],
]}
NB_UNITS = {"NB": ["Northumberland", "Restigouche", "York", "Victoria"]}


class CgndbPins(unittest.TestCase):
    def setUp(self):
        self.ws = CgndbWorkspace()

    def tearDown(self):
        self.ws.close()

    def run_nb(self, records):
        cgndb_file(self.ws, NB_FEATURES, NB_UNITS)
        self.ws.run({"canada_lookouts_weebly": records})
        return self.ws.towers_by_id(), json.loads(self.ws.report.read_text())

    def test_one_same_name_hill_in_the_county(self):
        towers, _ = self.run_nb([ca("canada_lookouts_weebly", "nb:ashton", "Ashton Hill", None, None, "NB",
                                    county="Northumberland County")])
        t = towers["ca-nb-ashton-hill"]
        loc = t["location"]
        self.assertTrue(loc["approximate"])
        self.assertEqual((loc["from"], loc["gazetteer"], loc["method"]), ("cgndb", "cgndb", "cgndb_name_match"))
        self.assertEqual(loc["gnis"]["county"], "Northumberland")
        self.assertNotIn("scope", loc)
        self.assertEqual(t["verification"], "unverified")

    def test_no_unit_means_the_whole_province(self):
        towers, _ = self.run_nb([ca("canada_lookouts_weebly", "nb:lone", "Lone Peak", None, None, "NB")])
        self.assertEqual(towers["ca-nb-lone-peak"]["location"]["scope"], "province")
        self.assertIsNone(towers["ca-nb-lone-peak"]["location"]["gnis"]["county"])

    def test_two_hills_of_the_name_in_the_province_are_not_enough(self):
        towers, report = self.run_nb([ca("canada_lookouts_weebly", "nb:blue", "Blue Mountain", None, None, "NB")])
        self.assertEqual(towers, {})
        self.assertEqual(report["unplaced_lookouts"][0]["gnis"], "ambiguous")
        # with the county, the one in it
        towers, _ = self.run_nb([ca("canada_lookouts_weebly", "nb:blue", "Blue Mountain", None, None, "NB",
                                    county="Restigouche County")])
        self.assertEqual(towers["ca-nb-blue-mountain"]["location"]["gnis"]["id"], "DAAAB")

    def test_a_unit_the_gazetteer_cannot_search_is_not_placed(self):
        cgndb_file(self.ws, {"AB": [["XAAAA", "Copton Ridge", "Ridge", [], 54.2, -119.6]]}, {})
        self.ws.run({"canada_lookouts_weebly": [ca("canada_lookouts_weebly", "ab:c", "Copton Ridge", None, None, "AB",
                                                   county="Division No. 18")]})
        report = json.loads(self.ws.report.read_text())
        self.assertEqual(report["unplaced_lookouts"][0]["gnis"], "county_unknown")
        # without one it is placed province-wide (Alberta's features carry no unit)
        self.ws.run({"canada_lookouts_weebly": [ca("canada_lookouts_weebly", "ab:c", "Copton Ridge", None, None, "AB")]})
        self.assertIn("ca-ab-copton-ridge", self.ws.towers_by_id())

    def test_without_the_extract_canada_stays_not_covered(self):
        self.ws.run({"canada_lookouts_weebly": [ca("canada_lookouts_weebly", "nb:ashton", "Ashton Hill", None, None, "NB")]})
        report = json.loads(self.ws.report.read_text())
        self.assertEqual(report["unplaced_lookouts"][0]["gnis"], "not_covered")


# ---------------------------------------------------------------------------------------------
# Merge rules of the round
# ---------------------------------------------------------------------------------------------

class MergeRules(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_never_joined_across_the_border(self):
        # Monument 83: a lookout on each side of the line, a few metres apart
        self.ws.run({"ffla": [rec("ffla", "wa:m83", "Monument 83", 49.0004, -120.6390, "WA")],
                     "survey_bc_yt": [ca("survey_bc_yt", "bc:m83", "Monument 83 Lookout", 49.0006, -120.6392, "BC")]})
        towers = self.ws.towers_by_id()
        self.assertEqual(len(towers), 2)
        self.assertEqual({t["country"] for t in towers.values()}, {"US", "CA"})

    def test_a_copied_position_does_not_verify(self):
        self.ws.run({"osm": [ca("osm", "node/1", "Dome Lookout", 64.0683, -139.3334, "YT")],
                     "survey_bc_yt": [ca("survey_bc_yt", "yt:dome", "Dome Lookout", 64.0683, -139.3334, "YT",
                                         extra={"position_copied_from": "osm"})]})
        t = self.ws.towers_by_id()["ca-yt-dome"]
        self.assertEqual(len(t["sources"]), 2)
        self.assertEqual(t["verification"], "unverified")    # one lineage only

    def test_status_picks_beat_precedence(self):
        key = next(iter(M.STATUS_PICKS))     # survey_qc_atl:ns:barr-settlement
        region = key.split(":")[1].upper()
        self.ws.run({"nhlr": [ca("nhlr", "CAN 6", "Barr Settlement Fire Tower", 45.0, -63.8, region,
                                 registers=[{"register": "NHLR", "number": "CAN 6"}])],
                     "survey_qc_atl": [ca("survey_qc_atl", key.split(":", 1)[1], "Barr Settlement", 45.0, -63.8, region,
                                          status="gone", status_raw="gone (nova scotia closure)")]})
        t = next(iter(self.ws.towers_by_id().values()))
        self.assertEqual(t["status"], "gone")
        self.assertIn("2015", t["status_note"])

    def test_staffing_as_of(self):
        self.ws.run({"survey_bc_yt": [ca("survey_bc_yt", "yt:ferry", "Ferry Hill Lookout", 63.6, -136.5, "YT",
                                         extra={"staffing_hint": "staffed", "staffing_as_of": 2024})]})
        t = next(iter(self.ws.towers_by_id().values()))
        self.assertEqual(t["staffing"], {"status": "staffed", "as_of": 2024})

    def test_one_canadian_lookout_listed_once_across_unit_spellings(self):
        self.ws.run({"nhlr": [ca("nhlr", "CAN 7", "Johnson Hill Fire Tower", None, None, "NS", county="Meagher's Grant, Halifax",
                                 registers=[{"register": "NHLR", "number": "CAN 7"}])],
                     "canada_lookouts_weebly": [ca("canada_lookouts_weebly", "ns:johnson-hill", "Johnson Hill", None, None, "NS",
                                                   county="Halifax County")],
                     "survey_qc_atl": [ca("survey_qc_atl", "ns:johnson-hill", "Johnson Hill", None, None, "NS")]})
        rows = [u for u in json.loads(self.ws.report.read_text())["unplaced_lookouts"] if u["region"] == "NS"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["records"]), 3)

    def test_canadian_place_line_is_a_hint(self):
        self.ws.run({"canada_lookouts_weebly": [ca("canada_lookouts_weebly", "qc:x", "Lac Canot", None, None, "QC",
                                                   extra={"place_line": "Manitou Division - The Laurentian Forest Protective Association"})]})
        row = json.loads(self.ws.report.read_text())["unplaced_lookouts"][0]
        self.assertEqual(row["hint"]["why"], "filed_under")


# ---------------------------------------------------------------------------------------------
# Canada's Fire Lookouts (canada-lookouts.weebly.com)
# ---------------------------------------------------------------------------------------------

class WeeblyNames(unittest.TestCase):
    def test_capitals_become_ordinary_case(self):
        self.assertEqual(clw.tidy_name("McBRIDE PEAK"), "McBride Peak")
        self.assertEqual(clw.tidy_name("LAC LA GARDE"), "Lac la Garde")
        self.assertEqual(clw.tidy_name("BM 229"), "BM 229")
        self.assertEqual(clw.tidy_name("MT JESMOND"), "Mt. Jesmond")

    def test_parentheticals(self):
        self.assertEqual(clw.split_name("AVERY", ["(VAVENBY)"])[:2], ("Avery", ["Vavenby"]))
        name, aliases, notes = clw.split_name("DOME", ["(AKA SECOND DOME OR FIRE DOME)"])
        self.assertEqual(aliases, ["Second Dome", "Fire Dome"])
        self.assertEqual(clw.split_name("Mount Hunter (Lower)", [])[0], "Mount Hunter (Lower)")
        name, aliases, notes = clw.split_name("BUTTE D'OR (SECONDARY)", [])
        self.assertEqual((name, aliases, notes), ("Butte D'Or", [], {"secondary": True}))
        name, aliases, notes = clw.split_name("PIGEON (Removed)", [])
        self.assertEqual((name, aliases, notes["status_word"]), ("Pigeon", [], "Removed"))

    def test_index_name_lines(self):
        self.assertTrue(clw.is_name_line("ALEZA LAKE EXP. STA."))
        self.assertTrue(clw.is_name_line("McBRIDE PEAK"))
        self.assertFalse(clw.is_name_line("Thompson - Nicola"))
        self.assertFalse(clw.is_name_line("BADGER (LINK)"))
        self.assertFalse(clw.is_name_line("CBRM", "NS"))          # a unit written in capitals
        self.assertFalse(clw.is_name_line("1948:"))

    def test_similar_keys(self):
        self.assertTrue(clw.similar_keys("doucet", "doucette"))
        self.assertTrue(clw.similar_keys("bodmin", "bodminhill"))
        self.assertFalse(clw.similar_keys("pelicanmountain", "pelicanpoint"))

    def test_place_parts(self):
        self.assertEqual(clw.place_parts("BC", ["Thompson - Nicola"]), ("Thompson-Nicola", []))
        self.assertEqual(clw.place_parts("ON", ["Pembrooke District - Algonquin Park"]),
                         (None, ["Pembrooke District", "Algonquin Park"]))
        unit, places = clw.place_parts("QC", ["The Laurentian Forest Protective Association",
                                              "The Laurentian Forest Protective Association, Ltd"])
        self.assertEqual((unit, places), (None, ["The Laurentian Forest Protective Association, Ltd"]))

    def test_coordinate_line_is_positive_west(self):
        m = clw.COORD_LINE_RE.search("Latitude: 49.383 Longitude: 120.407 Elevation: 1593")
        self.assertEqual((m.group("lat"), m.group("lon"), m.group("elev")), ("49.383", "120.407", "1593"))
        self.assertTrue(clw.COORD_LINE_RE.search("Lat. 54.935 Lon. 126.77 Elev. 1417"))


class WeeblyEvents(unittest.TestCase):
    T = {"perles", "busted"}

    def cls(self, s, quoted=False, year=1950, tokens=None):
        return clw.classify_sentence(s, year, quoted, tokens if tokens is not None else self.T)

    def test_what_counts(self):
        self.assertEqual(self.cls("A 50-foot wooden tower was erected."), "built")
        self.assertEqual(self.cls("Built 70-foot wooden replacement tower."), "replaced")
        self.assertEqual(self.cls("The tower was removed."), "removed")
        self.assertEqual(self.cls("The cupola was replaced at East la Ronge tower."), "modified")

    def test_what_does_not(self):
        self.assertIsNone(self.cls("A 10 x 12 Tower observer's camp cabin built."))           # a cabin
        self.assertIsNone(self.cls("Cut timber for building tower to replace old one."))      # a plan
        self.assertIsNone(self.cls("Construction of a new fire tower has started."))          # in progress
        self.assertIsNone(self.cls("The barn at Goose Mountain Lookout Tower was completed."))
        self.assertIsNone(self.cls("Haeckel Hill lookout tower was built in 1954.", year=1956))   # another year
        # a report's sentence must name the lookout (or say "the tower")
        self.assertIsNone(self.cls("A steel tower was erected near Atik.", quoted=True, tokens={"perles"}))
        self.assertEqual(self.cls("A steel tower was erected near Atik.", quoted=True, tokens={"atik"}), "built")

    def test_moves_go_both_ways(self):
        s = "Black Creek tower was moved to a higher point near Gillies Lake."
        self.assertEqual(self.cls(s, tokens={"black", "creek"}), "relocated")
        self.assertEqual(self.cls(s, tokens={"gillies"}), "arrived")
        self.assertEqual(self.cls("The Round Lake tower was dismantled and re-erected at Long Lake.", tokens={"long"}), "arrived")

    def test_a_new_site_replacing_another_is_built(self):
        self.assertEqual(self.cls("Built a new tower to replace the old Pigeon lookout.", tokens={"barrier"}), "built")

    def test_events_and_their_order(self):
        lines = ["c.1910:", "A forty-five foot wooden tower was erected.", "1931:", "A steel tower erected.",
                 "1961:", "A 100-foot steel tower was erected.", "(Annual Report)"]
        ev = clw.clip_events(lines, "https://example.org/t.html", ["Temagami"])
        self.assertEqual([(e["year"], e["event"]) for e in ev], [(1931, "built"), (1961, "replaced")])
        self.assertTrue(all(e["source_url"] == "https://example.org/t.html" for e in ev))


INDEX_HTML = """<html><body><div id="wsite-content" class="x">
<h2>BRITISH COLUMBIA</h2>
<h2><strong>AGATE</strong></h2><div class="paragraph"><em>Thompson - Nicola</em><br /></div>
<a href='https://canadafirelookouts.weebly.com/agate.html'>go</a>
<h2>AVERY</h2><div>(VAVENBY)</div><div>Thompson - Nicola</div>
<a href='https://canadafirelookouts.weebly.com/avery-vavenby.html'>go</a>
<div class="paragraph"><strong>BULL</strong></div><div>Cariboo</div>
<a href='https://canadafirelookouts.weebly.com/bull.html'>go</a>
<div>Powered by Weebly</div></div></body></html>"""


class WeeblyIndex(unittest.TestCase):
    def test_blocks(self):
        ents = clw.index_entries("BC", INDEX_HTML)
        self.assertEqual([(e["name"], e["unit"], e["aliases"], e.get("href_slug")) for e in ents],
                         [("Agate", "Thompson-Nicola", [], "agate"), ("Avery", "Thompson-Nicola", ["Vavenby"], "avery-vavenby"),
                          ("Bull", "Cariboo", [], "bull")])

    def test_status_tables(self):
        self.assertEqual(structure.status_info("canada_lookouts_weebly", "Removed")[0].status, "gone")
        self.assertEqual(structure.status_info("canada_lookouts_weebly", "Cut down")[0].status, "gone")


# ---------------------------------------------------------------------------------------------
# websiteservice.ca
# ---------------------------------------------------------------------------------------------

PAGE = """<table><tr>
<td valign="top" bgcolor="#FFFF99"><font><b>ANGLIN LAKE</b></font><p><b>LOCATION</b></p>
<p>53-42-41.9 X 105-59-52.2&nbsp; LSD 14- 36-54-28-W2</p><p><b>HEIGHT</b> 80'&nbsp; Heavy steel</p>
<p><b>YEAR of CONSTRUCTION</b> 19</p><p><b>NAMES of TOWERMEN</b></p><p>A. Person</p><p>NOTES - New cupola 1957</p></td>
<td valign="top"><a href="towerstuff/anglin/a1.jpg"><img src="x"></a></td></tr>
<tr><td valign="top" bgcolor="#FFFF99"><b>DUBE</b><p>LOCATION</p><p>54-46-40.2 X 197-51-34.7</p><p>HEIGHT</p>
<p>YEAR of CONSTRUCTION</p><p>NAMES of TOWERMEN</p></td></tr></table>"""


class Websiteservice(unittest.TestCase):
    def test_positions(self):
        self.assertEqual(ws_sk.parse_position("53-42-41.9 X 105-59-52.2")[:2], (53.71164, -105.99783))
        self.assertEqual(ws_sk.parse_position("53-22.1000 X 102-32.3667")[:2], (53.36833, -102.53945))
        self.assertEqual(ws_sk.parse_position("56-54,6833 X 108.09.3833")[:2], (56.91139, -108.15639))
        self.assertEqual(ws_sk.parse_position("5 5-07-08.9 X 108-11-53.3")[:2], (55.11914, -108.19814))
        for bad in ("54-46-40.2 X 197-51-34.7", "54-30-32.3 X 105-32-98.9", "52-28-12.0 X 103-99-23.0",
                    "5353-36-55.9 X 105-17-40.2"):
            lat, lon, raw, why = ws_sk.parse_position(bad)
            self.assertIsNone(lat, bad)
            self.assertTrue(why, bad)

    def test_records(self):
        recs = ws_sk.records_from(PAGE)
        a, d = recs
        self.assertEqual((a["name"], a["lat"], a["extra"]["legal_land_description"], a["extra"]["height_ft"]),
                         ("Anglin Lake Fire Tower", 53.71164, "14-36-54-28-W2", 80))
        self.assertEqual([(e["year"], e["event"]) for e in a["events"]], [(1957, "modified")])
        self.assertEqual(a["photos"][0]["url"], "https://www.websiteservice.ca/towerstuff/anglin/a1.jpg")
        self.assertNotIn("Person", json.dumps(a))          # towermen's names are not stored
        self.assertIsNone(d["lat"])
        self.assertIn("position_note", d["extra"])


# ---------------------------------------------------------------------------------------------
# BC Geographic Warehouse
# ---------------------------------------------------------------------------------------------

class BcLayers(unittest.TestCase):
    def test_symbol_centre(self):
        sq = {"type": "Polygon", "coordinates": [[[-120.0, 50.0], [-119.998, 50.0], [-119.998, 50.002], [-120.0, 50.002], [-120.0, 50.0]]]}
        lat, lon = bcgw.centroid(sq)
        self.assertAlmostEqual(lat, 50.001, places=6)
        self.assertAlmostEqual(lon, -119.999, places=6)

    def test_core_names(self):
        self.assertEqual(bcgw.core_key("Sinkut Mountain"), bcgw.core_key("Sinkut"))
        self.assertEqual(bcgw.core_key("Mount Kobau"), bcgw.core_key("Kobau Mountain"))

    def test_rec_site_name_and_years(self):
        self.assertEqual(bcgw.rec_name("OWEN HILL (Owen Lookout Cabin)"), "Owen Hill (Owen Lookout Cabin)")
        self.assertEqual(bcgw.BUILT_YEAR_RE.search("The present tower was built in 1974.").group(1), "1974")
        self.assertEqual(bcgw.REMOVED_YEAR_RE.search("dismantled in the fall of 2007 due to vandalism").group(1), "2007")


# ---------------------------------------------------------------------------------------------
# The surveys' rules
# ---------------------------------------------------------------------------------------------

class SurveyRules(unittest.TestCase):
    def test_rows_only_a_bulk_source_backs_are_left_out(self):
        weebly = cand(sources=["https://canada-lookouts.weebly.com/x.html"])
        self.assertFalse(sc.ca_keep(weebly, "qc-atl"))
        self.assertTrue(sc.ca_keep(cand(sources=["https://canada-lookouts.weebly.com/x.html", "http://marscan.com/nsdnrfiretowers.htm"]), "qc-atl"))
        # Saskatchewan's provincial towers carry the camera finding when they have a position
        sk = cand(lat=53.7, lon=-106.0, location_from="https://www.websiteservice.ca/firetowers_page4.htm",
                  access_note="since the 2013-14 move to cameras no observer lives in the tower")
        self.assertTrue(sc.ca_keep(sk, "prairies-north"))
        r = sc.build_records([sk], "survey_prairies_north", KINDS, survey="prairies-north")[0]
        self.assertEqual(r["extra"]["staffing_hint"], "unstaffed")
        self.assertEqual(r["extra"]["position_copied_from"], "websiteservice_sk")

    def test_dated_status_rules(self):
        ns = cand(region="NS", status="gone", sources=["http://marscan.com/nsdnrfiretowers.htm"],
                  status_note="Nova Scotia DNR closed its tower network in 2013 and, per CBC (2025), dismantled the towers in 2015")
        r = sc.build_records([ns], "survey_qc_atl", KINDS, survey="qc-atl")[0]
        self.assertEqual((r["status_raw"], r["status"]), ("gone (nova scotia closure)", "gone"))
        on = cand(region="ON", status="standing", staffed_now=False,
                  sources=["https://forestrangers.github.io/ontariofiretowers/stillstanding2.html"],
                  status_note="Listed as still standing c.2009-2013 (page undated)")
        r = sc.build_records([on], "survey_on", KINDS, survey="on")[0]
        self.assertEqual(r["status_raw"], "standing (ontario list c. 2009-2013)")
        self.assertIn("2013", structure.status_info("survey_on", r["status_raw"])[0].note)

    def test_yukon_staffed_as_of_2024(self):
        yt = cand(region="YT", status="standing", staffed_now=True, sources=["https://explorenorth.com/x.html"])
        r = sc.build_records([yt], "survey_bc_yt", KINDS, survey="bc-yt")[0]
        self.assertEqual((r["extra"]["staffing_hint"], r["extra"]["staffing_as_of"]), ("staffed", 2024))

    def test_units_that_are_not_units_become_hints(self):
        bc = cand(region="BC", county="Vernon area (Silver Star ski resort)", sources=["https://therainlander.ca/x/"])
        r = sc.build_records([bc], "survey_bc_yt", KINDS, survey="bc-yt")[0]
        self.assertIsNone(r["county"])
        self.assertEqual(r["extra"]["place_line"], "Vernon area (Silver Star ski resort)")

    def test_a_summit_position_is_a_hint(self):
        ab = cand(region="AB", lat=52.8594, lon=-117.967, location_from="https://www.cdnrockiesdatabases.ca/peaks/1251",
                  sources=["https://jaspermuseum.org/jasper-fire-towers/"])
        r = sc.build_records([ab], "survey_prairies_north", KINDS, survey="prairies-north")[0]
        self.assertIsNone(r["lat"])
        self.assertIn("position_note", r["extra"])


if __name__ == "__main__":
    unittest.main()
