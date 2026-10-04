"""2020 JGD2011 census: exact-area allocation to the existing 25m grid."""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from .grid import Grid
from .territory import ROOT, OUT, RESULT, area23, station_groups, rank

PROJECT=Transformer.from_crs('EPSG:6668','EPSG:6677',always_xy=True)
POP='T001142001'

def mesh_bounds(key):
    """Standard region mesh: 1km subdivided twice; quadrant 1=SW,2=SE,3=NW,4=NE."""
    s=str(key)
    if len(s)!=10 or not s.isdecimal() or any(q not in '1234' for q in s[8:]):
        raise ValueError('Expected 10-digit quarter mesh')
    lat=int(s[:2])*2/3+int(s[4])/12+int(s[6])/120
    lon=int(s[2:4])+100+int(s[5])/8+int(s[7])/80
    height,width=1/120,1/80
    for q in map(int,s[8:]):
        height/=2;width/=2
        lat+=(q>=3)*height;lon+=(q in (2,4))*width
    return lon,lat,lon+width,lat+height

def mesh_geometry(key):
    left,bottom,right,top=mesh_bounds(key)
    # Eight segments per edge retain curvature of projected parallels/meridians.
    a=np.linspace(0,1,9)[:-1]
    lon=np.concatenate([left+(right-left)*a,np.full(8,right),right-(right-left)*a,np.full(8,left)])
    lat=np.concatenate([np.full(8,bottom),bottom+(top-bottom)*a,np.full(8,top),top-(top-bottom)*a])
    x,y=PROJECT.transform(lon,lat)
    return shapely.Polygon(np.column_stack([x,y]))

def audit_secrecy(data):
    bykey=data.set_index('KEY_CODE')
    if len(bykey)!=len(data) or not bykey.index.is_unique:raise ValueError('Duplicate mesh keys')
    if not set(data.HTKSYORI)<= {'0','1','2'}:raise ValueError('Unknown confidentiality code')
    for row in data[data.HTKSYORI=='2'].itertuples():
        if row.HTKSAKI not in bykey.index:raise ValueError('Missing aggregation destination')
        target=bykey.loc[row.HTKSAKI]
        if target.HTKSYORI!='1' or row.KEY_CODE not in target.GASSAN.split(';'):
            raise ValueError('Inconsistent aggregation references')
    for row in data[data.HTKSYORI=='1'].itertuples():
        for key in row.GASSAN.split(';'):
            if key not in bykey.index or bykey.loc[key,'HTKSYORI']!='2' or bykey.loc[key,'HTKSAKI']!=row.KEY_CODE:
                raise ValueError('Inconsistent aggregation reverse references')

def allocations_for_geometry(geometry,grid,row_group):
    """Intersect all cell squares, including centres outside AOI; retain unreachable share."""
    left,bottom,right,top=geometry.bounds
    nr,nc=grid.dist.shape
    r0=max(0,int(np.floor((bottom-grid.y0)/grid.cell)))
    r1=min(nr,int(np.floor((top-grid.y0)/grid.cell))+1)
    c0=max(0,int(np.floor((left-grid.x0)/grid.cell)))
    c1=min(nc,int(np.floor((right-grid.x0)/grid.cell))+1)
    rr,cc=np.meshgrid(np.arange(r0,r1),np.arange(c0,c1),indexing='ij');rr=rr.ravel();cc=cc.ravel()
    x=grid.x0+cc*grid.cell;y=grid.y0+rr*grid.cell
    area=shapely.area(shapely.intersection(shapely.box(x,y,x+grid.cell,y+grid.cell),geometry))
    keep=area>1e-9;rr,cc,area=rr[keep],cc[keep],area[keep]
    distance=grid.dist[rr,cc];station=grid.station[rr,cc]
    valid=np.isfinite(distance)&(station>=0)
    owner=np.full(len(area),-1,dtype=int);owner[valid]=row_group[station[valid]]
    error=geometry.area-float(area.sum())
    if abs(error)>max(1e-4,geometry.area*1e-9):raise ValueError(f'Grid extent fails to cover AOI mesh: {error}')
    return owner,area,distance


