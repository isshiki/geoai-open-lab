"""Recalculate article evidence from fixed inputs; never download anything."""
import json
import numpy as np
import pandas as pd
from geoai_open_lab.region_clustering import (ROOT, load_inputs, transform, fit_kmeans,
    ordered_labels, scores, describe_clusters, digest)
from geoai_open_lab.similar_regions import FEATURES

f,s,source,cfg=load_inputs();x,_=transform(f);out=ROOT/cfg['output_dir']
m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
a=pd.read_csv(out/'assignments.csv');summary=pd.read_csv(out/'cluster_summary.csv')
assert len(a)==656 and a.region_id.is_unique and a.cluster.notna().all()
assert a.region_id.tolist()==f.region_id.tolist()
np.testing.assert_array_equal(ordered_labels(f,fit_kmeans(x,m['main_k']).labels_),a.cluster)
for name,expected in m['output_sha256'].items(): assert digest(out/name)==expected,name
for r in pd.read_csv(out/'k_metrics.csv').itertuples():
    model=fit_kmeans(x,r.k)
    for metric,value in scores(x,model.labels_).items(): assert np.isclose(value,getattr(r,metric),rtol=1e-10)
expected,details=describe_clusters(f,s,x,a.cluster.to_numpy())
pd.testing.assert_frame_equal(expected,summary)
np.testing.assert_allclose(pd.read_csv(out/'cluster_features.csv').select_dtypes('number'),details.select_dtypes('number'))
for row in summary.itertuples():
    assert (a.cluster==row.cluster).sum()==row.count
    for name in ('cluster_sizes.svg','cover_1600x900.svg'):
        assert f'{row.count}駅' in (out/name).read_text(encoding='utf8')
    for name in ('clustering-validation.md','clustering-article-handoff.md'):
        assert f'| C{row.cluster} | {row.count} |' in (ROOT/'docs'/name).read_text(encoding='utf8')
for row in details.itertuples():
    assert f'{row.transformed_mean_difference:+.2f}' in (out/'heatmap.svg').read_text(encoding='utf8')
    if row.feature == 'poi_density_per_km2':
        for name in ('clustering-validation.md','clustering-article-handoff.md'):
            assert f'{row.median:,.1f}' in (ROOT/'docs'/name).read_text(encoding='utf8')
for row in pd.read_csv(out/'k_metrics.csv').itertuples():
    for name in ('clustering-validation.md','clustering-article-handoff.md'):
        document=(ROOT/'docs'/name).read_text(encoding='utf8')
        assert f'{row.silhouette:.4f}' in document and f'{row.calinski_harabasz:.2f}' in document
        assert f'{row.davies_bouldin:.4f}' in document
nb=json.loads((ROOT/'notebooks/07_region_clustering.ipynb').read_text(encoding='utf8'))
for c in nb['cells']: assert not c.get('outputs') and c.get('execution_count') is None and not c.get('attachments')
print('PASS: pinned inputs, 656 assignments, all k metrics, representatives, CSV hashes, figure counts, handoff counts, clean notebook')
