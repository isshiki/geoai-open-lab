import unittest
import numpy as np
import pandas as pd
from geoai_open_lab.aoi_sensitivity import grid_counts, common_mask, alignment, orders, OUT, BASE

class SensitivityTests(unittest.TestCase):
    def test_grid_areas_and_boundary_uniqueness(self):
        for h in (500,600,700,800):
            xy=np.array([[-h,-h],[h,h],[0,0],[250,250],[-250,-250]])
            counts,areas=grid_counts(xy,(0,0),h)
            self.assertEqual(counts.sum(),5)
            self.assertEqual(areas.sum(),(2*h)**2)
            self.assertTrue(np.all(areas>0))
        self.assertEqual(grid_counts(np.empty((0,2)),(0,0),500)[0].shape,(4,4))
    def test_outside_is_not_zero(self):
        with self.assertRaises(ValueError): grid_counts([[801,0]],(0,0),800)
    def test_overlap_positive_area(self):
        stations=pd.DataFrame({'x':[0,1599,1600],'y':[0,0,0]})
        mask=common_mask(stations)
        self.assertFalse(mask[0,1]);self.assertTrue(mask[0,2])
        self.assertFalse(mask.diagonal().any())
    def test_permuted_clusters_match(self):
        base=np.array([1,1,2,2,3]);other=np.array([3,3,1,1,2])
        matched,_,cross=alignment(base,other)
        np.testing.assert_array_equal(matched,base)
        self.assertEqual(cross.sum(),len(base))
    def test_ties_use_input_id_order(self):
        x=np.zeros((12,2));mask=~np.eye(12,dtype=bool)
        order,_=orders(x,mask,'euclidean')
        np.testing.assert_array_equal(order[0,:10],np.arange(1,11))

    @unittest.skipUnless((OUT/'features.csv').exists(),'Local generated results unavailable')
    def test_real_baseline_and_area_conservation(self):
        from scipy import sparse
        from geoai_open_lab.region_clustering import load_inputs
        expected,_,_,_=load_inputs()
        frame=pd.read_csv(OUT/'features.csv')
        np.testing.assert_allclose(frame[frame.half_width_m==500].iloc[:,2:-1],expected.iloc[:,2:],rtol=0,atol=1e-9)
        for h,t in frame.groupby('half_width_m'):
            self.assertEqual(len(t),656);self.assertTrue(t.region_id.is_unique)
            np.testing.assert_allclose(t.area_km2,(2*h/1000)**2,rtol=0,atol=1e-12)
            np.testing.assert_allclose(t.poi_count/t.area_km2,t.poi_density_per_km2)
            shares=[c for c in t.columns if c.endswith('_share')]
            np.testing.assert_allclose(t[shares].sum(axis=1),1)
            np.testing.assert_allclose(t.peak_density_250m/t.poi_density_per_km2,t.peak_to_mean_density_250m)
            self.assertEqual(sparse.load_npz(OUT/f'counts_{h}.npz').shape,(656,961))
        self.assertEqual((sparse.load_npz(OUT/'counts_500.npz')!=sparse.load_npz(BASE/'category_counts.npz')).nnz,0)
        np.testing.assert_allclose(np.load(OUT/'embedding_500.npy'),np.load(BASE/'embedding_64.npy'),rtol=0,atol=1e-10)

    @unittest.skipUnless((OUT/'assignments.csv').exists(),'Local generated results unavailable')
    def test_real_cluster_metrics_and_candidate_sets(self):
        from sklearn.metrics import adjusted_rand_score
        a=pd.read_csv(OUT/'assignments.csv');metrics=pd.read_csv(OUT/'cluster_metrics.csv')
        for r in metrics.itertuples():
            t=a[(a.half_width_m==r.half_width_m)&(a['mode']==r.mode)]
            self.assertEqual(len(t),656);self.assertTrue(t.region_id.is_unique)
            self.assertEqual(sum(t.cluster!=t.baseline_cluster),r.changed)
            self.assertAlmostEqual(adjusted_rand_score(t.baseline_cluster,t.cluster),r.ari)
        audit=pd.read_csv(OUT/'audit.csv')
        self.assertTrue((audit.groupby('region_id').candidate_count.nunique()==1).all())

if __name__=='__main__': unittest.main()
