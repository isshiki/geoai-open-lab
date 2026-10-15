"""Explicit anonymous acquisition, one pinned scan for all target station AOIs."""
from datetime import datetime, timezone
import json
import platform
import threading
import time

import duckdb
from pyproj import Transformer

from .aoi import project_root
from .overture import source_uri, RELEASE, SCHEMA, validate_schema
from .region_features import digest
from .tokyo_stations import load_stations, N03_SHA256
from .station_square import N02_SHA256


def acquire(root=None):
    root = project_root(root)
    raw = root/'data/raw/similar_regions'
    stations = load_stations(root/'data/raw/region_features/station/N02-25_GML.zip', raw/'N03-20260101_13_GML.zip')
    run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-tokyo'
    out = raw/run
    out.mkdir(parents=True)
    stations.to_csv(out/'stations.csv', index=False)
    bounds = (float(stations.x.min()-500), float(stations.y.min()-500),
              float(stations.x.max()+500), float(stations.y.max()+500))
    west, south, east, north = Transformer.from_crs(6677,4326,always_xy=True).transform_bounds(*bounds,densify_pts=1000)
    west-=1e-7; south-=1e-7; east+=1e-7; north+=1e-7
    start = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    con = duckdb.connect(config={'extension_directory':str(root/'data/cache/duckdb/extensions'),
        'temp_directory':str(root/'data/cache/duckdb/tmp'), 'memory_limit':'2GB', 'threads':'4',
        'allow_persistent_secrets':'false'})
    timer = threading.Timer(1800, con.interrupt)
    timer.daemon = True
    try:
        for ext in ['httpfs','spatial']:
            con.execute('LOAD '+ext)
        con.execute("CREATE SECRET public_overture (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2', SCOPE 's3://overturemaps-us-west-2/')")
        timer.start()
        schema = con.execute('DESCRIBE SELECT * FROM read_parquet(?,hive_partitioning=true)',[source_uri()]).fetchall()
        validate_schema(schema)
        sql = '''SELECT id,geometry,bbox,basic_category,taxonomy,operating_status,sources
            FROM read_parquet(?,hive_partitioning=true)
            WHERE bbox.xmin<=? AND bbox.xmax>=? AND bbox.ymin<=? AND bbox.ymax>=?'''
        args = [source_uri(),east,west,north,south]
        plan = con.execute('EXPLAIN '+sql,args).fetchall()
        con.execute('CREATE TABLE candidates AS '+sql,args)
        candidate_count = con.execute('SELECT count(*) FROM candidates').fetchone()[0]
        if con.execute("SELECT count(*) FROM candidates WHERE id IS NULL OR geometry IS NULL OR ST_IsEmpty(geometry) OR ST_GeometryType(geometry)<>'POINT'").fetchone()[0]:
            raise ValueError('Invalid POI identity/geometry')
        con.execute('CREATE TABLE deduplicated AS SELECT DISTINCT * FROM candidates')
        if con.execute('SELECT count(*)-count(DISTINCT id) FROM deduplicated').fetchone()[0]:
            raise ValueError('Conflicting duplicate IDs')
        rows = con.execute('SELECT count(*) FROM deduplicated').fetchone()[0]
        if rows == 0:
            raise ValueError('Unexpected empty Tokyo extraction')
        path = out/'places.parquet'
        con.execute('COPY (SELECT * FROM deduplicated ORDER BY id) TO ? (FORMAT PARQUET)',[str(path)])
        licenses = [x[0] for x in con.execute('SELECT DISTINCT s.license FROM deduplicated,UNNEST(sources) t(s)').fetchall()]
        if set(licenses)-{'Apache-2.0','CDLA-Permissive-2.0','CC0-1.0'}:
            raise ValueError('Unreviewed source license')
        manifest = dict(run_id=run, release=RELEASE, schema_version=SCHEMA,
            started_at_utc=start, completed_at_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.perf_counter()-clock, coverage_complete=True,
            source_uri=source_uri(), acquisition_bbox=dict(west=west,south=south,east=east,north=north),
            all_square_projected_bounds=bounds, station_count=len(stations),
            row_count=rows, candidate_count=candidate_count, identical_duplicates_removed=candidate_count-rows,
            limit=None,country_filter=None,status_filter=None,confidence_filter=None,
            input_schema=schema,query=sql,parameters=args,plan=plan,licenses=sorted(licenses),
            output_sha256={p.name:digest(p) for p in [path,out/'stations.csv']},
            output_bytes=path.stat().st_size, network_bytes=None,scanned_bytes=None,
            official_sha256={'N02-25_GML.zip':N02_SHA256,'N03-20260101_13_GML.zip':N03_SHA256},
            n02_retrieved_utc='2026-10-03T09:28:23Z',n03_original_retrieved_utc=None,
            n03_reuse_verified_utc=start, python=platform.python_version(),duckdb=duckdb.__version__,
            design_sha256=digest(root/'docs/similar-regions-design.md'),
            source_code_sha256=digest(__file__),command='python -m geoai_open_lab.acquire_tokyo_places')
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'run':run,'rows':rows,'stations':len(stations),'bytes':path.stat().st_size}))
        return out
    except Exception as e:
        (out/'failure.json').write_text(json.dumps({'release':RELEASE,'error_type':type(e).__name__,'coverage_complete':False}),encoding='utf8')
        raise RuntimeError('Tokyo acquisition failed; partial inputs must not be used; no release fallback.') from None
    finally:
        timer.cancel()
        con.close()


if __name__=='__main__':
    acquire()
