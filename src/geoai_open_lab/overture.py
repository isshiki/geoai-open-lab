"""Fixed-release, anonymous DuckDB tutorial for Overture Places."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import platform
import threading
import time
import uuid
import duckdb
from .aoi import load_aoi, project_root, validate_aoi

RELEASE = "2026-09-23.0"
SCHEMA = "v2.0.0"
CAFE_DEFINITION = "basic_category IN ('cafe', 'coffee_shop'); no status filter"

def source_uri(release=RELEASE):
    if release != RELEASE:
        raise ValueError("Only the reviewed 2026-09-23.0 release is supported.")
    return f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*"

@dataclass(repr=False)
class OvertureSession:
    connection: object
    root: Path
    details: dict = field(default_factory=dict)
    def close(self):
        self.connection.close()

def connect_overture(*, root=None):
    """Load httpfs/spatial, disable persistent secrets, use anonymous public S3.

    No dotenv, environment credentials or credential-chain provider is used.
    Extensions and temporary storage remain in project-local ignored data/.
    """
    root = project_root(root)
    cache = root / "data/cache/duckdb"
    cache.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={"extension_directory": str(cache / "extensions"),
        "temp_directory": str(cache / "tmp"), "memory_limit": "1GB", "threads": "2",
        "allow_persistent_secrets": "false"})
    try:
        for extension in ("httpfs", "spatial"):
            con.execute(f"INSTALL {extension}")
            con.execute(f"LOAD {extension}")
        con.execute("CREATE SECRET overture_public (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2', SCOPE 's3://overturemaps-us-west-2/')")
        return OvertureSession(con, root)
    except Exception:
        con.close()
        raise RuntimeError("Overture setup failed; remote details suppressed.") from None

def validate_schema(schema):
    types = {r[0]: r[1] for r in schema}
    required = {"id", "geometry", "bbox", "names", "addresses", "basic_category",
        "taxonomy", "brand", "websites", "socials", "emails", "phones",
        "operating_status", "confidence", "sources"}
    if not required <= types.keys() or "categories" in types:
        raise ValueError("Unexpected Places schema; expected v2.0.0 fields without categories.")
    if not types["geometry"].startswith("GEOMETRY"):
        raise ValueError("Expected DuckDB spatial GEOMETRY; check DuckDB version.")
    if not all(part in types["taxonomy"] for part in ('"primary" VARCHAR', 'hierarchy VARCHAR[]', 'alternates VARCHAR[]')):
        raise ValueError("Unexpected taxonomy struct.")
    if not all(f"{part} DOUBLE" in types["bbox"] for part in ('xmin','xmax','ymin','ymax')):
        raise ValueError("Unexpected bbox struct.")
    if types['id'] != 'VARCHAR' or types['basic_category'] != 'VARCHAR':
        raise ValueError('Unexpected ID/category type.')

def _records(con, sql):
    cur = con.execute(sql)
    return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]

def fetch_overture_places(session, *, bbox, release=RELEASE, timeout_seconds=180):
    """Read all bbox candidates, then apply inclusive exact point coordinates.

    No LIMIT, country, operating status or confidence filter. Bounding-box overlap
    preserves boundary candidates even if stored bbox bounds are outward rounded.
    A deadline interrupts rather than silently publishing a partial sample.
    """
    validate_aoi(bbox, bbox['country'])
    uri = source_uri(release)
    con = session.connection
    session.details.clear()
    start = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    timer = threading.Timer(timeout_seconds, con.interrupt)
    timer.daemon = True
    timer.start()
    try:
        schema = con.execute("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=true)", [uri]).fetchall()
        validate_schema(schema)
        sql = """SELECT id, geometry, bbox, names, addresses, basic_category, taxonomy,
            brand, websites, socials, emails, phones, operating_status, confidence, sources
            FROM read_parquet(?, hive_partitioning=true)
            WHERE bbox.xmin <= ? AND bbox.xmax >= ?
              AND bbox.ymin <= ? AND bbox.ymax >= ?"""
        params = [uri, bbox['east'], bbox['west'], bbox['north'], bbox['south']]
        plan = con.execute("EXPLAIN " + sql, params).fetchall()
        con.execute("CREATE OR REPLACE TEMP TABLE overture_candidates AS " + sql, params)
        invalid = con.execute("""SELECT count(*) FROM overture_candidates
            WHERE geometry IS NULL OR ST_GeometryType(geometry) <> 'POINT'
              OR ST_IsEmpty(geometry)""").fetchone()[0]
        if invalid:
            raise ValueError("Null/non-point/empty geometries in bbox candidates.")
        con.execute("""CREATE OR REPLACE TEMP TABLE overture_places AS
            SELECT * FROM overture_candidates WHERE ST_X(geometry) BETWEEN ? AND ?
            AND ST_Y(geometry) BETWEEN ? AND ?""",
            [bbox['west'],bbox['east'],bbox['south'],bbox['north']])
        count, distinct_ids, null_ids, bad_bbox = con.execute("""SELECT count(*), count(DISTINCT id),
            count(*) FILTER (WHERE id IS NULL), count(*) FILTER (WHERE
            NOT (ST_X(geometry) BETWEEN bbox.xmin AND bbox.xmax
            AND ST_Y(geometry) BETWEEN bbox.ymin AND bbox.ymax)) FROM overture_places""").fetchone()
        if count != distinct_ids or null_ids or bad_bbox:
            raise ValueError("ID or geometry/bbox validation failed.")
        session.details.update(started_at_utc=start, completed_at_utc=datetime.now(timezone.utc).isoformat(),
            acquisition_seconds=time.perf_counter()-clock, release=release, schema_version=SCHEMA,
            source_uri=uri, schema=schema, aoi=dict(bbox), row_count=count,
            candidate_count=con.execute('SELECT count(*) FROM overture_candidates').fetchone()[0],
            sql=sql, parameters=params, plan=plan, null_geometry=invalid, duplicate_ids=count-distinct_ids,
            geometry_bbox_mismatch=bad_bbox, network_bytes=None, scanned_bytes=None,
            peak_memory_bytes=None, limit=None, boundary='inclusive', country_filter=None)
        return con.execute("""SELECT id, names.primary AS name, ST_X(geometry) AS longitude,
            ST_Y(geometry) AS latitude, basic_category, taxonomy.primary AS taxonomy_primary,
            taxonomy.hierarchy AS taxonomy_hierarchy, taxonomy.alternates AS taxonomy_alternates,
            operating_status, confidence FROM overture_places ORDER BY id""").df()
    except (ValueError,):
        raise
    except Exception:
        raise RuntimeError("Overture acquisition failed or timed out; no complete result recorded.") from None
    finally:
        timer.cancel()

def filter_overture_cafes(session):
    """Overture basic-category selection, including Internet Cafe descendants."""
    if 'row_count' not in session.details:
        raise ValueError('Complete acquisition first.')
    return session.connection.execute("""SELECT id, names.primary AS name,
        ST_X(geometry) AS longitude, ST_Y(geometry) AS latitude,
        basic_category, taxonomy.primary AS taxonomy_primary, operating_status
        FROM overture_places WHERE basic_category IN ('cafe','coffee_shop') ORDER BY id""").df()

def summarize_overture(session):
    """Aggregate categories, status, confidence and sources without exposing POIs."""
    con = session.connection
    result = {}
    for key, expr, where in [
        ('basic_category','basic_category','true'), ('taxonomy_primary','taxonomy.primary','true'),
        ('operating_status','operating_status','true'),
        ('cafe_taxonomy_primary','taxonomy.primary',"basic_category IN ('cafe','coffee_shop')"),
        ('cafe_operating_status','operating_status',"basic_category IN ('cafe','coffee_shop')")]:
        result[key] = _records(con, f"SELECT {expr} AS value, count(*) AS count FROM overture_places WHERE {where} GROUP BY 1 ORDER BY 2 DESC, 1")
    result['null_counts'] = _records(con, """SELECT count(*) AS total,
        count(*) FILTER (WHERE basic_category IS NULL) AS basic_category,
        count(*) FILTER (WHERE taxonomy IS NULL) AS taxonomy,
        count(*) FILTER (WHERE taxonomy.primary IS NULL) AS taxonomy_primary,
        count(*) FILTER (WHERE taxonomy.hierarchy IS NULL) AS taxonomy_hierarchy,
        count(*) FILTER (WHERE taxonomy.alternates IS NULL) AS taxonomy_alternates,
        count(*) FILTER (WHERE sources IS NULL) AS sources,
        count(*) FILTER (WHERE len(sources)>1) AS multiple_sources FROM overture_places""")[0]
    result['confidence'] = _records(con, """SELECT count(*)-count(confidence) AS null_count,
        min(confidence) AS minimum, quantile_cont(confidence,0.25) AS p25,
        median(confidence) AS median, quantile_cont(confidence,0.75) AS p75,
        max(confidence) AS maximum FROM overture_places""")[0]
    result['sources'] = _records(con, """SELECT s.dataset, s.provider, s.license, count(*) AS source_entries
        FROM overture_places, UNNEST(sources) AS t(s) GROUP BY 1,2,3 ORDER BY 4 DESC""")
    result['taxonomy_checks'] = _records(con, """SELECT
        count(*) FILTER (WHERE taxonomy.primary IS DISTINCT FROM list_last(taxonomy.hierarchy)) AS primary_hierarchy_mismatch,
        count(*) FILTER (WHERE basic_category IS NOT NULL AND taxonomy.hierarchy IS NOT NULL
          AND NOT list_contains(taxonomy.hierarchy,basic_category)) AS basic_hierarchy_mismatch
        FROM overture_places""")[0]
    return result

def save_overture_results(session):
    """Save local GeoParquet plus an allowlisted manifest and execution plan."""
    if 'row_count' not in session.details:
        raise ValueError('Complete acquisition first.')
    con = session.connection
    run = session.root / 'data/raw/overture' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    run.mkdir(parents=True)
    hashes, sizes = {}, {}
    for name, where in [('places','true'),('cafes',"basic_category IN ('cafe','coffee_shop')")]:
        path = run / (name+'.parquet')
        con.execute(f"COPY (SELECT * FROM overture_places WHERE {where} ORDER BY id) TO ? (FORMAT PARQUET)",[str(path)])
        hashes[path.name] = sha256(path.read_bytes()).hexdigest()
        sizes[path.name] = path.stat().st_size
    keys = ('started_at_utc','completed_at_utc','acquisition_seconds','release','schema_version',
        'source_uri','schema','aoi','row_count','candidate_count','sql','parameters','plan',
        'null_geometry','duplicate_ids','geometry_bbox_mismatch','network_bytes','scanned_bytes',
        'peak_memory_bytes','limit','boundary','country_filter')
    manifest = {key: session.details[key] for key in keys}
    manifest.update(provider='Overture Maps',theme='places',type='place',
        cafe_definition=CAFE_DEFINITION,cafe_count=len(filter_overture_cafes(session)),
        summary=summarize_overture(session), output_sha256=hashes, output_bytes=sizes,
        python=platform.python_version(),duckdb=duckdb.__version__,
        extensions=_records(con,"SELECT extension_name, extension_version FROM duckdb_extensions() WHERE extension_name IN ('httpfs','spatial')"))
    sources = ['src/geoai_open_lab/overture.py','src/geoai_open_lab/aoi.py',
        'configs/aoi/kichijoji.toml','notebooks/02_overture_places.ipynb','pyproject.toml','uv.lock']
    manifest['exact_geometry_filter'] = 'ST_X(geometry) BETWEEN west AND east AND ST_Y(geometry) BETWEEN south AND north'
    manifest['references'] = [
        'https://docs.overturemaps.org/blog/2026/09/23/release-notes/',
        'https://docs.overturemaps.org/schema/reference/places/place/',
        'https://docs.overturemaps.org/guides/places/taxonomy-explorer/',
        'https://docs.overturemaps.org/attribution/',
        'https://stac.overturemaps.org/2026-09-23.0/catalog.json']
    manifest['command'] = 'uv run --locked --group notebooks jupyter nbconvert --execute --to notebook notebooks/02_overture_places.ipynb --output 02_overture_places.executed --output-dir data/cache/overture --ExecutePreprocessor.timeout=240'
    manifest['source_sha256'] = {p:sha256((session.root/p).read_bytes()).hexdigest() for p in sources}
    (run/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    return run
