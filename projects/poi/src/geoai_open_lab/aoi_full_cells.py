"""Narrow A-only quality check using the saved full-cell peak audit.

Never fits TF-IDF, SVD or clusters and never writes the original results.
"""
import json
import shutil
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from .aoi_sensitivity import OUT as ORIGINAL, WIDTHS, common_mask, orders
from .region_clustering import ROOT, digest, load_inputs, transform
from .region_embedding import TARGET, ranking

OUT = ROOT / 'data/cache/aoi_sensitivity/a-full-cells-v1'
PEAK = 'peak_density_250m'
RATIO = 'peak_to_mean_density_250m'


def full_cell_features(frame, audit):
    """Only replace peak and peak / whole-AOI mean; retain all other columns."""
    if not frame.region_id.is_unique or not audit.region_id.is_unique:
        raise ValueError('Duplicate region ID')
    if set(frame.region_id) != set(audit.region_id):
        raise ValueError('Audit region IDs do not match')
    peak = audit.set_index('region_id').loc[frame.region_id, 'full_cell_peak'].to_numpy()
    if not np.isfinite(peak).all() or (peak < 0).any() or (peak > frame[PEAK].to_numpy()+1e-9).any():
        raise ValueError('Invalid full-cell peak')
    result = frame.copy()
    result[PEAK] = peak
    result[RATIO] = peak / result.poi_density_per_km2
    return result


def compare(order, distance, reference, ref_distance, mask, stations, half, comparison):
    rows = []
    for i, s in enumerate(stations.itertuples()):
        valid = mask[i]
        rows.append(dict(half_width_m=half, comparison=comparison, region_id=s.region_id,
                         station_name=s.station_name,
                         common_top10=len(set(order[i, :10]) & set(reference[i, :10])),
                         spearman=float(spearmanr(distance[i, valid], ref_distance[i, valid]).statistic)))
    return pd.DataFrame(rows)


