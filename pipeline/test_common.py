"""Tests for _common.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


def load_common():
    """Loads pipeline/_common.py under a name that never touches sys.modules["_common"] --
    several fetchers (pipeline/fetch_*.py, pipeline/regional/*.py) do their own
    sys.path.insert(0, ...) + `import _common as c` trick, each expecting to resolve to
    their OWN directory's _common.py; binding the bare name here would shadow that for the
    rest of this test process (see test_merge.py's PackedDMS test, which loads
    regional/fire_lookouts_org.py the same isolated way for the same reason)."""
    spec = importlib.util.spec_from_file_location(
        "firefinder_pipeline_common_under_test", Path(__file__).parent / "_common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RawRoot(unittest.TestCase):
    """RAW_ROOT defaults to the shared lab machine's path, but a CI runner has no
    /home/hoid -- FIREFINDER_RAW_ROOT lets .github/workflows/refresh-rentals.yml point it
    somewhere real instead."""

    def tearDown(self):
        os.environ.pop("FIREFINDER_RAW_ROOT", None)

    def test_defaults_to_the_lab_path(self):
        os.environ.pop("FIREFINDER_RAW_ROOT", None)
        self.assertEqual(str(load_common().RAW_ROOT), "/home/hoid/Desktop/firefinder/data/raw")

    def test_env_var_overrides_it(self):
        os.environ["FIREFINDER_RAW_ROOT"] = "/tmp/firefinder-raw-test"
        self.assertEqual(str(load_common().RAW_ROOT), "/tmp/firefinder-raw-test")


if __name__ == "__main__":
    unittest.main()
