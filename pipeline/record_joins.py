"""Human decisions that source records are one lookout: RECORD_JOINS, and LOCATION_PICKS.

RECORD_JOINS maps a source record's key to the lookout it belongs to: a tower id (permanent) or the key
of any record that tower holds (that form also works in a run from scratch). merge.py joins the record
there before it tries its key memory, the register number or the position, even if an earlier run put it
in a tower of its own. A tower all of whose records are sent elsewhere this way is retired: its file
stays (ids never change), hidden, with `merged_into` naming the tower that took its records, and the
site sends its old address to the new one (DESIGN.md 3.5, "Retired towers").

Records are matched source by source in merge.SOURCE_ORDER, so a key target must belong to a source that
is matched before the record that joins it (NHLR, FFLOS, FFLA, tnlandforms ... OSM, the western weebly
sites); a tower id has no such limit. One source's own two records are never joined here: a source that
lists two lookouts keeps them two (DESIGN.md 3.5).

2026-10-08 (dedupe-review): the groups after the first two are the pairs of separate towers the merge
report listed as possible duplicates (the same name 1.5 to 10 km apart, or different names within 350 m)
that the sources' own evidence settles. The evidence for every pair, joined or left apart, is in
docs/sources/dedupe_review_2026-10.md.
"""

from __future__ import annotations

RECORD_JOINS: dict[str, str] = {}


def _join(target: str, *keys: str) -> None:
    for key in keys:
        assert key not in RECORD_JOINS, key
        RECORD_JOINS[key] = target


# The recreation.gov rental "POST CREEK GUARD STATION" (234404) is the lookout NHLR registers as
# "Post Creek Fireman-Lookout House" (the FFLA lists it as "Post Creek Lookout"): a 1934 CCC
# cabin built for fire watching. The names share no words past "Post Creek" and RIDB's pin is
# 779 m from the registered position, outside the 400 m a partial name match may span, so
# without this it would start a second, permanent tower for the same building.
_join("nhlr:US 1363", "ridb:234404")
# "MT. BALDY-BUCKHORN RIDGE" (234432) is the Baldy Mountain Lookout in the Kootenai NF (NHLR
# 1512, FFLA "Mt. Baldy Lookout"). Its pin is 370 m from the registered one, inside the 400 m
# partial-name limit by 30 m; pinned so a small shift in RIDB's coordinates cannot start a
# duplicate tower.
_join("nhlr:US 1512", "ridb:234432")

# ---- Different names, under 350 m ----
# us-ma-mount-watatic into us-ma-ashburnham (clear, 191 m)
# FFLOS US 2 files its "Ashburnham Tower Site" under the area Mount Watatic; the other record is the
# burned-down tower on Mount Watatic near Ashburnham, 191 m away. Same tower, two names.
_join("fflos:US 2", "eastern_us_lookouts:ma:mount-watatic")
# us-ma-steerage-rock into us-ma-brimfield (clear, 202 m)
# NHLR US 1018 and FFLOS US 3 both name Steerage Rock as the area of the Brimfield tower; the
# eastern-weebly "Steerage Rock" tower (near Brimfield) is 202 m from the NHLR position.
_join("nhlr:US 1018", "eastern_us_lookouts:ma:steerage-rock")
# us-ma-captains-hill into us-ma-duxbury (clear, 131 m)
# FFLOS US 26 "Duxbury Tower Site" gives the area as Captains Hill; the eastern-weebly "Captain's
# Hill" tower (near Duxbury) is 131 m away.
_join("fflos:US 26", "eastern_us_lookouts:ma:captains-hill")
# us-ma-mount-toby into us-ma-sunderland (clear, 314 m)
# NHLR US 626 "Sunderland Fire Tower" stands in Mt. Toby State Reservation (1951 steel tower); the
# Wikidata item "Mount Toby Fire Tower" is 314 m away. No source lists a second tower on Mount Toby.
_join("nhlr:US 626", "wikidata:Q107454486")
# us-ma-west-tisbury into us-ma-vineyard (clear, 336 m)
# NHLR US 627 "Vineyard Fire Tower" is in the town of West Tisbury; OSM's "West Tisbury Fire Tower"
# (with the eastern-weebly "Airfield Hill") is 336 m away. No source lists a second tower on
# Martha's Vineyard.
_join("nhlr:US 627", "eastern_us_lookouts:ma:airfield-hill", "osm:node/12215345774")
# us-ms-gore-springs into us-ms-kincaid (clear, 106 m)
# The eastern-weebly "Gore Springs" tower is 106 m from NHLR US 1685 "Kincaid Lookout Tower", same
# county; the matcher's same-spot rule stops at 100 m. The weebly site names towers for the nearest
# town, NHLR for the tower.
_join("nhlr:US 1685", "eastern_us_lookouts:ms:gore-springs")
# us-nc-glenns-mountain into us-nc-tirzah (clear, 117 m)
# GNIS Glenns Mountain (summit, Person County) is 6 m from the OSM tower and 115 m from tnlandforms'
# "Tirzah" pin (Tirzah is the community, 2.2 km away). One tower on the summit, named two ways.
_join("tnlandforms:nc:nct182", "osm:way/1472495142")

