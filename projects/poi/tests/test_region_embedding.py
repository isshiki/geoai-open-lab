import unittest
import numpy as np
import pandas as pd
from scipy import sparse
from geoai_open_lab.embedding_input import count_matrix
from geoai_open_lab.region_embedding import tfidf,embed,neighbor_order,retention,ranking


class EmbeddingTests(unittest.TestCase):
    def test_shared_poi_split_conserves_counts(self):
        incidence=sparse.csr_matrix([[1,1,0,1],[0,1,1,0]])
        codes=np.array([0,1,0,-1]);chosen=np.array([1,0,1,0])
        a=count_matrix(incidence,codes,2,chosen)
        b=count_matrix(incidence,codes,2,1-chosen)
        np.testing.assert_array_equal((a+b).toarray(),[[1,1],[1,1]])
        np.testing.assert_array_equal(b.toarray()[:,1],[1,1])

    def test_tfidf_formula_and_zero_row(self):
        counts=sparse.csr_matrix([[2,1,0],[0,1,1],[0,0,0]])
        x,model=tfidf(counts)
        expected=np.log(4/np.array([2,3,2]))+1
        np.testing.assert_allclose(model.idf_,expected)
        raw=np.array([2,1,0])*expected
        np.testing.assert_allclose(x.toarray()[0],raw/np.linalg.norm(raw))
        self.assertEqual(x[2].nnz,0)

    def test_reduced_fit_idf(self):
        c=sparse.csr_matrix([[1,0],[1,1],[0,1]])
        x,m=tfidf(c,[0,1])
        np.testing.assert_allclose(m.idf_,[1,1+np.log(3/2)])
        self.assertEqual(x.shape,(3,2))

    def test_seed_and_norm(self):
        x=sparse.csr_matrix(np.random.default_rng(3).random((20,12)))
        a,_=embed(x,4);b,_=embed(x,4)
        np.testing.assert_array_equal(a,b)
        np.testing.assert_allclose(np.linalg.norm(a,axis=1),1)

    def test_dimension_rejected_against_fit_subset(self):
        x=sparse.eye(12,format='csr')
        for dim,keep in [(0,None),(12,None),(4,[0,1,2])]:
            with self.assertRaises(ValueError):embed(x,dim,fit_rows=keep)

    def test_overlap_boundary_ties_and_invalid(self):
        s=pd.DataFrame({'region_id':['a','b','c','d'],'station_name':['A','B','C','D'],
                        'x':[0,999,1000,2000],'y':[0,0,0,0]})
        x=np.ones((4,2));ii,d=neighbor_order(x,s)
        self.assertTrue(np.isinf(d[0,1]));self.assertTrue(np.isfinite(d[0,2]))
        self.assertEqual(ranking(ii,d,s,0).region_id.tolist(),['c','d'])
        ii,d=neighbor_order(x,s,valid=[True,True,False,True])
        self.assertEqual(ranking(ii,d,s,0).region_id.tolist(),['d'])

    def test_top10_retention(self):
        a=np.arange(15)[None,:]; b=np.roll(a,5,axis=1)
        self.assertEqual(retention(a,b)[0],.5)
        self.assertTrue(np.isnan(retention(a,b,[False])[0]))

    def test_exact_category_contribution(self):
        x,_=tfidf(sparse.csr_matrix(np.random.default_rng(5).integers(0,20,(20,12))))
        z,m=embed(x,4); raw=m.transform(x)
        contributions=x[0].toarray().ravel()*(raw[1]@m.components_)/(np.linalg.norm(raw[0])*np.linalg.norm(raw[1]))
        self.assertAlmostEqual(contributions.sum(),z[0]@z[1])


if __name__=='__main__':unittest.main()
