"""Offline JGD2011 standard meshes: codes, full-cell census aggregation and POI join."""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction
from datetime import datetime, timezone
import io
import json
import math
import platform
import shutil
import tomllib
import zipfile
from importlib.metadata import version
import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer, network
from shapely.geometry import Polygon, box

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/cache/regional_mesh/kichijoji-v1'
RAW = ROOT/'data/raw/similar_regions/20261015T080101Z-tokyo'
CENSUS = ROOT.parent/'station-territory/data/raw/tblT001142Q5339.zip'
POP = 'T001142001'
network.set_network_enabled(False)
PROJECT = Transformer.from_crs(6668, 6677, always_xy=True)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def encode_mesh(latitude, longitude, digits=9):
    """8/9/10 digits; south/west inclusive, north/east exclusive.

    Round scaled angular coordinates to 9 decimal places to absorb floating
    roundoff at exact boundaries (approximately 0.001 mm or less on the ground).
    This is a documented numerical tie rule, not a geodetic accuracy claim.
    """
    if digits not in (8, 9, 10) or not 0 <= latitude < 66 or not 100 <= longitude < 180:
        raise ValueError('Unsupported code length or coordinate domain')
    factor = 2**(digits-8)
    iy = math.floor(round(latitude*120*factor, 9))
    ix = math.floor(round((longitude-100)*80*factor, 9))
    y, x = iy//factor, ix//factor
    code = f'{y//80:02d}{x//80:02d}{y%80//10}{x%80//10}{y%10}{x%10}'
    for shift in reversed(range(digits-8)):
        code += str(1+2*((iy >> shift)&1)+((ix >> shift)&1))
    return code


def mesh_bounds(code):
    """Return west,south,east,north in EPSG:6668; code is a string."""
    s = str(code)
    if len(s) not in (8, 9, 10) or not s.isascii() or not s.isdigit() or int(s[4])>7 or int(s[5])>7 or any(q not in '1234' for q in s[8:]):
        raise ValueError('Invalid regional mesh code')
    lat = Fraction(int(s[:2])*2, 3)+Fraction(int(s[4]),12)+Fraction(int(s[6]),120)
    lon = 100+int(s[2:4])+Fraction(int(s[5]),8)+Fraction(int(s[7]),80)
    h,w = Fraction(1,120),Fraction(1,80)
    for digit in s[8:]:
        q=int(digit);h/=2;w/=2
        lat+=(q>=3)*h;lon+=(q in (2,4))*w
    return tuple(map(float,(lon,lat,lon+w,lat+h)))


def mesh_polygon(code, projected=False):
    """Densify angular sides before projection; never measure area in degrees."""
    w,s,e,n=mesh_bounds(code)
    corners=[(w,s),(e,s),(e,n),(w,n),(w,s)]
    points=[]
    for a,b in zip(corners,corners[1:]):
        points.extend((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])) for t in np.linspace(0,1,9)[:-1])
    if projected:
        x,y=PROJECT.transform(*zip(*points));points=list(zip(x,y))
    return Polygon(points)


def selected_meshes(station):
    """All complete 500m cells with positive-area intersection of old 1km square."""
    cx,cy=station['center_x'],station['center_y']
    square=box(cx-500,cy-500,cx+500,cy+500)
    inverse=Transformer.from_crs(6677,6668,always_xy=True)
    w,s,e,n=inverse.transform_bounds(*square.bounds,densify_pts=100)
    codes=set()
    for iy in range(math.floor(s*240)-1,math.floor(n*240)+2):
        for ix in range(math.floor((w-100)*160)-1,math.floor((e-100)*160)+2):
            code=encode_mesh((iy+.5)/240,100+(ix+.5)/160)
            if mesh_polygon(code,True).intersection(square).area>1e-6:codes.add(code)
    return sorted(codes)


def aggregate_population(data, codes):
    """Only nonsuppressed population TOTAL, no reassignment using GASSAN.

    Missing children produce missing population, not zero or a partial total.
    """
    if data.KEY_CODE.duplicated().any():raise ValueError('Duplicate census key')
    if not data.HTKSYORI.isin(['0','1','2']).all():raise ValueError('Unknown secrecy flag')
    indexed=data.set_index('KEY_CODE');rows=[]
    for code in codes:
        keys=[code+str(q) for q in range(1,5)]
        children=indexed.reindex(keys)
        population=pd.to_numeric(children[POP],errors='raise')
        if (population.dropna()<0).any() or ((population.dropna()%1)!=0).any():raise ValueError('Invalid population')
        complete=population.notna().all()
        rows.append(dict(mesh_code=code,population_2020=int(population.sum()) if complete else None,
                         children_present=int(children[POP].notna().sum()),population_complete=bool(complete),
                         suppressed_children=int(children.HTKSYORI.eq('2').sum()),aggregate_children=int(children.HTKSYORI.eq('1').sum())))
    return pd.DataFrame(rows)


