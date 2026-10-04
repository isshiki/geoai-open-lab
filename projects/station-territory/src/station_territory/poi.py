"""OSM facilities from the existing PBF only; extensions must already be installed."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
from collections import Counter
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import polygonize
import duckdb
from .territory import ROOT, OUT, RESULT, TR, area23, rank
from .local_duckdb import connect
from .provenance import digest

POLICY = json.loads((ROOT/'configs/poi_policy.json').read_text(encoding='utf-8'))


def category(tags):
    if tags.get('railway') in ('station','halt','platform','stop') or tags.get('public_transport') in ('station','platform','stop_position'):
        return None
    a=tags.get('amenity')
    active=lambda k: tags.get(k) and tags[k] not in POLICY['disabled_values']
    if active('healthcare') or a in POLICY['medical_amenity']: return 'healthcare'
    if a in POLICY['food']: return 'food'
    if a in POLICY['education']: return 'education'
    if active('shop'): return 'shop'
    if active('tourism'): return 'tourism'
    if active('leisure') and tags['leisure'] not in POLICY['excluded_leisure']: return 'leisure'
    if active('office'): return 'office'
    if active('amenity') and a not in POLICY['excluded_amenity']: return 'other_amenity'
    return None


def way_geom(refs,nodes):
    if not refs or any(int(i) not in nodes for i in refs): return None
    xy=[nodes[int(i)] for i in refs]
    if len(xy)<2: return None
    geom=Polygon(xy) if len(xy)>=4 and refs[0]==refs[-1] else LineString(xy)
    return shapely.make_valid(geom) if not geom.is_valid else geom


def relation_geometry(refs,ref_types,ref_roles,tags,members,nodes):
    """Only complete supported member topology is accepted; no nested relations."""
    geom=None;parts=[];outer=[];inner=[];complete=True
    for ref,typ,role in zip(refs,ref_types,ref_roles):
        if typ=='way':
            m=way_geom(list(members.get(int(ref),[])),nodes)
            if m is None: complete=False;break
            if tags.get('type')=='multipolygon':
                (inner if role=='inner' else outer).append(m.boundary if 'Polygon' in m.geom_type else m)
            else: parts.append(m)
        elif typ=='node' and int(ref) in nodes: parts.append(Point(nodes[int(ref)]))
        else: complete=False;break
    if complete:
        if tags.get('type')=='multipolygon' and outer:
            og=shapely.union_all(list(polygonize(shapely.union_all(outer))))
            ig=shapely.union_all(list(polygonize(shapely.union_all(inner)))) if inner else shapely.Polygon()
            geom=shapely.difference(og,ig)
        elif parts: geom=shapely.union_all(parts)
    return geom


def run():
    cache=OUT/'cache/osm_poi_candidates.parquet'
    cache.parent.mkdir(parents=True,exist_ok=True)
    fingerprint=hashlib.sha256((ROOT/'data/raw/kanto-261001.osm.pbf').read_bytes()).hexdigest()
    meta=cache.with_suffix('.json')
    pbf=(ROOT/'data/raw/kanto-261001.osm.pbf').as_posix()
    con=connect()
    keys=['shop','amenity','tourism','leisure','healthcare','office']
    where=' OR '.join(f"tags['{k}'] IS NOT NULL" for k in keys)
    cache_key={'pbf_sha256':fingerprint,'code_sha256':digest(Path(__file__)),
               'extraction_version':1,'keys':keys}
    reusable=False
    if cache.exists() and meta.exists():
        previous=json.loads(meta.read_text(encoding='utf-8'))
        if previous.get('cache_sha256') != digest(cache):
            raise ValueError('POI cache content hash mismatch')
        reusable=previous.get('cache_key')==cache_key
    if reusable: candidates=pd.read_parquet(cache)
    else:
        print('Read tagged OSM objects',flush=True)
        candidates=con.execute(f"SELECT kind::VARCHAR kind,id,tags,refs,lat,lon,ref_roles,ref_types FROM ST_ReadOSM('{pbf}') WHERE {where}").df()
        # Keep original tag and topology data as isolated local input cache.
        candidates['tags']=candidates.tags.apply(lambda t: json.dumps(t,ensure_ascii=False))
        candidates.to_parquet(cache,index=False)
        meta.write_text(json.dumps({'cache_key':cache_key,'cache_sha256':digest(cache)},indent=2),encoding='utf-8')
    candidates['category']=candidates.tags.apply(lambda t: category(json.loads(t)))
    candidates=candidates[candidates.category.notna()]
    relations=candidates[candidates.kind=='relation']
    ids=set()
    for row in relations.itertuples():
        ids.update(int(i) for i,t in zip(row.refs,row.ref_types) if t=='way')
    con.register('needed',pd.DataFrame({'id':list(ids)}))
    print('Read relation member ways',flush=True)
    ways=con.execute(f"SELECT o.id,o.refs FROM ST_ReadOSM('{pbf}') o JOIN needed n USING(id) WHERE o.kind='way'").fetchall()
    members={int(i):refs for i,refs in ways}
    # Only materialize nodes used by these candidates or their member ways.
    # The same bbox and complete-topology requirements still apply.
    needed_nodes=set(int(i) for i in candidates.loc[candidates.kind=='node','id'])
    for refs in candidates.loc[candidates.kind=='way','refs']:
        needed_nodes.update(int(i) for i in refs)
    for refs in members.values():
        needed_nodes.update(int(i) for i in refs)
    for row in relations.itertuples():
        needed_nodes.update(int(i) for i,t in zip(row.refs,row.ref_types) if t=='node')
    con.register('needed_nodes',pd.DataFrame({'id':pd.Series(sorted(needed_nodes),dtype='int64')}))
    print('Read referenced local node coordinates',flush=True)
    ns=con.execute(f"SELECT o.id,o.lon,o.lat FROM ST_ReadOSM('{pbf}') o JOIN needed_nodes n USING(id) WHERE o.kind='node' AND o.lon BETWEEN 138.90 AND 140.00 AND o.lat BETWEEN 35.47 AND 35.93").fetchnumpy()
    xx,yy=TR.transform(ns['lon'],ns['lat']);nodes={int(i):(float(x),float(y)) for i,x,y in zip(ns['id'],xx,yy)}
    con.close()
    print('Normalize candidate geometries',flush=True)
    aoi=area23()
    shapely.prepare(aoi)
    z=np.load(RESULT/'analysis_cells.npz');shape=tuple(z['shape']);own=np.full(shape,-1,dtype=np.int32)
    own[z['row'],z['col']]=z['owner'];stations=pd.read_parquet(RESULT/'all_stations.parquet')
    diagnostics=Counter();out=[]
    for row in candidates.itertuples():
        geom=None
        if row.kind=='node':
            if row.id in nodes: geom=Point(nodes[row.id])
        elif row.kind=='way': geom=way_geom(list(row.refs),nodes)
        else:
            geom=relation_geometry(row.refs,row.ref_types,row.ref_roles,json.loads(row.tags),members,nodes)
        if geom is None or geom.is_empty:
            diagnostics['unlocated_or_outside_coordinate_window']+=1
            diagnostics['unlocated_'+row.kind]+=1
            continue
        p=geom.representative_point()
        if not aoi.covers(p): continue
        r=int(np.floor((p.y-float(z['y0']))/float(z['cell'])));c=int(np.floor((p.x-float(z['x0']))/float(z['cell'])))
        owner=int(own[r,c]) if 0<=r<shape[0] and 0<=c<shape[1] else -1
        out.append({'osm_type':row.kind,'osm_id':row.id,'name':json.loads(row.tags).get('name'),
                    'category':row.category,'x':p.x,'y':p.y,'group':owner,
                    'key':stations.loc[owner,'key'] if owner>=0 else None})
    df=pd.DataFrame(out);assert not df.duplicated(['osm_type','osm_id']).any()
    df.to_parquet(RESULT/'poi_objects.parquet',index=False)
    valid=df[df.group>=0];counts=valid.groupby('group').size()
    stations['poi_count']=stations.index.map(counts).fillna(0).astype(int)
    stations['poi_per_km2']=stations.poi_count/stations.area_km2.replace(0,np.nan)
    for cat in POLICY['priority']:
        series=valid[valid.category==cat].groupby('group').size()
        stations[f'poi_{cat}']=stations.index.map(series).fillna(0).astype(int)
        rank(stations,f'poi_{cat}')[1].to_csv(RESULT/f'with_cutoff_ties_poi_{cat}.csv',index=False,encoding='utf-8-sig')
        rank(stations,f'poi_{cat}')[0].to_csv(RESULT/f'top10_poi_{cat}.csv',index=False,encoding='utf-8-sig')
    assert (stations[[f'poi_{c}' for c in POLICY['priority']]].sum(axis=1)==stations.poi_count).all()
    stations.to_parquet(RESULT/'all_stations.parquet',index=False)
    stations.to_csv(RESULT/'all_stations.csv',index=False,encoding='utf-8-sig')
    rank(stations,'poi_count')[1].to_csv(RESULT/'with_cutoff_ties_poi_count.csv',index=False)
    rank(stations,'poi_count')[0].to_csv(RESULT/'top10_poi_count.csv',index=False,encoding='utf-8-sig')
    audit={'total_objects_23':len(df),'unassigned_objects_23':int((df.group<0).sum()),
           'assigned_objects_23':len(valid),'outside_station_objects':int(stations.loc[~stations.station_in_23,'poi_count'].sum()),
           'category_counts':df.category.value_counts().to_dict(),'diagnostics_all_kanto_candidates':dict(diagnostics),
           'policy_sha256':hashlib.sha256((ROOT/'configs/poi_policy.json').read_bytes()).hexdigest(),
           'incomplete_geometries_may_include_inside_23':'unlocated count includes outside-window candidates; not an estimate of in-23 missing POI'}
    (RESULT/'poi_validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':run()
