import unittest
import tempfile
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_samples, adjusted_rand_score
from geoai_open_lab.region_clustering import (transform, fit_kmeans, scores,
    ordered_labels, describe_clusters, overlap_pairs, independent_subset, load_inputs, digest)
from geoai_open_lab.similar_regions import FEATURES, CATEGORIES


def fixture():
    rng=np.random.default_rng(17)
    x=np.vstack([rng.normal(i*7,.3,(12,8)) for i in range(3)])
    frame=pd.DataFrame(np.exp(x/10),columns=FEATURES)
    frame['poi_count']=100
    frame['region_id']=[f'r{i:03}' for i in range(len(x))]
    stations=frame[['region_id']].copy()
    stations['station_name']=stations.region_id
    stations['x']=np.arange(len(x))*1100.; stations['y']=0.
    return frame,stations


class ClusteringTests(unittest.TestCase):
    def test_pinned_input_hash_rows_and_ids(self):
        f,s=fixture()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            f.to_csv(p/'region_features.csv',index=False);s.to_csv(p/'stations.csv',index=False)
            manifest={'columns':list(f.columns),'output_sha256':{name:digest(p/name) for name in ('region_features.csv','stations.csv')}}
            (p/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
            cfg=p/'config.toml'
            def config(rows):
                cfg.write_text(f'input_dir = "{p.as_posix()}"\nmanifest_sha256 = "{digest(p/"manifest.json")}"\nexpected_rows = {rows}\n',encoding='utf8')
            config(len(f));self.assertEqual(len(load_inputs(cfg)[0]),len(f))
            config(len(f)+1)
            with self.assertRaises(ValueError):load_inputs(cfg)
            config(len(f));(p/'stations.csv').write_text('changed',encoding='utf8')
            with self.assertRaises(ValueError):load_inputs(cfg)

    def test_exact_transform(self):
        frame,_=fixture(); x,meta=transform(frame)
        values=frame[list(FEATURES)].copy()
        values.iloc[:,[0,7]]=np.log1p(values.iloc[:,[0,7]])
        expected=(values-values.median())/(values.quantile(.75)-values.quantile(.25))
        expected[list(CATEGORIES)]/=np.sqrt(6)
        np.testing.assert_allclose(x,expected)
        self.assertEqual(meta['columns'],list(FEATURES))

    def test_reject_bad_inputs(self):
        original,_=fixture()
        for mode in ('duplicate','missingid','nan','infinite','zero','iqr'):
            f=original.copy()
            if mode=='duplicate': f.loc[0,'region_id']=f.loc[1,'region_id']
            if mode=='missingid': f.loc[0,'region_id']=None
            if mode=='nan': f.loc[0,FEATURES[1]]=np.nan
            if mode=='infinite': f.loc[0,FEATURES[1]]=np.inf
            if mode=='zero': f.loc[0,'poi_count']=0
            if mode=='iqr': f[FEATURES[0]]=1.
            with self.subTest(mode=mode),self.assertRaises(ValueError): transform(f)

    def test_seed_and_assignment(self):
        f,_=fixture(); x,_=transform(f)
        a=fit_kmeans(x,3); b=fit_kmeans(x,3)
        np.testing.assert_array_equal(a.labels_,b.labels_)
        self.assertEqual(len(a.labels_),len(f))
        self.assertEqual(np.bincount(a.labels_).sum(),len(f))

    def test_canonical_labels_independent_of_numbering(self):
        f,_=fixture(); old=np.repeat([7,3,5],12)
        a=ordered_labels(f,old); b=ordered_labels(f,np.repeat([1,9,0],12))
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(a,np.repeat([1,2,3],12))

    def test_representatives_minimum_distance(self):
        f,s=fixture(); x,_=transform(f); lab=ordered_labels(f,fit_kmeans(x,3).labels_)
        summary,details=describe_clusters(f,s,x,lab)
        self.assertEqual(summary['count'].sum(),len(f))
        for row in summary.itertuples():
            ids=np.flatnonzero(lab==row.cluster)
            d=np.linalg.norm(x[ids]-x[ids].mean(axis=0),axis=1)
            nearest=f.iloc[ids[np.argmin(d)]].region_id
            self.assertEqual(row.representative_ids.split(';')[0],nearest)
        self.assertEqual(len(details),3*8)

    def test_metric_recalculation(self):
        f,_=fixture(); x,_=transform(f); labels=fit_kmeans(x,3).labels_
        result=scores(x,labels)
        self.assertAlmostEqual(result['silhouette'],silhouette_samples(x,labels).mean())
        centers=np.array([x[labels==i].mean(axis=0) for i in range(3)])
        counts=np.bincount(labels)
        between=(counts[:,None]*(centers-x.mean(axis=0))**2).sum()
        within=((x-centers[labels])**2).sum()
        self.assertAlmostEqual(result['calinski_harabasz'],between/2/(within/(len(x)-3)))
        scat=np.array([np.linalg.norm(x[labels==i]-centers[i],axis=1).mean() for i in range(3)])
        dist=np.linalg.norm(centers[:,None,:]-centers[None,:,:],axis=2)
        np.fill_diagonal(dist,np.inf)
        self.assertAlmostEqual(result['davies_bouldin'],((scat[:,None]+scat[None,:])/dist).max(axis=1).mean())

    def test_overlap_boundary_and_greedy(self):
        s=pd.DataFrame(dict(region_id=['b','a','c','d'],x=[500.,0.,1500.,0.],y=[0.,0.,0.,1000.]))
        pairs=overlap_pairs(s)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs.iloc[0].overlap_m2,500000.)
        kept=independent_subset(s)
        self.assertEqual(s.iloc[kept].region_id.tolist(),['a','c','d'])
        self.assertEqual(len(overlap_pairs(s.iloc[kept].reset_index(drop=True))),0)

    def test_ari_label_invariance(self):
        self.assertEqual(adjusted_rand_score([0,0,1,1],[8,8,2,2]),1)


if __name__=='__main__': unittest.main()
