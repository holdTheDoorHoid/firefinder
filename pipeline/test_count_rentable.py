"""Tests for count_rentable.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import count_rentable as C


class CountRentable(unittest.TestCase):
    def write(self, tmp: Path, records: list[dict]) -> Path:
        path = tmp / "ridb.json"
        path.write_text(json.dumps({"source": "ridb", "records": records}), encoding="utf-8")
        return path

    def test_counts_only_truthy_rental(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(Path(tmp), [
                {"key": "a", "rental": {"available": True}},
                {"key": "b", "rental": None},
                {"key": "c", "rental": {"available": False}},  # still a rental listing
                {"key": "d"},
            ])
            self.assertEqual(C.count_rentable(path), 2)

    def test_missing_file_counts_as_zero(self):
        self.assertEqual(C.count_rentable(Path("/nonexistent/ridb.json")), 0)

    def test_malformed_records_count_as_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ridb.json"
            path.write_text(json.dumps({"source": "ridb"}), encoding="utf-8")  # no "records"
            self.assertEqual(C.count_rentable(path), 0)


if __name__ == "__main__":
    unittest.main()
