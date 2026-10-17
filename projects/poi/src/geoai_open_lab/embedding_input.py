"""Pinned local POIs -> shared-POI incidence -> primary-category counts."""
import json
import tomllib
import duckdb
import numpy as np
import pandas as pd
from scipy import sparse
from pyproj import Transformer, network
from shapely import STRtree, points
from shapely.geometry import box
from .region_clustering import ROOT, digest, load_inputs
from .tokyo_region_features import validate_acquisition


def count_matrix(incidence, codes, n_categories, weights=None):
    valid=codes>=0
    if weights is None: weights=np.ones(len(codes))
    token=sparse.csr_matrix((np.asarray(weights)[valid],(np.flatnonzero(valid),codes[valid])),
                            shape=(len(codes),n_categories))
    return (incidence@token).tocsr()


def load_categories():
    profiles,stations,previous,_=load_inputs()
    cfg=tomllib.loads((ROOT/'configs/similar_regions.toml').read_text(encoding='utf8'))
    raw=ROOT/cfg['input_dir']
    if digest(raw/'manifest.json')!=cfg['manifest_sha256']: raise ValueError('Raw manifest changed')
    m=json.loads((raw/'manifest.json').read_text(encoding='utf8'))
    validate_acquisition(m,stations)
    for name,h in m['output_sha256'].items():
        if digest(raw/name)!=h: raise ValueError('Raw checksum mismatch')
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        frame=con.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat, taxonomy.primary category FROM read_parquet(?) ORDER BY id',[str(raw/'places.parquet')]).df()
    if len(frame)!=m['row_count'] or frame.id.isna().any() or frame.id.duplicated().any():
        raise ValueError('POI identity mismatch')
    network.set_network_enabled(False)
    x,y=Transformer.from_crs(4326,6677,always_xy=True).transform(frame.lon.to_numpy(),frame.lat.to_numpy())
    if not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError('Invalid geometry')
    tree=STRtree(points(x,y));rows=[];cols=[]
    for i,s in enumerate(stations.itertuples()):
        indices=np.sort(tree.query(box(s.x-500,s.y-500,s.x+500,s.y+500),predicate='covers'))
        rows.extend([i]*len(indices));cols.extend(indices)
    incidence=sparse.csr_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(stations),len(frame)))
    np.testing.assert_array_equal(np.asarray(incidence.sum(axis=1)).ravel(),profiles.poi_count)
    used=np.asarray(incidence.sum(axis=0)).ravel()>0
    incidence=incidence[:,used];category=frame.loc[used,'category'].fillna('').str.strip()
    vocabulary=sorted(set(category)-{''});lookup={v:i for i,v in enumerate(vocabulary)}
    codes=category.map(lookup).fillna(-1).to_numpy(dtype=int)
    counts=count_matrix(incidence,codes,len(vocabulary))
    df=np.asarray((counts>0).sum(axis=0)).ravel();keep=df>=5
    mapping=np.full(len(vocabulary),-1);mapping[keep]=np.arange(keep.sum())
    filtered=np.full(len(codes),-1);mask=codes>=0;filtered[mask]=mapping[codes[mask]]
    counts=counts[:,keep].tocsr()
    audit=stations[['region_id','station_name']].copy()
    audit['poi_count']=profiles.poi_count
    audit['category_missing']=np.asarray(incidence@(codes<0).astype(float)).ravel().astype(int)
    audit['rare_removed']=np.asarray(incidence@((codes>=0)&(filtered<0)).astype(float)).ravel().astype(int)
    audit['retained_count']=np.asarray(counts.sum(axis=1)).ravel().astype(int)
    assert (audit.category_missing+audit.rare_removed+audit.retained_count==audit.poi_count).all()
    if (audit.retained_count==0).any(): raise ValueError('Zero primary vocabulary row; stop')
    return profiles,stations,previous,counts,incidence,filtered,np.array(vocabulary)[keep],audit,dict(
        raw_manifest_sha256=digest(raw/'manifest.json'),raw_parquet_sha256=digest(raw/'places.parquet'),
        unique_aoi_pois=int(used.sum()),category_count_before_filter=len(vocabulary),
        retained_category_count=int(keep.sum()),unique_missing=int((codes<0).sum()))