# ---- Same name, 1.5-10 km apart ----
# us-az-horsethief into us-az-horsethief-2 (clear, 4625 m)
# OSM's tower carries GNIS feature 38521 "Horsethief Lookout Tower" (Crown King quad) at 2,041 m
# (6,700 ft), near Horsethief Basin; FFLA puts the lookout 2 km from that, and NHLR's own pin
# (elevation 4,334 ft) is the outlier, 4.6 km east. The Prescott NF has one Horsethief Lookout.
# NHLR's pin is likely wrong (see the location pick).
_join("nhlr:US 527", "osm:node/359278887")
# us-ca-black-butte-2 into us-ca-black-butte-shasta-trinity-national-forest (likely, 3306 m)
# FFLOS US 2008 sits on the one GNIS summit named Black Butte in Siskiyou County (0.0 km). The
# western-weebly pin (Shasta-Trinity NF, 1931 trail "to a lookout station on top of this peak") is
# 3.3 km north, at the GNIS locale of that name (0.4 km). Its PLSS (40N-2E-15) cannot be placed.
_join("fflos:US 2008", "west_us_lookouts:ca:black-butte1")
# us-ca-piute-peak into us-ca-piute (likely, 4348 m)
# One lookout on Piute Peak, Kern County (Sequoia NF: 1931 road from Bodfish "to the lookout station
# on Piute peak"). The weebly pin is on the GNIS summit; FFLA's ground-cabin pin is 4.3 km north-
# east along the range.
_join("ffla:ca:piute:35.4799:-118.3594", "west_us_lookouts:ca:piute")
# us-id-battle-creek-ridge into us-id-battle-creek (clear, 4554 m)
# The weebly entry (Idaho County, Nez Perce NF; "33N14E-10": camp 1928, L-4 cab on a 20-ft tower
# 1931, destroyed 1951) works out to 0.9 km from FFLA's Battle Creek tower and 4.9 km from its own
# map pin. Its county was read as "Gem" by mistake (a sidebar header the extractor misses).
_join("ffla:id:battle-creek:46.2107:-114.6865", "west_us_lookouts:id:battle-creek")
# us-id-black-butte-3 into us-id-black-butte-2 (clear, 8613 m)
# The weebly entry's PLSS (21N-13E-3) works out to 1.1 km from FFLA's Black Butte; the GNIS summit
# of that name in Valley County is at FFLA's pin; the weebly map pin is 8.3 km east, off its own
# PLSS. Kresek's c.1934 camp.
_join("ffla:id:black-butte:45.1813:-114.8508", "west_us_lookouts:id:black-butte")
# us-id-dennis-mountain into us-id-dennis-mountain-2 (likely, 4531 m)
# One GNIS summit named Dennis Mountain in Idaho County; idahofirelookouts.com's pin is on it (0.1
# km), FFLA's camp pin is 4.6 km south. Nothing else of the name in the state.
_join("ffla:id:dennis-mountain:45.5261:-114.9192", "idaho_fl:dennis-mountain:45.5669:-114.9198")
# us-id-elk-summit-3 into us-id-elk-summit-2 (clear, 9339 m)
# NHLR US 233 sits on the GNIS summit Elk Summit; the weebly entry's PLSS (29N-7E-1) is 1.0 km from
# it and says "1934: 100-foot Aermotor MC-40 tower", the Aermotor design firelookout.com gives. The
# weebly map pin (9.3 km east, rounded to two decimals) is wrong; the extractor read its county as
# "Gem" (a sidebar header the extractor misses).
_join("nhlr:US 233", "west_us_lookouts:id:elk-summit")
# us-id-mission-mtn into us-id-mission-mountain (likely, 4602 m)
# firelookout.com is FFLA's older map: its "Mission Mtn." pin (with idahofirelookouts.com and the
# GNIS summit, and the weebly PLSS 43N-5W-15) is 4.6 km west of FFLA's current "Mission Mountain"
# row, and the current FFLA table has no other row for it. FFLA moved its own pin and now calls it
# gone. The merge shows the corroborated summit position.
_join("ffla:id:mission-mountain:47.0668:-116.8832",
      "firelookout_com:id:mission-mtn:47.0674:-116.9440",
      "idaho_fl:mission-mountain:47.0681:-116.9437")
