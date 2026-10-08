"""Tests for fetch_ridb.py's choice of facilities. The 572 MB RIDB export is never read here: only
the explicit include list and the function that applies it are exercised.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_fetch_ridb():
    """fetch_ridb.py does `sys.path.insert(0, pipeline/); import _common as c`, expecting
    pipeline/_common.py (the regional fetchers expect their own `_common`), and creates a cache
    folder under RAW_ROOT as soon as it is imported. So load it with a throw-away
    FIREFINDER_RAW_ROOT (a CI runner has no /home/hoid) and without leaving a `_common` behind in
    sys.modules for the next test."""
    saved_module = sys.modules.pop("_common", None)
    saved_env = os.environ.get("FIREFINDER_RAW_ROOT")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FIREFINDER_RAW_ROOT"] = tmp
            spec = importlib.util.spec_from_file_location("firefinder_fetch_ridb_under_test", HERE / "fetch_ridb.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        sys.modules.pop("_common", None)
        if saved_module is not None:
            sys.modules["_common"] = saved_module
        if saved_env is None:
            os.environ.pop("FIREFINDER_RAW_ROOT", None)
        else:
            os.environ["FIREFINDER_RAW_ROOT"] = saved_env


R = load_fetch_ridb()

# FFLA's lookout rentals booked on recreation.gov that RIDB's names hide from the name pattern
# (2026-10-08): Post Creek, Mt. Baldy-Buckhorn Ridge, Bishop Mountain, Gird Point, Strawberry,
# Tamarack and Timber Butte.
FFLA_LISTED_BUT_UNNAMED = ["234404", "234432", "234304", "234281", "272173", "234138", "233133"]


class SelectIncludeIds(unittest.TestCase):
    def test_name_matches_and_by_hand_includes_are_kept_and_false_positives_dropped(self) -> None:
        got = R.select_include_ids({"1", "2"}, extra_include={"3": "by hand"}, name_match_rejects={"2": "not a lookout"})
        self.assertEqual(got, {"1", "3"})

    def test_a_by_hand_include_needs_no_name_match(self) -> None:
        self.assertEqual(R.select_include_ids(set(), extra_include={"234404": "why"}, name_match_rejects={}), {"234404"})

    def test_a_false_positive_is_dropped_even_when_also_listed_by_hand(self) -> None:
        # the tests below forbid the overlap in the real tables; this is what the function does if it happens
        self.assertEqual(R.select_include_ids({"9"}, extra_include={"9": "x"}, name_match_rejects={"9": "y"}), set())

    def test_the_real_tables_include_the_ffla_listed_rentals_and_spyglass(self) -> None:
        got = R.select_include_ids(set())
        for fid in FFLA_LISTED_BUT_UNNAMED + ["10007160"]:
            self.assertIn(fid, got)

    def test_the_real_false_positives_stay_out_even_if_their_names_match(self) -> None:
        got = R.select_include_ids(set(R.NAME_MATCH_REJECTS))
        self.assertFalse(got & set(R.NAME_MATCH_REJECTS))


class ExtraIncludeTable(unittest.TestCase):
    def test_every_entry_is_a_facility_id_with_a_reason(self) -> None:
        for fid, reason in R.EXTRA_INCLUDE.items():
            self.assertRegex(fid, r"^\d+$")
            self.assertGreater(len(reason.strip()), 20, fid)

    def test_no_entry_is_also_rejected(self) -> None:
        self.assertFalse(set(R.EXTRA_INCLUDE) & set(R.NAME_MATCH_REJECTS))
        self.assertFalse(set(R.EXTRA_INCLUDE) & set(R.ACTIVITY_ONLY_REJECTS))

    def test_the_committed_exclusion_list_does_not_still_list_an_included_facility(self) -> None:
        # Post Creek and Mt. Baldy were logged there as "no lookout signal" before they were included
        excluded = json.loads((HERE.parent / "data" / "sources" / "ridb_excluded.json").read_text(encoding="utf-8"))
        listed = {e["facility_id"] for e in excluded["excluded"]}
        self.assertFalse(listed & set(R.EXTRA_INCLUDE))


if __name__ == "__main__":
    unittest.main()
