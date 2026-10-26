import unittest
import numpy as np
from geoai_open_lab.urban_function import grid,minmax,memberships,radii,field,fixed_counts,comparison


class UrbanFunctionTests(unittest.TestCase):
    def test_grid_area_and_centers(self):
        for size,n in [(100,1600),(250,256)]:
            g=grid([0,0],size)
            self.assertEqual(len(g),n)
            self.assertEqual(n*size*size,16000000)
            self.assertEqual(g.x.min(),-2000+size/2)
    def test_grid_invalid(self):
        with self.assertRaises(ValueError):grid([0,0],300)
    def test_boundary_counts(self):
        pts=[[-2000,-2000],[2000,2000],[0,0]]
        z=fixed_counts(pts,[0,0],100)
        self.assertEqual(z.sum(),3)
        self.assertEqual(z[0],1);self.assertEqual(z[-1],1);self.assertEqual(z[820],1)
    def test_outside(self):
        with self.assertRaises(ValueError):fixed_counts([[2001,0]],[0,0],100)
    def test_gaussian_equation_and_no_cutoff(self):
        z=field([[0,0]],[[0,0],[10,0],[20,0]],10)
        np.testing.assert_allclose(z,[1,np.exp(-.5),np.exp(-2)])
    def test_superposition(self):
        np.testing.assert_allclose(field([[0,0],[0,0]],[[0,0]],10),[2])
    def test_invalid_bandwidth(self):
        with self.assertRaises(ValueError):field([[0,0]],[[0,0]],0)
    def test_normalize_before_membership(self):
        z=np.array([[0,0],[5,100],[10,50.]])
        mu=memberships(z)
        self.assertTrue(np.isnan(mu[0]).all())
        np.testing.assert_allclose(mu[1],[1/3,2/3])
        np.testing.assert_allclose(mu[2],[2/3,1/3])
    def test_constant_field(self):
        np.testing.assert_equal(minmax([1,1]),[0,0])
        self.assertTrue(np.isnan(memberships(np.ones((3,2)))).all())
    def test_bad_input(self):
        with self.assertRaises(ValueError):minmax([1,np.nan])
    def test_knn_and_logistic(self):
        p=np.column_stack([np.arange(12.)*10,np.zeros(12)])
        t=radii(p,5)
        self.assertEqual(t.knn_distance_m.iloc[0],50)
        np.testing.assert_allclose(t.density,5/(np.pi*t.knn_distance_m**2))
        self.assertTrue((t.h_m>=t.h_min).all() and (t.h_m<=t.h_max).all())
        np.testing.assert_allclose(t.h_m,t.h_min+(t.h_max-t.h_min)/(1+np.exp(-4*(t.C-.5))))
    def test_distinct_locations(self):
        p=np.column_stack([np.arange(12.)*10,np.zeros(12)])
        t=radii(np.vstack([p,p[0]]),5)
        self.assertEqual(t.knn_distance_m.iloc[0],t.knn_distance_m.iloc[-1])
    def test_insufficient_residential(self):
        with self.assertRaises(ValueError):radii([[0,0]],5)
    def test_repeat_and_identity(self):
        p=np.column_stack([np.arange(12.)*10,np.zeros(12)])
        np.testing.assert_array_equal(radii(p).h_m,radii(p).h_m)
        a=np.array([[.2,.8],[.7,.3]])
        r=comparison(a,a)
        self.assertEqual(r['mae'],0);self.assertEqual(r['dominant_agreement'],1)


if __name__=='__main__':unittest.main()
