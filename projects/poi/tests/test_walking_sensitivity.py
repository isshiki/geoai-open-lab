import json
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import pandas as pd
from geoai_open_lab import walking_sensitivity as w

class WalkingSensitivityTests(unittest.TestCase):
    def test_masks_boundaries_and_nested(self):
        f=pd.DataFrame(dict(dx=[500,500.01,400,0],dy=[500,0,0,0],straight_m=[2**.5*500,500.01,400,0],road_distance_m=[800,801,400,np.nan]))
        m=w.masks(f)
        self.assertEqual(m['square'].tolist(),[True,False,True,True])
        self.assertEqual(m['road400'].tolist(),[False,False,True,False])
        self.assertEqual(m['straight500'].tolist(),[False,False,True,True])
    def test_undefined_and_rejected(self):
        f=pd.DataFrame({'group':pd.Series(dtype=str)})
        m={c:pd.Series(dtype=bool) for c in w.CONDITIONS}
        r=w.compare(f,m)
        self.assertTrue(all(np.isnan(x['jaccard']) and np.isnan(x['composition_tvd']) for x in r))
        r=w.compare(f,m,False)
        self.assertEqual(sum(x['valid'] for x in r),3)
    def test_counts_tvd_and_threshold(self):
        f=pd.DataFrame({'group':['cafe']*15+['other']*15})
        m={c:pd.Series([True]*30) for c in w.CONDITIONS};m['road500']=pd.Series([True]*15+[False]*15)
        r=[x for x in w.compare(f,m) if x['first']=='straight500' and x['second']=='road500'][0]
        self.assertEqual(r['jaccard'],.5);self.assertEqual(r['count_difference'],-15)
        self.assertEqual(r['composition_tvd'],.5);self.assertEqual(r['cafe_difference_pp'],50)
        self.assertFalse(r['low_poi'])
    def test_local_long_edge_and_zero_connectivity(self):
        n=pd.DataFrame(dict(node_id=[1,2,3,4,5],x=[-3000,0,0,3000,0],y=[0,0,0,0,3000]))
        e=pd.DataFrame(dict(u=[0,1,2,3],v=[1,2,3,4],length_m=[3000,0,3000,np.hypot(3000,3000)]))
        idx=w.RoadIndex(n,e);edges=idx.local((0,0),100)
        self.assertEqual(idx.zero_edges,1);self.assertEqual(len(edges),3)
        self.assertEqual([(x['u'],x['v']) for x in edges],[(1,2),(2,4),(4,5)])
        d,_,o=w.routing(edges,(0,0));self.assertEqual(d[1],3000);self.assertEqual(d[4],3000)
    def test_conservative_index_matches_brute_force(self):
        rng=np.random.default_rng(31);xy=rng.uniform(-2000,2000,(100,2))
        n=pd.DataFrame(dict(node_id=np.arange(100)+100,x=xy[:,0],y=xy[:,1]))
        uv=np.arange(100).reshape(-1,2);e=pd.DataFrame(dict(u=uv[:,0],v=uv[:,1],length_m=np.linalg.norm(xy[uv[:,0]]-xy[uv[:,1]],axis=1)))
        idx=w.RoadIndex(n,e)
        for center in [(0,0),(800,-1000)]:
            a,b=xy[uv[:,0]],xy[uv[:,1]]
            ok=(np.maximum(a,b)>=np.array(center)-900).all(axis=1)&(np.minimum(a,b)<=np.array(center)+900).all(axis=1)
            self.assertEqual([(r['u'],r['v']) for r in idx.local(center)],[(int(u+100),int(v+100)) for u,v in uv[ok]])
    def test_saved_full_audit(self):
        if not (w.OUT/'manifest.json').exists():self.skipTest('Local results absent')
        audit,counts,pairs,dist=w.load_results()
        self.assertEqual(len(audit),656);self.assertTrue(audit.region_id.is_unique)
        self.assertEqual(len(counts),656*7);self.assertEqual(len(pairs),656*8)
        recomputed=[]
        for r in audit.itertuples():
            t=pd.read_parquet(w.OUT/'stations'/f'{r.region_id}.parquet')
            self.assertTrue(t.id.is_unique)
            ms=w.masks(t)
            for key,m in ms.items():
                self.assertTrue(np.array_equal(t[key],m))
                c=counts[(counts.region_id==r.region_id)&(counts.condition==key)].iloc[0]
                self.assertEqual(c.poi_count,int(m.sum()))
                self.assertEqual(sum(c[g+'_count'] for g in w.GROUPS),c.poi_count)
                if c.poi_count:self.assertAlmostEqual(sum(c[g+'_share'] for g in w.GROUPS),1)
            recomputed.extend([dict(region_id=r.region_id,station_name=r.station_name,**v) for v in w.compare(t,ms,r.valid)])
        pd.testing.assert_frame_equal(pd.DataFrame(recomputed),pairs,check_dtype=False,atol=1e-10)
        pd.testing.assert_frame_equal(w.summarize(pairs),dist,check_dtype=False,atol=1e-10)
        w.verify_baseline(pd.read_parquet(w.OUT/'stations/n02-003584.parquet'))
    def test_notebook11_unchanged(self):
        if not (w.OUT/'manifest.json').exists():self.skipTest('Local results absent')
        m=json.loads((w.OUT/'manifest.json').read_text(encoding='utf8'))
        for name,h in m['old_artifacts_sha256'].items():self.assertEqual(w.digest(w.OLD/name),h,name)

if __name__=='__main__':unittest.main()