# us-id-napoleon-hill into us-id-napolean-hill (likely, 3388 m)
# FFLA's "Napolean Hill" (Lemhi County, 2-story cab) is on the GNIS summit Napoleon Hill, the only
# one in the state; idahofirelookouts.com's "Napoleon Hill Lookout" is the same name spelled right,
# same longitude, 3.4 km north. The weebly page (Salmon NF, 1932 first lookout built by Murdock
# McNicoll) is already on the FFLA tower.
_join("ffla:id:napolean-hill:45.3455:-114.0042", "idaho_fl:napoleon-hill-lookout:45.3760:-114.0047")
# us-id-parachute-ridge into us-id-parachute-ridge-2 (likely, 4856 m)
# The GNIS ridge Parachute Ridge (Idaho County) is at FFLA's camp pin; idahofirelookouts.com's pin
# is 4.9 km north of it. Nothing else of the name in the state.
_join("ffla:id:parachute-ridge:45.8250:-114.9186", "idaho_fl:parachute-ridge:45.8646:-114.8923")
# us-id-ramey-ridge into us-id-ramey-ridge-2 (clear, 3738 m)
# The weebly entry (Idaho County, Payette NF, "8' x 8' log cab" 1931, removed; PLSS 22N-10E-33)
# works out to 0.8 km from FFLA's Ramey Ridge ground cabin and 4.4 km from idahofirelookouts.com's
# pin, which it was joined to; the GNIS ridge point lies between them.
_join("ffla:id:ramey-ridge:45.2087:-115.2418",
      "idaho_fl:ramey-ridge-lookout:45.2412:-115.2541",
      "west_us_lookouts:id:ramey-ridge")
# us-id-spruce-divide-2 into us-id-spruce-divide (clear, 4297 m)
# The weebly entry (Bonner County, Coeur d'Alene NF, 1931 crow's nest, PLSS 54N-1E-33) works out to
# 0.2 km from FFLA's Spruce Divide crow's nest, 4.3 km from idahofirelookouts.com's pin, which it
# was joined to.
_join("ffla:id:spruce-divide:47.9851:-116.3401",
      "idaho_fl:spruce-divide:47.9684:-116.2880",
      "west_us_lookouts:id:spruce-divide")
# us-id-squaw-butte-mountain into us-id-squaw-butte (likely, 3263 m)
# idahofirelookouts.com's "Squaw Butte Mountain" is marked staffed, as is the BLM lookout NHLR US
# 1425 / FFLA list as "Squaw Butte" (1981 two-story cab, Gem County); 3.3 km apart, and the weebly
# PLSS (8N-1W-25) is 0.7 km from the NHLR pin.
_join("nhlr:US 1425", "idaho_fl:squaw-butte-mountain:44.0327:-116.4121")
# us-id-surveyors-ridge into us-id-surveyors-ridge-2 (clear, 7570 m)
# idahofirelookouts.com's "Surveyors Ridge Lookout" is the St. Joe NF rental lookout (NHLR US 276,
# recreation.gov 234395); its pin is 7.6 km west of the registered one. The weebly PLSS (42N-7E-11)
# is 0.8 km from the register.
_join("nhlr:US 276", "idaho_fl:surveyors-ridge-lookout:47.0046:-115.6321")
# us-id-walker-peak into us-id-walkers-peak (likely, 3368 m)
# The only GNIS summit of the name is Walkers Peak (Valley County), at FFLA's pin;
# idahofirelookouts.com's "Walker Peak" is the same name 3.4 km north-east.
_join("ffla:id:walkers-peak:44.6575:-115.3528", "idaho_fl:walker-peak:44.6709:-115.3146")
# us-ma-sandwich into us-ma-sandwich-2 (clear, 7856 m)
# Mass.gov's list of fire observation towers puts the Sandwich tower "on Telegraph Hill at 402 Route
# 130, within Shawme-Crowell State Forest", which is where OSM's node is (Telegraph Hill is in NHLR
# US 623's own description); NHLR's typed coordinates (41 40.667, 70 25.700) are 7.9 km south-east
# of that node. NHLR's pin is likely wrong.
_join("nhlr:US 623", "osm:node/12215345768")
# us-mn-loman-2 into us-mn-loman (clear, 1750 m)
# The central-weebly pin is the GNIS populated place Loman (0.0 km); NHLR US 1482 / FFLA put the
# 1927 tower 1.7 km east of the village. One tower in Koochiching County.
_join("nhlr:US 1482", "central_us_lookouts:mn:loman")
# us-mt-andesite into us-mt-andesite-2 (clear, 1528 m)
# firelookout.com is FFLA's older map. Its Andesite pin (with the weebly page, PLSS 6S-3E-31) is 1.5
# km from FFLA's current row: FFLA moved its own pin 28 m past the matcher's 1.5 km limit.
_join("ffla:mt:andesite:45.2646:-111.4062",
      "firelookout_com:mt:andesite:45.2731:-111.3908",
      "west_us_lookouts:mt:andesite")
