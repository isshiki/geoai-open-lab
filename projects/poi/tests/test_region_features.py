"""Synthetic fixtures only; no downloads and no real POI samples."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from shapely.geometry import box
from geoai_open_lab.region_features import (make_grid, assign_cells,
    summarize_grid, cell_index, MISSING, OTHER, load_inputs)


def fixture(points, categories=None):
    n=len(points)
    return pd.DataFrame(dict(id=[f'invented-{i}' for i in range(n)],
        x=[p[0] for p in points], y=[p[1] for p in points],
        basic_category=categories or ['cafe']*n, operating_status=[None]*n,
        taxonomy_alternates=[['bar','restaurant'] for _ in points]))


class RegionFeaturesTests(unittest.TestCase):
    def test_boundary_unique_and_inclusive_outer_edge(self):
        grid=make_grid(box(0,0,500,500),250)
        p=fixture([(0,0),(250,250),(500,500),(250,0),(0,250)])
        a=assign_cells(p,grid,250)
        self.assertEqual(len(a),len(p))
        self.assertFalse(a.id.duplicated().any())
        self.assertEqual(a.cell_id.tolist(),['250:0:0','250:1:1','250:1:1','250:1:0','250:0:1'])

    def test_negative_coordinates_floor(self):
        self.assertEqual(cell_index(-.1,250),-1)
        self.assertEqual(cell_index(-250,250),-1)
        self.assertEqual(cell_index(-250.1,250),-2)

    def test_clipped_area_density_and_empty_share(self):
        grid=make_grid(box(0,0,300,250),250)
        a=assign_cells(fixture([(275,10)]),grid,250)
        c,t,_=summarize_grid(a,grid,{'cafe':['cafe']})
        edge=c[c.ix==1].iloc[0]
        self.assertEqual(edge.area_m2,12500)
        self.assertEqual(edge.density_per_km2,80)
        self.assertEqual(c.area_m2.sum(),75000)
        empty=t['category'].query('denominator==0')
        self.assertTrue(empty.share.isna().all())
        self.assertTrue((empty['count']==0).all())

    def test_category_denominator_and_alternates_not_exploded(self):
        g=make_grid(box(0,0,250,250),250)
        a=assign_cells(fixture([(1,1)]*4,['cafe',None,'bar','unknown_category']),g,250)
        c,t,f=summarize_grid(a,g,{'cafe':['cafe']})
        self.assertEqual(c.poi_count.sum(),4)
        self.assertEqual(t['category']['count'].sum(),4)
        self.assertEqual(set(t['category'].denominator),{4})
        self.assertEqual(t['category'].share.sum(),1)
        self.assertEqual(t['display_group'].set_index('display_group').loc[OTHER,'count'],2)
        self.assertEqual(t['display_group'].set_index('display_group').loc[MISSING,'count'],1)
        self.assertEqual(t['status'].set_index('status').loc[MISSING,'count'],4)

    def test_incomplete_is_not_zero(self):
        g=make_grid(box(0,0,250,250),250)
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            summarize_grid(fixture([]),g,{},coverage_complete=False)

    def test_nested_grids_reconcile_area_and_counts(self):
        poly=box(-310,-410,520,610)
        p=fixture([(-300,-400),(-.1,0),(0,0),(250,250),(500,500),(520,610)])
        results=[]
        for size in [250,500]:
            g=make_grid(poly,size)
            c,_,_=summarize_grid(assign_cells(p,g,size),g,{})
            self.assertEqual(c.poi_count.sum(),len(p))
            self.assertAlmostEqual(c.area_m2.sum(),poly.area)
            results.append(c)
        fine,coarse=results
        rolled=fine.assign(ix=fine.ix//2,iy=fine.iy//2).groupby(['ix','iy']).poi_count.sum()
        pd.testing.assert_series_equal(rolled,coarse.set_index(['ix','iy']).poi_count.sort_index())

    def test_outside_and_duplicate_rejected(self):
        g=make_grid(box(0,0,250,250),250)
        with self.assertRaises(ValueError):assign_cells(fixture([(251,1)]),g,250)
        p=fixture([(1,1)]*2);p['id']='duplicate'
        with self.assertRaises(ValueError):assign_cells(p,g,250)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):assign_cells(fixture([(np.nan,1)]),make_grid(box(0,0,250,250),250),250)

    def test_overlapping_display_mapping_rejected(self):
        g=make_grid(box(0,0,250,250),250)
        a=assign_cells(fixture([(1,1)]),g,250)
        with self.assertRaises(ValueError):summarize_grid(a,g,{'one':['cafe'],'two':['cafe']})

    def test_input_hash_failure_stops_before_read(self):
        with patch('geoai_open_lab.region_features.digest',return_value='bad'):
            with self.assertRaisesRegex(ValueError,'hash mismatch'):load_inputs()