def run():
    station_path=ROOT/'configs/aoi/kichijoji_station_1km.toml'
    station=tomllib.loads(station_path.read_text(encoding='utf8'))
    codes=selected_meshes(station)
    census_manifest=ROOT.parent/'station-territory/data/reference/population-manifest.json'
    cm=json.loads(census_manifest.read_text(encoding='utf8'))
    if digest(CENSUS)!=cm['sha256'] or cm['sha256']!='3e29a001e4fc0cfdd840a2885b6ab68cc183c79742e072f33e0ff906250e2d81':raise ValueError('Census checksum mismatch')
    with zipfile.ZipFile(CENSUS) as z:
        data=pd.read_csv(io.BytesIO(z.read('tblT001142Q5339.txt')),encoding='cp932',dtype=str,skiprows=[1],keep_default_na=False)
    # Check geometry correspondence for every official source key, not only the AOI.
    for key in data.KEY_CODE:
        w,s,e,n=mesh_bounds(key)
        if encode_mesh((s+n)/2,(w+e)/2,10)!=key:raise ValueError('Census key roundtrip mismatch')
    table=aggregate_population(data,codes)
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    if m['release']!='2026-09-23.0' or not m['coverage_complete'] or any(m[k] is not None for k in ('limit','country_filter','status_filter','confidence_filter')):raise ValueError('POI coverage contract changed')
    if digest(RAW/'places.parquet')!=m['output_sha256']['places.parquet'] or m['output_sha256']['places.parquet']!='77f385ecf6cfcddf9eb8415ba6db76472cd72f4a7b7a61ec446b90a0a99869e8':raise ValueError('POI checksum mismatch')
    bbox=m['acquisition_bbox']
    to_wgs=Transformer.from_crs(6668,4326,always_xy=True)
    for code in codes:
        w,s,e,n=to_wgs.transform_bounds(*mesh_bounds(code),densify_pts=100)
        if not (bbox['west']<=w and bbox['south']<=s and bbox['east']>=e and bbox['north']>=n):raise ValueError('Incomplete POI coverage; stop before download')
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        frame=con.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat FROM read_parquet(?) ORDER BY id',[str(RAW/'places.parquet')]).df()
    if len(frame)!=m['row_count'] or frame.id.isna().any() or not frame.id.is_unique:raise ValueError('Invalid POI identities')
    datum=Transformer.from_crs(4326,6668,always_xy=True)
    lon,lat=datum.transform(frame.lon.to_numpy(),frame.lat.to_numpy())
    frame['mesh_code']=[encode_mesh(y,x) for x,y in zip(lon,lat)]
    selected=frame[frame.mesh_code.isin(codes)].copy()
    table['poi_count']=table.mesh_code.map(selected.mesh_code.value_counts()).fillna(0).astype(int)
    table['area_km2']=[mesh_polygon(c,True).area/1e6 for c in codes]
    table['poi_density_per_km2']=table.poi_count/table.area_km2
    if table.poi_count.sum()!=len(selected):raise ValueError('POI conservation failed')
    children=data[data.KEY_CODE.str[:9].isin(codes)]
    if table.population_complete.all() and table.population_2020.sum()!=pd.to_numeric(children[POP]).sum():raise ValueError('Population conservation failed')
    OUT.mkdir(parents=True,exist_ok=True)
    table.to_csv(OUT/'mesh500.csv',index=False)
    selected.to_parquet(OUT/'poi_assignments.parquet',index=False)
    children[['KEY_CODE','HTKSYORI','HTKSAKI','GASSAN',POP]].to_csv(OUT/'population250_audit.csv',index=False)
    meta=dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),command='uv run --no-sync python -m geoai_open_lab.regional_mesh',
              census={k:cm[k] for k in ('url','reference_date','version','retrieved_end_utc','sha256','bytes')},census_source_rows=len(data),
              poi_release=m['release'],poi_acquired_utc=m['completed_at_utc'],poi_source_rows=len(frame),poi_schema=m['input_schema'],
              poi_sha256=m['output_sha256']['places.parquet'],poi_manifest_sha256=digest(RAW/'manifest.json'),poi_bbox=bbox,
              poi_bytes=(RAW/'places.parquet').stat().st_size,poi_source_uri=m['source_uri'],census_columns=list(data.columns),
              station=station,station_config_sha256=digest(station_path),mesh_codes=codes,mesh_count=len(table),children_count=len(children),
              complete_population_cells=int(table.population_complete.sum()),population_2020=int(table.population_2020.sum()) if table.population_complete.all() else None,
              poi_count=len(selected),area_km2=float(table.area_km2.sum()),census_secrecy_flags=children.HTKSYORI.value_counts().to_dict(),
              code_crs='EPSG:6668',area_crs='EPSG:6677',poi_crs='EPSG:4326',datum_operation=datum.description,datum_accuracy_m=datum.accuracy,
              official_check_date='2026-10-23',code_sha256=digest(__file__),lock_sha256=digest(ROOT/'uv.lock'),python=platform.python_version(),
              packages={p:version(p) for p in ('pandas','duckdb','pyproj','shapely')},
              output_sha256={n:digest(OUT/n) for n in ('mesh500.csv','poi_assignments.parquet','population250_audit.csv')})
    (OUT/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        source=ROOT/'data/cache/maup/kichijoji-v1'/name
        shutil.copyfile(source,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:
        f.write('\n2026-10-23: Aggregated POI counts by JGD2011 standard 500m mesh; joined with 2020 census population.\n')
    return table,meta


if __name__=='__main__':
    table,meta=run()
    print(table.to_string(index=False))
    print({k:meta[k] for k in ('mesh_count','children_count','population_2020','poi_count','area_km2')})