# us-mt-bear-gulch-2 into us-mt-bear-gulch (likely, 3380 m)
# The weebly entry (Mineral County, Lolo NF, 1925 log cabin and crow's nest; PLSS 16N-26W-30) is a
# crow's nest like FFLA's; its PLSS is 2.7 km from the FFLA pin and 5.0 km from its own map pin,
# which sits on the GNIS valley.
_join("ffla:mt:bear-gulch:47.1177:-114.9278", "west_us_lookouts:mt:bear-gulch")
# us-mt-bull-mountain-2 into us-mt-bull-mountain (clear, 3096 m)
# The weebly entry (Jefferson County, Deerlodge NF, PLSS 4N-4W-11, "proposed lookout point" 1939)
# works out to 0.4 km from FFLA's Bull Mountain pin and 3.1 km from its own map pin (the GNIS range
# point).
_join("ffla:mt:bull-mountain:46.1122:-112.0710", "west_us_lookouts:mt:bull-mountain")
# us-mt-cable-mountain-2 into us-mt-cable-mountain (clear, 4448 m)
# The weebly entry (Deer Lodge County, 1937 lookout NE of Georgetown Lake, PLSS 5N-13W-3) works out
# to 0.6 km from FFLA's Cable Mountain tower and 4.6 km from its own map pin.
_join("ffla:mt:cable-mountain:46.2177:-113.2213", "west_us_lookouts:mt:cable-mountain")
# us-mt-condon-ranger-2 into us-mt-condon-ranger (clear, 5600 m)
# The weebly entry (Missoula County, Flathead NF, removed, PLSS 21N-17W-14) works out to 1.3 km from
# FFLA's Condon Ranger Station tower and 5.0 km from its own map pin; same exact name.
_join("ffla:mt:condon-ranger-station:47.5847:-113.7361", "west_us_lookouts:mt:condon-ranger-station")
# us-mt-government-mountain-2 into us-mt-government-mountain (likely, 4810 m)
# The only GNIS summit named Government Mountain in Montana is at FFLA's pin; the weebly page
# (Sanders County, Kootenai NF, 1930 lookout tower "on Government Peak in the Rock Creek country")
# is the same place; its PLSS is 3.0 km from FFLA's pin and 2.3 km from its own, so it does not
# choose.
_join("ffla:mt:government-mountain:48.0415:-115.7890", "west_us_lookouts:mt:government-mountain")
# us-or-illahee-rock-2 into us-or-illahee-rock (clear, 7986 m)
# The weebly entry (Umpqua NF, Douglas County; 1925 "standard lookout house ... with a cupola")
# matches the "cupola and 20' L-4 tower" that Every Lookout in Oregon lists for NHLR US 98; the only
# GNIS Illahee Rock (a pillar) is at NHLR's pin; the weebly pin is 8.0 km west of it.
_join("nhlr:US 98", "west_us_lookouts:or:illahee-rock")
# us-or-madrona-park-2 into us-or-madrona-park (clear, 9339 m)
# firelookout.com is FFLA's older map: its Madrona Park pin (NE Portland, copied by the weebly page)
# is 9.3 km from FFLA's current row, which is at Linnton, the foot of Forest Park, whose fire the
# weebly text gives as the reason the Parks Bureau built the lookout (it dates it 1952).
_join("ffla:or:madrona-park:45.6125:-122.7833",
      "firelookout_com:or:madrona-park:45.5575:-122.6926",
      "west_us_lookouts:or:madrona-park")
