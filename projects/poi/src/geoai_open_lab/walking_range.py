"""Point-based walking reachability. Frozen inputs; fixed OSM snapshot only by default."""
import argparse
import itertools
import json
import platform
import shutil
import tomllib
from datetime import datetime, timezone
from importlib.metadata import version
import duckdb
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer, network
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
from .region_clustering import ROOT, digest
from .region_features import SHARE_GROUPS, MISSING, OTHER
from .walking_inputs import load_fixed_roads

OUT=ROOT/'data/cache/walking_range/kichijoji-v1'
RAW=ROOT/'data/raw/similar_regions/20261015T080101Z-tokyo'
CONDITIONS=('square','circle','walk5','walk10')


def snap(edges, points):
    """Nearest segment, deterministic ID-order tie; returns edge index, offset, position."""
    lines=[e['line'] for e in edges];tree=STRtree(lines);rows=[]
    for p in points:
        choices=tree.query_nearest(p,all_matches=True)
        i=int(min(choices));line=lines[i]
        rows.append((i,float(line.distance(p)),float(line.project(p))))
    return rows


def routing(edges, center, max_snap=100):
    graph=nx.Graph()
    for e in edges:graph.add_edge(e['u'],e['v'],weight=e['line'].length)
    index,offset,position=snap(edges,[Point(center)])[0]
    if offset>max_snap:raise ValueError('Station connector exceeds limit')
    edge=edges[index];source='station'
    graph.add_edge(source,edge['u'],weight=offset+position)
    graph.add_edge(source,edge['v'],weight=offset+edge['line'].length-position)
    distances,paths=nx.single_source_dijkstra(graph,source,weight='weight')
    return distances,paths,(index,offset,position)


def poi_distance(edges, distances, origin, snapped, max_snap=100):
    i,offset,t=snapped;e=edges[i];length=e['line'].length
    if offset>max_snap:return np.nan,'connector_over_limit'
    d=min(distances.get(e['u'],np.inf)+t,distances.get(e['v'],np.inf)+length-t)
    if i==origin[0]:d=min(d,origin[1]+abs(t-origin[2]))
    if not np.isfinite(d):return np.nan,'disconnected'
    return d+offset,'connected'


def reachable_intervals(edge, distances, budget, source_position=None):
    """Union of reachable intervals, including a source inside the edge."""
    length=edge['line'].length;parts=[]
    for start,end in [(0,budget-distances.get(edge['u'],np.inf)),(length-budget+distances.get(edge['v'],np.inf),length)]:
        lo,hi=max(0,start),min(length,end)
        if hi>lo:parts.append((lo,hi))
    if source_position is not None:
        offset,t=source_position;r=budget-offset
        if r>=0:parts.append((max(0,t-r),min(length,t+r)))
    merged=[]
    for lo,hi in sorted(parts):
        if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
        else:merged.append((lo,hi))
    return merged


def load_places(center):
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    assert m['release']=='2026-09-23.0' and m['coverage_complete'] and m['limit'] is None
    assert all(m[k] is None for k in ('country_filter','status_filter','confidence_filter'))
    for name,h in m['output_sha256'].items():assert digest(RAW/name)==h
    inv=Transformer.from_crs(6677,4326,always_xy=True)
    w,s,e,n=inv.transform_bounds(center[0]-1000,center[1]-1000,center[0]+1000,center[1]+1000,densify_pts=100)
    b=m['acquisition_bbox'];assert b['west']<=w and b['south']<=s and b['east']>=e and b['north']>=n
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        f=con.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat, basic_category, operating_status FROM read_parquet(?) ORDER BY id',[str(RAW/'places.parquet')]).df()
    assert len(f)==m['row_count'] and f.id.is_unique and f.id.notna().all()
    f['x'],f['y']=Transformer.from_crs(4326,6677,always_xy=True).transform(f.lon.to_numpy(),f.lat.to_numpy())
    f=f[(abs(f.x-center[0])<=1000)&(abs(f.y-center[1])<=1000)].copy().reset_index(drop=True)
    cfg=tomllib.loads((ROOT/'configs/region_features.toml').read_text(encoding='utf8'))
    mapping={c:g for g,cats in cfg['display_groups'].items() for c in cats}
    f['group']=f.basic_category.fillna('').map(lambda c:MISSING if not c else mapping.get(c,OTHER))
    return f,m


