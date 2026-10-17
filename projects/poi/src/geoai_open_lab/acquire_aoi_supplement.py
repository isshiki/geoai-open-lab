"""Acquire only uncovered parts of the fixed 800 m station squares."""
import json
import time
from datetime import datetime, timezone
import duckdb
import pandas as pd
from pyproj import Transformer
from .region_clustering import ROOT, digest
from .overture import source_uri, validate_schema

RAW=ROOT/'data/raw/similar_regions/20261015T080101Z-tokyo'
OUT=ROOT/'data/raw/aoi_sensitivity/supplement-v1'

def acquire():
    if OUT.exists() and any(OUT.iterdir()): raise ValueError('Do not overwrite existing acquisition')
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    stations=pd.read_csv(RAW/'stations.csv'); b=m['acquisition_bbox']
    trans=Transformer.from_crs(6677,4326,always_xy=True)
    targets=[]; boxes=[]
    for r in stations.itertuples():
        bounds=trans.transform_bounds(r.x-800,r.y-800,r.x+800,r.y+800,densify_pts=100)
        w,s,e,n=bounds
        if not(b['west']<=w and b['south']<=s and b['east']>=e and b['north']>=n):
            targets.append(dict(region_id=r.region_id,station_name=r.station_name,x=r.x,y=r.y))
            boxes.append([w-1e-7,s-1e-7,e+1e-7,n+1e-7])
    OUT.mkdir(parents=True,exist_ok=True)
    print(f'Coverage checked: {len(targets)} stations need supplement',flush=True)
    start=time.perf_counter()
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions'),'threads':'4','memory_limit':'2GB','allow_persistent_secrets':'false'}) as con:
        for ext in ['httpfs','spatial']: con.execute('LOAD '+ext)
        con.execute("CREATE SECRET public_overture (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2', SCOPE 's3://overturemaps-us-west-2/')")
        con.execute('SET http_timeout=30')
        con.execute('SET http_retries=0')
        print('Checking fixed-release schema',flush=True)
        schema=con.execute('DESCRIBE SELECT * FROM read_parquet(?,hive_partitioning=true)',[source_uri()]).fetchall()
        validate_schema(schema)
        sql='SELECT id,geometry,bbox,basic_category,taxonomy,operating_status,sources FROM read_parquet(?,hive_partitioning=true) WHERE bbox.xmin<=? AND bbox.xmax>=? AND bbox.ymin<=? AND bbox.ymax>=? AND NOT (bbox.xmin<=? AND bbox.xmax>=? AND bbox.ymin<=? AND bbox.ymax>=?)'
        args=[]
        for i,(w,s,e,n) in enumerate(boxes):
            params=[source_uri(),e,w,n,s,b['east'],b['west'],b['north'],b['south']];args.append(params)
            con.execute(('CREATE TABLE candidates AS ' if i==0 else 'INSERT INTO candidates ')+sql,params)
            print(f'Acquired missing box {i+1}/{len(boxes)}',flush=True)
        con.execute('CREATE TABLE unique_candidates AS SELECT DISTINCT * FROM candidates')
        con.execute('DROP TABLE candidates')
        con.execute('ALTER TABLE unique_candidates RENAME TO candidates')
        if con.execute('SELECT count(*)-count(DISTINCT id) FROM candidates').fetchone()[0]:raise ValueError('Conflicting duplicate ID')
        print('Download query completed',flush=True)
        frame=con.execute('SELECT id,ST_X(geometry) lon,ST_Y(geometry) lat FROM candidates').df()
        x,y=Transformer.from_crs(4326,6677,always_xy=True).transform(frame.lon.to_numpy(),frame.lat.to_numpy())
        keep=sum(((abs(x-t['x'])<=800)&(abs(y-t['y'])<=800)).astype(int) for t in targets)>0
        ids=frame.loc[keep,['id']];con.register('selected_ids',ids)
        path=OUT/'places.parquet'
        con.execute('COPY (SELECT c.* FROM candidates c JOIN selected_ids USING(id) ORDER BY id) TO ? (FORMAT PARQUET)',[str(path)])
        licenses=[r[0] for r in con.execute('SELECT DISTINCT s.license FROM candidates,UNNEST(sources) t(s)').fetchall()]
        if set(licenses)-{'Apache-2.0','CC0-1.0','CDLA-Permissive-2.0'}: raise ValueError('Unexpected license')
        report=dict(release=m['release'],schema_version=m['schema_version'],coverage_complete=True,targets=targets,acquisition_boxes=boxes,excludes_bbox=b,query=sql,parameters=args,rows=len(ids),candidate_rows=len(frame),bytes=path.stat().st_size,sha256=digest(path),base_manifest_sha256=digest(RAW/'manifest.json'),licenses=licenses,completed_at_utc=datetime.now(timezone.utc).isoformat(),seconds=time.perf_counter()-start,network_bytes=None,scanned_bytes=None)
        (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({k:report[k] for k in ['rows','bytes','sha256','seconds']}))

if __name__=='__main__': acquire()