# us-or-mount-emily into us-or-mount-emily-lookout-site-snf (clear, 5300 m)
# FFLOS US 794 sits on the GNIS summit Mount Emily (Curry County, Siskiyou NF); the weebly page is
# the same forest and county (1917-22 lookout at the top of Mt. Emily, Brookings), its PLSS
# 40S-12W-8 is 3.0 km from the FFLOS pin. The other Mount Emily is in Union County, 600 km away.
_join("fflos:US 794", "west_us_lookouts:or:mount-emily1")
# us-or-price-peak-2 into us-or-price-peak (likely, 3693 m)
# The GNIS summit Price Peak (Benton County) is at FFLA's pin; the weebly page (Oregon Dept of
# Forestry, 1942 observation post) pins 3.7 km away and its PLSS (10S-5W-29) is 3.6 km from FFLA's
# pin, 7.1 km from its own.
_join("ffla:or:price-peak:44.6562:-123.3624", "west_us_lookouts:or:price-peak")
# us-or-shirley-gap-2 into us-or-shirley-gap (clear, 9684 m)
# The weebly entry (Umpqua NF, Douglas County, PLSS 24S-2W-32) works out to 0.6 km from FFLOS US
# 903, which Ray Kresek registered; its map pin sits on the GNIS gap of that name, 10 km away.
_join("fflos:US 903", "west_us_lookouts:or:shirley-gap")
# us-pa-strattanville-2 into us-pa-strattanville (clear, 1779 m)
# The NGS text on the weebly page puts the removed 90-ft steel tower "about 1 mile west of
# Strattanville"; that is FFLOS US 500 (steel tower), 1.8 km from the weebly pin.
_join("fflos:US 500", "eastern_us_lookouts:pa:strattenville")
# us-sc-parsons-mountain-2 into us-sc-parsons-mountain (clear, 2052 m)
# NHLR US 837 (1935, Sumter NF, Long Cane Ranger District, on the GNIS summit Parsons Mountain) and
# the weebly page (the third steel tower of the Long Cane district, 1935, "on the very top of Little
# mountain, or Parson's mountain") are one tower; weebly pin 2.0 km off.
_join("nhlr:US 837", "eastern_us_lookouts:sc:parsons-mountain")
# us-tn-fall-creek-falls into us-tn-fall-creek-falls-2 (clear, 4035 m)
# NHLR US 50 is the Fall Creek Falls Lookout Tower, Bledsoe County; Wikidata calls the NRHP-listed
# tower by the same name ("Fall Creek Falls Lookout Tower" is its alias) and puts it, with
# tnlandforms and OSM, on Bradden Knob (GNIS summit). Three sources agree; NHLR's pin is 4 km away
# at the falls.
_join("nhlr:US 50", "tnlandforms:tn:blt002", "wikidata:Q86925971", "osm:way/1094656625")
# us-tn-hornsby-2 into us-tn-hornsby (clear, 6255 m)
# NHLR US 1709 and tnlandforms 8-24 have the same longitude (88 51.997 W / 88 51.984 W) but
# latitudes 6.2 km apart; NHLR's 35 16.977 N looks like a slip for 13.977, which would put it 0.7 km
# from tnlandforms. One standing Aermotor tower at a Tennessee Division of Forestry work center.
# NHLR's pin is likely wrong.
_join("nhlr:US 1709", "tnlandforms:tn:hrt002")
# us-va-meadows-lower-henrico into us-va-meadows (clear, 2712 m)
# The weebly name "Meadows (lower henrico)" is FFLA's exact name for the NHLR US 1489 tower; its NGS
# text ("4.5 miles E of Sandston, on U.S. Highway 60", 100-ft Aermotor) fits the NHLR pin better;
# the weebly pin is 2.7 km west of it.
_join("nhlr:US 1489", "eastern_us_lookouts:va:meadows")
# us-vt-round-mountain-2 into us-vt-round-mountain (likely, 2580 m)
# The GNIS summit Round Mountain (Essex County) is at the weebly pin; FFLA's crow's nest is 2.6 km
# west. No other Round Mountain in Essex County; both say it is gone.
_join("ffla:vt:round-mountain:44.6020:-71.6620", "eastern_us_lookouts:vt:round-mountain")
# us-wa-burnt-hill-2 into us-wa-burnt-hill (clear, 7821 m)
# Both describe the 2-story 14x14 R-6 lookout house of 1942-43 in Grays Harbor County; the weebly
# pin is on the GNIS summit and its PLSS (21N-9W-7) lands within 4 km of FFLA's pin, which agrees
# with the weebly's longitude. FFLOS's own pin is the outlier, 8 km east.
_join("fflos:US 1158", "west_us_lookouts:wa:burnt-hill")
# us-wa-carbon-ridge-2 into us-wa-carbon-ridge (clear, 5018 m)
# FFLOS US 1271 (1961 DNR tower, gone by 1969) and the weebly page (1960 tower erected, removed
# 1969, PLSS 18N-7E-17) are one tower: the PLSS is 0.7 km from the FFLOS pin, the weebly pin 5.7 km.
_join("fflos:US 1271", "west_us_lookouts:wa:carbon-ridge")
# us-wa-solduc-mountain into us-wa-solduc (clear, 8463 m)
# The weebly entry's PLSS (T28N R9W sec 17, Olympic NF, a 1919 lookout house on Solduc Mountain)
# works out to 1.6 km from FFLA's Solduc pin and 8.3 km from its own map pin; one lookout of the
# name in Clallam County.
_join("ffla:wa:solduc:47.9321:-123.8807", "west_us_lookouts:wa:solduc-mountain")
# us-wa-vulcan-mountain-2 into us-wa-vulcan-mountain (likely, 4061 m)
# FFLOS US 1476 (Colville NF, Ferry County, 1933 55-ft pole tower) and the weebly page (Colville NF,
# 1915 and 1931 lookouts on Vulcan Mountain) are one lookout; the weebly pin is on the GNIS summit,
# FFLOS 4 km south-west on the mountain.
_join("fflos:US 1476", "west_us_lookouts:wa:vulcan-mountain")
# us-wy-barrett-ridge-2 into us-wy-barrett-ridge (likely, 3707 m)
# The weebly page is the 1912 lookout tower on Barrett Ridge, Medicine Bow NF; its pin is the GNIS
# ridge point, FFLA's tower pin 3.7 km north-west along the same ridge.
_join("ffla:wy:barrett-ridge:41.3266:-106.5263", "west_us_lookouts:wy:barrett-ridge")
# us-wy-deadline-ridge-castle into us-wy-deadline-ridge (clear, 4572 m)
# The weebly page records the lookout building on Deadline Ridge restored in 2015-16 by the Sublette
# County Historic Preservation Board, the cooperator in NHLR US 1520; same ridge, same county.
_join("nhlr:US 1520", "west_us_lookouts:wy:deadline-ridge")


