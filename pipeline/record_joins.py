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

# Where a joined tower shows its position from, when a human has checked which source is right: a record
# key of the tower -> the key of the record whose position it shows. The default is merge.py's
# precedence with corroboration (DESIGN.md 3.5), which cannot tell that the top-ranked source is the one
# with the slip.
LOCATION_PICKS: dict[str, str] = {}
