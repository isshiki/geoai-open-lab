"""Independent checks on the fixed run; reads generated outputs without downloads."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import adjusted_rand_score,silhouette_score,davies_bouldin_score
from geoai_open_lab.region_clustering import digest

root=Path(__file__).resolve().parents[1];out=root/'data/cache/embedding/tokyo-v1'
m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
for name,sha in m['output_sha256'].items():
    assert digest(out/name)==sha,name
a=pd.read_csv(out/'assignments.csv'); audit=pd.read_csv(out/'input_audit.csv')
assert len(a)==656 and a.region_id.is_unique
assert a.region_id.tolist()==audit.region_id.tolist()
assert a.cluster.value_counts().sort_index().tolist()==m['cluster_counts']
assert sum(m['cluster_counts'])==656
assert (audit.category_missing+audit.rare_removed+audit.retained_count==audit.poi_count).all()
counts=sparse.load_npz(out/'category_counts.npz');b=sparse.load_npz(out/'tfidf.npz')
assert counts.shape==(656,961)
np.testing.assert_array_equal(np.asarray(counts.sum(axis=1)).ravel(),audit.retained_count)
df=np.asarray((counts>0).sum(axis=0)).ravel();assert (df>=5).all()
expected=counts.toarray()*(np.log(657/(1+df))+1)
expected/=np.linalg.norm(expected,axis=1)[:,None]
np.testing.assert_allclose(b.toarray(),expected)
dim=m['selected_dimension'];z=np.load(out/f'embedding_{dim}.npy');v=np.load(out/f'components_{dim}.npy')
projection=b@v.T;projection/=np.linalg.norm(projection,axis=1)[:,None]
np.testing.assert_allclose(z,projection)
np.testing.assert_allclose(np.linalg.norm(z,axis=1),1)
assert np.isclose(adjusted_rand_score(a.old_cluster,a.cluster),m['cluster_ari'])
assert np.isclose(silhouette_score(z,a.cluster,metric='cosine'),m['cluster_cosine_silhouette'])
assert np.isclose(davies_bouldin_score(z,a.cluster),m['cluster_scores']['davies_bouldin'])
# Recompute all-query top10 without the production neighbor_order helper.
xy=a[['x','y']].to_numpy();mask=(np.abs(xy[:,None]-xy[None,:])<1000).all(axis=2)
def neighbors(x):
    d=1-x@x.T;d[mask]=np.inf
    return np.argsort(d,axis=1,kind='stable')[:,:10]
bn=neighbors(b.toarray());cn=neighbors(z)
common=np.array([len(set(i)&set(j))/10 for i,j in zip(bn,cn)])
metrics=pd.read_csv(out/'dimension_metrics.csv');row=metrics[metrics.dimension==dim].iloc[0]
assert np.isclose(common.mean(),row.b_retention_mean)
target=a.index[a.region_id=='n02-003584'][0]
rank=pd.read_csv(out/f'ranking_C{dim}.csv')
assert a.iloc[cn[target]].region_id.tolist()==rank.head(10).region_id.tolist()
splits=pd.read_csv(out/'split_station_stability.csv')
assert np.isclose(splits.loc[splits['mode']==f'C{dim}','retention'].mean(),row.split_mean)
summary=pd.read_csv(out/'cluster_summary.csv')
for r in summary.itertuples():
    idx=np.flatnonzero(a.cluster==r.cluster)
    nearest=idx[np.argsort(np.linalg.norm(z[idx]-z[idx].mean(axis=0),axis=1),kind='stable')[:3]]
    assert ' / '.join(a.iloc[nearest].station_name)==r.representatives
nb=json.loads((root/'notebooks/08_region_embedding.ipynb').read_text(encoding='utf8'))
for cell in nb['cells']:
    assert not cell.get('attachments')
    if cell['cell_type']=='code':assert cell['outputs']==[] and cell['execution_count'] is None
executed=json.loads((out/'08_region_embedding.executed.ipynb').read_text(encoding='utf8'))
assert all(c['execution_count'] is not None for c in executed['cells'] if c['cell_type']=='code')
for name in ('representations','neighbors','dimensions','clusters','latent_axes','cover_1600x900'):
    raw=(out/(name+'.png')).read_bytes()
    assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert int.from_bytes(raw[16:20],'big')==1600 and int.from_bytes(raw[20:24],'big')==900
    svg=(out/(name+'.svg')).read_text(encoding='utf8')
    assert m['release'] in svg and 'masahiko.info' in svg
validation=(root/'docs/embedding-validation.md').read_text(encoding='utf8')
handoff=(root/'docs/embedding-article-handoff.md').read_text(encoding='utf8')
assert f"{m['cluster_ari']:.6f}" in validation and f"{m['cluster_ari']:.4f}" in handoff
assert f"{m['split_b_mean']:.1%}" in handoff and f'{row.split_mean:.1%}' in handoff
assert f'{row.b_retention_mean:.1%}' in handoff
for mode in ('A','B',f'C{dim}'):
    ranked=pd.read_csv(out/f'ranking_{mode}.csv').head(10)
    for r in ranked.itertuples():
        assert f'{r.station_name} ({r.region_id})' in validation
        assert f'{r.station_name} ({r.region_id})' in handoff
for r in metrics.itertuples():
    assert f'{r.explained_variance:.4f}' in validation and f'{r.split_mean:.4f}' in validation
    assert f'{r.b_retention_mean:.1%}' in (out/'dimensions.svg').read_text(encoding='utf8')
for r in summary.itertuples():
    assert f'C{r.cluster}：{r.count}駅' in (out/'clusters.svg').read_text(encoding='utf8')
print('Verified checksums, counts, TF-IDF, projection, metrics, nearest stations, cluster representatives, Notebook and 6 figures.')
