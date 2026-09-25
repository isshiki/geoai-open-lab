"""Test the tutorial helpers with invented in-memory rows, never live data."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import unittest
import json
import tempfile
from hashlib import sha256
from unittest.mock import patch

import duckdb
from geoai_open_lab.foursquare import (FoursquareSession, FoursquareError, fetch_places,
    filter_places_by_category, load_aoi, _schemas, _select_snapshots, save_results,
    connect_foursquare)


class NotebookQueryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        (self.root / "data/cache/refactor").mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect()
        self.addCleanup(self.connection.close)
        self.connection.execute("""
            CREATE TABLE fixture_places (
                fsq_place_id VARCHAR, name VARCHAR, latitude DOUBLE,
                longitude DOUBLE, country VARCHAR, locality VARCHAR,
                region VARCHAR, address VARCHAR, fsq_category_ids VARCHAR[],
                date_closed VARCHAR
            )
        """)
        self.connection.executemany(
            "INSERT INTO fixture_places VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("invented-001", "Invented Cafe", 35.703, 139.58, "JP", None, None, None, ["coffee", "espresso"], "2020-01-01"),
                ("invented-002", "Invented Other", 35.704, 139.58, "JP", None, None, None, ["missing"], None),
                ("invented-003", "Invented Empty", 35.705, 139.58, "JP", None, None, None, [], None),
                ("invented-004", "Outside bbox", 35.703, 139.60, "JP", None, None, None, ["coffee"], None),
                ("invented-005", "Wrong country", 35.703, 139.58, "US", None, None, None, ["coffee"], None),
            ],
        )
        self.connection.execute("""
            CREATE TABLE fixture_categories (
                category_id VARCHAR, category_name VARCHAR, category_label VARCHAR,
                level1_category_id VARCHAR, level2_category_id VARCHAR,
                level3_category_id VARCHAR, level4_category_id VARCHAR,
                level5_category_id VARCHAR, level6_category_id VARCHAR
            )
        """)
        self.connection.executemany(
            "INSERT INTO fixture_categories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("coffee", "Coffee Shop", "Invented > Coffee Shop", "coffee", None, None, None, None, None),
                ("espresso", "Espresso Bar", "Invented > Coffee Shop > Espresso Bar", "coffee", "espresso", None, None, None, None),
                ("cafeteria", "Cafeteria", "Invented > Cafeteria", "cafeteria", None, None, None, None, None),
            ],
        )

    def run_extraction(self, limit=500):
        session = FoursquareSession(self.connection, self.root, {
            "sources": {"places": "fixture_places", "categories": "fixture_categories"},
            "executed_sql": {},
        })
        self.session = session
        places = fetch_places(session, bbox=load_aoi(root=self.root), country="JP", limit=limit)
        with redirect_stdout(io.StringIO()):
            cafes = filter_places_by_category(session, places, categories=["Cafe", "Coffee Shop"])
        return session, places, cafes

    def test_country_bbox_category_children_and_no_join_inflation(self):
        session, places, cafes = self.run_extraction()
        checks = session.details["checks"]
        self.assertEqual(len(places), 3)
        self.assertFalse(checks["truncated"])
        self.assertEqual(checks["aoi_total_if_complete"], 3)
        self.assertEqual(checks["unmatched_category_id_count"], 1)
        self.assertEqual(checks["category_ids_missing_or_empty"], 1)
        self.assertEqual(checks["date_closed_present"], 1)
        self.assertEqual(cafes["fsq_place_id"].tolist(), ["invented-001"])
        self.assertEqual(self.connection.execute("SELECT count(*) FROM cafe_categories").fetchone()[0], 2)
        self.assertEqual([r["category_name"] for r in session.details["cafe_root_categories"]], ["Coffee Shop"])

    def test_cap_does_not_claim_full_aoi_count(self):
        session, places, _ = self.run_extraction(limit=2)
        self.assertEqual(len(places), 2)
        self.assertTrue(session.details["checks"]["truncated"])
        self.assertIsNone(session.details["checks"]["aoi_total_if_complete"])

    def test_duplicate_category_dictionary_stops(self):
        self.connection.execute("INSERT INTO fixture_categories SELECT * FROM fixture_categories LIMIT 1")
        with self.assertRaisesRegex(FoursquareError, "Duplicate or null"):
            self.run_extraction()

    def test_duplicate_poi_stops(self):
        self.connection.execute("INSERT INTO fixture_places SELECT * FROM fixture_places WHERE fsq_place_id='invented-001'")
        with self.assertRaisesRegex(FoursquareError, "Duplicate or null POI"):
            self.run_extraction()

    def test_schema_drift_stops(self):
        self.connection.execute("ALTER TABLE fixture_places DROP COLUMN fsq_category_ids")
        with self.assertRaisesRegex(FoursquareError, "schema changed"):
            _schemas(self.connection, {"places":"fixture_places", "categories":"fixture_categories"})

    def test_country_must_match_aoi(self):
        session, _, _ = self.run_extraction()
        with self.assertRaisesRegex(ValueError, "CRS/country"):
            fetch_places(session, bbox=load_aoi(root=self.root), country="US")

    def test_rerun_clears_stale_category_results(self):
        session, _, _ = self.run_extraction()
        fetch_places(session, bbox=load_aoi(root=self.root), limit=1)
        self.assertNotIn("cafes", session.records)

    def test_changed_dataframe_is_rejected(self):
        session, places, _ = self.run_extraction()
        places.loc[0, "name"] = "changed"
        with self.assertRaisesRegex(ValueError, "unchanged"):
            filter_places_by_category(session, places)

    def test_no_category_match_is_not_reported_as_zero_cafes(self):
        session, places, _ = self.run_extraction()
        with self.assertRaisesRegex(FoursquareError, "not found"):
            filter_places_by_category(session, places, categories=["No such category"])
        self.assertNotIn("cafes", session.records)

    def test_saved_snapshot_is_reused_even_when_newer_exists(self):
        cache = self.root / "data/cache/refactor"
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            root = Path(directory)
            pins = root / "data/cache/foursquare/snapshots.json"
            pins.parent.mkdir(parents=True)
            pins.write_text(json.dumps({k:{"snapshot_id":"100"} for k in ["places","categories"]}))
            snapshots = [{"snapshot_id":200,"timestamp_ms":"new","sequence_number":2},
                         {"snapshot_id":100,"timestamp_ms":"old","sequence_number":1}]
            with patch("geoai_open_lab.foursquare.query"), patch(
                "geoai_open_lab.foursquare.rows", return_value=snapshots
            ):
                _, selected = _select_snapshots(self.connection, root, None)
                self.assertEqual(selected["places"]["snapshot_id"], "100")
                with self.assertRaisesRegex(FoursquareError, "no latest fallback"):
                    _select_snapshots(self.connection, root, {"places":"99", "categories":"99"})

    def test_empty_catalog_listing_does_not_prevent_connection(self):
        with tempfile.TemporaryDirectory(dir=self.root / "data/cache/refactor") as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text("")
            pins = {k:{"snapshot_id":"100"} for k in ["places","categories"]}
            with patch("geoai_open_lab.foursquare.connect", return_value=self.connection), patch(
                "geoai_open_lab.foursquare.rows", return_value=[]
            ), patch("geoai_open_lab.foursquare._select_snapshots", return_value=(root/'pins.json',pins)), patch(
                "geoai_open_lab.foursquare._schemas", return_value={}
            ):
                session = connect_foursquare(root=root)
            self.assertEqual(session.details["available_tables"], [])
            self.assertEqual(session.details["snapshots"], pins)

    def test_manifest_preserves_checks_hashes_and_keeps_secrets_out(self):
        session, _, _ = self.run_extraction()
        with tempfile.TemporaryDirectory(dir=self.root / "data/cache/refactor") as directory:
            root = Path(directory)
            for name in ["notebooks/01_foursquare_places.ipynb", "src/geoai_open_lab/foursquare.py",
                         "src/geoai_open_lab/_foursquare_provenance.py", "configs/aoi/kichijoji.toml",
                         "pyproject.toml", "uv.lock"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("invented source fixture")
            session.root = root
            session.details.update(started_at_utc="2026-09-24T00:00:00+00:00",
                snapshots={"places":{"snapshot_id":"100"},"categories":{"snapshot_id":"200"}},
                schema={}, available_tables=[], secret="invented-secret-must-not-be-saved")
            result = save_results(session)
            self.assertTrue(result.is_relative_to(root / "data/raw/foursquare"))
            manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["checks"]["sample_count"], 3)
            self.assertEqual(manifest["snapshots"]["places"]["snapshot_id"], "100")
            self.assertNotIn("invented-secret", (result / "manifest.json").read_text(encoding="utf-8"))
            for name, digest in manifest["output_sha256"].items():
                self.assertEqual(sha256((result / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
