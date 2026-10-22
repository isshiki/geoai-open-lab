"""Offline boundary-definition audit. Never writes Notebook 11 artifacts."""
import argparse
import itertools
import json
import os
import shutil
import platform
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from importlib.metadata import version
import duckdb
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer, network
from shapely.geometry import LineString, Point
from .region_clustering import ROOT, digest, load_inputs
from .region_features import SHARE_GROUPS, OTHER, MISSING
from .walking_inputs import HASHES, PBF_HASH
from .walking_range import RAW, snap, routing, poi_distance

OUT = ROOT/'data/cache/walking_sensitivity/tokyo-v1'
SUP = ROOT/'data/raw/aoi_sensitivity/supplement-v1'
OLD = ROOT/'data/cache/walking_range/kichijoji-v1'
CONDITIONS = ('square', 'straight400', 'straight500', 'straight800', 'road400', 'road500', 'road800')
PAIRS = tuple(itertools.combinations(CONDITIONS[1:4], 2)) + tuple(itertools.combinations(CONDITIONS[4:], 2)) + (('straight500','road500'),('square','road800'))
CONTROLS = ('003584','003700','003766','003634','004387','003260','004029','003069')
GROUPS = tuple({OTHER:'other', MISSING:'missing'}.get(g,g) for g in SHARE_GROUPS)
LOW_POI = 30


def json_write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')


def masks(frame):
    result = {'square': (abs(frame.dx)<=500)&(abs(frame.dy)<=500)}
    for limit in (400,500,800):
        result['straight'+str(limit)] = frame.straight_m <= limit
        result['road'+str(limit)] = frame.road_distance_m <= limit
    return result


def compare(frame, selected, road_valid=True):
    rows=[]
    for a,b in PAIRS:
        valid=road_valid or not ('road' in a or 'road' in b)
        ma,mb=selected[a],selected[b];na,nb=int(ma.sum()),int(mb.sum())
        union=int((ma|mb).sum());shared=int((ma&mb).sum())
        row=dict(first=a,second=b,valid=valid,n_first=na,n_second=nb,shared=shared,union=union,
                 jaccard=shared/union if valid and union else np.nan,
                 count_difference=nb-na if valid else np.nan, low_poi=union<LOW_POI)
        differences=[]
        for group in GROUPS:
            delta=float(frame.loc[mb,'group'].eq(group).sum()/nb-frame.loc[ma,'group'].eq(group).sum()/na) if valid and na and nb else np.nan
            row[group+'_difference_pp']=100*delta;differences.append(delta)
        row['composition_tvd']=sum(abs(v) for v in differences)/2
        rows.append(row)
    return rows


class RoadIndex:
    """Conservative local edge extraction, zero-edge contraction, stable OSM IDs."""
    def __init__(self, nodes, edges):
        xy=nodes[['x','y']].to_numpy();uv=edges[['u','v']].to_numpy(copy=True)
        assert nodes.node_id.is_unique and np.isfinite(xy).all()
        assert np.issubdtype(uv.dtype,np.integer) and uv.min()>=0 and uv.max()<len(nodes)
        length=np.linalg.norm(xy[uv[:,0]]-xy[uv[:,1]],axis=1)
        assert np.allclose(length,edges.length_m,rtol=1e-10,atol=1e-7)
        # Retain connectivity of coincident endpoints without projecting on degenerate lines.
        parent={}
        def root(i):
            while i in parent:i=parent[i]
            return i
        for u,v in uv[length==0]:
            a,b=root(int(u)),root(int(v))
            if a!=b:parent[max(a,b)]=min(a,b)
        for node in parent:uv[uv==node]=root(node)
        self.zero_edges=int((length==0).sum())
        keep=length>0;uv=uv[keep];length=length[keep]
        ids=nodes.node_id.to_numpy();self.ids=ids[uv]
        self.a=xy[uv[:,0]];self.b=xy[uv[:,1]]
        self.short=np.flatnonzero(length<=200);self.long=np.flatnonzero(length>200)
        self.tree=cKDTree((self.a[self.short]+self.b[self.short])/2)

    def local(self, center, half=900):
        candidates=self.short[self.tree.query_ball_point(center,np.sqrt(2)*half+100)]
        candidates=np.concatenate([candidates,self.long])
        a,b=self.a[candidates],self.b[candidates]
        ok=(np.maximum(a,b)>=np.asarray(center)-half).all(axis=1)&(np.minimum(a,b)<=np.asarray(center)+half).all(axis=1)
        result={}
        for i in candidates[ok]:
            u,v=map(int,self.ids[i]);a,b=self.a[i],self.b[i]
            if u>v:u,v,a,b=v,u,b,a
            line=LineString([a,b])
            if (u,v) not in result or line.length<result[u,v].length:result[u,v]=line
        return [dict(u=u,v=v,line=line) for (u,v),line in sorted(result.items())]


