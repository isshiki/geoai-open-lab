"""Primary-category TF-IDF/SVD with paired global POI splits and baselines."""
import json
import time
import shutil
import platform
from importlib.metadata import version
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linear_sum_assignment
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from sklearn.metrics import pairwise_distances, adjusted_rand_score, silhouette_score
from threadpoolctl import threadpool_limits
from .region_clustering import ROOT,digest,transform,fit_kmeans,ordered_labels,scores,independent_subset
from .similar_regions import rank_regions
from .embedding_input import load_categories,count_matrix

DIMS=(8,16,32,64)
TARGET='n02-003584'


def tfidf(counts, fit_rows=None):
    model=TfidfTransformer(norm='l2',use_idf=True,smooth_idf=True,sublinear_tf=False)
    model.fit(counts if fit_rows is None else counts[fit_rows])
    return model.transform(counts),model


def embed(x,dim,seed=42,fit_rows=None):
    fit = x if fit_rows is None else x[fit_rows]
    if dim < 1 or dim>=min(fit.shape): raise ValueError('Dimension must be less than fitted matrix rank bound')
    with threadpool_limits(limits=1):
        model=TruncatedSVD(n_components=dim,algorithm='randomized',n_iter=10,random_state=seed)
        model.fit(fit)
        z=model.transform(x)
    if not np.isfinite(z).all():raise ValueError('Nonfinite embedding')
    return normalize(z),model


def neighbor_order(x,stations,metric='cosine',valid=None,exclude_overlap=True):
    with threadpool_limits(limits=1): d=pairwise_distances(x,metric=metric)
    valid=np.ones(len(stations),bool) if valid is None else np.asarray(valid)
    d[:,~valid]=np.inf;d[~valid,:]=np.inf
    if exclude_overlap:
        xy=stations[['x','y']].to_numpy()
        overlap=np.all(np.abs(xy[:,None,:]-xy[None,:,:])<1000,axis=2)
        d[overlap]=np.inf
    np.fill_diagonal(d,np.inf)
    # Inputs are sorted by region ID; stable argsort implements deterministic ties.
    order=np.argsort(d,axis=1,kind='stable')
    return order,d


def retention(first,second,valid=None):
    values=np.array([len(set(a[:10])&set(b[:10]))/10 for a,b in zip(first,second)])
    if valid is not None: values=np.where(valid,values,np.nan)
    return values


def ranking(order,distances,stations,target):
    idx=[i for i in order[target] if np.isfinite(distances[target,i])]
    result=stations.iloc[idx][['region_id','station_name']].copy()
    result['rank']=np.arange(1,len(idx)+1);result['distance']=distances[target,idx]
    return result.reset_index(drop=True)


