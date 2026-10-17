import json
import unittest
import numpy as np
import pandas as pd
from geoai_open_lab.aoi_full_cells import full_cell_features, OUT, ORIGINAL, PEAK, RATIO
from geoai_open_lab.aoi_sensitivity import grid_counts
from geoai_open_lab.region_clustering import digest, load_inputs, transform


class FullCellTests(unittest.TestCase):
    def test_only_two_columns_change(self):
        frame=pd.DataFrame({'region_id':['a','b'],PEAK:[100.,200.],RATIO:[10.,10.],
                            'poi_density_per_km2':[10.,20.],'cafe_share':[.1,.2]})
        audit=pd.DataFrame({'region_id':['b','a'],'full_cell_peak':[120.,80.]})
        result=full_cell_features(frame,audit)
        np.testing.assert_array_equal(result[PEAK],[80.,120.])
        np.testing.assert_array_equal(result[RATIO],[8.,6.])
        pd.testing.assert_frame_equal(frame.drop(columns=[PEAK,RATIO]),result.drop(columns=[PEAK,RATIO]))

    def test_invalid_audit_rejected(self):
        frame=pd.DataFrame({'region_id':['a'],PEAK:[100.],RATIO:[10.],'poi_density_per_km2':[10.]})
        for ids,values in [(['x'],[50]),(['a','a'],[50,50]),(['a'],[101]),(['a'],[np.nan])]:
            with self.assertRaises(ValueError):full_cell_features(frame,pd.DataFrame({'region_id':ids,'full_cell_peak':values}))

    def test_corner_peak_excluded_but_count_retained(self):
        counts,areas=grid_counts(np.array([[799,799],[10,10]]),(0,0),800)
        self.assertEqual(counts.sum(),2)
        self.assertEqual((counts/(areas/1e6)).max(),400)
        self.assertEqual((counts/(areas/1e6))[areas==62500].max(),16)

    def test_full_cell_support(self):
        for h,n in [(500,16),(600,16),(700,16),(800,36)]:
            _,areas=grid_counts(np.empty((0,2)),(0,0),h)
            self.assertEqual((areas==62500).sum(),n)

    @unittest.skipUnless((OUT/'manifest.json').exists(),'Local results unavailable')
    def test_real_features_baseline_and_protected_outputs(self):
        m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
        for name,h in m['original_files_sha256'].items():self.assertEqual(digest(ORIGINAL/name),h)
        old=pd.read_csv(ORIGINAL/'features.csv');new=pd.read_csv(OUT/'features.csv')
        pd.testing.assert_frame_equal(old.drop(columns=[PEAK,RATIO]),new.drop(columns=[PEAK,RATIO]))
        np.testing.assert_allclose(new[PEAK]/new.poi_density_per_km2,new[RATIO])
        np.testing.assert_allclose(transform(old[old.half_width_m==500])[0],transform(new[new.half_width_m==500])[0],rtol=0,atol=1e-12)
        for name in ('rankings.csv','station_stability.csv'):
            a=pd.read_csv(ORIGINAL/name);b=pd.read_csv(OUT/name)
            cols=a.columns
            pd.testing.assert_frame_equal(a[a['mode']!='A'].reset_index(drop=True),b[b['mode']!='A'][cols].reset_index(drop=True))

    @unittest.skipUnless((OUT/'comparison_station.csv').exists(),'Local results unavailable')
    def test_summary_recomputed_from_656_rows(self):
        rows=pd.read_csv(OUT/'comparison_station.csv');s=pd.read_csv(OUT/'comparison_summary.csv')
        for r in s.itertuples():
            t=rows[(rows.comparison==r.comparison)&(rows.half_width_m==r.half_width_m)]
            self.assertEqual(len(t),656);self.assertTrue(t.region_id.is_unique)
            self.assertAlmostEqual(t.common_top10.mean(),r.common_mean)
            self.assertAlmostEqual(t.spearman.mean(),r.spearman_mean)


if __name__=='__main__':unittest.main()
