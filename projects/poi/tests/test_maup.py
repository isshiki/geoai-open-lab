import unittest
import numpy as np
import pandas as pd
from shapely.geometry import box
from shapely.ops import unary_union
from geoai_open_lab.maup import partition,summaries,SCHEMES,SHARE_GROUPS

class MaupTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({'x':[-2000,-1750,0,2000,2000], 'y':[-2000,-1750,0,2000,-2000], 'group':['restaurant','cafe','bar','__OTHER__','__MISSING__']})
    def test_exact_partition_geometry(self):
        for name,(w,h) in SCHEMES.items():
            t,ids=partition(self.frame(),(0,0),w,h)
            polygons=[box(r.west,r.south,r.west+w,r.south+h) for r in t.itertuples()]
            union=unary_union(polygons)
            self.assertTrue(union.equals(box(-2000,-2000,2000,2000)))
            self.assertEqual(sum(p.area for p in polygons),union.area)
            self.assertEqual(len(t),16000000//(w*h))
            self.assertTrue((t.area_km2==w*h/1e6).all())
            self.assertEqual(t.poi_count.sum(),5);self.assertEqual(len(ids),5)
    def test_internal_and_outer_boundaries(self):
        t,ids=partition(self.frame(),(0,0),250,250)
        np.testing.assert_array_equal(ids,[0,17,136,255,15])
    def test_no_clipping_outside(self):
        f=self.frame();f.loc[0,'x']=-2001
        with self.assertRaises(ValueError):partition(f,(0,0),500,500)
    def test_empty_cells_undefined_shares(self):
        t,_=partition(self.frame(),(0,0),500,500)
        self.assertTrue(t.loc[t.poi_count==0,'restaurant_share'].isna().all())
        self.assertTrue(t.loc[t.poi_count==0,'density_per_km2'].eq(0).all())
        self.assertTrue(np.allclose(t.filter(like='_share').sum(axis=1)[t.poi_count>0],1))
    def test_repeat_and_all_pairs(self):
        tables=[]
        for s,(w,h) in SCHEMES.items():
            a,_=partition(self.frame(),(0,0),w,h);b,_=partition(self.frame(),(0,0),w,h)
            pd.testing.assert_frame_equal(a,b);tables.append(a.assign(scheme=s))
        stats,cor=summaries(pd.concat(tables))
        self.assertEqual(len(cor),75)
        self.assertTrue((cor.groupby('scheme').size()==15).all())
        self.assertTrue(cor[cor['first'].eq('fashion')].rho.isna().all())
    def test_non_tiling_rejected(self):
        with self.assertRaises(ValueError):partition(self.frame(),(0,0),600,500)

    def test_saved_input_replay_and_real_totals(self):
        import json
        from geoai_open_lab.maup import OUT, RAW, run
        from geoai_open_lab.region_clustering import digest
        if not (RAW/'places.parquet').exists() or not (OUT/'manifest.json').exists():
            self.skipTest('Fixed local inputs unavailable')
        before=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))['output_sha256']
        c,s,r,m,_=run()
        self.assertEqual(before,m['output_sha256'])
        self.assertEqual(c.groupby('scheme').poi_count.sum().nunique(),1)
        self.assertEqual(c.groupby('scheme').poi_count.sum().iloc[0],m['poi_count'])
        self.assertEqual(len(r),75)
        for scheme,t in c.groupby('scheme'):
            self.assertAlmostEqual(t.area_km2.sum(),16)
            self.assertAlmostEqual(t.density_per_km2.mean(),m['poi_count']/16)
            rho=t[['restaurant_count','cafe_count']].corr(method='spearman').iloc[0,1]
            expected=r[(r.scheme==scheme)&(r['first']=='restaurant')&(r.second=='cafe')].rho.iloc[0]
            self.assertAlmostEqual(rho,expected)

if __name__=='__main__':unittest.main()
