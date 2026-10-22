"""Three operational definitions, read-only reuse of Notebook 11b membership."""
import argparse
import itertools
import json
import os
import shutil
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from . import walking_sensitivity as ws
from .walking_range import routing,reachable_intervals
from .walking_inputs import HASHES

ROOT=ws.ROOT
OUT=ROOT/'data/cache/station_range_methods/tokyo-v1'
METHODS=('square','straight500','road500')
PAIRS=tuple(itertools.combinations(METHODS,2))
STATIONS=('n02-003700','n02-003584')


def snapshot():
    """Guard all artifacts of 11/11b, including their figures and execution records."""
    return {str(p.relative_to(ROOT)):ws.digest(p) for folder in (ws.OLD,ws.OUT) for p in folder.rglob('*') if p.is_file()}


def compare(frame,valid=True):
    rows=[]
    for a,b in PAIRS:
        ma,mb=frame[a],frame[b];na,nb=int(ma.sum()),int(mb.sum())
        shared=int((ma&mb).sum());union=int((ma|mb).sum())
        ok=valid or b!='road500'
        r=dict(first=a,second=b,valid=ok,n_first=na,n_second=nb,shared=shared,union=union,
               jaccard=shared/union if union and ok else np.nan,count_difference=nb-na if ok else np.nan,low_poi=union<30)
        differences=[]
        for g in ws.GROUPS:
            delta=frame.loc[mb,'group'].eq(g).sum()/nb-frame.loc[ma,'group'].eq(g).sum()/na if na and nb and ok else np.nan
            r[g+'_difference_pp']=float(delta)*100;differences.append(delta)
        r['composition_tvd']=sum(abs(v) for v in differences)/2
        rows.append(r)
    return rows


def run(road_dir=None):
    before=snapshot();audit,conditions,old_pairs,_=ws.load_results()
    records=[]
    for r in audit.itertuples():
        f=pd.read_parquet(ws.OUT/'stations'/f'{r.region_id}.parquet')
        assert f.id.is_unique and f.group.isin(ws.GROUPS).all()
        assert (~f.straight500|f.square).all() and (~f.road500|f.straight500).all()
        for method in METHODS:
            expected=conditions[(conditions.region_id==r.region_id)&(conditions.condition==method)].iloc[0]
            assert int(f[method].sum())==expected.poi_count
        records.extend(dict(region_id=r.region_id,station_name=r.station_name,**c) for c in compare(f,r.valid))
    pairs=pd.DataFrame(records)
    repeated=pairs[pairs['first'].eq('straight500')].reset_index(drop=True)
    old=old_pairs[old_pairs['first'].eq('straight500')&old_pairs['second'].eq('road500')].reset_index(drop=True)
    pd.testing.assert_frame_equal(repeated,old,check_dtype=False,atol=1e-12,rtol=1e-12)
    OUT.mkdir(parents=True,exist_ok=True)
    distributions=ws.summarize(pairs)
    pairs.to_csv(OUT/'comparisons.csv',index=False);distributions.to_csv(OUT/'distributions.csv',index=False)
    conditions[conditions.condition.isin(METHODS)].to_csv(OUT/'conditions.csv',index=False)
    pairs[pairs.region_id.isin(STATIONS)].to_csv(OUT/'examples.csv',index=False)
    road_dir=Path(road_dir or os.environ['GEOAI_OSM_ROAD_DIR'])
    for name,h in HASHES.items():assert ws.digest(road_dir/name)==h
    index=ws.RoadIndex(pd.read_parquet(road_dir/'nodes.parquet'),pd.read_parquet(road_dir/'edges.parquet'))
    # Only Shinjuku needs newly rendered network segments; no new routing analysis for 656 stations.
    station=audit[audit.region_id.eq(STATIONS[0])].iloc[0];center=(station.x,station.y)
    edges=index.local(center);distances,_,origin=routing(edges,center)
    assert np.isclose(origin[1],station.source_connector_m,atol=1e-8,rtol=0)
    segments=[]
    for i,e in enumerate(edges):
        for lo,hi in reachable_intervals(e,distances,500,origin[1:] if i==origin[0] else None):
            a,b=e['line'].interpolate(lo),e['line'].interpolate(hi)
            segments.append(dict(x1=a.x,y1=a.y,x2=b.x,y2=b.y,length_m=hi-lo))
    pd.DataFrame(segments).to_csv(OUT/'shinjuku_reachable500.csv',index=False)
    pd.DataFrame([dict(x1=e['line'].coords[0][0],y1=e['line'].coords[0][1],x2=e['line'].coords[1][0],y2=e['line'].coords[1][1]) for e in edges]).to_csv(OUT/'shinjuku_roads.csv',index=False)
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):shutil.copyfile(ws.OUT/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as file:file.write('\n2026-10-22: Three station-range definitions; Shinjuku article figures.\n')
    assert before==snapshot(),'Existing artifacts changed'
    ws.json_write(OUT/'manifest.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),input_manifest_sha256=ws.digest(ws.OUT/'manifest.json'),
       source_sha256=ws.digest(Path(__file__)),lock_sha256=ws.digest(ROOT/'uv.lock'),existing_artifacts_sha256=before,
       methods=list(METHODS),station_count=len(audit),valid_stations=int(audit.valid.sum()),low_poi_threshold=30,road_sha256=HASHES,
       output_sha256={p.name:ws.digest(p) for p in OUT.glob('*.csv')},selection='User-selected Shinjuku and Kichijoji; both predeclared 11b controls'))
    print(distributions[['first','second','cohort','valid_stations','jaccard_median','composition_tvd_median']].to_string(index=False))
    return pairs,distributions


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--road-dir');args=p.parse_args();run(args.road_dir)
