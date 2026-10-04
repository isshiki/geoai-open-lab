"""Full local comparison pipeline on invented data, including replay gates."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq
from shapely import Point, to_wkb

from geoai_open_lab._comparison_io import PINS, prepare_inputs, run_comparison
from geoai_open_lab.aoi import load_aoi


class ComparisonIOTests(unittest.TestCase):
    def setUp(self):
        parent = Path("data/cache/comparison/tests")
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        aoi = load_aoi()
        paths = ["pyproject.toml", "uv.lock", "configs/aoi/kichijoji.toml",
                 "src/geoai_open_lab/poi_comparison.py", "src/geoai_open_lab/_comparison_io.py",
                 "src/geoai_open_lab/_foursquare_full.py", "src/geoai_open_lab/foursquare.py",
                 "src/geoai_open_lab/openstreetmap.py", "src/geoai_open_lab/overture.py",
                 "notebooks/04_poi_comparison.ipynb"]
        for name in paths:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(Path(name).read_bytes())
        fs = self.root / "data/raw/foursquare_full/test"
        ov = self.root / "data/raw/overture/test"
        osm = self.root / "data/raw/osm/test"
        for p in (fs, ov, osm):
            p.mkdir(parents=True)
        write = lambda p, v: p.write_text(json.dumps(v), encoding="utf-8")
        digest = lambda p: sha256(p.read_bytes()).hexdigest()
        fsrow = {"fsq_place_id": "invented-f", "name": "Invented cafe", "longitude": 139.58,
                 "latitude": 35.703, "country": "JP", "has_geometry": True, "fsq_category_ids": ["fiction"]}
        write(fs / "places.json", [fsrow])
        write(fs / "categories.json", [{"category_id": "fiction", "category_name": "Imaginary category"}])
        self.fsqm = {"status": "completed", "aoi": aoi, "country": "JP", "limit": None,
            "snapshots": {k: {"snapshot_id": v} for k, v in PINS.items()},
            "checks": {"full_aoi_gate_passed": True, "count_query": 1, "retrieved_rows": 1,
                       "unique_ids": 1, "saved_rows": 1},
            "output_sha256": {n: digest(fs / n) for n in ("places.json", "categories.json")}}
        self.fsq_manifest = fs / "manifest.json"
        write(self.fsq_manifest, self.fsqm)
        pq.write_table(pa.Table.from_pylist([{"id": "invented-o", "names": {"primary": "Invented cafe"},
                       "geometry": to_wkb(Point(139.58, 35.703))}]), ov / "places.parquet")
        write(ov / "manifest.json", {"aoi": aoi, "release": "2026-09-23.0", "limit": None,
              "row_count": 1, "output_sha256": {"places.parquet": digest(ov / "places.parquet")}})
        pq.write_table(pa.Table.from_pylist([{"osm_type": "node", "osm_id": 1, "name": "Invented cafe",
                       "longitude": 139.58, "latitude": 35.703, "amenity": "cafe"}]), osm / "places.parquet")
        raw = self.root / "data/cache/osm/raw.json"
        raw.parent.mkdir(parents=True)
        write(raw, {"response": {"elements": [{"type": "node", "id": 1, "tags": {"addr:full": "Invented"}}]}})
        write(osm / "manifest.json", {"aoi": aoi, "osmnx_version": "2.1.1", "checks": {"final_count": 1},
            "outputs": {"places.parquet": {"sha256": digest(osm / "places.parquet")}},
            "raw_cache": "data/cache/osm/raw.json", "raw_cache_sha256": digest(raw)})

    def test_offline_pipeline_pending_samples_and_hashes(self):
        inputs = prepare_inputs(root=self.root)
        result = run_comparison(inputs, root=self.root)
        self.assertEqual(result["summary"]["three_way"], 1)
        self.assertEqual(result["summary"]["samples"]["high_confidence"]["review_status"], "pending")
        self.assertEqual(result["summary"]["samples"]["unmatched_nearby"]["count"], 0)
        self.assertEqual(result["manifest"]["remote_queries_in_comparison"], 0)
        for name, data in result["manifest"]["outputs"].items():
            self.assertEqual(sha256((result["path"] / name).read_bytes()).hexdigest(), data["sha256"])
        self.assertNotIn(str(self.root), (result["path"] / "manifest.json").read_text(encoding="utf-8"))

    def test_count_tamper_stops_before_comparison(self):
        self.fsqm["checks"]["saved_rows"] = 500
        self.fsq_manifest.write_text(json.dumps(self.fsqm), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "counts disagree"):
            prepare_inputs(root=self.root)

    def test_hash_tamper_stops(self):
        (self.fsq_manifest.parent / "places.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            prepare_inputs(root=self.root)

    def test_old_sample_cannot_pass_gate(self):
        self.fsqm["limit"] = 500
        self.fsq_manifest.write_text(json.dumps(self.fsqm), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "gate"):
            prepare_inputs(root=self.root)


if __name__ == "__main__":
    unittest.main()