def inputs():
    network.set_network_enabled(False)
    _,stations,station_manifest,_=load_inputs()
    pm=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    sm=json.loads((SUP/'manifest.json').read_text(encoding='utf8'))
    assert pm['coverage_complete'] and sm['coverage_complete'] and pm['release']==sm['release']=='2026-09-23.0'
    assert all(pm[k] is None for k in ('limit','country_filter','status_filter','confidence_filter'))
    assert sm['base_manifest_sha256']==digest(RAW/'manifest.json')
    assert digest(SUP/'places.parquet')==sm['sha256']
    for name,h in pm['output_sha256'].items():assert digest(RAW/name)==h
    bbox=pm['acquisition_bbox'];boxes=[tuple(bbox[k] for k in ('west','south','east','north'))]+sm['acquisition_boxes']
    inv=Transformer.from_crs(6677,4326,always_xy=True)
    for r in stations.itertuples():
        w,s,e,n=inv.transform_bounds(r.x-800,r.y-800,r.x+800,r.y+800,densify_pts=100)
        assert any(bw<=w+1e-10 and bs<=s+1e-10 and be>=e-1e-10 and bn>=n-1e-10 for bw,bs,be,bn in boxes),r.region_id
        w,s,e,n=inv.transform_bounds(r.x-900,r.y-900,r.x+900,r.y+900,densify_pts=100)
        assert w>=138.90 and s>=35.47 and e<=140.00 and n<=35.93,'Road extract coverage'
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        f=con.execute('SELECT id,ST_X(geometry) lon,ST_Y(geometry) lat,basic_category,operating_status FROM read_parquet(?) ORDER BY id',[[str(RAW/'places.parquet'),str(SUP/'places.parquet')]]).df()
    assert len(f)==pm['row_count']+sm['rows'] and f.id.is_unique and f.id.notna().all()
    f['x'],f['y']=Transformer.from_crs(4326,6677,always_xy=True).transform(f.lon.to_numpy(),f.lat.to_numpy())
    cfg=tomllib.loads((ROOT/'configs/region_features.toml').read_text(encoding='utf8'))
    mapping={c:g for g,cs in cfg['display_groups'].items() for c in cs}
    f['group']=f.basic_category.fillna('').map(lambda c:'missing' if not c else mapping.get(c,'other'))
    return stations,f,dict(poi_manifest_sha256=digest(RAW/'manifest.json'),supplement_manifest_sha256=digest(SUP/'manifest.json'),
                           station_manifest_sha256=digest(ROOT/'data/cache/similar_regions/tokyo-v1/manifest.json'),
                           category_config_sha256=digest(ROOT/'configs/region_features.toml'),release=pm['release'],
                           poi_acquired_utc=pm['completed_at_utc'],supplement_acquired_utc=sm['completed_at_utc'])


