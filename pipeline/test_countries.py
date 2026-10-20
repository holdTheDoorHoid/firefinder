"""Tests for Firefinder's countries and regions (owner decision 2026-10-20: Alaska, Hawaii and
Canada): pipeline/regions.py, the merge's country rules and the firelookout.ca reader.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import merge as M
import regions as R
import validate as V
from test_merge import Workspace, rec

sys.path.insert(0, str(Path(__file__).resolve().parent / "regional"))
import firelookout_ca as FCA  # noqa: E402


def ca(source: str, key: str, name: str | None, lat, lon, region: str = "ON", **kw) -> dict:
    r = rec(source, key, name, lat, lon, region, **kw)
    r["country"] = "CA"
    return r


class Regions(unittest.TestCase):
    def test_codes_are_unique_and_name_their_country(self):
        self.assertEqual(R.country_of("ON"), "CA")
        self.assertEqual(R.country_of("OR"), "US")
        self.assertEqual(R.country_of("AK"), "US")
        self.assertIsNone(R.country_of("ZZ"))
        self.assertEqual(len(R.REGION_COUNTRY), len(R.REGION_NAMES))

    def test_names_english_and_french(self):
        self.assertEqual(R.parse_region("Québec"), "QC")
        self.assertEqual(R.parse_region("Quebec"), "QC")
        self.assertEqual(R.parse_region("Colombie-Britannique"), "BC")
        self.assertEqual(R.parse_region("Nouvelle-Écosse"), "NS")
        self.assertEqual(R.parse_region("Territoires du Nord-Ouest"), "NT")
        self.assertEqual(R.parse_region("B.C."), "BC")
        self.assertEqual(R.parse_region("Oregon"), "OR")
        self.assertIsNone(R.parse_region("Ontario", "US"))
        self.assertIsNone(R.parse_region("Northeastern Ontario"))

    def test_ids_and_folders(self):
        self.assertEqual(R.id_prefix("CA", "ON"), "ca-on")
        self.assertEqual(R.id_prefix(None, "AK"), "us-ak")
        # a US tower keeps its bare state folder; any other country names itself, so Canada's
        # folders never meet a US state's (and Australia's WA would not meet Washington's)
        self.assertEqual(R.tower_dir("us-or-abbot-butte"), "or")
        self.assertEqual(R.tower_dir("us-ca-buck-rock"), "ca")
        self.assertEqual(R.tower_dir("ca-on-shining-tree"), "ca-on")

    def test_alaska_crosses_the_180th_meridian(self):
        self.assertTrue(R.in_region_box("AK", 52.9, 172.9))     # Attu
        self.assertTrue(R.in_region_box("AK", 61.2, -149.9))    # Anchorage
        self.assertIsNone(R.flag_coordinate("AK", 52.9, 172.9))
        self.assertEqual(R.flag_coordinate("OR", 44.0, 121.0), "lon_positive_sign")
        self.assertTrue(R.in_country("US", 52.9, 172.9))
        self.assertFalse(R.in_country("CA", 52.9, 172.9))

    def test_hawaii(self):
        self.assertTrue(R.in_region_box("HI", 21.3, -157.8))
        self.assertTrue(R.in_region_box("HI", 28.4, -178.3))    # Kure Atoll

    def test_local_units(self):
        self.assertEqual(R.local_unit_label("US", "OR", "Jefferson"), "Jefferson County")
        self.assertEqual(R.local_unit_label("US", "LA", "Caddo"), "Caddo Parish")
        self.assertEqual(R.local_unit_label("US", "AK", "Bethel"), "Bethel Census Area")
        self.assertEqual(R.local_unit_label("US", "AK", "Matanuska-Susitna"), "Matanuska-Susitna Borough")
        self.assertEqual(R.local_unit_label("US", "AK", "Kenai Peninsula Borough"), "Kenai Peninsula Borough")
        # Canadian units carry their own words: nothing appended
        self.assertEqual(R.local_unit_label("CA", "ON", "Sudbury District"), "Sudbury District")
        self.assertEqual(R.local_unit_label("CA", "SK", "Division No. 18"), "Division No. 18")
        self.assertEqual(R.local_unit_label("CA", "NS", "Cumberland County"), "Cumberland County")


class CountriesInMerge(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def test_canadian_tower_ids_folders_and_country(self):
        self.ws.run({"firelookout_ca": [ca("firelookout_ca", "1", "Shining Tree Fire Tower", 47.579264, -81.353059,
                                           county="Sudbury District")],
                     "ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR")]})
        towers = self.ws.towers_by_id()
        self.assertIn("ca-on-shining-tree", towers)
        self.assertIn("us-or-abbot-butte", towers)
        t = towers["ca-on-shining-tree"]
        self.assertEqual((t["country"], t["region"], t["county"]), ("CA", "ON", "Sudbury District"))
        self.assertEqual(towers["us-or-abbot-butte"]["country"], "US")
        self.assertTrue((self.ws.towers / "ca-on" / "ca-on-shining-tree.json").exists())
        self.assertTrue((self.ws.towers / "or" / "us-or-abbot-butte.json").exists())
        vocab = json.loads((M.DATA / "vocab.json").read_text())
        for p in self.ws.towers.rglob("*.json"):
            errs, warns = V.check(json.loads(p.read_text()), p, vocab)
            self.assertEqual(errs, [], p.name)
            self.assertEqual(warns, [], p.name)

    def test_a_us_row_placed_in_canada_is_not_used(self):
        # a slipped coordinate of a US list must not make a tower in Canada under a US id
        self.ws.run({"ffla": [rec("ffla", "a", "Abbot Butte", 44.5577, -121.7088, "OR"),
                              rec("ffla", "b", "Slipped", 50.5, -121.7, "WA")]})
        rows = json.loads(self.ws.report.read_text())["coordinates_not_used"]
        self.assertEqual([r["key"] for r in rows], ["ffla:b"])

    def test_no_gnis_placement_outside_the_us(self):
        self.ws.run({"firelookout_ca": [ca("firelookout_ca", "1", "Gull Lake Fire Tower", None, None, county="Kawartha Lakes",
                                           extra={"place_hint": {"name": "Lindsay", "lat": 44.355, "lon": -78.737, "why": "district_office"}})]})
        report = json.loads(self.ws.report.read_text())
        rows = report["unplaced_lookouts"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["region"], "ON")
        self.assertEqual(rows[0]["gnis"], "not_covered")
        self.assertEqual(rows[0]["hint"]["name"], "Lindsay")
        self.assertEqual(self.ws.towers_by_id(), {})

    def test_unconfirmed_osm_tower_is_hidden_until_another_source_names_it(self):
        why = "Not confirmed as a fire lookout (an observation tower OpenStreetMap does not tag or name as one)"
        osm = [ca("osm", "node/1", "Scenic Lookout Tower", 45.339, -80.028, extra={"unconfirmed_lookout": why}),
               ca("osm", "node/2", "Dorcet Lookout Tower", 45.252, -78.893, extra={"unconfirmed_lookout": why})]
        flca = [ca("firelookout_ca", "9872", "Dorset Fire Tower", 45.2525, -78.8935)]
        self.ws.run({"osm": osm, "firelookout_ca": flca})
        scenic = self.ws.tower_with_key("osm:node/1")
        dorset = self.ws.tower_with_key("osm:node/2")
        self.assertTrue(scenic["hidden"])
        self.assertEqual(scenic["hidden_reason"], why)
        self.assertFalse(dorset["hidden"])
        self.assertEqual(dorset, self.ws.tower_with_key("firelookout_ca:9872"))

    def test_not_a_fire_lookout_is_hidden(self):
        self.ws.run({"firelookout_ca": [ca("firelookout_ca", "35798", "Thunder Cape Bird Observatory", 48.3, -88.9,
                                           extra={"not_fire_lookout": "Not a fire lookout (a bird observatory)"})]})
        t = self.ws.tower_with_key("firelookout_ca:35798")
        self.assertTrue(t["hidden"])

    def test_hawaii_fire_control_stations_and_alaska_shelters_are_hidden(self):
        self.ws.run({"osm": [rec("osm", "node/5", "Diamond Head Fire Control Station", 21.26, -157.80, "HI"),
                             rec("osm", "node/6", "Pinta Cove Shelter Lookout/Cabin", 57.6, -134.5, "AK")]})
        hi = self.ws.tower_with_key("osm:node/5")
        ak = self.ws.tower_with_key("osm:node/6")
        self.assertTrue(hi["hidden"])
        self.assertIn("coastal-artillery", hi["hidden_reason"])
        self.assertTrue(ak["hidden"])
        self.assertIn("shelter", ak["hidden_reason"])
        # "fire control" elsewhere is forestry: Florida's Monticello tower stays
        self.ws.run({"osm": [rec("osm", "node/7", "Monticello Fire Control Headquarters Fire Tower", 30.55, -83.87, "FL")]})
        self.assertFalse(self.ws.tower_with_key("osm:node/7")["hidden"])

    def test_canadian_register_numbers_match(self):
        nhlr = [ca("nhlr", "CAN 16", "Fort Frances Lookout Tower", 48.606964, -93.375864,
                   registers=[{"register": "NHLR", "number": "CAN 16", "state_number": "ON 1"}])]
        other = [ca("survey_on", "x", "Fort Frances Fire Tower", None, None,
                    registers=[{"register": "NHLR", "number": "CAN 16", "state_number": "ON 1"}])]
        self.ws.run({"nhlr": nhlr, "survey_on": other})
        self.assertEqual(self.ws.tower_with_key("nhlr:CAN 16"), self.ws.tower_with_key("survey_on:x"))

    def test_keep_apart_splits_two_lookouts_a_name_would_join(self):
        import record_joins
        pair = frozenset(("nhlr:CAN 2", "osm:node/11803949555"))
        self.assertIn(pair, record_joins.KEEP_APART_PAIRS)
        nhlr = [ca("nhlr", "CAN 2", "Baseline Lookout", 52.137417, -115.415733, "AB",
                   registers=[{"register": "NHLR", "number": "CAN 2", "state_number": "AB 2"}])]
        osm = [ca("osm", "node/11803949555", "Baseline Fire Lookout", 52.1311, -115.428935, "AB")]
        ab = [ca("alberta_wildfire", "BL", "Baseline", None, None, "AB")]
        self.ws.run({"nhlr": nhlr, "osm": osm, "alberta_wildfire": ab})
        old = self.ws.tower_with_key("nhlr:CAN 2")
        active = self.ws.tower_with_key("osm:node/11803949555")
        self.assertNotEqual(old["id"], active["id"])
        self.assertEqual(self.ws.tower_with_key("alberta_wildfire:BL")["id"], active["id"])
        # and a second run keeps them apart (the key memory honours it too)
        self.ws.run()
        self.assertNotEqual(self.ws.tower_with_key("nhlr:CAN 2")["id"], self.ws.tower_with_key("osm:node/11803949555")["id"])

    def test_fallback_name_only_when_no_source_names_it(self):
        lio = [ca("ontario_lio", "1", None, 48.37, -83.30, extra={"fallback_name": "Fire tower (LIO 1)"}),
               ca("ontario_lio", "2", None, 46.0, -80.0, extra={"fallback_name": "Fire tower (LIO 2)"})]
        flca = [ca("firelookout_ca", "7", "Lloyd Fire Tower", 48.3702, -83.3043)]
        self.ws.run({"ontario_lio": lio, "firelookout_ca": flca})
        self.assertEqual(self.ws.tower_with_key("ontario_lio:1")["name"], "Lloyd Fire Tower")
        self.assertEqual(self.ws.tower_with_key("ontario_lio:2")["name"], "Fire tower (LIO 2)")


class SiteData(unittest.TestCase):
    def test_country_on_features_and_in_meta(self):
        import build_site_data as B
        from collections import Counter
        base = {"name": "X", "kind": "tower", "status": "standing", "verification": "unverified", "events": [],
                "location": {"lat": 47.5, "lon": -81.3}}
        ca_feat = B.feature(dict(base, id="ca-on-x", region="ON", country="CA"))
        us_feat = B.feature(dict(base, id="us-or-x", region="OR", country="US", location={"lat": 44.0, "lon": -121.0}))
        self.assertEqual(ca_feat["properties"]["cc"], "CA")
        self.assertNotIn("cc", us_feat["properties"])
        meta = B.regions_meta(Counter({"ON": 3, "OR": 2}))
        self.assertEqual([c["code"] for c in meta["countries"]], ["US", "CA"])
        on = next(r for r in meta["countries"][1]["regions"] if r["code"] == "ON")
        self.assertEqual(on["towers"], 3)

    def test_place_hint_reaches_the_site(self):
        import build_site_data as B
        self.assertIn("hint", B.UNPLACED_KEYS)

    def test_summary_names_the_country_and_reads_metres_first(self):
        import auto_summary as A
        text = A.summarize({"name": "Shining Tree Fire Tower", "country": "CA", "region": "ON", "county": "Sudbury District",
                            "status": "standing", "kind": "tower", "elevation_m": 459})
        self.assertIn("in Sudbury District, Ontario, Canada", text)
        self.assertIn("459 m (1,506 ft)", text)
        us = A.summarize({"name": "Abbot Butte Lookout", "country": "US", "region": "OR", "county": "Jefferson",
                          "status": "gone", "kind": "tower", "elevation_m": 1500})
        self.assertIn("in Jefferson County, Oregon, at 4,921 ft (1,500 m)", us)


class FirelookoutCaAddresses(unittest.TestCase):
    def test_ontario_district(self):
        self.assertEqual(FCA.read_address("Unorganized North Sudbury, Sudbury District, Northeastern Ontario, Ontario, Canada",
                                          "Northeastern Ontario"), ("ON", "Sudbury District"))
        self.assertEqual(FCA.read_address("South Nipissing District, ON", "Ontario"), ("ON", "Nipissing District"))
        self.assertEqual(FCA.read_address("Webster's Lane, Georgian Bay Township, District Municipality of Muskoka, "
                                          "Muskoka District, Central Ontario, Ontario, Canada", "Central Ontario"),
                         ("ON", "Muskoka District"))
        self.assertEqual(FCA.read_address("Black Creek Road, North Algona Wilberforce, Renfrew County, Eastern Ontario, "
                                          "Ontario, K8A 6W4, Canada", "Eastern Ontario"), ("ON", "Renfrew County"))

    def test_bc_regional_districts_and_sk_units(self):
        self.assertEqual(FCA.read_address("Central Kootenay, BC V0G 1B0", "British Columbia"),
                         ("BC", "Regional District of Central Kootenay"))
        self.assertEqual(FCA.read_address("Cariboo D, Cariboo, BC, Canada", "British Columbia"),
                         ("BC", "Cariboo Regional District"))
        self.assertEqual(FCA.read_address("Division No. 18, Unorganized, SK, Canada", "Saskatchewan"), ("SK", "Division No. 18"))
        self.assertEqual(FCA.read_address("Unorganized Division No. 18, Saskatchewan, Canada", "Unorganized Division No. 18"),
                         ("SK", "Division No. 18"))
        self.assertEqual(FCA.read_address("Meadow Lake No. 588, SK S0M, Canada", "Saskatchewan"), ("SK", "Meadow Lake No. 588"))

    def test_other_province_address_gives_no_unit(self):
        # Maria Fire Tower: the index files it under Ontario; its reverse-geocoded address is in Quebec
        self.assertEqual(FCA.read_address("Les Lacs-du-Témiscamingue, Témiscamingue, Abitibi-Témiscamingue, Quebec, Canada",
                                          "Ontario"), ("ON", None))

    def test_district_office_pins_are_found(self):
        towers = [{"id": i, "title": f"{n} Fire Tower", "lat": 44.4747, "lng": -77.3102, "address": "Tweed, ON, Canada"}
                  for i, n in enumerate(["Olden", "Marmora", "Limerick"], 1)]
        towers += [{"id": 9, "title": "Moon River Fire Tower", "lat": 45.0864, "lng": -79.8317, "address": "Parry Sound, ON"},
                   {"id": 10, "title": "Moon River Fire Tower", "lat": 45.0864, "lng": -79.8317, "address": "Parry Sound, ON"},
                   {"id": 11, "title": "Big Crow Lake Fire Tower", "lat": 45.82152, "lng": -78.43343, "address": "x"},
                   {"id": 12, "title": "Freswick Fire Lookout", "lat": 45.82152, "lng": -78.43561, "address": "y"}]
        shared = FCA.shared_points(towers)
        self.assertEqual(set(shared), {1, 2, 3})
        self.assertEqual(shared[1]["name"], "Tweed")

    def test_page_facts(self):
        page = ("<table><tr><th>Elevation</th><td>459 m (1506 ft)</td></tr><tr><th>Tower Type</th><td>Steel Tower</td></tr>"
                "<tr><th>Year Built</th><td>N/A</td></tr></table>")
        facts = FCA.page_facts(page)
        self.assertEqual(facts, {"Elevation": "459 m (1506 ft)", "Tower Type": "Steel Tower"})
        self.assertEqual(FCA.elevation_m(facts["Elevation"]), 459.0)


if __name__ == "__main__":
    unittest.main()
