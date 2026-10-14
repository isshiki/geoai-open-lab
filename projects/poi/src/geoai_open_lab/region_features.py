"""Offline, pinned Overture sample -> clipped metric grids and POI features.

Counts describe registrations, never active stores. EPSG:6677 is used with
always_xy=True (easting, northing). No network, dotenv, INSTALL or latest lookup.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import platform
import tomllib

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer, network
from shapely.geometry import Polygon, Point, box
from .aoi import load_aoi, project_root

MISSING = "__MISSING__"
OTHER = "__OTHER__"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def load_inputs(root=None):
    """Verify exact files and original complete-acquisition manifest before use."""
    root = project_root(root)
    cfg = tomllib.loads((root / 'configs/region_features.toml').read_text(encoding='utf8'))
    path, mp = root / cfg['input'], root / cfg['input_manifest']
    if digest(path) != cfg['input_sha256'] or digest(mp) != cfg['manifest_sha256']:
        raise ValueError('Pinned input or manifest hash mismatch.')
    manifest = json.loads(mp.read_text(encoding='utf8'))
    aoi = load_aoi(cfg['aoi'], root=root)
    if (manifest['release'] != cfg['release'] or manifest['aoi'] != aoi
            or manifest['limit'] is not None or manifest['country_filter'] is not None
            or manifest['row_count'] != cfg['expected_rows']
            or manifest['output_sha256']['places.parquet'] != cfg['input_sha256']):
        raise ValueError('Input provenance/coverage does not match this experiment.')
    # LOAD only: absence of the previously installed extension is an explicit error.
    with duckdb.connect(config={'extension_directory': str(root / 'data/cache/duckdb/extensions'),
                                'allow_unsigned_extensions': 'false'}) as con:
        con.execute('LOAD spatial')
        schema = con.execute('DESCRIBE SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
        frame = con.execute('''SELECT id, ST_X(geometry) AS longitude,
            ST_Y(geometry) AS latitude, basic_category,
            taxonomy.primary AS taxonomy_primary, taxonomy.hierarchy AS taxonomy_hierarchy,
            taxonomy.alternates AS taxonomy_alternates, operating_status
            FROM read_parquet(?) ORDER BY id''', [str(path)]).df()
    if len(frame) != cfg['expected_rows'] or frame.id.isna().any() or frame.id.duplicated().any():
        raise ValueError('Incomplete input or invalid POI IDs.')
    inside = (frame.longitude.between(aoi['west'], aoi['east'])
              & frame.latitude.between(aoi['south'], aoi['north']))
    if not inside.all():
        raise ValueError('Input contains a point outside the inclusive AOI.')
    network.set_network_enabled(False)
    transform = Transformer.from_crs('EPSG:4326', cfg['crs'], always_xy=True)
    frame['x'], frame['y'] = transform.transform(frame.longitude.to_numpy(), frame.latitude.to_numpy())
    if not np.isfinite(frame[['x', 'y']]).all().all():
        raise ValueError('Non-finite projected coordinate.')
    # Densify all four geographic edges to avoid treating curved projected edges
    # as a bounding rectangle. 100 segments/edge; area sensitivity is audited.
    polygon = projected_aoi(aoi, transform, 100)
    return frame, polygon, cfg, {'input_schema': schema, 'acquisition_utc': manifest['completed_at_utc'],
                                'aoi': aoi, 'transform_description': transform.description}


def projected_aoi(aoi, transformer, segments=100):
    corners = [(aoi['west'], aoi['south']), (aoi['east'], aoi['south']),
               (aoi['east'], aoi['north']), (aoi['west'], aoi['north'])]
    points = []
    for first, last in zip(corners, corners[1:] + corners[:1]):
        points.extend(transformer.transform(first[0] + (last[0]-first[0])*i/segments,
                                             first[1] + (last[1]-first[1])*i/segments)
                      for i in range(segments))
    return Polygon(points)


def cell_index(value, size, origin=0):
    """Half-open [lower, upper); snap only sub-10 nm numeric boundary noise."""
    q = (value-origin)/size
    if abs(q-round(q))*size <= 1e-8:
        q = round(q)
    return math.floor(q)


def make_grid(aoi_polygon, size, origin=(0, 0)):
    """All positive-area intersections, including zero-registration cells."""
    if size <= 0 or not aoi_polygon.is_valid or aoi_polygon.area <= 0:
        raise ValueError('Invalid grid size/AOI.')
    xmin, ymin, xmax, ymax = aoi_polygon.bounds
    rows = []
    for iy in range(math.floor((ymin-origin[1])/size), math.ceil((ymax-origin[1])/size)):
        for ix in range(math.floor((xmin-origin[0])/size), math.ceil((xmax-origin[0])/size)):
            x, y = origin[0]+ix*size, origin[1]+iy*size
            geometry = box(x,y,x+size,y+size).intersection(aoi_polygon)
            if geometry.area > 0:
                rows.append(dict(cell_id=f'{size}:{ix}:{iy}', ix=ix, iy=iy,
                                 area_m2=geometry.area, geometry=geometry))
    return pd.DataFrame(rows)


def assign_cells(places, grid, size, origin=(0,0)):
    """One deterministic assignment; inclusive outer AOI edges use covered cell.

    Internal boundaries go east/north. A point exactly on the AOI outer edge
    whose half-open cell has zero intersection is assigned to a covering cell,
    sorted by (iy, ix). No spatial-join duplication or nearest-cell guessing.
    """
    if places.id.isna().any() or places.id.duplicated().any():
        raise ValueError('POI IDs must be unique and non-null.')
    lookup = {(r.ix,r.iy):r.cell_id for r in grid.itertuples()}
    result = places.copy()
    ids=[]
    for row in places.itertuples():
        if not math.isfinite(row.x) or not math.isfinite(row.y):
            raise ValueError('Non-finite point.')
        key=(cell_index(row.x,size,origin[0]),cell_index(row.y,size,origin[1]))
        point=Point(row.x,row.y)
        # All inputs must belong to the AOI; tolerate 1 micrometre edge roundoff.
        candidates=grid[grid.geometry.map(lambda g:g.distance(point)<=1e-6)]
        if candidates.empty:
            raise ValueError('Point outside grid coverage; not an unobserved zero.')
        preferred=lookup.get(key)
        ids.append(preferred if preferred in set(candidates.cell_id)
                   else candidates.sort_values(['iy','ix']).iloc[0].cell_id)
    result['cell_id']=ids
    return result


def summarize_grid(assigned, grid, display_groups, *, coverage_complete=True):
    """Full denominator = all input registrations, including missing categories.

    Missing basic_category is explicit; alternates/hierarchy are preserved in
    inputs, but never exploded or counted. Empty cells have undefined shares.
    Incomplete coverage is rejected instead of mislabelled as zero.
    """
    if not coverage_complete:
        raise ValueError('Incomplete coverage: features cannot be labelled observed.')
    mapping={}
    for group, values in display_groups.items():
        for value in values:
            if value in mapping:
                raise ValueError('Overlapping display category mapping.')
            mapping[value]=group
    frame=assigned.copy()
    frame['category']=frame.basic_category.fillna(MISSING).replace('',MISSING)
    frame['display_group']=frame.category.map(lambda c:MISSING if c==MISSING else mapping.get(c,OTHER))
    frame['status']=frame.operating_status.fillna(MISSING).replace('',MISSING)
    cells=grid.copy()
    counts=frame.groupby('cell_id').size()
    cells['poi_count']=cells.cell_id.map(counts).fillna(0).astype(int)
    cells['density_per_km2']=cells.poi_count/(cells.area_m2/1e6)
    cells['coverage']='observed_fixed_release'
    cells['partial_cell']=cells.area_m2 < (float(cells.cell_id.iloc[0].split(':')[0])**2-1e-6)
    tables={}
    for field in ['category','display_group','status']:
        levels=sorted(set(frame[field])|{MISSING})
        index=pd.MultiIndex.from_product([cells.cell_id,levels], names=['cell_id',field])
        values=frame.groupby(['cell_id',field]).size().reindex(index,fill_value=0).rename('count').reset_index()
        values['denominator']=values.cell_id.map(counts).fillna(0).astype(int)
        values['share']=values['count']/values.denominator.replace(0,np.nan)
        tables[field]=values
    return cells, tables, frame


def run_experiment(root=None):
    """Write only ignored theme-local outputs. Reuse exact inputs, never acquire."""
    root=project_root(root)
    places,polygon,cfg,provenance=load_inputs(root)
    out=root/cfg['output'];out.mkdir(parents=True,exist_ok=True)
    runs={}
    for size in cfg['grid_sizes']:
        grid=make_grid(polygon,size,cfg['origin'])
        assigned=assign_cells(places,grid,size,cfg['origin'])
        cells,tables,assigned=summarize_grid(assigned,grid,cfg['display_groups'])
        assert cells.poi_count.sum()==len(places)
        assert abs(cells.area_m2.sum()-polygon.area)<1e-5
        for table in tables.values():
            assert table['count'].sum()==len(places)
        cells.drop(columns='geometry').to_csv(out/f'cells_{size}.csv',index=False)
        for name,t in tables.items():t.to_csv(out/f'{name}_{size}.csv',index=False)
        assigned.to_parquet(out/f'assigned_{size}.parquet',index=False)
        runs[size]=(cells,tables)
    # Nested grids must retain every POI under the same 500 m parent.
    fine=runs[250][0];coarse=runs[500][0]
    rolled=fine.assign(ix=fine.ix//2,iy=fine.iy//2).groupby(['ix','iy'])[['poi_count','area_m2']].sum()
    actual=coarse.set_index(['ix','iy'])[['poi_count','area_m2']]
    if not np.allclose(rolled.sort_index(),actual.sort_index(),atol=1e-5):
        raise ValueError('250/500 m nesting reconciliation failed.')
    transform=Transformer.from_crs('EPSG:4326',cfg['crs'],always_xy=True)
    area_delta=abs(projected_aoi(provenance['aoi'],transform,1000).area-polygon.area)
    summary={str(size):dict(cells=len(c),zero_cells=int((c.poi_count==0).sum()),
        partial_cells=int(c.partial_cell.sum()),total=int(c.poi_count.sum()),
        max_count=int(c.poi_count.max()),max_density=float(c.density_per_km2.max()),
        highest_density_cell=c.loc[c.density_per_km2.idxmax(),'cell_id']) for size,(c,t) in runs.items()}
    manifest=dict(experiment=cfg['experiment'],completed_utc=datetime.now(timezone.utc).isoformat(),
        config=cfg,**provenance,area_m2=polygon.area,edge_densification_delta_m2=area_delta,
        summary=summary,category_counts=places.basic_category.fillna(MISSING).value_counts().to_dict(),
        status_counts=places.operating_status.fillna(MISSING).value_counts().to_dict(),
        python=platform.python_version(),packages={p:importlib.metadata.version(p) for p in
        ['duckdb','pandas','numpy','pyproj','shapely','pyarrow']},
        source_sha256={p:digest(root/p) for p in ['src/geoai_open_lab/region_features.py',
            'src/geoai_open_lab/region_figures.py','notebooks/05_region_features.ipynb',
            'configs/region_features.toml',cfg['aoi'],'pyproject.toml','uv.lock']},
        output_sha256={p.name:digest(p) for p in sorted(out.iterdir()) if p.suffix in {'.csv','.parquet'}},
        command='Run notebooks/05_region_features.ipynb top-to-bottom from projects/poi',
        coverage='Complete saved AOI extraction; real-world completeness not assessed')
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return runs,manifest,out
