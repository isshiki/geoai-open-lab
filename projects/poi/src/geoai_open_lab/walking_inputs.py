"""Read-only import of a reviewed, fixed eki-walk road snapshot. No network calls."""
import json
import os
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from .region_clustering import ROOT,digest

CACHE=ROOT/'data/cache/walking_range/roads-20261001'
HASHES={'nodes.parquet':'48cbab547e9f7b87453e44044c904b5ba56b5aefa15e37a1de6db22bea45dd01',
        'edges.parquet':'a95533cd09652be977924af23b8d969afef02f03dfa1c15e1f163b8080de8fd1'}
PBF_HASH='5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83'


def select_edges(nodes,edges,center,half_width=1100):
    """u/v are ROW INDICES, not OSM IDs. Preserve full segments intersecting bbox.

    With Euclidean segment weights, any path of <=800m stays inside +/-800m.
    +/-1100m additionally contains 100m snaps for all candidate POIs (+/-1000m).
    AABB selection is conservative: do not clip edges or connect crossings.
    """
    if not nodes.node_id.is_unique or nodes.isna().any().any():raise ValueError('Invalid node keys/values')
    xy=nodes[['x','y']].to_numpy();uv=edges[['u','v']].to_numpy()
    if not np.issubdtype(uv.dtype,np.integer) or uv.min()<0 or uv.max()>=len(nodes):raise ValueError('Invalid row-index endpoints')
    if not np.isfinite(xy).all() or not np.isfinite(edges.length_m).all() or (edges.length_m<0).any():raise ValueError('Invalid coordinates or lengths')
    a,b=xy[uv[:,0]],xy[uv[:,1]];length=np.linalg.norm(a-b,axis=1)
    if not np.allclose(length,edges.length_m,rtol=1e-10,atol=1e-7):raise ValueError('Stored lengths are not EPSG:6677 node-segment lengths')
    mask=(np.maximum(a,b)>=np.asarray(center)-half_width).all(axis=1)&(np.minimum(a,b)<=np.asarray(center)+half_width).all(axis=1)&(length>0)
    uv=uv[mask];a=a[mask];b=b[mask];ids=nodes.node_id.to_numpy()
    result=pd.DataFrame(dict(u=ids[uv[:,0]],v=ids[uv[:,1]],x1=a[:,0],y1=a[:,1],x2=b[:,0],y2=b[:,1],length_m=length[mask]))
    swap=result.u>result.v
    for first,second in [('u','v'),('x1','x2'),('y1','y2')]:result.loc[swap,[first,second]]=result.loc[swap,[second,first]].to_numpy(copy=True)
    if result.duplicated(['u','v']).any():raise ValueError('Duplicate undirected edges')
    return result.sort_values(['u','v']).reset_index(drop=True),int((length==0).sum())


def load_fixed_roads(center,road_dir=None,osm_pbf=None):
    road_dir=road_dir or os.environ.get('GEOAI_OSM_ROAD_DIR')
    manifest_path=CACHE/'manifest.json';cache_path=CACHE/'edges.parquet'
    if not manifest_path.exists():
        if not road_dir:raise FileNotFoundError('Pass --road-dir or GEOAI_OSM_ROAD_DIR once to import the fixed snapshot')
        source=Path(road_dir)
        for name,expected in HASHES.items():
            if digest(source/name)!=expected:raise ValueError('Unexpected fixed road file: '+name)
        pbf=Path(osm_pbf or os.environ.get('GEOAI_OSM_PBF',''))
        if not pbf.is_file() or digest(pbf)!=PBF_HASH:raise ValueError('Initial import requires --osm-pbf / GEOAI_OSM_PBF with expected SHA-256')
        nodes=pd.read_parquet(source/'nodes.parquet');edges=pd.read_parquet(source/'edges.parquet')
        assert len(nodes)==3466737 and len(edges)==4035109
        subset,zero=select_edges(nodes,edges,center)
        CACHE.mkdir(parents=True,exist_ok=True);subset.to_parquet(cache_path,index=False)
        m=dict(center=list(center),crs='EPSG:6677',crop_half_width_m=1100,road_release='kanto-261001',source_url='https://download.geofabrik.de/asia/japan/kanto-261001.osm.pbf',
               pbf_sha256=PBF_HASH,source_sha256=HASHES,source_rows={'nodes':len(nodes),'edges':len(edges)},source_acquired_utc='2026-10-03T09:29:33Z',imported_utc=datetime.now(timezone.utc).isoformat(),
               upstream_commit='4176263',upstream_network_sha256='a09e43cd5c6626cefa5099368450188601160c12cef6b64b69936c65bb6e5ce1',upstream_osmtags_sha256='f861794f7aa51489a10ee8e615ac19a0a9d2b2ad519932e90acf214dac851f5a',
               zero_length_edges_removed=zero,edges=len(subset),nodes=len(set(subset.u)|set(subset.v)),cache_sha256=digest(cache_path),license='ODbL-1.0')
        manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
    m=json.loads(manifest_path.read_text(encoding='utf8'))
    assert m['center']==list(center) and m['crs']=='EPSG:6677' and m['crop_half_width_m']==1100
    assert m['source_sha256']==HASHES and m['pbf_sha256']==PBF_HASH and digest(cache_path)==m['cache_sha256']
    t=pd.read_parquet(cache_path)
    result=[dict(u=int(r.u),v=int(r.v),line=LineString([(r.x1,r.y1),(r.x2,r.y2)])) for r in t.itertuples()]
    return result,m
