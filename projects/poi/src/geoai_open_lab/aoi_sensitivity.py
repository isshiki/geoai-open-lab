"""Fixed-vocabulary AOI sensitivity; never overwrite the article baseline."""
import json
import tomllib
import shutil
import platform
from importlib.metadata import version
from datetime import datetime, timezone
import duckdb
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr
from scipy.optimize import linear_sum_assignment
from pyproj import Transformer, network
from shapely import STRtree, points
from shapely.geometry import box
from sklearn.metrics import adjusted_rand_score, pairwise_distances
from threadpoolctl import threadpool_limits
from .region_clustering import ROOT, digest, load_inputs, transform, fit_kmeans, ordered_labels
from .region_embedding import tfidf, embed, neighbor_order, ranking, TARGET
from .embedding_input import count_matrix
from .region_features import REGION_COLUMNS, SHARE_COLUMNS, SHARE_GROUPS, OTHER, MISSING
from .acquire_aoi_supplement import RAW, OUT as SUPPLEMENT

OUT=ROOT/'data/cache/aoi_sensitivity/tokyo-v1'
BASE=ROOT/'data/cache/embedding/tokyo-v1'
WIDTHS=(500,600,700,800)

def grid_counts(xy,center,half,size=250):
    """Station-anchored grid, exact clipped areas, internal east/north rule."""
    local=np.asarray(xy)-np.asarray(center)
    if np.any(abs(local)>half+1e-8): raise ValueError('POI outside AOI')
    lo=int(np.floor(-half/size));hi=int(np.ceil(half/size))
    edges=np.clip(np.arange(lo,hi+1)*size,-half,half)
    widths=np.diff(edges);areas=np.outer(widths,widths)
    q=local/size;near=np.rint(q);q=np.where(abs(q-near)*size<=1e-8,near,q)
    ids=np.clip(np.floor(q).astype(int)-lo,0,len(widths)-1)
    counts=np.zeros_like(areas,dtype=int)
    np.add.at(counts,(ids[:,1],ids[:,0]),1)
    assert counts.sum()==len(xy) and np.isclose(areas.sum(),(2*half)**2)
    return counts,areas

def profile(frame,station,half,groups):
    counts,areas=grid_counts(frame[['x','y']],(station.x,station.y),half)
    mapping={c:g for g,values in groups.items() for c in values}
    cats=frame.basic_category.fillna('').map(lambda c:MISSING if c=='' else mapping.get(c,OTHER)).value_counts()
    n=len(frame);area=(2*half)**2/1e6;density=n/area
    if not n: raise ValueError('Zero POI profile')
    peak=float((counts/(areas/1e6)).max())
    values=dict(region_id=station.region_id,region_label=station.station_name,area_km2=area,poi_count=n,poi_density_per_km2=density,
        **{col:float(cats.get(g,0))/n for col,g in zip(SHARE_COLUMNS,SHARE_GROUPS)},peak_density_250m=peak,peak_to_mean_density_250m=peak/density)
    partial=areas<250**2
    audit=dict(partial_cells=int(partial.sum()),min_cell_area=float(areas.min()),peak_in_partial=bool(np.any(partial & np.isclose(counts/(areas/1e6),peak))),full_cell_peak=float(np.max((counts/(areas/1e6))[~partial])))
    return values,audit

def common_mask(stations,half=800):
    xy=stations[['x','y']].to_numpy()
    return ~np.all(abs(xy[:,None,:]-xy[None,:,:])<2*half,axis=2)

def orders(x,mask,metric):
    with threadpool_limits(limits=1): d=pairwise_distances(x,metric=metric)
    d[~mask]=np.inf
    if (mask.sum(axis=1)<10).any():raise ValueError('Fewer than ten common candidates')
    return np.argsort(d,axis=1,kind='stable'),d

