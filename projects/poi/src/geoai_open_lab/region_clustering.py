"""Offline station clustering, explicit transformations and stability audits."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
from itertools import combinations
import importlib.metadata
import json
import platform
import shutil
import tomllib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import (silhouette_score, calinski_harabasz_score,
                             davies_bouldin_score, adjusted_rand_score)
from threadpoolctl import threadpool_limits
from .similar_regions import FEATURES, CATEGORIES, DENSITY, CONCENTRATION

ROOT = Path(__file__).resolve().parents[2]
KS = tuple(range(3, 9))
SEEDS = tuple(range(10))


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(config=None):
    config = Path(config) if config else ROOT/'configs/clustering.toml'
    cfg = tomllib.loads(config.read_text(encoding='utf8'))
    src = ROOT/cfg['input_dir']
    if digest(src/'manifest.json') != cfg['manifest_sha256']:
        raise ValueError('Input manifest hash mismatch')
    provenance = json.loads((src/'manifest.json').read_text(encoding='utf8'))
    for name in ('region_features.csv', 'stations.csv'):
        if digest(src/name) != provenance['output_sha256'][name]:
            raise ValueError('Input CSV hash mismatch: '+name)
    frame = pd.read_csv(src/'region_features.csv').sort_values('region_id').reset_index(drop=True)
    stations = pd.read_csv(src/'stations.csv').sort_values('region_id').reset_index(drop=True)
    if list(frame.columns) != provenance['columns'] or len(frame) != cfg['expected_rows']:
        raise ValueError('Input schema/row count mismatch')
    if stations.region_id.duplicated().any() or frame.region_id.tolist() != stations.region_id.tolist():
        raise ValueError('Station identity mismatch')
    return frame, stations, provenance, cfg


def transform(frame):
    """Same weighted Euclidean representation as Notebook 06, no PCA."""
    if frame.region_id.isna().any() or frame.region_id.duplicated().any():
        raise ValueError('Missing or duplicate region ID')
    if not np.isfinite(frame.poi_count).all() or (frame.poi_count <= 0).any():
        raise ValueError('Zero/invalid POI count: undefined composition; stop')
    values = frame[list(FEATURES)].astype(float).copy()
    if not np.isfinite(values).all().all() or (values < 0).any().any():
        raise ValueError('Nonfinite or negative features')
    values[[DENSITY, CONCENTRATION]] = np.log1p(values[[DENSITY, CONCENTRATION]])
    median = values.median()
    iqr = values.quantile(.75)-values.quantile(.25)
    if (iqr == 0).any():
        raise ValueError('IQR zero: stop without dropping columns')
    z = (values-median)/iqr
    z[list(CATEGORIES)] /= np.sqrt(6)
    return z.to_numpy(), dict(columns=list(FEATURES), median=median.to_dict(),
                             iqr=iqr.to_dict(), category_weight=1/np.sqrt(6))


def fit_kmeans(x, k, seed=42):
    with threadpool_limits(limits=1):
        return KMeans(n_clusters=k, init='k-means++', n_init=30, max_iter=500,
                      tol=1e-4, algorithm='lloyd', random_state=seed).fit(x)


def scores(x, labels):
    with threadpool_limits(limits=1):
        return dict(silhouette=float(silhouette_score(x, labels)),
                    calinski_harabasz=float(calinski_harabasz_score(x, labels)),
                    davies_bouldin=float(davies_bouldin_score(x, labels)))


def ordered_labels(frame, labels):
    """Stable display order: raw median density then minimum region ID."""
    keys = sorted(np.unique(labels), key=lambda c: (
        frame.loc[labels == c, DENSITY].median(), frame.loc[labels == c, 'region_id'].min()))
    mapping = {int(old): i+1 for i, old in enumerate(keys)}
    return np.array([mapping[int(v)] for v in labels])


def compare_k(x):
    records, seeds, pairs = [], [], []
    for k in KS:
        main = fit_kmeans(x, k)
        ward = AgglomerativeClustering(n_clusters=k, linkage='ward').fit_predict(x)
        variants = []
        for seed in SEEDS:
            model = fit_kmeans(x, k, seed)
            variants.append(model.labels_)
            seeds.append(dict(k=k, seed=seed, ari_to_seed42=float(adjusted_rand_score(main.labels_, model.labels_)),
                              inertia=float(model.inertia_)))
        aris = []
        for a, b in combinations(range(len(SEEDS)), 2):
            ari = float(adjusted_rand_score(variants[a], variants[b]))
            pairs.append(dict(k=k, seed_a=SEEDS[a], seed_b=SEEDS[b], ari=ari))
            aris.append(ari)
        counts = np.bincount(main.labels_)
        records.append(dict(k=k, **scores(x, main.labels_), inertia=float(main.inertia_),
            min_cluster_size=int(counts.min()), sizes=';'.join(map(str, sorted(counts))),
            small_cluster_count=int((counts < 20).sum()), seed_pair_ari_min=min(aris),
            seed_pair_ari_median=float(np.median(aris)),
            ward_ari=float(adjusted_rand_score(main.labels_, ward))))
    return pd.DataFrame(records), pd.DataFrame(seeds), pd.DataFrame(pairs)


def overlap_pairs(stations):
    rows = []
    xy = stations[['x', 'y']].to_numpy()
    if not np.isfinite(xy).all():
        raise ValueError('Invalid station coordinates')
    for i in range(len(xy)):
        area = np.prod(np.maximum(1000-np.abs(xy[i+1:]-xy[i]), 0), axis=1)
        for offset in np.flatnonzero(area > 0):
            j = i+1+offset
            rows.append(dict(region_a=stations.iloc[i].region_id, region_b=stations.iloc[j].region_id,
                             overlap_m2=float(area[offset])))
    return pd.DataFrame(rows, columns=['region_a', 'region_b', 'overlap_m2'])


def independent_subset(stations):
    """Greedy ID-order non-overlapping AOIs; NOT a statistical independence claim."""
    xy = stations[['x', 'y']].to_numpy()
    keep = []
    for i in np.argsort(stations.region_id.to_numpy()):
        if not keep or not np.any(np.all(np.abs(xy[keep]-xy[i]) < 1000, axis=1)):
            keep.append(int(i))
    return np.array(keep)


def describe_clusters(frame, stations, x, labels):
    details, summary = [], []
    for c in sorted(np.unique(labels)):
        idx = np.flatnonzero(labels == c)
        center = x[idx].mean(axis=0)
        distances = np.linalg.norm(x[idx]-center, axis=1)
        order = sorted(range(len(idx)), key=lambda j: (distances[j], frame.iloc[idx[j]].region_id))
        nearest = idx[np.array(order[:3])]
        farthest = idx[order[-1]]
        contrasts = center-x.mean(axis=0)
        strongest = np.argsort(-np.abs(contrasts), kind='stable')[:3]
        summary.append(dict(cluster=int(c), count=len(idx),
            representatives=' / '.join(stations.iloc[nearest].station_name),
            representative_ids=';'.join(frame.iloc[nearest].region_id),
            contrasting_station=stations.iloc[farthest].station_name,
            contrasting_id=frame.iloc[farthest].region_id,
            strongest_features=';'.join(FEATURES[j] for j in strongest)))
        for j, feature in enumerate(FEATURES):
            raw = frame.iloc[idx][feature]
            details.append(dict(cluster=int(c), feature=feature, median=float(raw.median()),
                mean=float(raw.mean()), global_mean=float(frame[feature].mean()),
                mean_difference=float(raw.mean()-frame[feature].mean()),
                transformed_mean_difference=float(contrasts[j])))
    return pd.DataFrame(summary), pd.DataFrame(details)


def run_clustering(k=None):
    """Compare all k; optionally finalize the documented choice using fixed input."""
    frame, stations, source, cfg = load_inputs()
    x, scaling = transform(frame)
    # Validate exact transformation compatibility with the preceding experiment.
    for name in ('median', 'iqr'):
        if not np.allclose(list(scaling[name].values()), [source['scaling'][name][f] for f in FEATURES], atol=1e-12):
            raise ValueError('Previous transform mismatch')
    out = ROOT/cfg['output_dir']; out.mkdir(parents=True, exist_ok=True)
    metrics, seeds, pairs = compare_k(x)
    metrics.to_csv(out/'k_metrics.csv', index=False)
    seeds.to_csv(out/'seed_stability.csv', index=False)
    pairs.to_csv(out/'seed_pair_stability.csv', index=False)
    for candidate in KS:
        candidate_labels = ordered_labels(frame, fit_kmeans(x, candidate).labels_)
        summary, details = describe_clusters(frame, stations, x, candidate_labels)
        summary.to_csv(out/f'candidate_{candidate}_summary.csv', index=False)
        details.to_csv(out/f'candidate_{candidate}_features.csv', index=False)
    report = dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),
        input_manifest_sha256=cfg['manifest_sha256'], input_sha256={n:source['output_sha256'][n]
        for n in ('region_features.csv','stations.csv')}, rows=len(frame), release=source['release'],
        acquisition_utc=source['acquisition_utc'], scaling=scaling, k_candidates=list(KS),
        seed=42, seeds=list(SEEDS), n_init=30, main_k=k, python=platform.python_version(),
        packages={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','scikit-learn')})
    if k is not None:
        if k not in KS: raise ValueError('Main k outside predeclared candidates')
        model = fit_kmeans(x, k)
        labels = ordered_labels(frame, model.labels_)
        assignments = stations[['region_id','station_name','longitude','latitude','x','y']].copy()
        assignments['cluster'] = labels
        summary, details = describe_clusters(frame, stations, x, labels)
        ward = AgglomerativeClustering(n_clusters=k, linkage='ward').fit_predict(x)
        pd.crosstab(labels, ward, rownames=['main'], colnames=['ward']).to_csv(out/'ward_cross.csv')
        overlap = overlap_pairs(stations)
        byid = dict(zip(frame.region_id, labels))
        overlap['cluster_a'] = overlap.region_a.map(byid); overlap['cluster_b'] = overlap.region_b.map(byid)
        overlap['same_cluster'] = overlap.cluster_a == overlap.cluster_b
        overlap.to_csv(out/'overlap_pairs.csv', index=False)
        audit=[]
        for c in range(1,k+1):
            ids=set(frame.loc[labels==c,'region_id'])
            involved=set(overlap.region_a)|set(overlap.region_b)
            audit.append(dict(cluster=c,count=len(ids),overlap_involved=len(ids&involved)))
        pd.DataFrame(audit).to_csv(out/'overlap_clusters.csv',index=False)
        keep = independent_subset(stations)
        reduced = fit_kmeans(x[keep], k)
        predicted = reduced.predict(x)
        assignments['overlap_suppressed_kept'] = np.isin(np.arange(len(frame)),keep)
        assignments['overlap_suppressed_cluster'] = predicted
        assignments['ward_cluster'] = ward
        pd.crosstab(labels,predicted,rownames=['main'],colnames=['suppressed']).to_csv(out/'suppressed_cross.csv')
        pca = PCA(n_components=2, svd_solver='full')
        coords = pca.fit_transform(x)
        assignments['pc1'] = coords[:,0]; assignments['pc2'] = coords[:,1]
        assignments.to_csv(out/'assignments.csv',index=False)
        summary.to_csv(out/'cluster_summary.csv',index=False)
        details.to_csv(out/'cluster_features.csv',index=False)
        frame.to_csv(out/'region_features.csv',index=False)
        pd.DataFrame(pca.components_,columns=FEATURES).to_csv(out/'pca_loadings.csv',index=False)
        report.update(main_scores=scores(x,labels), pca_explained_ratio=pca.explained_variance_ratio_.tolist(),
            overlap_pair_count=len(overlap),overlap_same_cluster_fraction=float(overlap.same_cluster.mean()),
            suppressed_count=len(keep),suppressed_all_ari=float(adjusted_rand_score(labels,predicted)),
            suppressed_retained_ari=float(adjusted_rand_score(labels[keep],predicted[keep])),
            ward_ari=float(adjusted_rand_score(labels,ward)),counts=summary['count'].tolist())
        assert len(labels)==len(frame) and summary['count'].sum()==len(frame)
    provenance_paths = [Path(__file__), ROOT/'src/geoai_open_lab/clustering_figures.py',
        ROOT/'configs/clustering.toml', ROOT/'configs/clustering-presentation.json',
        ROOT/'docs/clustering-design.md', ROOT/'docs/clustering-selection.md',
        ROOT/'notebooks/07_region_clustering.ipynb', ROOT/'uv.lock', ROOT/'pyproject.toml']
    report['code_sha256']={p.name:digest(p) for p in provenance_paths}
    outputs = sorted(out.glob('*.csv'))
    if k is None:
        outputs = [p for p in outputs if p.name.startswith(('candidate_', 'k_metrics', 'seed_'))]
    report['output_sha256']={p.name:digest(p) for p in outputs}
    manifest_name = 'manifest.json' if k is not None else 'comparison_manifest.json'
    (out/manifest_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(ROOT/cfg['input_dir']/name,out/name)
    with (out/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:
        f.write('\n2026-10-16: station feature clustering and aggregate figures.\n')
    return metrics, report, out


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--k',type=int)
    args=parser.parse_args()
    metrics, report, out=run_clustering(args.k)
    print(metrics.to_string(index=False)); print(out)
