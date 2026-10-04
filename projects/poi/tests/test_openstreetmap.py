"""Invented OSM fixtures only. Public Overpass is never contacted by tests."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch, Mock
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point,Polygon,MultiPolygon,LineString
from geoai_open_lab.openstreetmap import (TAG_KEYS,poi_tags,normalize_osm_features,
    filter_osm_cafes,summarize_osm,_relation_audit,_cached_response,_validate_response,
    fetch_osm_pois,save_osm_results,load_aoi,_bounded_download)

ROOT=Path(__file__).resolve().parents[1]
class OSMTests(unittest.TestCase):
    def setUp(self):
        self.aoi=load_aoi(root=ROOT)
        self.poly=Polygon([(139.579,35.702),(139.582,35.702),(139.582,35.706),
            (139.581,35.706),(139.581,35.703),(139.580,35.703),
            (139.580,35.706),(139.579,35.706)])
        self.gdf=gpd.GeoDataFrame({'amenity':['cafe','internet_cafe','restaurant'],
            'shop':[None,'coffee',None],'cafe':[None,None,'yes'],
            'geometry':[Point(139.58,35.704),self.poly,MultiPolygon([self.poly])]},
            index=pd.MultiIndex.from_tuples([('node',1),('way',1),('relation',1)]),crs=4326)
        folder=ROOT/'data/cache/osm/tests';folder.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def test_tags_are_eight_key_union(self):
        self.assertEqual(len(poi_tags()),8);self.assertTrue(all(poi_tags().values()))
        self.assertNotIn('cafe',poi_tags())
    def test_types_ids_and_surface_points(self):
        data,checks=normalize_osm_features(self.gdf,self.aoi)
        self.assertEqual(len(data),3);self.assertEqual(checks['representative_point_outside'],0)
        for row in data.itertuples(): self.assertTrue(row.geometry.covers(Point(row.longitude,row.latitude)))
        self.assertEqual(set(data.osm_type),{'node','way','relation'})
    def test_cafe_is_exact_and_related_scope(self):
        data,_=normalize_osm_features(self.gdf,self.aoi)
        self.assertEqual(len(filter_osm_cafes(data)),1)
        values=summarize_osm(data)['related_tags']
        self.assertIn({'key':'cafe','value':'yes','count':1},values)
        self.assertIn({'key':'shop','value':'coffee','count':1},values)
    def test_boundary_included_and_outside_excluded(self):
        self.gdf.loc[('node',1),'geometry']=Point(self.aoi['west'],self.aoi['south'])
        self.gdf.loc[('way',1),'geometry']=Point(self.aoi['east']+0.01,self.aoi['north'])
        data,c=normalize_osm_features(self.gdf,self.aoi)
        self.assertEqual(c['representative_point_outside'],1);self.assertEqual(len(data),2)
    def test_null_empty_unsupported(self):
        self.gdf.geometry=[None,Point(),LineString([(139.58,35.70),(139.58,35.71)])]
        data,c=normalize_osm_features(self.gdf,self.aoi)
        self.assertEqual(len(data),0)
        self.assertEqual((c['null_geometry'],c['empty_geometry'],c['unsupported_geometry']),(1,1,1))
    def test_duplicate_keys_rejected(self):
        self.gdf.index=pd.MultiIndex.from_tuples([('node',1)]*3)
        with self.assertRaises(ValueError):normalize_osm_features(self.gdf,self.aoi)
    def test_bad_aoi_rejected(self):
        with self.assertRaises(ValueError):normalize_osm_features(self.gdf,self.aoi|{'crs':'EPSG:3857'})
    def test_relation_audit(self):
        raw={'elements':[{'type':'relation','id':1,'tags':{'amenity':'restaurant','type':'multipolygon'}},
            {'type':'relation','id':2,'tags':{'shop':'mall','type':'site'}}]}
        data,_=normalize_osm_features(self.gdf,self.aoi)
        a=_relation_audit(raw,self.gdf,data)
        self.assertEqual(a['raw_tag_matching'],2);self.assertEqual(a['final_accepted'],1)
        self.assertEqual(a['unsupported_type'],1);self.assertEqual(a['absent_after_osmnx'],1)
    def test_remark_rejected(self):
        with self.assertRaises(ValueError):_validate_response({'elements':[],'remark':'timeout'})
    def test_cache_replays_without_network(self):
        timing={'retrieval_start_utc':'2026-01-01T00:00:00Z','retrieval_end_utc':'2026-01-01T00:00:01Z','download_seconds':1,'response_body_bytes':20}
        with patch('geoai_open_lab.openstreetmap._bounded_download',return_value=({'elements':[]},timing)) as call:
            a,path,hit=_cached_response(self.root,'invented query')
            b,other,hit=_cached_response(self.root,'invented query')
            call.assert_called_once();self.assertTrue(hit);self.assertEqual(a,b)
            self.assertTrue(path.is_relative_to(self.root/'data/cache/osm'))
    def test_fetch_manifest_and_version(self):
        record={'response':{'elements':[], 'osm3s':{'timestamp_osm_base':'2026-01-01T00:00:00Z'}},
            'query':'invented','retrieval_start_utc':'start','retrieval_end_utc':'end','download_seconds':1,'response_body_bytes':10}
        path=self.root/'raw.json';path.write_text(json.dumps(record))
        for name in ['src/geoai_open_lab/openstreetmap.py','src/geoai_open_lab/aoi.py','configs/aoi/kichijoji.toml','notebooks/03_openstreetmap_poi.ipynb','pyproject.toml','uv.lock']:
            dest=self.root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
        def features(*args,**kwargs):
            from osmnx import _overpass
            response = _overpass._overpass_request({'data':'invented'})
            response.pop('elements')
            return self.gdf
        with patch('geoai_open_lab.openstreetmap._cached_response',return_value=(record,path,True)), patch('geoai_open_lab.openstreetmap.ox.features.features_from_bbox',side_effect=features):
            data=fetch_osm_pois(bbox=self.aoi,root=self.root)
        run=save_osm_results(data,root=self.root)
        self.assertTrue(run.is_relative_to(self.root/'data/raw/osm'))
        m=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(m['osmnx_version'],'2.1.1');self.assertTrue(m['cache_hit'])
        self.assertEqual(m['summary']['cafe_count'],1)
    def test_busy_status_does_not_post(self):
        with patch('geoai_open_lab.openstreetmap.requests.Session') as factory:
            client=factory.return_value.__enter__.return_value
            client.get.return_value.text='Slot available after a later time'
            with self.assertRaises(RuntimeError):_bounded_download('invented')
            client.post.assert_not_called()

    def test_intersecting_polygon_with_outside_representative_point(self):
        from shapely.geometry import box
        self.gdf.loc[('way',1),'geometry']=box(self.aoi['west']-0.02,self.aoi['south'],self.aoi['west']+0.001,self.aoi['north'])
        data,c=normalize_osm_features(self.gdf,self.aoi)
        self.assertEqual(c['representative_point_outside'],1)
        self.assertEqual(c['final_representative_point_outside'],0)
        self.assertEqual(len(data),2)
