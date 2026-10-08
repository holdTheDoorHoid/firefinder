"""Tests for _common.py, common.py and regional/_common.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import importlib.util
import os
import tempfile
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


def load_registers_common():
    """Loads pipeline/common.py (the data-registers fetchers' helpers) the same isolated way.
    No other module shares its bare name, but fetch_registers.py, fetch_ffla.py and
    mirror_photos.py all `from common import RAW_ROOT, ...`, and test_merge.py's RemovedField
    loads fetch_registers.py in this same test process. A plain `import common` here would
    either return a copy cached before the test set FIREFINDER_RAW_ROOT (so the test checks
    nothing) or cache one built with the test's override for every later importer."""
    spec = importlib.util.spec_from_file_location(
        "firefinder_registers_common_under_test", Path(__file__).parent / "common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_regional_common():
    """Loads pipeline/regional/_common.py (the regional fetchers' helpers) the same isolated way:
    it shares the bare name `_common` with pipeline/_common.py, which is why it is never imported
    by that name here."""
    spec = importlib.util.spec_from_file_location(
        "firefinder_regional_common_under_test", Path(__file__).parent / "regional" / "_common.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RawRoot(unittest.TestCase):
    """RAW_ROOT defaults to the shared lab machine's path, but a CI runner has no
    /home/hoid -- FIREFINDER_RAW_ROOT lets .github/workflows/refresh-rentals.yml point it
    somewhere real instead."""

    def setUp(self):
        self._saved = os.environ.get("FIREFINDER_RAW_ROOT")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("FIREFINDER_RAW_ROOT", None)
        else:
            os.environ["FIREFINDER_RAW_ROOT"] = self._saved

    def test_defaults_to_the_lab_path(self):
        os.environ.pop("FIREFINDER_RAW_ROOT", None)
        self.assertEqual(str(load_common().RAW_ROOT), "/home/hoid/Desktop/firefinder/data/raw")

    def test_env_var_overrides_it(self):
        os.environ["FIREFINDER_RAW_ROOT"] = "/tmp/firefinder-raw-test"
        self.assertEqual(str(load_common().RAW_ROOT), "/tmp/firefinder-raw-test")


class RegistersRawRoot(RawRoot):
    """pipeline/common.py's RAW_ROOT honours the same override, so a future NHLR/FFLOS or FFLA
    refresh workflow can run fetch_registers.py / fetch_ffla.py on a runner the same way."""

    def test_defaults_to_the_lab_path(self):
        os.environ.pop("FIREFINDER_RAW_ROOT", None)
        self.assertEqual(str(load_registers_common().RAW_ROOT), "/home/hoid/Desktop/firefinder/data/raw")

    def test_env_var_overrides_it(self):
        os.environ["FIREFINDER_RAW_ROOT"] = "/tmp/firefinder-raw-test"
        self.assertEqual(str(load_registers_common().RAW_ROOT), "/tmp/firefinder-raw-test")


class RegionalRawRoot(RawRoot):
    """pipeline/regional/_common.py honours the override too, so the weekly rentals refresh can
    re-read FFLA's rentals page (regional/ffla_rentals.py) on a runner with no /home/hoid."""

    def test_defaults_to_the_lab_path(self):
        os.environ.pop("FIREFINDER_RAW_ROOT", None)
        self.assertEqual(str(load_regional_common().RAW_ROOT), "/home/hoid/Desktop/firefinder/data/raw")

    def test_env_var_overrides_it(self):
        os.environ["FIREFINDER_RAW_ROOT"] = "/tmp/firefinder-raw-test"
        self.assertEqual(str(load_regional_common().RAW_ROOT), "/tmp/firefinder-raw-test")

    def test_an_empty_value_falls_back_to_the_lab_path(self):
        os.environ["FIREFINDER_RAW_ROOT"] = ""
        self.assertEqual(str(load_regional_common().RAW_ROOT), "/home/hoid/Desktop/firefinder/data/raw")

    def test_cache_path_follows_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["FIREFINDER_RAW_ROOT"] = tmp
            got = load_regional_common().cache_path("ffla_rentals", "firelookout.org", "index.html")
            self.assertEqual(str(got), f"{tmp}/ffla_rentals/firelookout.org/index.html")


if __name__ == "__main__":
    unittest.main()
