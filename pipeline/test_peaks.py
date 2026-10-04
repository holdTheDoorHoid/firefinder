"""Tests for the GNIS summits extract and its website chunks.
Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import build_peaks
import build_site_data as bsd
import fetch_peaks
import merge

HEADER = (
    "feature_id|feature_name|feature_class|state_name|state_numeric|county_name|county_numeric|map_name|"
    "date_created|date_edited|bgn_type|bgn_authority|bgn_date|prim_lat_dms|prim_long_dms|prim_lat_dec|"
    "prim_long_dec|source_lat_dms|source_long_dms|source_lat_dec|source_long_dec"
)


def row(fid, name, cls, state, lat, lon) -> str:
    return f"{fid}|{name}|{cls}|{state}|41|Lane|039|Map|01/01/1980|01/01/2020||||0N|0W|{lat}|{lon}|||0.0|0.0"


class ParseTest(unittest.TestCase):
    def test_keeps_named_summits_with_coordinates(self):
        text = "\n".join(
            [
                HEADER,
                row(1141004, "Diamond Peak", "Summit", "Oregon", "43.5205801", "-122.1494768"),
                row(2, "Camp Creek", "Stream", "Oregon", "43.1", "-122.1"),
                row(3, "Old Baldy (historical)", "Summit", "Oregon", "43.2", "-122.2"),
                row(4, "Nowhere Hill", "Summit", "Oregon", "0", "0"),
                row(5, "Mauna Kea", "Summit", "Hawaii", "19.8207", "-155.4681"),
            ]
        )
        rows = fetch_peaks.parse_rows(io.StringIO(text))
        self.assertEqual(rows, [[1141004, "Diamond Peak", 43.52058, -122.14948, "OR"], [5, "Mauna Kea", 19.8207, -155.4681, "HI"]])


class ChunkTest(unittest.TestCase):
    def test_cells_are_one_degree_from_the_south_west_corner(self):
        self.assertEqual(build_peaks.cell_of(43.52, -122.15), "43_-123")
        self.assertEqual(build_peaks.cell_of(-0.5, 0.5), "-1_0")

    def test_build_writes_index_and_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "peaks.json"
            out = Path(tmp) / "peaks"
            fetch_peaks.write([[1, "A Peak", 43.5, -122.1, "OR"], [2, "B Peak", 43.9, -122.9, "OR"], [3, "C Peak", 44.1, -122.1, "OR"]], src, "2026-10-04")
            index = build_peaks.build(src, out)
            self.assertEqual(index["cells"], ["43_-123", "44_-123"])
            self.assertEqual(index["count"], 3)
            chunk = json.loads((out / "43_-123.json").read_text())
            self.assertEqual(chunk, [["A Peak", 43.5, -122.1, 1], ["B Peak", 43.9, -122.9, 2]])


class NotALookoutSourceTest(unittest.TestCase):
    """The peaks extract lives in data/sources but must never become lookouts or a lookout source."""

    def test_merge_and_site_data_skip_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            fetch_peaks.write([[1, "A Peak", 43.5, -122.1, "OR"]], d / "peaks_gnis.json", "2026-10-04")
            headers, records = merge.load_sources(d, log=lambda *_: None)
            self.assertEqual(headers, {})
            self.assertEqual(records, {})
            self.assertEqual(bsd.load_source_headers(d, bsd.Log(quiet=True)), {})


if __name__ == "__main__":
    unittest.main()