def calculate_station(row, f, tree, roads):
    center=(row.x,row.y)
    ix=tree.query_ball_point(center,np.sqrt(2)*800+1e-7)
    t=f.iloc[ix].copy();t['dx']=t.x-row.x;t['dy']=t.y-row.y
    t=t[(abs(t.dx)<=800)&(abs(t.dy)<=800)].sort_values('id').reset_index(drop=True)
    t['straight_m']=np.hypot(t.dx,t.dy);edges=roads.local(center)
    source_offset=snap(edges,[Point(center)])[0][1] if edges else np.nan
    valid=bool(edges) and source_offset<=100
    t['road_distance_m']=np.nan;t['connector_m']=np.nan;t['routing_status']='station_unconnected'
    if valid:
        distances,_,origin=routing(edges,center)
        ss=snap(edges,[Point(x,y) for x,y in zip(t.x,t.y)])
        rr=[poi_distance(edges,distances,origin,p) for p in ss]
        t['road_distance_m']=[r[0] for r in rr];t['routing_status']=[r[1] for r in rr];t['connector_m']=[p[1] for p in ss]
        finite=t.road_distance_m.notna()
        assert (t.loc[finite,'road_distance_m']+1e-7>=t.loc[finite,'straight_m']).all()
    selected=masks(t)
    for key,m in selected.items():t[key]=m
    for prefix in ('straight','road'):
        assert (~t[prefix+'400']|t[prefix+'500']).all() and (~t[prefix+'500']|t[prefix+'800']).all()
    for d in (400,500,800):assert (~t['road'+str(d)]|t['straight'+str(d)]).all()
    audit=dict(region_id=row.region_id,station_name=row.station_name,x=row.x,y=row.y,valid=valid,
               reason='ok' if valid else ('no_edges' if not edges else 'station_connector_over_100m'),
               source_connector_m=source_offset,local_edges=len(edges),candidates=len(t),
               poi_connector_over_100m=int(t.routing_status.eq('connector_over_limit').sum()),poi_disconnected=int(t.routing_status.eq('disconnected').sum()))
    rows=[]
    for key,m in selected.items():
        rr=dict(region_id=row.region_id,condition=key,valid=valid or not key.startswith('road'),poi_count=int(m.sum()))
        for g in GROUPS:rr[g+'_count']=int(t.loc[m,'group'].eq(g).sum());rr[g+'_share']=rr[g+'_count']/rr['poi_count'] if rr['poi_count'] else np.nan
        rows.append(rr)
    comparisons=[dict(region_id=row.region_id,station_name=row.station_name,**r) for r in compare(t,selected,valid)]
    return t,audit,rows,comparisons


def summarize(comparisons):
    rows=[]
    for (a,b),all_rows in comparisons.groupby(['first','second'],sort=False):
        for cohort,mask in [('all',all_rows.valid),('union_ge30',all_rows.valid&~all_rows.low_poi),('union_lt30',all_rows.valid&all_rows.low_poi)]:
            t=all_rows[mask];r=dict(first=a,second=b,cohort=cohort,valid_stations=len(t),jaccard_defined=int(t.jaccard.notna().sum()),
                                   ge_09=int(t.jaccard.ge(.9).sum()),lt_07=int(t.jaccard.lt(.7).sum()))
            for col in ['jaccard','count_difference','composition_tvd']+[g+'_difference_pp' for g in GROUPS]:
                q=t[col].quantile([0,.1,.5,.9,1])
                for label,v in zip(['min','p10','median','p90','max'],q):r[col+'_'+label]=v
            k=t[t.region_id.eq('n02-003584')]
            r['kichijoji_percentile']=100*((t.jaccard<k.jaccard.iloc[0]).sum()+.5*(t.jaccard==k.jaccard.iloc[0]).sum())/t.jaccard.notna().sum() if len(k) and t.jaccard.notna().any() else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def verify_baseline(t):
    old=pd.read_csv(OLD/'pois.csv')
    for before,after in [('square','square'),('circle','straight500'),('walk5','road400'),('walk10','road800')]:
        assert set(old.loc[old[before],'id'])==set(t.loc[t[after],'id']),after
    shared=t.merge(old[['id','road_distance_m','connector_m']],on='id',suffixes=('','_old'),validate='one_to_one')
    assert len(shared)==len(t)
    # Local edge truncation can alter long (>800m) detours; only reachable distances are the comparison target.
    active=(shared.road_distance_m<=800)|(shared.road_distance_m_old<=800)
    assert np.allclose(shared.loc[active,'road_distance_m'],shared.loc[active,'road_distance_m_old'],atol=1e-7,rtol=0)
    assert np.allclose(shared.loc[active,'connector_m'],shared.loc[active,'connector_m_old'],atol=1e-7,rtol=0)
    return dict(membership_exact=True,reachable_distances_equal=True,checked_pois=int(active.sum()))