def run():
    original_manifest = json.loads((ORIGINAL/'manifest.json').read_text(encoding='utf8'))
    protected = {p.name:digest(p) for p in ORIGINAL.iterdir() if p.is_file()}
    for name, sha in original_manifest['output_sha256'].items():
        assert protected[name] == sha, name
    _, stations, _, _ = load_inputs()
    features = pd.read_csv(ORIGINAL/'features.csv', float_precision='round_trip')
    audit = pd.read_csv(ORIGINAL/'audit.csv', float_precision='round_trip')
    saved_top = pd.read_csv(ORIGINAL/'all_station_top10.csv')
    saved_stats = pd.read_csv(ORIGINAL/'station_stability.csv')
    mask = common_mask(stations)
    target = int(np.flatnonzero(stations.region_id == TARGET)[0])
    comparisons=[]; profiles=[]; rankings=[]; tops=[]; scaling={}
    baseline = None
    for half in WIDTHS:
        old = features[features.half_width_m == half].reset_index(drop=True)
        assert len(old) == 656 and old.region_id.tolist() == stations.region_id.tolist()
        new = full_cell_features(old, audit[audit.half_width_m == half])
        pd.testing.assert_frame_equal(old.drop(columns=[PEAK,RATIO]), new.drop(columns=[PEAK,RATIO]))
        ox,_ = transform(old); nx,scaling[str(half)] = transform(new)
        oo,od = orders(ox,mask,'euclidean'); no,nd = orders(nx,mask,'euclidean')
        saved = saved_top[(saved_top['mode']=='A') & (saved_top.half_width_m==half)]
        assert saved.region_id.tolist() == stations.region_id.to_numpy()[oo[:,:10]].ravel().tolist()
        np.testing.assert_allclose(saved.distance, od[np.arange(656)[:,None],oo[:,:10]].ravel(), atol=1e-10,rtol=0)
        if half == 500:
            # No clipped cells exist here: numerical features and distances must match.
            np.testing.assert_allclose(new[[PEAK,RATIO]],old[[PEAK,RATIO]],rtol=0,atol=1e-12)
            np.testing.assert_allclose(nd,od,rtol=0,atol=1e-12)
            np.testing.assert_array_equal(no,oo)
            baseline=(oo,od)
        br,bd=baseline
        for label,o,d,r,rd in [('old_vs_500',oo,od,br,bd),('full_vs_500',no,nd,br,bd),('full_vs_old_same_width',no,nd,oo,od)]:
            comparisons.append(compare(o,d,r,rd,mask,stations,half,label))
        table=ranking(no,nd,stations,target).assign(mode='A',half_width_m=half)
        table['baseline_rank']=table.region_id.map(ranking(br,bd,stations,target).set_index('region_id')['rank'])
        table['rank_change']=table.baseline_rank-table['rank']
        table['old_same_width_rank']=table.region_id.map(ranking(oo,od,stations,target).set_index('region_id')['rank'])
        rankings.append(table); profiles.append(new)
        for i,s in enumerate(stations.itertuples()):
            for rank,j in enumerate(no[i,:10],1):
                tops.append(dict(half_width_m=half,query_region_id=s.region_id,rank=rank,
                                 region_id=stations.iloc[j].region_id,station_name=stations.iloc[j].station_name,distance=nd[i,j]))
    detail=pd.concat(comparisons,ignore_index=True)
    old_check=detail[detail.comparison=='old_vs_500'].reset_index(drop=True)
    expected=saved_stats[saved_stats['mode']=='A'].reset_index(drop=True)
    np.testing.assert_array_equal(old_check.common_top10,expected.common_top10)
    np.testing.assert_allclose(old_check.spearman,expected.spearman,atol=1e-12,rtol=0)
    summary=detail.groupby(['comparison','half_width_m']).agg(common_mean=('common_top10','mean'),common_median=('common_top10','median'),spearman_mean=('spearman','mean'),spearman_median=('spearman','median')).reset_index()
    # Presentation tables contain new A plus verbatim numerical B/C results.
    updated=detail[detail.comparison=='full_vs_500'].drop(columns='comparison').assign(mode='A')
    lookup=features.set_index(['half_width_m','region_id']).poi_count
    updated['poi_count']=[lookup.loc[h,r] for h,r in zip(updated.half_width_m,updated.region_id)]
    updated['baseline_poi_count']=[lookup.loc[500,r] for r in updated.region_id]
    stats=pd.concat([updated,saved_stats[saved_stats['mode']!='A']],ignore_index=True)
    oldr=pd.read_csv(ORIGINAL/'rankings.csv')
    combined=pd.concat([pd.concat(rankings),oldr[oldr['mode']!='A']],ignore_index=True)
    OUT.mkdir(parents=True,exist_ok=True)
    tables={'comparison_summary':summary,'comparison_station':detail,'features':pd.concat(profiles),
            'rankings':combined,'station_stability':stats,'all_station_top10_A':pd.DataFrame(tops)}
    tables['summary']=stats.groupby(['mode','half_width_m']).agg(common_mean=('common_top10','mean'),common_median=('common_top10','median'),spearman_mean=('spearman','mean'),spearman_median=('spearman','median')).reset_index()
    for name,frame in tables.items():frame.to_csv(OUT/(name+'.csv'),index=False)
    # These remain original audit clustering results, not new A clustering.
    for name in ('cluster_metrics.csv','assignments.csv','Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(ORIGINAL/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:
        f.write('\n2026-10-17: A full-250m-cell peak quality check; B/C unchanged.\n')
    assert protected == {p.name:digest(p) for p in ORIGINAL.iterdir() if p.is_file()}
    manifest={**original_manifest,'completed_at_utc':datetime.now(timezone.utc).isoformat(),
              'a_peak_rule':'full 250m cells only; denominator is whole AOI mean',
              'original_files_sha256':protected,'original_unchanged':True,'baseline_reproduced':True,
              'full_cell_counts':{'500':16,'600':16,'700':16,'800':36},
              'scaling':scaling,'output_sha256':{p.name:digest(p) for p in OUT.glob('*.csv')},
              'quality_check_code_sha256':digest(__file__)}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return summary,manifest,OUT


if __name__=='__main__':print(run()[0].to_string(index=False))
