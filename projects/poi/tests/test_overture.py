"""Offline Overture tests; invented fixtures only, no network downloads."""
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest
import duckdb
from geoai_open_lab.aoi import load_aoi, validate_aoi
from geoai_open_lab.overture import (source_uri, validate_schema, connect_overture,
    OvertureSession, fetch_overture_places, filter_overture_cafes,
    summarize_overture, save_overture_results)

ROOT = Path(__file__).resolve().parents[1]

class OvertureTests(unittest.TestCase):
    def setUp(self):
        cache=ROOT/'data/cache/overture/tests'; cache.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=cache); self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.con=duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')})
        self.addCleanup(self.con.close)
        # LOAD uses an already installed extension. No INSTALL/network in tests.
        self.con.execute('LOAD spatial')
        self.con.execute("""CREATE TABLE fixture AS SELECT
            'invented-' || i AS id, ST_Point(139.58,35.703) AS geometry,
            {'xmin':139.58::DOUBLE,'xmax':139.58::DOUBLE,'ymin':35.703::DOUBLE,'ymax':35.703::DOUBLE} AS bbox,
            {'primary':'Invented'} AS names,
            [{'country':'JP'}] AS addresses,
            CASE WHEN i=3 THEN 'restaurant' ELSE 'cafe' END AS basic_category,
            {'primary':CASE WHEN i=1 THEN 'internet_cafe' WHEN i=2 THEN 'cat_cafe' ELSE 'cafeteria' END,
             'hierarchy':CASE WHEN i=3 THEN ['restaurant','cafeteria'] ELSE ['cafe',CASE WHEN i=1 THEN 'internet_cafe' ELSE 'cat_cafe' END] END,
             'alternates':NULL::VARCHAR[]} AS taxonomy,
            NULL::VARCHAR AS brand, []::VARCHAR[] AS websites, []::VARCHAR[] AS socials,
            []::VARCHAR[] AS emails, []::VARCHAR[] AS phones,
            CASE WHEN i=1 THEN 'permanently_closed' ELSE NULL END AS operating_status,
            CASE WHEN i=1 THEN 0.0 ELSE 0.9 END::DOUBLE AS confidence,
            [{'dataset':'invented','provider':NULL::VARCHAR,'license':'invented'}] AS sources
            FROM range(1,4) t(i)""")
        self.path=self.dir/'fixture.parquet'
        self.con.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(self.path)])
        self.session=OvertureSession(self.con,ROOT)
    def acquire(self):
        with patch('geoai_open_lab.overture.source_uri',return_value=str(self.path)):
            return fetch_overture_places(self.session,bbox=load_aoi(root=ROOT))
    def test_release(self):
        self.assertIn('/2026-09-23.0/theme=places/type=place/',source_uri())
        for v in ['latest','2026-08-19.0',"'; SELECT 1"]:
            with self.assertRaises(ValueError): source_uri(v)
    def test_aoi(self):
        area=load_aoi(root=ROOT)
        for change in [{'crs':'EPSG:3857'},{'west':float('nan')},{'east':area['west']}]:
            with self.assertRaises(ValueError): validate_aoi(area|change,'JP')
    def test_schema_rejects_legacy_and_missing_fields(self):
        schema=self.con.execute('DESCRIBE fixture').fetchall()
        validate_schema(schema)
        with self.assertRaises(ValueError): validate_schema(schema+[('categories','VARCHAR')])
        with self.assertRaises(ValueError): validate_schema([r for r in schema if r[0]!='taxonomy'])
    def test_no_limit_status_filter_and_cafe_descendants(self):
        places=self.acquire(); self.assertEqual(len(places),3)
        cafes=filter_overture_cafes(self.session)
        self.assertEqual(set(cafes.taxonomy_primary),{'internet_cafe','cat_cafe'})
        self.assertIn('permanently_closed',cafes.operating_status.tolist())
        summary=summarize_overture(self.session)
        self.assertEqual(len(summary['cafe_taxonomy_primary']),2)
        self.assertIsNone(self.session.details['limit'])
    def test_inclusive_boundary(self):
        area=load_aoi(root=ROOT)
        self.con.execute('UPDATE fixture SET geometry=ST_Point(?,?), bbox={xmin:?::DOUBLE,xmax:?::DOUBLE,ymin:?::DOUBLE,ymax:?::DOUBLE} WHERE id=?', [area['west'],area['south'],area['west'],area['west'],area['south'],area['south'],'invented-1'])
        self.con.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(self.path)])
        self.assertEqual(len(self.acquire()),3)
    def test_manifest_and_ignored_destination(self):
        self.acquire()
        # Preserve source hashes but isolate generated output in a project-local temp root.
        self.session.root=self.dir
        for p in ['src/geoai_open_lab/overture.py','src/geoai_open_lab/aoi.py','configs/aoi/kichijoji.toml','notebooks/02_overture_places.ipynb','pyproject.toml','uv.lock']:
            dest=self.dir/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/p).read_bytes())
        self.session.details['secret']='invented-secret-must-not-publish'
        run=save_overture_results(self.session)
        self.assertTrue(run.is_relative_to(self.dir/'data/raw/overture'))
        m=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
        self.assertNotIn('invented-secret',json.dumps(m))
        self.assertEqual(m['cafe_count'],2);self.assertEqual(m['schema_version'],'v2.0.0')
        self.assertIsNone(m['network_bytes']);self.assertGreater(m['output_bytes']['places.parquet'],0)
    def test_connection_does_not_load_credentials(self):
        with patch('geoai_open_lab.overture.duckdb.connect') as factory:
            session=connect_overture(root=ROOT)
            sql=' '.join(call.args[0] for call in factory.return_value.execute.call_args_list)
            self.assertNotIn('credential_chain',sql)
            self.assertIn("KEY_ID ''",sql)
            self.assertEqual(factory.call_args.kwargs['config']['allow_persistent_secrets'],'false')

    def test_bbox_candidate_outside_exact_geometry_is_excluded(self):
        self.con.execute("UPDATE fixture SET geometry=ST_Point(139.60,35.703), bbox=struct_update(bbox,xmax:=139.60) WHERE id='invented-1'")
        self.con.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(self.path)])
        self.assertEqual(len(self.acquire()),2)
        self.assertEqual(self.session.details['candidate_count'],3)
    def test_null_geometry_stops(self):
        self.con.execute("UPDATE fixture SET geometry=NULL WHERE id='invented-1'")
        self.con.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(self.path)])
        with self.assertRaisesRegex(ValueError,'geometries'): self.acquire()
        self.assertNotIn('row_count',self.session.details)
    def test_duplicate_ids_stop(self):
        self.con.execute("UPDATE fixture SET id='same'")
        self.con.execute('COPY fixture TO ? (FORMAT PARQUET)',[str(self.path)])
        with self.assertRaisesRegex(ValueError,'ID'): self.acquire()