# Where a joined tower shows its position from, when a human has checked which source is right: a record
# key of the tower -> the key of the record whose position it shows. The default is merge.py's
# precedence with corroboration (DESIGN.md 3.5), which cannot tell that the top-ranked source is the one
# with the slip.
LOCATION_PICKS: dict[str, str] = {
    # NHLR US 527 types 34 09.735 N 112 13.210 W and 4,334 ft. GNIS "Horsethief Lookout Tower" (OSM carries
    # its id, 38521) is 4.6 km west at 6,700 ft, near Horsethief Basin; FFLA's pin is 2 km from it.
    "nhlr:US 527": "osm:node/359278887",
    # NHLR US 623 types 41 40.667 N 70 25.700 W. The Mass.gov list puts the tower on Telegraph Hill at 402
    # Route 130 in Shawme-Crowell State Forest, where OSM's node is, 7.9 km north-west.
    "nhlr:US 623": "osm:node/12215345768",
    # NHLR US 1709 has tnlandforms's longitude to 0.01 minute but a latitude 6 km north; its 35 16.977 N
    # looks like a slip for 13.977.
    "nhlr:US 1709": "tnlandforms:tn:hrt002",
    # firelookout.com is FFLA's older map. FFLA has since moved these two pins (Andesite by 1.5 km, Madrona
    # Park by 9.3 km); the weebly pins match the old ones (probably copied from that map). The default
    # would keep the old pin, since another lineage "corroborates" it; FFLA's current row is shown.
    "ffla:mt:andesite:45.2646:-111.4062": "ffla:mt:andesite:45.2646:-111.4062",
    "ffla:or:madrona-park:45.6125:-122.7833": "ffla:or:madrona-park:45.6125:-122.7833",
}
