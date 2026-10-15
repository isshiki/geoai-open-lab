"""Synthetic data only: identities, geometry, scaling, exclusions and audit."""
import unittest
import numpy as np
import pandas as pd
from shapely.geometry import LineString,box
from geoai_open_lab.similar_regions import rank_regions,overlap_audit,FEATURES,CATEGORIES
from geoai_open_lab.tokyo_region_features import square_runs,validate_acquisition
from geoai_open_lab.region_features import assign_cells,make_grid,summarize_grid,region_profile,REGION_COLUMNS
from geoai_open_lab.tokyo_stations import representative,select_stations


def population(n=30):
    rng=np.random.default_rng(42)
    ids=[f'synthetic-{i:02d}' for i in range(n)]
    profiles=pd.DataFrame(rng.uniform(.01,.15,(n,8)),columns=FEATURES)
    profiles['region_id']=ids
    profiles['poi_count']=np.arange(1,n+1)
    profiles['poi_density_per_km2']=np.arange(1,n+1)*20.
    profiles['peak_to_mean_density_250m']=np.linspace(1,8,n)
    stations=pd.DataFrame(dict(region_id=ids,station_name=ids,x=np.arange(n)*1500.,y=0.,longitude=139.,latitude=35.))
    return profiles,stations


class SimilarRegionTests(unittest.TestCase):
    def test_acquisition_coverage_and_filters(self):
        from geoai_open_lab.tokyo_stations import N03_SHA256
        from geoai_open_lab.station_square import N02_SHA256
        _,s=population(3)
        m=dict(coverage_complete=True,release='2026-09-23.0',schema_version='v2.0.0',
            limit=None,country_filter=None,status_filter=None,confidence_filter=None,station_count=3,
            official_sha256={'N02-25_GML.zip':N02_SHA256,'N03-20260101_13_GML.zip':N03_SHA256},
            all_square_projected_bounds=[-500,-500,3500,500],
            acquisition_bbox=dict(west=130,south=30,east=145,north=40))
        validate_acquisition(m,s)
        for k,v in [('coverage_complete',False),('limit',500),('release','latest'),('status_filter','open'),
                ('all_square_projected_bounds',[0,0,3000,0]),('acquisition_bbox',dict(west=0,south=0,east=1,north=1))]:
            with self.assertRaises(ValueError):validate_acquisition({**m,k:v},s)

    def test_square_boundary_and_legacy_equivalence(self):
        center={'x':-22941.702420628444,'y':-32905.06120966877}
        w,s=center['x']-500,center['y']-500
        frame=pd.DataFrame(dict(id=list('abcd'),x=[w,w+250,w+1000,w+500],
            y=[s,s+250,s+1000,s+500],basic_category=['cafe',None,'other','restaurant'],operating_status=[None]*4))
        groups={'cafe':['cafe'],'restaurant':['restaurant']}
        runs=square_runs(frame,center,groups)
        for size in (250,500):
            grid=make_grid(box(w,s,w+1000,s+1000),size,(w,s))
            expected,_,_=summarize_grid(assign_cells(frame,grid,size,(w,s)),grid,groups)
            pd.testing.assert_series_equal(runs[size][0].poi_count,expected.poi_count)
            self.assertEqual(len(runs[size][0]),(1000//size)**2)
        profile=region_profile(runs,'test','test')
        self.assertEqual(list(profile),list(REGION_COLUMNS))
        self.assertEqual(profile.poi_count.iloc[0],4)
        self.assertEqual(profile.area_km2.iloc[0],1)

    def test_non_binary_center_no_slivers(self):
        frame=pd.DataFrame(dict(id=[],x=[],y=[],basic_category=[],operating_status=[]))
        for center in ({'x':12345.123456789,'y':-23456.987654321},{'x':-.00000000001,'y':.00000000003}):
            runs=square_runs(frame,center,{})
            self.assertEqual(len(runs[250][0]),16)
            self.assertFalse(runs[250][0].partial_cell.any())
            p=region_profile(runs,'test','test')
            self.assertTrue(np.isnan(p.cafe_share.iloc[0]))

    def test_outside_duplicates_nonfinite(self):
        for xs,ids in [([501],['a']),([0,0],['a','a']),([np.nan],['a'])]:
            f=pd.DataFrame(dict(id=ids,x=xs,y=[0]*len(xs),basic_category=['cafe']*len(xs),operating_status=[None]*len(xs)))
            with self.assertRaises(ValueError):square_runs(f,{'x':0,'y':0},{})

    def test_overlap_positive_area_and_edge_contact(self):
        _,s=population(4);s['x']=[0,999,1000,1500]
        a=overlap_audit(s,'synthetic-00')
        self.assertEqual(a.excluded_from_main.tolist(),[True,True,False,False])
        self.assertEqual(a.overlap_m2.iloc[1],1000)

    def test_self_zero_ties_determinism_and_contributions(self):
        p,s=population();p.loc[1,list(FEATURES)]=p.loc[0,list(FEATURES)].to_numpy()
        r,st,a,sc=rank_regions(p,s,'synthetic-00')
        r2,_,_,_=rank_regions(p.sample(frac=1,random_state=2),s.sample(frac=1,random_state=3),'synthetic-00')
        for mode in r:
            pd.testing.assert_frame_equal(r[mode],r2[mode])
            self.assertNotIn('synthetic-00',r[mode].region_id.tolist())
            z=r[mode].query('distance==0')
            self.assertTrue(z[['density_contribution','composition_contribution','concentration_contribution']].isna().all().all())
        self.assertEqual(st.set_index('mode').loc['main','top10_overlap'],10)
        first=r['main'].iloc[-1]; ident=first.region_id
        v=p.set_index('region_id')[list(FEATURES)].copy()
        v[FEATURES[0]]=np.log1p(v[FEATURES[0]]);v[FEATURES[-1]]=np.log1p(v[FEATURES[-1]])
        z=(v-v.median())/(v.quantile(.75)-v.quantile(.25))
        d=(z.loc[ident]-z.loc['synthetic-00'])**2
        self.assertAlmostEqual(first.composition_squared,d[list(CATEGORIES)].sum()/6)
        self.assertAlmostEqual(first.distance**2,first.density_squared+first.composition_squared+first.concentration_squared)

    def test_zero_count_kept_out_of_scaler(self):
        p,s=population();p.loc[1,'poi_count']=0;p.loc[1,list(FEATURES)]=np.nan
        r,_,_,sc=rank_regions(p,s,'synthetic-00')
        self.assertEqual(sc['zero_count_excluded'],['synthetic-01'])
        self.assertEqual(len(sc['fit_region_ids']),29)

    def test_zero_iqr_and_nan_fail(self):
        p,s=population();p['cafe_share']=.1
        with self.assertRaisesRegex(ValueError,'Zero IQR'):rank_regions(p,s,'synthetic-00')
        p,s=population();p.loc[2,'cafe_share']=np.nan
        with self.assertRaises(ValueError):rank_regions(p,s,'synthetic-00')

    def test_missing_identity_fails(self):
        p,s=population()
        with self.assertRaises(ValueError):rank_regions(p.iloc[:-1],s,'synthetic-00')

    def test_sensitivity_components(self):
        p,s=population();r,st,_,_=rank_regions(p,s,'synthetic-00')
        self.assertTrue((r['no_density'].density_squared==0).all())
        self.assertTrue((r['no_concentration'].concentration_squared==0).all())
        self.assertTrue((r['density_only'].composition_squared==0).all())
        self.assertTrue(st.top10_overlap.between(0,10).all())

    def test_disconnected_longest_and_tie_deterministic(self):
        lines=[LineString([(0,0),(2,0)]),LineString([(0,5),(4,5)])]
        a,disc=representative(lines);b,_=representative(lines[::-1])
        self.assertTrue(disc);self.assertEqual(a,b);self.assertEqual((a.x,a.y),(2,5))
        with self.assertRaises(ValueError):representative([])

    def test_station_group_and_boundary(self):
        from pyproj import Transformer
        t=Transformer.from_crs(6668,6677,always_xy=True)
        line=LineString([(139.5,35.7),(139.501,35.7)])
        from shapely.ops import transform
        midpoint=transform(t.transform,line).interpolate(.5,normalized=True)
        def feature(code,group):
            return dict(properties=dict(N02_005g=group,N02_005c=code,N02_005='合成駅',N02_001='11'),geometry=line.__geo_interface__)
        boundary=box(midpoint.x,midpoint.y-100,midpoint.x+100,midpoint.y+100)
        s=select_stations([feature('a','a'),feature('b','a'),feature('c','c')],boundary)
        self.assertEqual(len(s),2);self.assertTrue(s.on_boundary.all());self.assertTrue(s.same_name_other_group.all())
        with self.assertRaises(ValueError):select_stations([feature('b','a')],boundary)


if __name__=='__main__':unittest.main()
