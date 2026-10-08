"""Tests for how merge.py handles FFLA's other list views and its rentals list.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import unittest

import merge as M
import validate as V
from test_merge import Workspace, rec

RIDB_RENTAL = {"available": True, "provider": "recreation.gov", "url": "https://www.recreation.gov/camping/campgrounds/234447",
               "ridb_facility_id": "234447", "season": "June to October", "max_occupancy": 4}


def rental_rec(name: str, region: str, url: str, **kw) -> dict:
    """A record of the ffla_rentals source (no position), as regional/ffla_rentals.py writes it."""
    fid = url.rstrip("/").rsplit("/", 1)[-1] if "recreation.gov" in url else None
    rental = {"available": True, "provider": "recreation.gov" if fid else "Airbnb", "url": url, "ridb_facility_id": fid,
              "manager": kw.pop("manager", None), "status_note": kw.pop("status_note", None), "checked": "2026-10-08"}
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    r = rec("ffla_rentals", f"{region.lower()}:{slug}", name, kw.pop("lat", None), kw.pop("lon", None), region,
            kind=kw.pop("kind", "unknown"), status=kw.pop("status", "unknown"), rental=rental, **kw)
    r["url"] = "https://firelookout.org/resources/rentals/"
    r["links"] = [{"label": f"Book or read about {name}", "url": url, "kind": "rental"}]
    return r


class BorderPointers(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def pointer(self, name: str, region: str, see: str, **kw) -> dict:
        return rec("ffla", f"{region}:{name}", name, None, None, region, extra={"section": f"(Border – see {see})"}, **kw)

    def test_a_pointer_without_a_position_joins_the_lookout_in_the_other_states_list(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "id:bloom", "Bloom Peak", 47.95, -115.9, "ID"),
                              self.pointer("Bloom Peak", "MT", "Idaho")]})
        t = self.ws.tower_with_key("ffla:id:bloom")
        self.assertEqual(sorted(s["key"] for s in t["sources"]), ["ffla:MT:Bloom Peak", "ffla:id:bloom"])
        self.assertEqual(t["region"], "ID")

    def test_without_the_border_section_a_position_less_row_in_another_state_stays_unplaced(self) -> None:
        plain = rec("ffla", "MT:Bloom Peak", "Bloom Peak", None, None, "MT", extra={"section": "Lookout Structures"})
        rep = self.ws.run({"ffla": [rec("ffla", "id:bloom", "Bloom Peak", 47.95, -115.9, "ID"), plain]})
        self.assertEqual([u["key"] for u in rep["unplaced"]], ["ffla:MT:Bloom Peak"])

    def test_a_pointer_that_names_two_lookouts_is_left_unplaced(self) -> None:
        rep = self.ws.run({"ffla": [rec("ffla", "id:a", "Bald Mountain", 47.9, -115.9, "ID"),
                                    rec("ffla", "id:b", "Bald Mountain", 47.5, -115.5, "ID"),
                                    self.pointer("Bald Mountain", "MT", "Idaho")]})
        self.assertEqual([u["key"] for u in rep["unplaced"]], ["ffla:MT:Bald Mountain"])

    def test_border_lookouts_listed_in_both_states_a_few_hundred_metres_apart_are_one_tower(self) -> None:
        a = rec("ffla", "md:interstate", "Interstate", 38.80156, -75.72056, "MD", extra={"section": "Lookout Structures"})
        b = rec("ffla", "de:interstate", "Interstate", 38.79917, -75.72111, "DE", extra={"section": "(Border – see Maryland)"})
        self.ws.run({"ffla": [a, b]})
        t = self.ws.tower_with_key("ffla:md:interstate")
        self.assertEqual(len(t["sources"]), 2)
        # the home state's row gives the position, not the border row that sorts first by key
        self.assertEqual((t["location"]["lat"], t["location"]["lon"]), (38.80156, -75.72056))

    def test_two_ordinary_ffla_rows_270_m_apart_are_still_two_towers(self) -> None:
        a = rec("ffla", "md:interstate", "Interstate", 38.80156, -75.72056, "MD", extra={"section": "Lookout Structures"})
        b = rec("ffla", "de:interstate", "Interstate", 38.79917, -75.72111, "DE", extra={"section": "Lookout Structures"})
        self.ws.run({"ffla": [a, b]})
        self.assertNotEqual(self.ws.tower_with_key("ffla:md:interstate")["id"], self.ws.tower_with_key("ffla:de:interstate")["id"])


class UndocumentedList(unittest.TestCase):
    SECTION = "Unknown/Undocumented – from Thornton’s “Fixed Point Fire Detection : The Lookouts”"

    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def test_a_site_only_the_undocumented_list_has_is_kept_but_hidden(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "un", "Beegum Peak", 40.4, -122.9, "CA", kind="unknown", status="unknown",
                                  extra={"section": self.SECTION})]})
        t = self.ws.tower_with_key("ffla:un")
        self.assertTrue(t["hidden"])
        self.assertIn("unknown or undocumented", t["hidden_reason"])

    def test_a_real_lookout_there_is_not_hidden_by_an_undocumented_row_beside_it(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "real", "Beegum Peak", 40.4, -122.9, "CA", extra={"section": "Lookout Structures"}),
                              rec("ffla", "un", "Beegum Peak", 40.4, -122.9, "CA", kind="unknown", status="unknown",
                                  extra={"section": self.SECTION})]})
        self.assertFalse(self.ws.tower_with_key("ffla:real")["hidden"])

    def test_another_sources_structure_keeps_it_visible(self) -> None:
        self.ws.run({"ffla": [rec("ffla", "un", "Beegum Peak", 40.4, -122.9, "CA", kind="unknown", status="unknown",
                                  extra={"section": self.SECTION})],
                     "osm": [rec("osm", "n1", "Beegum Peak Lookout", 40.4001, -122.9, "CA")]})
        self.assertFalse(self.ws.tower_with_key("ffla:un")["hidden"])


class RentalsList(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def ridb(self, key: str, name: str, lat: float, lon: float, region: str = "ID", fid: str = "234447") -> dict:
        r = rec("ridb", key, name, lat, lon, region, rental=dict(RIDB_RENTAL, ridb_facility_id=fid,
                                                                  url=f"https://www.recreation.gov/camping/campgrounds/{fid}"))
        r["key"] = f"ridb:{fid}"
        r["agency"] = "USDA Forest Service"
        return r

    def run_with(self, *rentals: dict, towers: list[dict] | None = None, ridb: list[dict] | None = None):
        sources = {"ffla": towers if towers is not None else [rec("ffla", "arid", "Arid Peak", 44.9, -114.9, "ID")],
                   "ffla_rentals": list(rentals)}
        if ridb is not None:
            sources["ridb"] = ridb
        return self.ws.run(sources)

    def test_matched_by_the_recreation_gov_facility_number_even_when_the_names_differ(self) -> None:
        r = rental_rec("Walde Lookout Cabin", "ID", "https://www.recreation.gov/camping/campgrounds/234447")
        rep = self.run_with(r, towers=[rec("ffla", "w", "Walde Mountain", 44.9, -114.9, "ID")],
                            ridb=[self.ridb("1", "Walde Lookout", 44.9, -114.9)])
        t = self.ws.tower_with_key("ffla:w")
        self.assertIn("ffla_rentals:id:walde-lookout-cabin", [s["key"] for s in t["sources"]])
        self.assertEqual(rep["matching"]["by_source"]["ffla_rentals"], {"facility": 1})
        self.assertEqual(rep["unplaced"], [])

    def test_ridb_stays_the_rental_and_gets_the_closure_note_and_manager(self) -> None:
        r = rental_rec("Arid Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/234447",
                       status_note="Maintenance Closure 2026", manager="USFS")
        self.run_with(r, ridb=[self.ridb("1", "Arid Peak Lookout", 44.9, -114.9)])
        rental = self.ws.tower_with_key("ffla:arid")["rental"]
        self.assertTrue(rental["available"])
        self.assertEqual(rental["max_occupancy"], 4)                     # RIDB's details kept
        self.assertEqual(rental["status_note"], "Maintenance Closure 2026")
        self.assertEqual(rental["status_note_from"], "ffla")
        self.assertEqual(rental["manager"], "USFS")
        self.assertNotIn("source", rental)                               # still a recreation.gov record

    def test_a_closure_note_that_goes_away_goes_away(self) -> None:
        noted = rental_rec("Arid Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/234447",
                           status_note="Maintenance Closure 2026")
        self.run_with(noted, ridb=[self.ridb("1", "Arid Peak Lookout", 44.9, -114.9)])
        self.assertEqual(self.ws.tower_with_key("ffla:arid")["rental"]["status_note"], "Maintenance Closure 2026")
        clear = rental_rec("Arid Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/234447")
        self.run_with(clear, ridb=[self.ridb("1", "Arid Peak Lookout", 44.9, -114.9)])
        self.assertNotIn("status_note", self.ws.tower_with_key("ffla:arid")["rental"])

    def test_a_rental_only_the_ffla_list_has_becomes_the_towers_rental(self) -> None:
        r = rental_rec("Thorny Mountain Fire Tower", "WV", "https://wvstateparks.com/places-to-stay/cabins/seneca-state-forest-cabins/",
                       manager="WV State Parks")
        r["rental"]["provider"] = "West Virginia State Parks"
        rep = self.run_with(r, towers=[rec("ffla", "t", "Thorny Mountain", 38.31, -79.94, "WV")])
        t = self.ws.tower_with_key("ffla:t")
        self.assertEqual({k: t["rental"][k] for k in ("available", "source", "provider", "manager", "url")}, {
            "available": True, "source": "ffla", "provider": "West Virginia State Parks", "manager": "WV State Parks",
            "url": "https://wvstateparks.com/places-to-stay/cabins/seneca-state-forest-cabins/"})
        self.assertEqual(t["rental"]["checked"], "2026-10-08")
        self.assertEqual(rep["counts"]["rentable"], 1)
        self.assertIn("FFLA lookout rentals list (firelookout.org)", [l["label"] for l in t["links"]])
        self.assertIn("https://wvstateparks.com/places-to-stay/cabins/seneca-state-forest-cabins/", [l["url"] for l in t["links"]])
        self.assertTrue(V.check(t, next(self.ws.towers.rglob("*.json")), M._vocab())[0] == [])

    def test_the_name_alone_places_a_rental_on_the_one_tower_of_that_name_in_its_state(self) -> None:
        r = rental_rec("Gordon Fire Tower Cabin", "WI", "https://www.airbnb.com/rooms/37930902")
        rep = self.run_with(r, towers=[rec("ffla", "g", "Gordon", 46.24, -91.8, "WI"), rec("ffla", "g2", "Gordon", 44.0, -90.0, "MN")])
        self.assertIn("ffla_rentals:wi:gordon-fire-tower-cabin", [s["key"] for s in self.ws.tower_with_key("ffla:g")["sources"]])
        self.assertEqual(rep["matching"]["by_source"]["ffla_rentals"], {"name": 1})

    def test_among_same_named_towers_the_one_recreation_gov_rents_wins(self) -> None:
        r = rental_rec("Bald Mountain Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/234507")
        towers = [rec("ffla", "gone", "Bald Mountain", 45.1, -115.1, "ID", status="gone"),
                  rec("ffla", "rented", "Bald Mountain", 46.1, -116.1, "ID")]
        self.run_with(r, towers=towers, ridb=[self.ridb("1", "Bald Mountain Lookout", 46.1, -116.1, fid="999")])
        self.assertIn("ffla_rentals:id:bald-mountain-lookout", [s["key"] for s in self.ws.tower_with_key("ffla:rented")["sources"]])

    def test_among_same_named_towers_one_not_known_to_be_gone_wins(self) -> None:
        r = rental_rec("Bald Mountain Lookout", "ID", "https://example.org/stay")
        towers = [rec("ffla", "gone", "Bald Mountain", 45.1, -115.1, "ID", status="gone"),
                  rec("ffla", "here", "Bald Mountain", 46.1, -116.1, "ID", status="standing")]
        self.run_with(r, towers=towers)
        self.assertIn("ffla_rentals:id:bald-mountain-lookout", [s["key"] for s in self.ws.tower_with_key("ffla:here")["sources"]])

    def test_several_equally_good_towers_leave_the_rental_unplaced_and_say_so(self) -> None:
        r = rental_rec("Bald Mountain Lookout", "ID", "https://example.org/stay")
        towers = [rec("ffla", "a", "Bald Mountain", 45.1, -115.1, "ID"), rec("ffla", "b", "Bald Mountain", 46.1, -116.1, "ID")]
        rep = self.run_with(r, towers=towers)
        self.assertEqual([(u["key"], u["reason"]) for u in rep["unplaced"]],
                         [("ffla_rentals:id:bald-mountain-lookout", "several lookouts of that name in the state")])
        self.assertEqual([x["type"] for x in rep["review"] if x["type"].startswith("ffla_rental")], ["ffla_rental_unplaced"])
        self.assertEqual(len(next(x for x in rep["review"] if x["type"] == "ffla_rental_unplaced")["towers"]), 2)

    def test_a_nearly_matching_name_is_taken_only_for_the_one_tower_recreation_gov_rents(self) -> None:
        r = rental_rec("Dominion Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/555")
        towers = [rec("ffla", "r", "Dominion Mountain", 47.9, -115.9, "ID"), rec("ffla", "x", "Dominion Mountain", 47.5, -115.5, "ID")]
        rep = self.run_with(r, towers=towers, ridb=[self.ridb("1", "Dominion Mountain Lookout", 47.9, -115.9, fid="777")])
        self.assertIn("ffla_rentals:id:dominion-peak-lookout", [s["key"] for s in self.ws.tower_with_key("ffla:r")["sources"]])
        self.assertIn("ffla_rental_loose_name_match", [x["type"] for x in rep["review"]])

    def test_an_override_wins_over_the_name_and_may_name_a_source_key(self) -> None:
        r = rental_rec("Crystal Peak Relocated Lookout", "ID", "https://www.airbnb.com/rooms/25687274", manager="private owner")
        towers = [rec("ffla", "old", "Crystal Peak", 47.14, -116.31, "ID", status="gone"),
                  rec("ffla", "moved", "Stranger Mountain (Crystal Ridge)", 47.14, -116.33, "ID")]
        saved = dict(M.FFLA_RENTAL_OVERRIDES)
        M.FFLA_RENTAL_OVERRIDES["ffla_rentals:id:crystal-peak-relocated-lookout"] = "ffla:moved"
        try:
            rep = self.run_with(r, towers=towers)
        finally:
            M.FFLA_RENTAL_OVERRIDES.clear()
            M.FFLA_RENTAL_OVERRIDES.update(saved)
        t = self.ws.tower_with_key("ffla:moved")
        self.assertIn("ffla_rentals:id:crystal-peak-relocated-lookout", [s["key"] for s in t["sources"]])
        self.assertEqual(rep["matching"]["by_source"]["ffla_rentals"], {"override": 1})

    def test_every_override_in_the_real_table_points_at_something_that_exists(self) -> None:
        for key, target in M.FFLA_RENTAL_OVERRIDES.items():
            self.assertTrue(key.startswith("ffla_rentals:"), key)
            self.assertTrue(target.startswith("us-") or ":" in target, (key, target))

    def test_a_rental_with_its_own_position_makes_a_tower_of_its_own_and_two_listings_share_it(self) -> None:
        a = rental_rec("Moon Pass Replica Lookout", "ID", "https://www.airbnb.com/rooms/1", manager="private owner",
                       lat=47.47, lon=-115.92, kind="tower", status="replica", extra={"ownership": "private"})
        b = rental_rec("Moon Pass Replica Lookout", "ID", "https://www.airbnb.com/rooms/2", manager="private owner",
                       lat=47.47, lon=-115.92, kind="tower", status="replica", extra={"ownership": "private"})
        b["key"] = "ffla_rentals:id:moon-pass-second"
        rep = self.run_with(a, b, towers=[])
        t = self.ws.tower_with_key(a["key"])
        self.assertEqual({s["key"] for s in t["sources"]}, {a["key"], b["key"]})
        self.assertEqual(t["location"]["precision"], "approximate")
        self.assertEqual(t["status"], "replica")
        self.assertEqual(t["ownership"], "private")
        self.assertEqual(t["access"]["level"], "permission")
        self.assertTrue(t["rental"]["available"])
        urls = [l["url"] for l in t["links"]]
        self.assertIn("https://www.airbnb.com/rooms/1", urls)
        self.assertIn("https://www.airbnb.com/rooms/2", urls)     # the second listing is a link, not lost
        self.assertEqual(rep["matching"]["by_source"]["ffla_rentals"], {"name": 1, "new": 1})

    def test_the_same_match_is_found_again_by_key_on_the_next_run(self) -> None:
        r = rental_rec("Gordon Fire Tower Cabin", "WI", "https://www.airbnb.com/rooms/37930902")
        tower = rec("ffla", "g", "Gordon", 46.24, -91.8, "WI")
        self.run_with(r, towers=[tower])
        # a second same-named tower appears in the state: the first run's match is not undone
        rep = self.run_with(r, towers=[tower, rec("ffla", "g3", "Gordon", 45.0, -90.0, "WI")])
        self.assertIn(r["key"], [s["key"] for s in self.ws.tower_with_key("ffla:g")["sources"]])
        self.assertEqual(rep["matching"]["by_source"]["ffla_rentals"], {"key": 1})

    def test_a_listed_rental_on_a_lookout_gone_by_the_sources_warns_without_naming_recreation_gov(self) -> None:
        r = rental_rec("North Mountain Lookout", "WA", "https://www.airbnb.com/rooms/50778329", manager="Friends of North Mountain")
        gone = rec("ffla", "n", "North Mountain", 48.3, -121.6, "WA", status="gone")
        gone["events"] = [{"year": 2026, "event": "burned", "note": None, "from": "ffla"}]
        self.run_with(r, towers=[gone])
        rental = self.ws.tower_with_key("ffla:n")["rental"]
        self.assertIs(rental["available"], False)
        self.assertEqual(rental["warning"], "FFLA reports this lookout burned in 2026, but the FFLA rentals list still lists it. "
                                            "Check with the managing agency before booking.")

    def test_a_vanished_ffla_listing_does_not_disturb_a_recreation_gov_rental(self) -> None:
        r = rental_rec("Arid Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/234447", status_note="Maintenance Closure 2026")
        self.run_with(r, ridb=[self.ridb("1", "Arid Peak Lookout", 44.9, -114.9)])
        self.ws.run({"ffla": [rec("ffla", "arid", "Arid Peak", 44.9, -114.9, "ID")], "ridb": [self.ridb("1", "Arid Peak Lookout", 44.9, -114.9)]})
        rental = self.ws.tower_with_key("ffla:arid")["rental"]
        self.assertTrue(rental["available"])
        self.assertNotIn("status_note", rental)


class RentalsReport(unittest.TestCase):
    def test_the_report_compares_the_ffla_list_with_recreation_gov(self) -> None:
        ws = Workspace()
        try:
            def ridb(fid, name, lat, lon):
                r = rec("ridb", fid, name, lat, lon, "ID", rental=dict(RIDB_RENTAL, ridb_facility_id=fid, url=f"https://www.recreation.gov/camping/campgrounds/{fid}"))
                r["key"] = f"ridb:{fid}"
                return r
            rep = ws.run({
                "ffla": [rec("ffla", "a", "Arid Peak", 44.9, -114.9, "ID"), rec("ffla", "u", "Unlisted Peak", 44.5, -114.5, "ID"),
                         rec("ffla", "t", "Thorny Mountain", 38.31, -79.94, "WV")],
                "ridb": [ridb("111", "Arid Peak Lookout", 44.9, -114.9), ridb("222", "Unlisted Peak Lookout", 44.5, -114.5)],
                "ffla_rentals": [rental_rec("Arid Peak Lookout", "ID", "https://www.recreation.gov/camping/campgrounds/111", status_note="Maintenance Closure 2026"),
                                 rental_rec("Thorny Mountain Fire Tower", "WV", "https://wvstateparks.com/x"),
                                 rental_rec("Nowhere Peak", "ID", "https://example.org/y")]})
            fr = rep["ffla_rentals"]
            self.assertEqual((fr["listed"], fr["placed"]), (3, 2))
            self.assertEqual(fr["placed_by"], {"facility": 1, "name": 1})
            self.assertEqual([u["key"] for u in fr["unplaced"]], ["ffla_rentals:id:nowhere-peak"])
            self.assertEqual([x["name"] for x in fr["listed_by_ffla_not_in_recreation_gov_data"]], ["Thorny Mountain Fire Tower"])
            self.assertEqual([x["note"] for x in fr["with_closure_note"]], ["Maintenance Closure 2026"])
            self.assertEqual([x["name"] for x in fr["rentable_but_not_listed_by_ffla"]], ["Unlisted Peak Lookout"])
        finally:
            ws.close()

    def test_no_report_section_without_the_extract(self) -> None:
        ws = Workspace()
        try:
            self.assertIsNone(ws.run({"ffla": [rec("ffla", "a", "Arid Peak", 44.9, -114.9, "ID")]})["ffla_rentals"])
        finally:
            ws.close()


class RecordJoins(unittest.TestCase):
    """RECORD_JOINS pins a record to a tower that position and name cannot be trusted to find: the
    recreation.gov "Post Creek Guard Station" (234404) is NHLR's "Post Creek Fireman-Lookout House",
    779 m from the registered position and sharing no name beyond "Post Creek"."""

    def setUp(self) -> None:
        self.ws = Workspace()
        self.saved = dict(M.RECORD_JOINS)
        M.RECORD_JOINS.clear()
        self.nhlr = rec("nhlr", "US 1363", "Post Creek Fireman-Lookout House", 40.235595, -122.925628, "CA", kind="ground")
        self.ridb = rec("ridb", "234404", "POST CREEK GUARD STATION", 40.23333, -122.91694, "CA",
                        rental=dict(RIDB_RENTAL, ridb_facility_id="234404",
                                    url="https://www.recreation.gov/camping/campgrounds/234404"))

    def tearDown(self) -> None:
        M.RECORD_JOINS.clear()
        M.RECORD_JOINS.update(self.saved)
        self.ws.close()

    def test_without_a_pin_the_far_pin_with_a_different_name_starts_a_second_tower(self) -> None:
        self.ws.run({"nhlr": [self.nhlr], "ridb": [self.ridb]})
        self.assertNotEqual(self.ws.tower_with_key("nhlr:US 1363")["id"], self.ws.tower_with_key("ridb:234404")["id"])

    def test_a_pinned_record_joins_the_tower_holding_the_named_record(self) -> None:
        M.RECORD_JOINS["ridb:234404"] = "nhlr:US 1363"
        rep = self.ws.run({"nhlr": [self.nhlr], "ridb": [self.ridb]})
        t = self.ws.tower_with_key("nhlr:US 1363")
        self.assertEqual({s["key"] for s in t["sources"]}, {"nhlr:US 1363", "ridb:234404"})
        self.assertEqual(len(self.ws.towers_by_id()), 1)
        self.assertEqual(t["rental"]["ridb_facility_id"], "234404")
        self.assertEqual(rep["matching"]["by_source"]["ridb"], {"override": 1})

    def test_the_pin_also_takes_a_tower_id_and_survives_a_second_run(self) -> None:
        self.ws.run({"nhlr": [self.nhlr]})
        tower_id = self.ws.tower_with_key("nhlr:US 1363")["id"]
        M.RECORD_JOINS["ridb:234404"] = tower_id
        self.ws.run({"nhlr": [self.nhlr], "ridb": [self.ridb]})
        self.assertEqual({s["key"] for s in self.ws.towers_by_id()[tower_id]["sources"]}, {"nhlr:US 1363", "ridb:234404"})
        rep = self.ws.run()      # the tower file now remembers the key
        self.assertEqual(len(self.ws.towers_by_id()), 1)
        self.assertEqual(rep["matching"]["by_source"]["ridb"], {"key": 1})

    def test_a_pin_to_a_tower_that_does_not_exist_falls_back_to_matching_and_is_reported(self) -> None:
        M.RECORD_JOINS["ridb:234404"] = "nhlr:US 9999"
        rep = self.ws.run({"nhlr": [self.nhlr], "ridb": [self.ridb]})
        self.assertEqual(len(self.ws.towers_by_id()), 2)
        self.assertIn({"type": "record_join_unknown_tower", "key": "ridb:234404", "target": "nhlr:US 9999"}, rep["review"])

    def test_every_pin_in_the_real_table_names_a_record_and_a_tower(self) -> None:
        for key, target in self.saved.items():
            self.assertRegex(key, r"^[a-z_]+:\S+")
            self.assertTrue(target.startswith("us-") or ":" in target, (key, target))


class VanishedListing(unittest.TestCase):
    def test_a_rental_only_the_ffla_list_had_is_kept_with_a_warning_when_the_list_drops_it(self) -> None:
        ws = Workspace()
        try:
            r = rental_rec("Thorny Mountain Fire Tower", "WV", "https://wvstateparks.com/x")
            tower = rec("ffla", "t", "Thorny Mountain", 38.31, -79.94, "WV")
            ws.run({"ffla": [tower], "ffla_rentals": [r]})
            self.assertTrue(ws.tower_with_key("ffla:t")["rental"]["available"])
            # a run that never read the FFLA list at all must not mistake that for every rental having gone
            ws.run({"ffla": [tower]})
            skipped = ws.tower_with_key("ffla:t")["rental"]
            self.assertIs(skipped["available"], True)
            self.assertNotIn("warning", skipped)
            # the list was read and no longer has it
            ws.run({"ffla": [tower], "ffla_rentals": [rental_rec("Other Peak", "WV", "https://example.org/z", lat=38.9, lon=-79.9)]})
            after = ws.tower_with_key("ffla:t")["rental"]
            self.assertIs(after["available"], False)
            self.assertEqual(after["url"], "https://wvstateparks.com/x")        # kept
            self.assertIn("no longer finds it there", after["warning"])
        finally:
            ws.close()


class ValidatesRentals(unittest.TestCase):
    def test_the_new_rental_fields_are_checked(self) -> None:
        ws = Workspace()
        try:
            ws.run({"ffla": [rec("ffla", "a", "Gold Hill", 45.0, -116.0)]})
            path = next(ws.towers.rglob("*.json"))
            import json
            t = json.loads(path.read_text())
            vocab = M._vocab()
            ok = dict(t, rental={"available": True, "source": "ffla", "provider": "Airbnb", "url": "https://x", "manager": "private owner",
                                 "status_note": "Maintenance Closure 2026", "status_note_from": "ffla"})
            self.assertEqual(V.check(ok, path, vocab)[0], [])
            for field, value in (("status_note", 3), ("manager", ""), ("source", "ridb")):
                bad = dict(t, rental=dict(ok["rental"], **{field: value}))
                self.assertTrue(any(f"rental.{field}" in e for e in V.check(bad, path, vocab)[0]), field)
        finally:
            ws.close()


if __name__ == "__main__":
    unittest.main()
