"""Smoke tests for build_site_data.py. Run: python3 -m unittest discover -s pipeline"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import build_site_data as bsd

FIXTURES = bsd.FIXTURES


def quiet() -> bsd.Log:
    return bsd.Log(quiet=True)


def tower(rid: str, **extra) -> dict:
    rec = {
        "id": rid,
        "name": rid.split("-", 2)[-1].replace("-", " ").title() + " Lookout",
        "other_names": [],
        "country": "US",
        "region": rid.split("-")[1].upper(),
        "county": None,
        "location": {"lat": 44.123456789, "lon": -121.987654321, "precision": "exact", "from": "ffla"},
        "kind": "tower",
        "status": "standing",
        "registers": [],
        "access": {"level": "public", "note": None},
        "rental": None,
        "events": [],
        "photos": [],
        "links": [],
        "sources": [{"source": "ffla", "key": "ffla:x", "fields": ["location"]}],
        "conflicts": [],
        "verification": "unverified",
        "hidden": False,
    }
    rec.update(extra)
    return rec


class BuildFromFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "data"
        cls.meta = bsd.build(
            FIXTURES / "towers",
            FIXTURES / "stories",
            FIXTURES / "photos",
            Path(cls.tmp.name) / "no-sources",
            bsd.DATA / "vocab.json",
            cls.out,
            fixtures=True,
            log=quiet(),
        )
        cls.geo = json.loads((cls.out / "towers.geojson").read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_every_visible_fixture_is_on_the_map(self) -> None:
        records = [json.loads(p.read_text()) for p in (FIXTURES / "towers").rglob("*.json")]
        visible = {r["id"] for r in records if not r.get("hidden")}
        self.assertTrue(visible, "fixtures are missing")
        self.assertEqual({f["properties"]["i"] for f in self.geo["features"]}, visible)
        self.assertEqual(self.meta["counts"]["total"], len(visible))
        self.assertEqual(self.meta["counts"]["hidden"], len(records) - len(visible))

    def test_hidden_records_are_not_published(self) -> None:
        hidden = [json.loads(p.read_text())["id"] for p in (FIXTURES / "towers").rglob("*.json") if json.loads(p.read_text()).get("hidden")]
        self.assertTrue(hidden)
        for rid in hidden:
            self.assertFalse((self.out / "t" / f"{rid}.json").exists())

    def test_geojson_is_compact_and_follows_the_contract(self) -> None:
        for f in self.geo["features"]:
            p = f["properties"]
            self.assertLessEqual(set(p), set(bsd.GEOJSON_FORMAT))
            for key in ("i", "n", "r", "k", "s", "v", "a"):
                self.assertIn(key, p)
            for key in ("rt", "rg"):
                self.assertIn(p.get(key, 1), (1,))
            for c in f["geometry"]["coordinates"]:
                self.assertEqual(c, round(c, 5))
        self.assertNotIn(b": ", (self.out / "towers.geojson").read_bytes()[:2000])

    def test_tower_files_have_the_full_record_and_story(self) -> None:
        for f in self.geo["features"]:
            rid = f["properties"]["i"]
            rec = json.loads((self.out / "t" / f"{rid}.json").read_text())
            self.assertEqual(rec["id"], rid)
        story = json.loads((self.out / "t" / "us-or-dutchmans-peak.json").read_text())["story_html"]
        self.assertIn('class="footnotes"', story)
        self.assertIn("&quot;the Dutchman&quot; &amp; still do", story)

    def test_meta_lists_sources_with_credit_lines(self) -> None:
        self.assertTrue(self.meta["fixtures"])
        by_id = {s["id"]: s for s in self.meta["sources"]}
        self.assertEqual(by_id["ridb"]["credit"], "Data source: ridb.recreation.gov")
        self.assertIn("OpenStreetMap contributors", by_id["osm"]["credit"])
        self.assertGreater(by_id["nhlr"]["towers"], 0)
        self.assertEqual(self.meta["counts"]["rentable"], sum(1 for f in self.geo["features"] if f["properties"].get("rt")))


class RecordHandling(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.towers = self.root / "towers"
        (self.towers / "or").mkdir(parents=True)
        self.out = self.root / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, rec: object) -> None:
        text = rec if isinstance(rec, str) else json.dumps(rec)
        (self.towers / "or" / name).write_text(text)

    def build(self, **kw) -> dict:
        with contextlib.redirect_stderr(io.StringIO()):  # expected warnings
            return bsd.build(self.towers, self.root / "stories", self.root / "photos", self.root / "sources", bsd.DATA / "vocab.json", self.out, log=quiet(), **kw)

    def test_bad_records_are_skipped_not_fatal(self) -> None:
        self.write("good.json", tower("us-or-good", events=[{"year": 1935, "event": "built"}, {"year": 1931, "event": "built"}], rental={"available": True}, registers=[{"register": "NHLR"}], other_names=["Old | Name"]))
        self.write("broken.json", "{not json")
        self.write("traversal.json", {**tower("us-or-x"), "id": "../../etc/passwd"})
        self.write("nocoords.json", {**tower("us-or-nocoords"), "location": {"lat": None, "lon": None}})
        self.write("zz-dupe.json", tower("us-or-good"))  # sorted after good.json, so it is the duplicate
        self.write("hidden.json", tower("us-or-tree", kind="tree", hidden=True))
        meta = self.build()
        self.assertEqual(meta["counts"]["total"], 1)
        self.assertEqual(meta["counts"]["skipped"], 4)
        self.assertEqual(meta["counts"]["hidden"], 1)
        props = json.loads((self.out / "towers.geojson").read_text())["features"][0]["properties"]
        self.assertEqual(props, {"i": "us-or-good", "n": "Good Lookout", "r": "OR", "k": "tower", "s": "standing", "v": "unverified", "a": "public", "b": 1931, "rt": 1, "rg": 1, "o": "Old / Name"})
        self.assertEqual(sorted(p.name for p in (self.out / "t").iterdir()), ["us-or-good.json"])

    def test_strict_mode_fails_on_bad_records(self) -> None:
        self.write("broken.json", "{not json")
        with self.assertRaises(SystemExit):
            self.build(strict=True)

    def test_unavailable_rental_is_not_rentable(self) -> None:
        self.write("a.json", tower("us-or-a", rental={"available": False}))
        self.build()
        props = json.loads((self.out / "towers.geojson").read_text())["features"][0]["properties"]
        self.assertNotIn("rt", props)

    def test_stale_tower_files_are_removed(self) -> None:
        self.write("a.json", tower("us-or-a"))
        self.build()
        (self.towers / "or" / "a.json").unlink()
        self.write("b.json", tower("us-or-b"))
        self.build()
        self.assertEqual(sorted(p.name for p in (self.out / "t").iterdir()), ["us-or-b.json"])

    def test_refuses_to_clear_a_folder_it_did_not_make(self) -> None:
        self.out.mkdir()
        (self.out / "important.txt").write_text("keep me")
        self.write("a.json", tower("us-or-a"))
        with self.assertRaises(SystemExit):
            self.build()
        self.assertTrue((self.out / "important.txt").exists())

    def test_photo_file_and_thumb_pass_through_unchanged(self) -> None:
        # pipeline/merge.py is what fills in file/thumb from data/photos_manifest.json; this
        # script neither copies photo files nor validates them -- the site resolves file/thumb
        # against site.config.json's photosBase at render time (web/src/render/tower.ts).
        self.write("a.json", tower("us-or-a", photos=[{"file": "bd/bdc82644.webp", "thumb": "bd/bdc82644.t.webp", "url": "https://example.org/1.jpg", "credit": "X"}]))
        self.build()
        rec = json.loads((self.out / "t" / "us-or-a.json").read_text())
        self.assertEqual(rec["photos"][0]["file"], "bd/bdc82644.webp")
        self.assertEqual(rec["photos"][0]["thumb"], "bd/bdc82644.t.webp")
        self.assertEqual(rec["photos"][0]["url"], "https://example.org/1.jpg")


class CommandLine(unittest.TestCase):
    def test_empty_towers_without_fallback_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = bsd.main(["--towers", str(Path(tmp) / "none"), "--out", str(Path(tmp) / "out"), "--quiet"])
            self.assertEqual(code, 2)
            self.assertIn("--fallback-fixtures", err.getvalue())

    def test_empty_towers_with_fallback_uses_fixtures_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = bsd.main(["--towers", str(Path(tmp) / "none"), "--out", str(Path(tmp) / "out"), "--fallback-fixtures", "--quiet"])
            self.assertEqual(code, 0)
            self.assertIn("USING FIXTURE DATA", out.getvalue())
            meta = json.loads((Path(tmp) / "out" / "meta.json").read_text())
            self.assertTrue(meta["fixtures"])
            self.assertGreater(meta["counts"]["total"], 10)


class Markdown(unittest.TestCase):
    def test_escapes_html_and_unsafe_links(self) -> None:
        out = bsd.markdown_to_html('<script>alert(1)</script> [a](javascript:alert(2)) [b](https://ok.org/?x=1&y=2)\n')
        self.assertNotIn("<script", out)
        self.assertNotIn("javascript:", out)
        self.assertIn('<a href="https://ok.org/?x=1&amp;y=2">b</a>', out)

    def test_structure(self) -> None:
        out = bsd.markdown_to_html("---\ntitle: x\n---\n# Head\n\n> Quoted\n\n- one\n- two\n\nText[^1].\n\n[^1]: Note.\n")
        self.assertNotIn("title: x", out)
        self.assertIn('<h2 id="s-head">Head</h2>', out)
        self.assertIn("<blockquote><p>Quoted</p></blockquote>", out)
        self.assertIn("<ul><li>one</li><li>two</li></ul>", out)
        self.assertIn('<li id="fn-1">Note. <a href="#fnref-1"', out)

    def test_safe_href(self) -> None:
        for bad in ("javascript:x", "JAVASCRIPT:x", "java\tscript:x", "data:x", "vbscript:x"):
            self.assertIsNone(bsd.safe_href(bad), bad)
        for good in ("https://a.org", "http://a.org", "mailto:a@b.org", "#fn-1", "/firefinder/"):
            self.assertEqual(bsd.safe_href(good), good)


if __name__ == "__main__":
    unittest.main()