def alignment(base,current):
    matrix=np.array([[np.sum((base==a)&(current==b)) for b in range(1,4)] for a in range(1,4)])
    rows,cols=linear_sum_assignment(-matrix)
    mapping={int(b+1):int(a+1) for a,b in zip(rows,cols)}
    aligned=np.array([mapping[int(c)] for c in current])
    return aligned,mapping,matrix

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    old,stations,source,_=load_inputs()
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    sm=json.loads((SUPPLEMENT/'manifest.json').read_text(encoding='utf8'))
    assert sm['coverage_complete'] and sm['release']==m['release']=='2026-09-23.0'
    assert sm['base_manifest_sha256']==digest(RAW/'manifest.json')
    assert digest(SUPPLEMENT/'places.parquet')==sm['sha256']
    for name,h in m['output_sha256'].items():assert digest(RAW/name)==h
    oldm=json.loads((BASE/'manifest.json').read_text(encoding='utf8'))
    assert digest(RAW/'manifest.json')==oldm['input']['raw_manifest_sha256']
    for name,h in oldm['output_sha256'].items():assert digest(BASE/name)==h
    vocab=pd.read_csv(BASE/'vocabulary.csv').primary.tolist();assert len(vocab)==961
    groups=tomllib.loads((ROOT/'configs/region_features.toml').read_text(encoding='utf8'))['display_groups']
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        frame=con.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat,basic_category,taxonomy.primary category FROM read_parquet(?) ORDER BY id',[[str(RAW/'places.parquet'),str(SUPPLEMENT/'places.parquet')]]).df()
    assert frame.id.notna().all() and not frame.id.duplicated().any()
    network.set_network_enabled(False)
    trans=Transformer.from_crs(4326,6677,always_xy=True)
    frame['x'],frame['y']=trans.transform(frame.lon.to_numpy(),frame.lat.to_numpy())
    assert np.isfinite(frame[['x','y']]).all().all()
    # Check coverage metadata for every station, not observed POI extent.
    inverse=Transformer.from_crs(6677,4326,always_xy=True);bb=m['acquisition_bbox']
    targetmap={t['region_id']:t for t in sm['targets']}
    for s in stations.itertuples():
        w,so,e,n=inverse.transform_bounds(s.x-800,s.y-800,s.x+800,s.y+800,densify_pts=100)
        if not(bb['west']<=w and bb['south']<=so and bb['east']>=e and bb['north']>=n):
            assert s.region_id in targetmap and targetmap[s.region_id]['x']==s.x and targetmap[s.region_id]['y']==s.y
    tree=STRtree(points(frame.x.to_numpy(),frame.y.to_numpy()))
    codes=frame.category.fillna('').str.strip().map({c:i for i,c in enumerate(vocab)}).fillna(-1).to_numpy(int)
    mask=common_mask(stations);target=int(np.flatnonzero(stations.region_id==TARGET)[0])
    allranks=[];all_top10=[];audits=[];features=[];summary=[];cluster_stats=[];cluster_rows=[];cluster_summaries=[];deltas=[];overlaps=[]
    region_ids=stations.region_id.to_numpy();station_names=stations.station_name.to_numpy()
    baseline={};baseline_labels={};baseline_counts=None
    far=np.triu(np.all(abs(stations[['x','y']].to_numpy()[:,None,:]-stations[['x','y']].to_numpy()[None,:,:])<1600,axis=2),1)
    pi,pj=np.where(far)
    for half in WIDTHS:
        rows=[];cols=[];profiles=[]
        for i,s in enumerate(stations.itertuples()):
            ids=np.sort(tree.query(box(s.x-half,s.y-half,s.x+half,s.y+half),predicate='covers'))
            p,a=profile(frame.iloc[ids],s,half,groups);profiles.append(p)
            rows.extend([i]*len(ids));cols.extend(ids)
            audits.append(dict(half_width_m=half,region_id=s.region_id,station_name=s.station_name,poi_count=len(ids),vocabulary_excluded=int((codes[ids]<0).sum()),missing_primary=int(frame.iloc[ids].category.fillna('').eq('').sum()),candidate_count=int(mask[i].sum()),**a))
        prof=pd.DataFrame(profiles,columns=REGION_COLUMNS);features.append(prof.assign(half_width_m=half))
        incidence=sparse.csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(656,len(frame)))
        counts=count_matrix(incidence,codes,961)
        assert np.all(np.asarray(counts.sum(axis=1)).ravel()>0)
        if baseline_counts is not None: assert np.all((counts-baseline_counts).data>=0)
        xa,_=transform(prof);b,_=tfidf(counts);c,svd=embed(b,64)
        representations={'A':xa,'B':b,'C':c}
        if half==500:
            np.testing.assert_allclose(prof.iloc[:,2:],old.iloc[:,2:],rtol=0,atol=1e-9)
            assert (counts!=sparse.load_npz(BASE/'category_counts.npz')).nnz==0
            np.testing.assert_allclose(b.toarray(),sparse.load_npz(BASE/'tfidf.npz').toarray(),rtol=0,atol=1e-12)
            np.testing.assert_allclose(c,np.load(BASE/'embedding_64.npy'),rtol=0,atol=1e-10)
            baseline_counts=counts
        for mode,x in representations.items():
            metric='euclidean' if mode=='A' else 'cosine'
            order,d=orders(x,mask,metric)
            if half==500:
                oi,od=neighbor_order(x,stations,metric=metric)
                legacy=ranking(oi,od,stations,target);saved=pd.read_csv(BASE/f'ranking_{"C64" if mode=="C" else mode}.csv')
                assert legacy.region_id.tolist()==saved.region_id.tolist()
                np.testing.assert_allclose(legacy.distance,saved.distance,rtol=0,atol=1e-10)
                baseline[mode]=(order,d)
            br,bd=baseline[mode]
            table=ranking(order,d,stations,target).assign(half_width_m=half,mode=mode)
            ref=ranking(br,bd,stations,target).set_index('region_id')['rank']
            table['baseline_rank']=table.region_id.map(ref);table['rank_change']=table.baseline_rank-table['rank'];allranks.append(table)
            for i,s in enumerate(stations.itertuples()):
                common=len(set(order[i,:10])&set(br[i,:10]));valid=mask[i]
                rho=float(spearmanr(d[i,valid],bd[i,valid]).statistic)
                summary.append(dict(half_width_m=half,mode=mode,region_id=s.region_id,station_name=s.station_name,common_top10=common,spearman=rho,poi_count=int(prof.iloc[i].poi_count),baseline_poi_count=int(old.iloc[i].poi_count)))
                positions=np.empty(len(stations),int);positions[br[i]]=np.arange(1,len(stations)+1)
                for rank,j in enumerate(order[i,:10],1):
                    all_top10.append(dict(half_width_m=half,mode=mode,query_region_id=s.region_id,query_station_name=s.station_name,rank=rank,region_id=region_ids[j],station_name=station_names[j],distance=float(d[i,j]),baseline_rank=int(positions[j])))
            labels=ordered_labels(prof,fit_kmeans(x.toarray() if sparse.issparse(x) else x,3).labels_)
            if half==500:
                baseline_labels[mode]=labels
                if mode in ('A','C'):
                    saved=pd.read_csv((ROOT/'data/cache/clustering/tokyo-v1' if mode=='A' else BASE)/'assignments.csv')
                    np.testing.assert_array_equal(labels,saved.cluster)
            aligned,mapping,cross=alignment(baseline_labels[mode],labels)
            cluster_stats.append(dict(half_width_m=half,mode=mode,ari=float(adjusted_rand_score(baseline_labels[mode],labels)),changed=int(np.sum(aligned!=baseline_labels[mode])),kichijoji_cluster=int(aligned[target]),sizes=[int(np.sum(aligned==g)) for g in range(1,4)]))
            for i,s in enumerate(stations.itertuples()):cluster_rows.append(dict(half_width_m=half,mode=mode,region_id=s.region_id,station_name=s.station_name,cluster=int(aligned[i]),baseline_cluster=int(baseline_labels[mode][i])))
            xx=x.toarray() if sparse.issparse(x) else x
            for g in range(1,4):
                ii=np.flatnonzero(aligned==g);cent=xx[ii].mean(axis=0);near=ii[np.argsort(np.linalg.norm(xx[ii]-cent,axis=1),kind='stable')[:3]]
                mean=np.asarray(b[ii].mean(axis=0)).ravel();top=np.argsort(-mean,kind='stable')[:8]
                cluster_summaries.append(dict(half_width_m=half,mode=mode,cluster=g,count=len(ii),representatives=' / '.join(stations.iloc[near].station_name),categories=';'.join(vocab[j] for j in top),**{col:float(prof.iloc[ii][col].median()) for col in REGION_COLUMNS[2:]}))
            if mode in ('B','C'):
                sim=np.asarray((x[pi].multiply(x[pj])).sum(axis=1)).ravel() if sparse.issparse(x) else np.sum(x[pi]*x[pj],axis=1)
                shared=np.asarray(incidence.multiply(incidence).sum(axis=1)).ravel()
                joint=np.asarray((incidence@incidence.T)[pi,pj]).ravel()
                jacc=joint/(shared[pi]+shared[pj]-joint)
                for q in range(len(pi)):overlaps.append(dict(half_width_m=half,mode=mode,first=stations.iloc[pi[q]].region_id,second=stations.iloc[pj[q]].region_id,shared_poi_jaccard=float(jacc[q]),cosine_similarity=float(sim[q])))
        if half>500:
            diff=(counts-baseline_counts).toarray()
            for i,s in enumerate(stations.itertuples()):
                for j in np.argsort(-diff[i],kind='stable')[:5]:
                    if diff[i,j]>0:deltas.append(dict(half_width_m=half,region_id=s.region_id,station_name=s.station_name,category=vocab[j],added_count=int(diff[i,j])))
        sparse.save_npz(OUT/f'counts_{half}.npz',counts)
        np.save(OUT/f'embedding_{half}.npy',c)
        print(f'Computed {half} m: {int(prof.poi_count.sum())} assignments',flush=True)
    for name,data in [('rankings',pd.concat(allranks)),('all_station_top10',all_top10),('features',pd.concat(features)),('audit',audits),('station_stability',summary),('cluster_metrics',cluster_stats),('assignments',cluster_rows),('cluster_summary',cluster_summaries),('added_categories',deltas),('overlap_pairs',overlaps)]:
        pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False)
    stats=pd.DataFrame(summary)
    stats.groupby(['mode','half_width_m']).agg(common_mean=('common_top10','mean'),common_median=('common_top10','median'),spearman_mean=('spearman','mean'),spearman_median=('spearman','median')).reset_index().to_csv(OUT/'summary.csv',index=False)
    report=dict(release=m['release'],acquisition_utc=sm['completed_at_utc'],baseline_acquisition_utc=m['completed_at_utc'],completed_at_utc=datetime.now(timezone.utc).isoformat(),baseline_reproduced=True,station_count=656,category_count=961,common_exclusion_half_width_m=800,raw_manifest_sha256=digest(RAW/'manifest.json'),supplement_manifest_sha256=digest(SUPPLEMENT/'manifest.json'),vocabulary_sha256=digest(BASE/'vocabulary.csv'),supplement_rows=sm['rows'],supplement_bytes=sm['bytes'],baseline_manifest_sha256=digest(BASE/'manifest.json'),output_sha256={p.name:digest(p) for p in OUT.iterdir() if p.suffix in ('.csv','.npz','.npy')})
    report['environment']={'python':platform.python_version(),**{p:version(p) for p in ('numpy','scipy','pandas','scikit-learn','duckdb','pyproj','shapely')}}
    report['code_and_conditions_sha256']={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'uv.lock',ROOT/'src/geoai_open_lab/aoi_sensitivity.py',ROOT/'src/geoai_open_lab/region_embedding.py',ROOT/'configs/region_features.toml',ROOT/'docs/aoi-sensitivity-design.md']}
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):shutil.copyfile(BASE/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:f.write('\n2026-10-17: AOI half-width sensitivity and aggregate analysis.\n')
    return pd.read_csv(OUT/'summary.csv'),report,OUT

if __name__=='__main__': print(run()[0].to_string(index=False))