def run(road_dir=None):
    road_dir=Path(road_dir or os.environ['GEOAI_OSM_ROAD_DIR'])
    for name,h in HASHES.items():assert digest(road_dir/name)==h,name
    stations,f,provenance=inputs()
    old_hashes={p.name:digest(p) for p in OLD.iterdir() if p.is_file()}
    roads=RoadIndex(pd.read_parquet(road_dir/'nodes.parquet'),pd.read_parquet(road_dir/'edges.parquet'))
    tree=cKDTree(f[['x','y']].to_numpy());OUT.mkdir(parents=True,exist_ok=True);(OUT/'stations').mkdir(exist_ok=True)
    audits=[];summaries=[];comparisons=[];baseline=None
    for i,r in enumerate(stations.itertuples()):
        t,a,s,c=calculate_station(r,f,tree,roads)
        t.to_parquet(OUT/'stations'/f'{r.region_id}.parquet',index=False)
        audits.append(a);summaries.extend(s);comparisons.extend(c)
        if r.region_id=='n02-003584':baseline=verify_baseline(t)
        if (i+1)%25==0:print(f'{i+1}/656 stations',flush=True)
    audit=pd.DataFrame(audits);summary=pd.DataFrame(summaries);pairs=pd.DataFrame(comparisons)
    assert len(audit)==656 and audit.region_id.is_unique and baseline
    distributions=summarize(pairs)
    candidates=pairs[pairs['first'].eq('square')&pairs['second'].eq('road800')&pairs.valid&~pairs.low_poi]
    chosen=[]
    for label,ascending in [('low',True),('high',False)]:
        r=candidates.sort_values(['jaccard','region_id'],ascending=[ascending,True]).iloc[0]
        chosen.append(dict(selection=label,region_id=r.region_id,station_name=r.station_name,jaccard=float(r.jaccard)))
    controls=pairs[pairs.region_id.isin(['n02-'+x for x in CONTROLS])]
    for name,table in dict(stations=audit,conditions=summary,comparisons=pairs,distributions=distributions,controls=controls).items():table.to_csv(OUT/(name+'.csv'),index=False)
    json_write(OUT/'examples.json',chosen)
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(OLD/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as file:
        file.write('\n2026-10-22: 656-station boundary-definition sensitivity aggregates and figures.\n')
    assert old_hashes=={p.name:digest(p) for p in OLD.iterdir() if p.is_file()},'Notebook 11 output changed'
    manifest=dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),**provenance,road_sha256=HASHES,pbf_sha256=PBF_HASH,
                  road_release='kanto-261001',road_source_url='https://download.geofabrik.de/asia/japan/kanto-261001.osm.pbf',road_acquired_utc='2026-10-03T09:29:33Z',
                  lock_sha256=digest(ROOT/'uv.lock'),routing_sha256=digest(ROOT/'src/geoai_open_lab/walking_range.py'),
                  command='uv run --no-sync python -m geoai_open_lab.walking_sensitivity --road-dir <fixed-road-directory>',
                  zero_edges_contracted=roads.zero_edges,baseline=baseline,crs='EPSG:6677',connector_limit_m=100,crop_half_width_m=900,
                  low_poi_union_threshold=LOW_POI,controls=['n02-'+x for x in CONTROLS],station_count=len(audit),valid_road_stations=int(audit.valid.sum()),
                  python=platform.python_version(),packages={p:version(p) for p in ['numpy','pandas','scipy','networkx','shapely','pyproj','duckdb']},
                  source_sha256=digest(Path(__file__)),design_sha256=digest(ROOT/'docs/walking-sensitivity-design.md'),old_artifacts_sha256=old_hashes,
                  output_sha256={str(p.relative_to(OUT)).replace('\\','/'):digest(p) for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.csv','.parquet')})
    json_write(OUT/'manifest.json',manifest)
    print(distributions[['first','second','cohort','valid_stations','jaccard_median']].to_string(index=False))
    return audit,summary,pairs,distributions


def load_results():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    for name,h in m['output_sha256'].items():
        if digest(OUT/name)!=h:raise ValueError('Output checksum mismatch: '+name)
    return tuple(pd.read_csv(OUT/(n+'.csv')) for n in ('stations','conditions','comparisons','distributions'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--road-dir');a=p.parse_args();run(a.road_dir)