def run(road_dir=None, osm_pbf=None):
    network.set_network_enabled(False)
    station=ROOT/'configs/aoi/kichijoji_station_1km.toml'
    cfg=tomllib.loads(station.read_text(encoding='utf8'));center=(cfg['center_x'],cfg['center_y'])
    assert cfg['crs']=='EPSG:6677'
    f,pm=load_places(center);edges,road_meta=load_fixed_roads(center,road_dir,osm_pbf)
    distances,paths,origin=routing(edges,center)
    snapped=snap(edges,[Point(x,y) for x,y in zip(f.x,f.y)])
    results=[poi_distance(edges,distances,origin,p) for p in snapped]
    f['road_distance_m']=[r[0] for r in results];f['routing_status']=[r[1] for r in results]
    f['edge_index']=[r[0] for r in snapped];f['connector_m']=[r[1] for r in snapped];f['position_m']=[r[2] for r in snapped]
    f['straight_m']=np.hypot(f.x-center[0],f.y-center[1])
    assert (f.loc[f.road_distance_m.notna(),'road_distance_m']+1e-7>=f.loc[f.road_distance_m.notna(),'straight_m']).all()
    f['square']=(abs(f.x-center[0])<=500)&(abs(f.y-center[1])<=500)
    f['circle']=f.straight_m<=500
    f['walk5']=f.road_distance_m<=400;f['walk10']=f.road_distance_m<=800
    assert (~f.walk5|f.walk10).all() and (~f.walk5|f.circle).all()
    segments=[]
    for minutes,budget in [(5,400),(10,800)]:
        for i,edge in enumerate(edges):
            for lo,hi in reachable_intervals(edge,distances,budget,origin[1:] if i==origin[0] else None):
                a=edge['line'].interpolate(lo);b=edge['line'].interpolate(hi)
                segments.append(dict(minutes=minutes,edge_index=i,x1=a.x,y1=a.y,x2=b.x,y2=b.y,length_m=hi-lo))
    seg=pd.DataFrame(segments)
    # Every reachable point is within 800m of origin, safely inside the +/-1100m extraction.
    assert max(abs(seg.x1-center[0]).max(),abs(seg.y1-center[1]).max(),abs(seg.x2-center[0]).max(),abs(seg.y2-center[1]).max())<1100
    rows=[]
    for condition in CONDITIONS:
        t=f[f[condition]];row=dict(condition=condition,poi_count=len(t),road_length_m=float(seg.loc[seg.minutes.eq({'walk5':5,'walk10':10}.get(condition,0)),'length_m'].sum()) if condition.startswith('walk') else np.nan)
        for group in SHARE_GROUPS:
            name={OTHER:'other',MISSING:'missing'}.get(group,group);count=int(t.group.eq(group).sum());row[name+'_count']=count;row[name+'_share']=count/len(t) if len(t) else np.nan
        rows.append(row)
    summary=pd.DataFrame(rows);overlap=[]
    for a,b in itertools.combinations(CONDITIONS,2):
        shared=int((f[a]&f[b]).sum());union=int((f[a]|f[b]).sum())
        overlap.append(dict(first=a,second=b,shared=shared,union=union,jaccard=shared/union if union else np.nan,first_only=int((f[a]&~f[b]).sum()),second_only=int((f[b]&~f[a]).sum())))
    examples=[]
    for name,mask in [('square_not_walk10',f.square&~f.walk10),('walk10_not_square',f.walk10&~f.square),('circle_not_walk5',f.circle&~f.walk5)]:
        candidates=f[mask & f.road_distance_m.notna()].sort_values(['straight_m','id'])
        if candidates.empty:continue
        r=candidates.iloc[0];i=int(r.edge_index);edge=edges[i];t=r.position_m;poi_projection=edge['line'].interpolate(t)
        options=[(distances.get(edge['u'],np.inf)+t,edge['u']),(distances.get(edge['v'],np.inf)+edge['line'].length-t,edge['v'])]
        best,node=min(options)
        source_projection=edges[origin[0]]['line'].interpolate(origin[2]);points=[list(center),list(source_projection.coords[0])]
        if i!=origin[0] or best<origin[1]+abs(t-origin[2]):
            coordinates={e['u']:list(e['line'].coords[0]) for e in edges};coordinates.update({e['v']:list(e['line'].coords[-1]) for e in edges})
            points.extend(coordinates[n] for n in paths[node] if n!='station')
        points.extend([list(poi_projection.coords[0]),[float(r.x),float(r.y)]])
        assert np.isclose(sum(np.linalg.norm(np.subtract(b,a)) for a,b in zip(points,points[1:])),r.road_distance_m)
        examples.append(dict(example=name,id=r.id,category=r.basic_category,straight_m=r.straight_m,road_distance_m=r.road_distance_m,connector_m=r.connector_m,path=points))
    OUT.mkdir(parents=True,exist_ok=True)
    tables={'pois':f,'summary':summary,'overlap':pd.DataFrame(overlap),'reachable':seg,
            'roads':pd.DataFrame([dict(edge_index=i,u=e['u'],v=e['v'],x1=e['line'].coords[0][0],y1=e['line'].coords[0][1],x2=e['line'].coords[-1][0],y2=e['line'].coords[-1][1]) for i,e in enumerate(edges)])}
    for name,t in tables.items():t.to_csv(OUT/(name+'.csv'),index=False)
    (OUT/'examples.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf8')
    manifest=dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),center=center,crs='EPSG:6677',release=pm['release'],poi_acquisition_utc=pm['completed_at_utc'],input_sha256=pm['output_sha256'],station_config_sha256=digest(station),category_config_sha256=digest(ROOT/'configs/region_features.toml'),
       road_source=road_meta,source_snap_m=origin[1],source_edge_index=origin[0],source_position_m=origin[2],connector_limit_m=100,speed_m_per_minute=80,
       poi_candidates=len(f),routing_status=f.routing_status.value_counts().to_dict(),square_routing_status=f[f.square].routing_status.value_counts().to_dict(),nodes=len({n for e in edges for n in (e['u'],e['v'])}),edges=len(edges),source_component_nodes=len(distances)-1,coverage_complete=True,
       environment={'python':platform.python_version(),**{p:version(p) for p in ['networkx','shapely','pyproj','duckdb','pandas']}},code_sha256=digest(__file__),importer_sha256=digest(ROOT/'src/geoai_open_lab/walking_inputs.py'),lock_sha256=digest(ROOT/'uv.lock'),output_sha256={p.name:digest(p) for p in [*OUT.glob('*.csv'),OUT/'examples.json']})
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):shutil.copyfile(ROOT/'data/cache/embedding/tokyo-v1'/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as file:file.write('\n2026-10-22: Walking-range comparison aggregates and figures.\n')
    return summary,pd.DataFrame(overlap),manifest,OUT

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--road-dir');parser.add_argument('--osm-pbf');args=parser.parse_args()
    summary,overlap,m,out=run(args.road_dir,args.osm_pbf);print(summary.to_string(index=False));print(overlap.to_string(index=False));print('station snap',m['source_snap_m'],'OSM',m['road_source']['road_release'])