def run_embedding(dimension=None):
    profiles,stations,source,counts,incidence,codes,vocab,audit,input_meta=load_categories()
    cfg=json.loads((ROOT/'configs/embedding.json').read_text(encoding='utf8'))
    oldfile=ROOT/'data/cache/clustering/tokyo-v1/assignments.csv'
    if digest(oldfile)!=cfg['previous_assignments_sha256']:raise ValueError('Previous labels changed')
    old=pd.read_csv(oldfile)
    if old.region_id.tolist()!=stations.region_id.tolist():raise ValueError('Previous IDs changed')
    out=ROOT/cfg['output_dir'];out.mkdir(parents=True,exist_ok=True)
    audit.to_csv(out/'input_audit.csv',index=False)
    sparse.save_npz(out/'category_counts.npz',counts)
    pd.Series(vocab,name='primary').to_csv(out/'vocabulary.csv',index=False)
    x_a,scaling=transform(profiles);b,idf=tfidf(counts)
    sparse.save_npz(out/'tfidf.npz',b)
    ai,ad=neighbor_order(x_a,stations,metric='euclidean');bi,bd=neighbor_order(b,stations)
    target=int(np.flatnonzero(stations.region_id==TARGET)[0])
    ranks={'A':ranking(ai,ad,stations,target),'B':ranking(bi,bd,stations,target)}
    previous=rank_regions(profiles,stations)[0]['main'].dropna(subset=['rank']).sort_values('rank')
    density=rank_regions(profiles,stations)[0]['density_only']
    density.to_csv(out/'density_only_reference.csv',index=False)
    assert previous.region_id.tolist()==ranks['A'].region_id.tolist()
    np.testing.assert_allclose(previous.distance,ranks['A'].distance,atol=1e-12)
    old_x=ordered_labels(profiles,fit_kmeans(x_a,3).labels_)
    np.testing.assert_array_equal(old_x,old.cluster)
    representations={};models={};evaluations=[];seed_records=[];split_records=[];split_rankings=[];skipped=[]
    for dim in DIMS:
        if dim>=min(b.shape):skipped.append(dim);continue
        start=time.perf_counter();z,svd=embed(b,dim);seconds=time.perf_counter()-start
        ci,cd=neighbor_order(z,stations);representations[dim]=(z,ci,cd);models[dim]=svd
        ranks[f'C{dim}']=ranking(ci,cd,stations,target)
        np.save(out/f'embedding_{dim}.npy',z);np.save(out/f'components_{dim}.npy',svd.components_)
        rr=retention(bi,ci)
        evaluations.append(dict(dimension=dim,explained_variance=float(svd.explained_variance_ratio_.sum()),
            b_retention_mean=float(rr.mean()),b_retention_median=float(np.median(rr)),
            kichijoji_b_common=int(rr[target]*10),fit_seconds=seconds))
        for seed in range(5):
            zz,_=embed(b,dim,seed);ii,_=neighbor_order(zz,stations)
            sr=retention(ci,ii)
            seed_records.append(dict(dimension=dim,seed=seed,mean_retention=float(sr.mean()),target_common=int(sr[target]*10)))
    # Complementary halves: shared POI belongs to same half in every station.
    for seed in range(100,105):
        chosen=np.random.default_rng(seed).integers(0,2,incidence.shape[1])
        halves=[count_matrix(incidence,codes,len(vocab),weights) for weights in (chosen,1-chosen)]
        valid=np.logical_and.reduce([np.asarray(h.sum(axis=1)).ravel()>0 for h in halves])
        if valid.sum()<12:raise ValueError('Too few valid split rows')
        bh=[tfidf(h)[0] for h in halves]
        pairs={'B':bh}
        for dim in representations: pairs[f'C{dim}']=[embed(h,dim)[0] for h in bh]
        for mode,xx in pairs.items():
            orders=[neighbor_order(h,stations,valid=valid) for h in xx]
            ii=[item[0] for item in orders]
            for half,(order,distance) in enumerate(orders):
                ranked=ranking(order,distance,stations,target).head(10)
                for r in ranked.itertuples():
                    split_rankings.append(dict(seed=seed,mode=mode,half=half,
                        rank=r.rank,region_id=r.region_id,station_name=r.station_name,distance=r.distance))
            r=retention(*ii,valid)
            for i in range(len(stations)):
                split_records.append(dict(seed=seed,mode=mode,region_id=stations.iloc[i].region_id,
                    poi_count=int(profiles.iloc[i].poi_count),valid=bool(valid[i]),retention=r[i]))
    splits=pd.DataFrame(split_records);seeds=pd.DataFrame(seed_records)
    pd.DataFrame(split_rankings).to_csv(out/'split_target_rankings.csv',index=False)
    splits['poi_band']=pd.cut(splits.poi_count,bins=[-1,49,199,np.inf],labels=['<50','50-199','>=200'])
    splits.to_csv(out/'split_station_stability.csv',index=False)
    split_summary=splits.groupby(['mode','poi_band'],observed=True).agg(mean_retention=('retention','mean'),valid_evaluations=('retention','count'),total_evaluations=('valid','size')).reset_index()
    split_summary.to_csv(out/'split_summary.csv',index=False)
    seeds.to_csv(out/'seed_stability.csv',index=False)
    evaluation=pd.DataFrame(evaluations)
    for i,row in evaluation.iterrows():
        mode=f'C{int(row.dimension)}'
        evaluation.loc[i,'split_mean']=splits.loc[splits['mode']==mode,'retention'].mean()
        evaluation.loc[i,'seed_mean']=seeds.loc[seeds.dimension==row.dimension,'mean_retention'].mean()
    evaluation.to_csv(out/'dimension_metrics.csv',index=False)
    for mode,r in ranks.items():r.to_csv(out/f'ranking_{mode}.csv',index=False)
    comparisons=[]
    for a in ranks:
        for c in ranks:
            comparisons.append(dict(first=a,second=c,common_top10=len(set(ranks[a].head(10).region_id)&set(ranks[c].head(10).region_id))))
    pd.DataFrame(comparisons).to_csv(out/'rank_comparison.csv',index=False)
    report=dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),release=source['release'],
        acquisition_utc=source['acquisition_utc'],input=input_meta,station_count=len(stations),
        dimensions_skipped=skipped,selected_dimension=dimension,split_b_mean=float(splits.loc[splits['mode']=='B','retention'].mean()),
        split_invalid_station_seed_pairs=int((~splits.loc[splits['mode']=='B','valid']).sum()),
        environment={'python':platform.python_version(),**{p:version(p) for p in ('numpy','scipy','pandas','scikit-learn','duckdb','pyproj','shapely')}},
        previous_assignments_sha256=cfg['previous_assignments_sha256'])
    if dimension is not None:
        if dimension not in representations:raise ValueError('Unsupported selected dimension')
        z,ci,cd=representations[dimension];svd=models[dimension]
        labels=ordered_labels(profiles,fit_kmeans(z,3).labels_)
        assignments=stations[['region_id','station_name','x','y','longitude','latitude']].copy()
        assignments['old_cluster']=old.cluster;assignments['cluster']=labels
        cross=pd.crosstab(old.cluster,labels);cross.to_csv(out/'cluster_cross.csv')
        rr,cc=linear_sum_assignment(-cross.to_numpy());mapping={int(cross.columns[c]):int(cross.index[r]) for r,c in zip(rr,cc)}
        assignments['aligned_old_cluster']=[mapping[v] for v in labels]
        assignments['changed']=assignments.aligned_old_cluster!=assignments.old_cluster
        assignments['axis1']=z[:,0];assignments['axis2']=z[:,1]
        assignments.to_csv(out/'assignments.csv',index=False)
        profiles.assign(cluster=labels).groupby('cluster')[list(scaling['columns'])].median().to_csv(out/'cluster_feature_medians.csv')
        summary=[];contrasts=[]
        overall=np.asarray(b.mean(axis=0)).ravel()
        for c in range(1,4):
            idx=np.flatnonzero(labels==c);center=z[idx].mean(axis=0)
            nearest=idx[np.argsort(np.linalg.norm(z[idx]-center,axis=1),kind='stable')[:3]]
            mean=np.asarray(b[idx].mean(axis=0)).ravel();top=np.argsort(-mean,kind='stable')[:5]
            summary.append(dict(cluster=c,count=len(idx),representatives=' / '.join(stations.iloc[nearest].station_name),
                main_categories=';'.join(vocab[top]),kichijoji=bool(target in idx)))
            for j in np.argsort(-np.abs(mean-overall),kind='stable')[:10]:
                contrasts.append(dict(cluster=c,category=vocab[j],tfidf_mean=float(mean[j]),difference=float(mean[j]-overall[j])))
        pd.DataFrame(summary).to_csv(out/'cluster_summary.csv',index=False)
        pd.DataFrame(contrasts).to_csv(out/'cluster_category_contrasts.csv',index=False)
        changed=assignments[assignments.changed].sort_values('region_id').copy()
        changed['poi_density']=profiles.set_index('region_id').loc[changed.region_id,'poi_density_per_km2'].to_numpy()
        changed.to_csv(out/'cluster_changes.csv',index=False)
        axes=[]
        for axis,loading in enumerate(svd.components_):
            for side,ids in [('positive',np.argsort(-loading,kind='stable')[:5]),('negative',np.argsort(loading,kind='stable')[:5])]:
                for j in ids:axes.append(dict(axis=axis+1,side=side,category=vocab[j],loading=float(loading[j])))
        pd.DataFrame(axes).to_csv(out/'axis_categories.csv',index=False)
        # Exact decomposition x_target · (V.T V x_candidate), normalized in C space.
        explain=[];lookup={v:i for i,v in enumerate(stations.region_id)}
        bt=b[target].toarray().ravel();raw_z=svd.transform(b)
        candidates=set().union(*(set(ranks[mode].head(10).region_id) for mode in ('A','B',f'C{dimension}')))
        for rid in sorted(candidates):
            i=lookup[rid];bv=b[i].toarray().ravel();product=bt*bv
            contribution=bt*(raw_z[i]@svd.components_)/(np.linalg.norm(raw_z[target])*np.linalg.norm(raw_z[i]))
            assert np.isclose(contribution.sum(),z[target]@z[i],atol=1e-10)
            for j in np.argsort(-np.abs(contribution),kind='stable')[:6]:
                explain.append(dict(region_id=rid,station_name=stations.iloc[i].station_name,category=vocab[j],
                    b_cosine_product=float(product[j]),c_cosine_contribution=float(contribution[j]),
                    target_count=int(counts[target,j]),candidate_count=int(counts[i,j])))
        pd.DataFrame(explain).to_csv(out/'neighbor_categories.csv',index=False)
        keep=independent_subset(stations);reduced_b,_=tfidf(counts,keep)
        reduced_z,_=embed(reduced_b,dimension,fit_rows=keep);ni,nd=neighbor_order(reduced_z,stations)
        reduced_ranking=ranking(ni,nd,stations,target);reduced_ranking.to_csv(out/'ranking_overlap_suppressed.csv',index=False)
        overlap_orders,_=neighbor_order(z,stations,exclude_overlap=False)
        self_norm=ordered_labels(profiles,fit_kmeans(x_a,3).labels_)
        report.update(cluster_ari=float(adjusted_rand_score(self_norm,labels)),
            cluster_scores=scores(z,labels),cluster_cosine_silhouette=float(silhouette_score(z,labels,metric='cosine')),
            old_cluster_scores=scores(x_a,self_norm),cluster_counts=np.bincount(labels)[1:].tolist(),
            kichijoji_cluster=int(labels[target]),aligned_changed=int(assignments.changed.sum()),
            pca_note='axis1/axis2 are selected normalized SVD coordinates, not clustering input reduction',
            overlap_suppressed_fit_count=len(keep),overlap_suppressed_retention=float(retention(ci,ni).mean()),
            overlap_suppressed_target_common=int(retention(ci,ni)[target]*10),
            allow_overlap_retention=float(retention(ci,overlap_orders).mean()),
            allow_overlap_target_common=int(retention(ci,overlap_orders)[target]*10))
    report['code_sha256']={p.name:digest(p) for p in [ROOT/'src/geoai_open_lab/region_embedding.py',ROOT/'src/geoai_open_lab/embedding_input.py',ROOT/'docs/embedding-design.md',ROOT/'configs/embedding.json',ROOT/'uv.lock']}
    report['output_sha256']={p.name:digest(p) for p in sorted(out.iterdir()) if p.suffix in ('.csv','.npz','.npy')}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(ROOT/'data/cache/similar_regions/tokyo-v1'/name,out/name)
    with (out/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:f.write('\n2026-10-17: primary-category TF-IDF/SVD and aggregate analysis.\n')
    return evaluation,report,out


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--dimension',type=int)
    args=parser.parse_args();table,report,out=run_embedding(args.dimension)
    print(table.to_string(index=False));print(json.dumps(report,ensure_ascii=True)[:1500]);print(out)