def run():
    """Recompute population from the census ZIP and geometry, never old results."""
    source = ROOT / 'data/raw/tblT001142Q5339.zip'
    with zipfile.ZipFile(source) as archive:
        data = pd.read_csv(io.BytesIO(archive.read('tblT001142Q5339.txt')),
                           encoding='cp932', dtype=str, skiprows=[1], keep_default_na=False)
    audit_secrecy(data)
    total = pd.to_numeric(data[POP], errors='raise')
    if total.isna().any() or (total < 0).any():
        raise ValueError('Missing or negative population; do not impute zero.')
    aoi = area23()
    shapely.prepare(aoi)
    grid = Grid.load(ROOT / 'data/build/tokyo/grid-base.npz')
    row_group, _ = station_groups('tokyo')
    stations = pd.read_parquet(RESULT / 'all_stations.parquet')
    values = {k: np.zeros(len(stations)) for k in (
        'population', 'inhabited_mesh_area_km2', 'population_distance_sum')}
    mesh_rows, contributions = [], []
    for i, row in enumerate(data.itertuples()):
        mesh = mesh_geometry(row.KEY_CODE)
        if not aoi.intersects(mesh):
            continue
        clipped = mesh if aoi.covers(mesh) else shapely.intersection(mesh, aoi)
        if clipped.area < 1e-7:
            continue
        owner, area, distance = allocations_for_geometry(clipped, grid, row_group)
        pop = float(total.iloc[i])
        fraction = area / mesh.area
        valid = owner >= 0
        allocated = pop * fraction[valid].sum()
        inpop = pop * clipped.area / mesh.area
        np.add.at(values['population'], owner[valid], pop * fraction[valid])
        np.add.at(values['population_distance_sum'], owner[valid], pop * fraction[valid] * distance[valid])
        if pop > 0:
            np.add.at(values['inhabited_mesh_area_km2'], owner[valid], area[valid] / 1e6)
        mesh_rows.append({'mesh': row.KEY_CODE, 'population': pop,
                         'confidentiality': row.HTKSYORI, 'population_in_23': inpop,
                         'assigned_population': allocated, 'unassigned_population': inpop - allocated})
        for group in np.unique(owner[valid]):
            take = owner == group
            contributions.append({'mesh': row.KEY_CODE, 'group': int(group),
                                  'area_m2': float(area[take].sum()),
                                  'population': pop * float(fraction[take].sum()),
                                  'population_distance_sum': float((pop * fraction[take] * distance[take]).sum())})
    for key, value in values.items():
        stations[key] = value
    stations['population_mean_m'] = stations.population_distance_sum / stations.population.replace(0, np.nan)
    meshes = pd.DataFrame(mesh_rows)
    totals = meshes[['population_in_23', 'assigned_population', 'unassigned_population']].sum()
    error = totals.population_in_23 - totals.assigned_population - totals.unassigned_population
    if abs(error) > 1e-5 or abs(stations.population.sum() - totals.assigned_population) > 1e-5:
        raise ValueError('Population conservation failed')
    parts = pd.DataFrame(contributions)
    check = parts.groupby('group')[['population', 'population_distance_sum']].sum().reindex(stations.index, fill_value=0)
    if not np.allclose(check.population, stations.population, atol=1e-7) or not np.allclose(check.population_distance_sum, stations.population_distance_sum, atol=1e-5):
        raise ValueError('Contribution reconciliation failed')
    stations.to_parquet(RESULT / 'all_stations.parquet', index=False)
    meshes.to_parquet(RESULT / 'population_mesh_audit.parquet', index=False)
    parts.to_parquet(RESULT / 'mesh_station_allocations.parquet', index=False)
    for field in ('population', 'inhabited_mesh_area_km2', 'population_mean_m'):
        eligible = stations.eligible & ((stations.population >= 1000) if field == 'population_mean_m' else True)
        top, ties = rank(stations.assign(eligible=eligible), field)
        top.to_csv(RESULT / f'top10_{field}.csv', index=False)
        ties.to_csv(RESULT / f'with_cutoff_ties_{field}.csv', index=False)
    audit = {**totals.to_dict(), 'source_table': 'T001142', 'datum': 'JGD2011',
             'census_date': '2020-10-01', 'source_rows': len(data),
             'intersecting_listed_meshes': len(meshes), 'conservation_error_people': float(error),
             'population_outside_station': float(stations.loc[~stations.station_in_23, 'population'].sum()),
             'unlisted_meshes': 'not imputed into observed zero',
             'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (RESULT / 'population_validation.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    return audit
