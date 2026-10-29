import json
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
from shapely.geometry import shape
from geoai_open_lab.geojson_tutorial import (
    ROOT, basic_check, cases, content_check, example_collection, example_frame,
    probe, run, strict_loads,
)


class GeoJSONTutorialTests(unittest.TestCase):
    def test_normal_three_geometries(self):
        self.assertEqual(example_frame().geom_type.tolist(),['Point','LineString','Polygon'])
        self.assertEqual(basic_check(example_collection()),[])

    def test_source_ring_closed_counterclockwise(self):
        polygon=example_collection()['features'][2]['geometry']
        self.assertEqual(polygon['coordinates'][0][0],polygon['coordinates'][0][-1])
        self.assertTrue(shape(polygon).exterior.is_ccw)

    def test_broken_json(self):
        with self.assertRaises(json.JSONDecodeError):json.loads(cases()['broken_json'])

    def test_wrong_structure(self):
        self.assertTrue(basic_check(json.loads(cases()['wrong_structure'])))

    def test_swapped_is_geometrically_valid(self):
        obj=json.loads(cases()['swapped_lon_lat'])
        self.assertTrue(shape(obj['features'][0]['geometry']).is_valid)
        self.assertTrue(basic_check(obj))

    def test_unclosed_detected_before_construction(self):
        obj=json.loads(cases()['unclosed_polygon'])
        self.assertTrue(basic_check(obj))
        self.assertTrue(shape(obj['features'][2]['geometry']).is_valid)

    def test_self_intersection_separate_from_structure(self):
        obj=json.loads(cases()['self_intersection'])
        self.assertEqual(basic_check(obj),[])
        self.assertFalse(shape(obj['features'][2]['geometry']).is_valid)

    def test_content_requires_context(self):
        obj=json.loads(cases()['wrong_place_valid_range'])
        self.assertEqual(basic_check(obj),[])
        self.assertTrue(content_check(obj))

    def test_unsupported_not_called_invalid_rfc(self):
        obj=example_collection();obj['features'][0]['geometry']=None
        self.assertIn('non-null geometry required in this tutorial',basic_check(obj))

    def test_nonfinite_and_bool(self):
        for value in [float('nan'),float('inf'),True]:
            obj=example_collection();obj['features'][0]['geometry']['coordinates'][0]=value
            self.assertTrue(basic_check(obj))
        with self.assertRaises(ValueError):strict_loads('{"value":NaN}')

    def test_wgs_export_from_projected(self):
        frame=example_frame().to_crs(6677)
        self.assertIn('crs',json.loads(frame.to_json()))
        obj=json.loads(frame.to_json(to_wgs84=True))
        self.assertNotIn('crs',obj)
        self.assertEqual(basic_check(obj),[])

    def test_roundtrip_and_reexecution(self):
        scratch=ROOT/'data/cache/geojson/test-tmp';scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            a=run(tmp); first=(Path(tmp)/'results.json').read_bytes()
            b=run(tmp)
            self.assertEqual(a,b)
            self.assertEqual(first,(Path(tmp)/'results.json').read_bytes())
            self.assertTrue(a['geometry_exact_roundtrip'] and a['properties_exact_roundtrip'])
            row=next(r for r in a['cases'] if r['case']=='unclosed_polygon')
            self.assertTrue(row['from_features_changed'])
            self.assertFalse(row['read_file_ok'])


if __name__=='__main__':unittest.main()
