"""Recalculate ranking metrics and verify local outputs and public Notebook."""
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
import nbformat
from scipy import sparse
from scipy.stats import spearmanr
from geoai_open_lab.aoi_sensitivity import OUT,BASE,WIDTHS,common_mask,orders
from geoai_open_lab.region_clustering import load_inputs,transform,digest,ROOT
from geoai_open_lab.region_embedding import tfidf

_,stations,_,_=load_inputs();mask=common_mask(stations)
m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
for name,h in m['output_sha256'].items():assert digest(OUT/name)==h
base=json.loads((BASE/'manifest.json').read_text(encoding='utf8'))
for name,h in base['output_sha256'].items():assert digest(BASE/name)==h
f=pd.read_csv(OUT/'features.csv');s=pd.read_csv(OUT/'station_stability.csv')
top=pd.read_csv(OUT/'all_station_top10.csv')
assert len(top)==656*3*4*10
assert (top.groupby(['half_width_m','mode','query_region_id']).size()==10).all()
previous={}
for h in WIDTHS:
    profile=f[f.half_width_m==h].reset_index(drop=True)
    assert profile.region_id.tolist()==stations.region_id.tolist()
    a,_=transform(profile);b,_=tfidf(sparse.load_npz(OUT/f'counts_{h}.npz'));c=np.load(OUT/f'embedding_{h}.npy')
    for mode,x in [('A',a),('B',b),('C',c)]:
        ii,d=orders(x,mask,'euclidean' if mode=='A' else 'cosine')
        if h==500:previous[mode]=(ii,d)
        oi,od=previous[mode];actual=s[(s.half_width_m==h)&(s['mode']==mode)]
        assert actual.region_id.tolist()==stations.region_id.tolist()
        common=[len(set(ii[i,:10])&set(oi[i,:10])) for i in range(656)]
        rho=[spearmanr(d[i,mask[i]],od[i,mask[i]]).statistic for i in range(656)]
        np.testing.assert_array_equal(common,actual.common_top10)
        np.testing.assert_allclose(rho,actual.spearman,rtol=0,atol=1e-12)
        saved=top[(top.half_width_m==h)&(top['mode']==mode)]
        np.testing.assert_array_equal(saved.region_id.to_numpy(),stations.region_id.to_numpy()[ii[:,:10]].ravel())
nb=nbformat.read(ROOT/'notebooks/09_aoi_sensitivity.ipynb',as_version=4)
nbformat.validate(nb)
for cell in nb.cells:
    assert not cell.get('attachments')
    if cell.cell_type=='code':assert cell.execution_count is None and not cell.outputs
executed=nbformat.read(OUT/'09_aoi_sensitivity.executed.ipynb',as_version=4)
assert all(c.execution_count is not None for c in executed.cells if c.cell_type=='code')
names=['aoi_sizes','target_rankings','common_distribution','station_sensitivity','cluster_changes','cover_1600x900']
for name in names:
    raw=(OUT/(name+'.png')).read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert int.from_bytes(raw[16:20],'big')==1600 and int.from_bytes(raw[20:24],'big')==900
for name in ('aoi-sensitivity-validation.md','aoi-sensitivity-article-handoff.md','aoi-sensitivity.md'):
    p=ROOT/'docs'/name
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
        if not target.startswith(('https://','http://','#')):assert (p.parent/target.split('#')[0]).exists(),target
print('Recomputed 7,872 station comparisons; baseline hashes, 6 PNGs, Notebook and local links verified.')
