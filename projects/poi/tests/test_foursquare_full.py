"""Full acquisition gates, using invented records and an offline DuckDB table."""
from pathlib import Path
import json
import tempfile
import unittest

import duckdb

from geoai_open_lab._foursquare_full import FULL_COLUMNS, validate_full_records
from geoai_open_lab.foursquare import FoursquareError, FoursquareSession, fetch_all_places, save_all_results

AOI = {"crs": "EPSG:4326", "country": "JP", "west": 139.574,
       "east": 139.586, "south": 35.699, "north": 35.708}
RECORD = {"fsq_place_id": "invented-a", "longitude": 139.58, "latitude": 35.70,
          "country": "JP", "has_geometry": True}


class FullGateTests(unittest.TestCase):
    def test_counts_and_geometry(self):
        self.assertEqual(validate_full_records([RECORD], 1, AOI, "JP")["unique_ids"], 1)
        for data, count in [([RECORD], 2), ([RECORD, RECORD], 2), ([], 0)]:
            with self.subTest(count=count), self.assertRaises(FoursquareError):
                validate_full_records(data, count, AOI, "JP")
        for key, value in [("fsq_place_id", None), ("latitude", None),
                           ("latitude", float("nan")), ("longitude", 140),
                           ("country", "XX"), ("has_geometry", False)]:
            with self.subTest(key=key), self.assertRaises(FoursquareError):
                validate_full_records([{**RECORD, key: value}], 1, AOI, "JP")

    def test_fetch_without_limit_and_independent_count(self):
        db = duckdb.connect()
        self.addCleanup(db.close)
        columns = []
        for c in FULL_COLUMNS:
            value = ("139.58::DOUBLE" if c == "longitude" else "35.70::DOUBLE" if c == "latitude" else
                     "['invented-category']" if c.startswith("fsq_category_") else
                     "'JP'" if c == "country" else "'invented-a'" if c == "fsq_place_id" else
                     "NULL::VARCHAR")
            columns.append(f"{value} AS {c}")
        db.execute("CREATE TABLE test_places AS SELECT " + ", ".join(columns) + ", 'x'::BLOB AS geom")
        db.execute("CREATE TABLE test_categories AS SELECT 'invented-category' AS category_id")
        schema = [{"column_name": c[0], "column_type": c[1]} for c in db.execute("DESCRIBE test_places").fetchall()]
        session = FoursquareSession(db, Path.cwd(), {"schema": {"places": schema},
            "sources": {"places": "test_places", "categories": "test_categories"}})
        result = fetch_all_places(session, bbox=AOI)
        self.assertEqual(len(result), 1)
        sql = session.details["full_acquisition"]["executed_sql"]
        self.assertIn("COUNT(*)", sql["count"])
        self.assertNotIn("LIMIT", sql["places"])
        cache = Path("data/cache/comparison/tests")
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            root = Path(directory).resolve()
            for name in ("src/geoai_open_lab/foursquare.py", "src/geoai_open_lab/_foursquare_full.py",
                         "configs/aoi/kichijoji.toml", "uv.lock"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(Path(name).read_bytes())
            session.root = root
            session.details["snapshots"] = {"places": {"snapshot_id": "100"}, "categories": {"snapshot_id": "200"}}
            session.details["full_acquisition"]["unrelated_secret"] = "invented-never-export"
            path = save_all_results(session)
            manifest_text = (path / "manifest.json").read_text(encoding="utf-8")
            manifest = json.loads(manifest_text)
            self.assertEqual(manifest["checks"]["saved_rows"], 1)
            self.assertTrue(manifest["checks"]["full_aoi_gate_passed"])
            self.assertNotIn("invented-never-export", manifest_text)
        db.execute("UPDATE test_places SET geom=NULL")
        with self.assertRaises(FoursquareError):
            fetch_all_places(session, bbox=AOI)
        self.assertNotIn("full_acquisition", session.details)
        self.assertNotIn("full_places", session.records)


if __name__ == "__main__":
    unittest.main()
