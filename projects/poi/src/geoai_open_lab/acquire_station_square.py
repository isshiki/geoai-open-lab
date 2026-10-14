"""Explicit one-off acquisition for Kichijoji only; never called by the Notebook."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json
import threading
import duckdb
from pyproj import Transformer
from .aoi import project_root
from .station_square import station_center, acquisition_bbox, square_geometry
from .overture import source_uri, RELEASE, SCHEMA


def acquire(root=None):
    root=project_root(root)
    station=station_center(root/'data/raw/region_features/station/N02-25_GML.zip')
    bbox=acquisition_bbox(station);square=square_geometry(station)
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-station-square'
    out=root/'data/raw/region_features'/run;out.mkdir(parents=True)
    start=datetime.now(timezone.utc).isoformat()
    con=duckdb.connect(config={'extension_directory':str(root/'data/cache/duckdb/extensions'),
        'memory_limit':'1GB','threads':'2','allow_persistent_secrets':'false'})
    timer=threading.Timer(300,con.interrupt);timer.daemon=True
    try:
        for ext in ['httpfs','spatial']:con.execute('LOAD '+ext)
        con.execute("CREATE SECRET public_overture (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2', SCOPE 's3://overturemaps-us-west-2/')")
        timer.start()
        schema=con.execute('DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=true)',[source_uri()]).fetchall()
        required={'id','geometry','bbox','basic_category','taxonomy','operating_status','sources'}
        if not required<={s[0] for s in schema}:raise ValueError('Unexpected schema')
        sql='''SELECT id,geometry,bbox,basic_category,taxonomy,operating_status,sources
            FROM read_parquet(?,hive_partitioning=true)
            WHERE bbox.xmin<=? AND bbox.xmax>=? AND bbox.ymin<=? AND bbox.ymax>=?'''
        args=[source_uri(),bbox['east'],bbox['west'],bbox['north'],bbox['south']]
        plan=con.execute('EXPLAIN '+sql,args).fetchall()
        con.execute('CREATE TEMP TABLE candidates AS '+sql,args)
        if con.execute("SELECT count(*) FROM candidates WHERE geometry IS NULL OR ST_IsEmpty(geometry) OR ST_GeometryType(geometry)<>'POINT'").fetchone()[0]:raise ValueError('Invalid geometry')
        points=con.execute('SELECT id,ST_X(geometry) lon,ST_Y(geometry) lat FROM candidates').df()
        x,y=Transformer.from_crs(4326,6677,always_xy=True).transform(points.lon.to_numpy(),points.lat.to_numpy())
        west,south,east,north=square.bounds
        selected=points.loc[(x>=west)&(x<=east)&(y>=south)&(y<=north),['id']]
        if selected.id.isna().any() or selected.id.duplicated().any():raise ValueError('Invalid IDs')
        con.register('selected',selected)
        path=out/'places.parquet'
        con.execute('COPY (SELECT c.* FROM candidates c JOIN selected s USING (id) ORDER BY id) TO ? (FORMAT PARQUET)',[str(path)])
        licenses=con.execute('SELECT DISTINCT s.license FROM candidates, UNNEST(sources) t(s)').fetchall()
        manifest=dict(release=RELEASE,schema_version=SCHEMA,input_schema=schema,station=station,
            run_id=run,started_at_utc=start,completed_at_utc=datetime.now(timezone.utc).isoformat(),
            acquisition_bbox=bbox,projected_bounds=list(square.bounds),crs='EPSG:6677',area_m2=square.area,
            row_count=len(selected),candidate_count=len(points),limit=None,country_filter=None,
            coverage_complete=True,boundary='inclusive; exact projected square',source_uri=source_uri(),
            query=sql,parameters=args,plan=plan,licenses=[v[0] for v in licenses],
            output_sha256={'places.parquet':sha256(path.read_bytes()).hexdigest()},
            output_bytes=path.stat().st_size,modified_date='2026-10-14',
            command='python -m geoai_open_lab.acquire_station_square',
            notice_url='https://opensource.foursquare.com/places-notice-txt/',
            network_bytes=None,scanned_bytes=None)
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'run':run,'rows':len(selected),'bytes':path.stat().st_size,'licenses':manifest['licenses']},ensure_ascii=False))
        return out
    except Exception as e:
        (out/'failure.json').write_text(json.dumps({'release':RELEASE,'error_type':type(e).__name__,'complete':False}),encoding='utf8')
        raise RuntimeError('Pinned release acquisition failed; no fallback release used. See local failure.json.') from None
    finally:
        timer.cancel();con.close()


if __name__=='__main__':acquire()
