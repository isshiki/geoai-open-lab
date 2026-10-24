"""Offline numerical invariants; fixed-data checks are run by verify_crs_results.py."""
import unittest
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from pyproj.exceptions import ProjError
from geoai_open_lab.crs_experiment import (GEOD, station, transformer, crs_metadata,
    distance_examples, poi_comparison, geodesic_area, densify_geodesic,
    equal_area_patch, synthetic_density, project, BUFFER_SEGMENTS)


class CRSTests(unittest.TestCase):
    def setUp(self):
        self.s=station();self.lon=self.s['longitude'];self.lat=self.s['latitude']

    def test_roundtrip_and_existing_center(self):
        x,y=transformer(6677).transform(self.lon,self.lat)
        self.assertAlmostEqual(x,self.s['center_x'],places=5)
        self.assertAlmostEqual(y,self.s['center_y'],places=5)
        lo,la=transformer(4326,6677).transform(x,y)
        self.assertLess(GEOD.inv(self.lon,self.lat,lo,la)[2],1e-6)

    def test_axis_units(self):
        c={r['epsg']:r for r in crs_metadata()}
        self.assertEqual(c[4326]['axes'][0]['direction'],'north')
        self.assertEqual(c[6677]['axes'][0]['direction'],'north')
        self.assertEqual(c[3857]['axes'][0]['unit'],'metre')
        self.assertIsNone(c[6668]['projection'])

    def test_swapped_coordinates_rejected(self):
        with self.assertRaises(ProjError):transformer(3857).transform(self.lat,self.lon,errcheck=True)

    def test_set_vs_transform(self):
        s=gpd.GeoSeries([Point(self.lon,self.lat)])
        labeled=s.set_crs(4326)
        self.assertEqual(s.iloc[0],labeled.iloc[0])
        self.assertNotEqual(labeled.iloc[0],labeled.to_crs(6677).iloc[0])
        self.assertEqual(labeled.iloc[0],labeled.set_crs(3857,allow_override=True).iloc[0])

    def test_distances_have_expected_scale(self):
        d=distance_examples(self.lon,self.lat)
        self.assertTrue((d[d.crs.eq(6677)].error_pct.abs()<.02).all())
        self.assertTrue((d[d.crs.eq(3857)].error_pct>20).all())
        self.assertTrue((d.raw_degree_distance<.02).all())

    def test_buffer_discretization_submillimeter(self):
        deficit=500*(1-np.cos(np.pi/(4*BUFFER_SEGMENTS)))
        self.assertLess(deficit,.001)

    def test_membership_and_overlap(self):
        lon,lat,_=GEOD.fwd(np.full(3,self.lon),np.full(3,self.lat),np.full(3,90),np.array([100,450,600]))
        f=pd.DataFrame(dict(lon=lon,lat=lat))
        assigned,summary,overlap=poi_comparison(f,self.lon,self.lat)
        self.assertEqual(assigned.geodesic.tolist(),[True,True,False])
        self.assertEqual(assigned['3857'].tolist(),[True,False,False])
        self.assertEqual(summary.poi_count.tolist(),[2,2,1])
        self.assertEqual(overlap.changed.tolist(),[0,1,1])

    def test_geodesic_area_orientation_and_hole(self):
        p=Polygon([(0,0),(1,0),(1,1),(0,1)])
        reverse=Polygon(list(p.exterior.coords)[::-1])
        self.assertAlmostEqual(geodesic_area(p),geodesic_area(reverse),delta=.01)
        inner=Polygon([(.2,.2),(.8,.2),(.8,.8),(.2,.8)])
        donut=Polygon(p.exterior.coords,[inner.exterior.coords])
        self.assertAlmostEqual(geodesic_area(donut),geodesic_area(p)-geodesic_area(inner),delta=.01)

    def test_densification_preserves_geodesic_area(self):
        p=Polygon([(135,30),(141,30),(141,40),(135,40)])
        q=densify_geodesic(p)
        self.assertAlmostEqual(geodesic_area(p)/geodesic_area(q),1,places=9)
        self.assertLess(abs(project(q,8857).area/geodesic_area(q)-1),1e-5)

    def test_equal_area_synthetic_input(self):
        for lat in (0,35.7,65):
            p=equal_area_patch(139.58,lat)
            self.assertAlmostEqual(geodesic_area(p),100e6,delta=.1)

    def test_synthetic_density_bias(self):
        d=synthetic_density()
        self.assertTrue(np.allclose(d.true_density,10))
        self.assertTrue(np.allclose(d[d.crs.eq(8857)].apparent_density,10,atol=1e-5))
        self.assertTrue(np.all(np.diff(d[d.crs.eq(3857)].apparent_density)<0))

    def test_no_nonfinite_transforms(self):
        for code in (3857,6677,8857):
            self.assertTrue(np.isfinite(transformer(code).transform(self.lon,self.lat)).all())


if __name__=='__main__':unittest.main()
