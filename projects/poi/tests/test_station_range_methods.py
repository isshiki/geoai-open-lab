import json
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
import pandas as pd
from geoai_open_lab import station_range_methods as m

class ThreeMethodsTests(unittest.TestCase):
    def test_exact_nested_counts_and_tvd(self):
        f=pd.DataFrame(dict(group=['cafe','cafe','other','missing'],square=[True]*4,straight500=[True,True,True,False],road500=[True,False,False,False]))
        rows=m.compare(f)
        self.assertEqual([r['shared'] for r in rows],[3,1,1])
        self.assertEqual([r['count_difference'] for r in rows],[-1,-3,-2])
        np.testing.assert_allclose([r['jaccard'] for r in rows],[.75,.25,1/3])
        np.testing.assert_allclose([r['composition_tvd'] for r in rows],[.25,.5,1/3])
    def test_empty_and_invalid(self):
        f=pd.DataFrame({k:pd.Series(dtype=bool) for k in m.METHODS});f['group']=pd.Series(dtype=str)
        for r in m.compare(f):self.assertTrue(np.isnan(r['jaccard']) and np.isnan(r['composition_tvd']))
        self.assertEqual([r['valid'] for r in m.compare(f,False)],[True,False,False])
    def test_low_count_boundary(self):
        for n,expected in [(29,True),(30,False)]:
            f=pd.DataFrame(dict(group=['cafe']*n,**{c:[True]*n for c in m.METHODS}))
            self.assertTrue(all(r['low_poi']==expected for r in m.compare(f)))
    def test_saved_results_independently_reconciled(self):
        if not (m.OUT/'manifest.json').exists():self.skipTest('Saved artifacts absent')
        p=pd.read_csv(m.OUT/'comparisons.csv');c=pd.read_csv(m.OUT/'conditions.csv')
        self.assertEqual(len(p),656*3);self.assertEqual(p.region_id.nunique(),656)
        self.assertEqual(len(c),656*3)
        for rid,rows in p.groupby('region_id'):
            f=pd.read_parquet(m.ws.OUT/'stations'/f'{rid}.parquet')
            for r in rows.itertuples():
                first=set(f.loc[f[r.first],'id']);second=set(f.loc[f[r.second],'id'])
                self.assertEqual(r.shared,len(first&second));self.assertEqual(r.union,len(first|second))
                self.assertEqual(r.n_first,len(first));self.assertEqual(r.n_second,len(second))
                self.assertAlmostEqual(r.jaccard,len(first&second)/len(first|second))
                pa=f.loc[f[r.first],'group'].value_counts(normalize=True).reindex(m.ws.GROUPS,fill_value=0)
                pb=f.loc[f[r.second],'group'].value_counts(normalize=True).reindex(m.ws.GROUPS,fill_value=0)
                self.assertAlmostEqual(r.composition_tvd,float((pa-pb).abs().sum()/2))
        old=pd.read_csv(m.ws.OUT/'comparisons.csv')
        cols=list(p.columns)
        pd.testing.assert_frame_equal(p[p['first'].eq('straight500')].reset_index(drop=True),old[old['first'].eq('straight500')&old['second'].eq('road500')][cols].reset_index(drop=True),check_dtype=False)
        d=pd.read_csv(m.OUT/'distributions.csv')
        pd.testing.assert_frame_equal(m.ws.summarize(p),d,check_dtype=False)
    def test_existing_artifacts_unchanged(self):
        if not (m.OUT/'manifest.json').exists():self.skipTest('Saved artifacts absent')
        manifest=json.loads((m.OUT/'manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['existing_artifacts_sha256'],m.snapshot())
        for name,h in manifest['output_sha256'].items():self.assertEqual(m.ws.digest(m.OUT/name),h)
    def test_figures_read_actual_values_and_repeat(self):
        if not (m.OUT/'manifest.json').exists():self.skipTest('Saved artifacts absent')
        from geoai_open_lab import station_range_methods_figures as figs
        paths=figs.figures();before={p.name:m.ws.digest(p) for p in paths};figs.figures()
        self.assertEqual(before,{p.name:m.ws.digest(p) for p in paths})
        p=pd.read_csv(m.OUT/'comparisons.csv')
        for r in p[p.region_id.isin(m.STATIONS)].itertuples():
            self.assertIn(f'J={r.jaccard:.3f}',(m.OUT/'station_comparison.svg').read_text(encoding='utf8'))
        self.assertEqual(len(paths),5)

if __name__=='__main__':unittest.main()
