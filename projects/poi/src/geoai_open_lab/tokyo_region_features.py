"""Saved full extraction -> shared schema-v1 profiles -> reproducible comparison."""
from datetime import datetime, timezone
import importlib.metadata
import json
import platform
import tomllib

import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer, network
from shapely import points, STRtree
from shapely.geometry import box

from .aoi import project_root
from .station_square import square_geometry
from .region_features import (digest,make_grid,summarize_grid,region_profile,
    REGION_COLUMNS,SHARE_COLUMNS,load_inputs)
from .similar_regions import rank_regions
from .tokyo_stations import N03_SHA256
from .station_square import N02_SHA256


def validate_acquisition(manifest, stations):
    """Reject incomplete, filtered, wrong-release or undersized saved coverage."""
    if (not manifest['coverage_complete'] or manifest['release']!='2026-09-23.0'
            or manifest['schema_version']!='v2.0.0'
            or any(manifest[k] is not None for k in ['limit','country_filter','status_filter','confidence_filter'])
            or manifest['station_count']!=len(stations)
            or manifest['official_sha256']!={'N02-25_GML.zip':N02_SHA256,'N03-20260101_13_GML.zip':N03_SHA256}):
        raise ValueError('Incomplete/incorrect acquisition')
    expected=(stations.x.min()-500,stations.y.min()-500,stations.x.max()+500,stations.y.max()+500)
    if not np.allclose(manifest['all_square_projected_bounds'],expected,rtol=0,atol=1e-8):
        raise ValueError('Target AOI coverage differs')
    w,s,e,n=Transformer.from_crs(6677,4326,always_xy=True).transform_bounds(*expected,densify_pts=1000)
    b=manifest['acquisition_bbox']
    if not (b['west']<=w and b['south']<=s and b['east']>=e and b['north']>=n):
        raise ValueError('Acquisition bbox does not cover all target squares')


def square_runs(frame, center, groups):
    """Vectorized half-open assignment; same snapping and inclusive outer edges."""
    polygon = square_geometry(center)
    west,south,east,north = polygon.bounds
    if frame.id.isna().any() or frame.id.duplicated().any():
        raise ValueError('Invalid POI IDs')
    if not np.isfinite(frame[['x','y']]).all().all():
        raise ValueError('Nonfinite coordinates')
    if not (frame.x.between(west,east)&frame.y.between(south,north)).all():
        raise ValueError('Outside square')
    runs={}
    for size in (250,500):
        # Integer subdivision avoids ceil(4.000000000000001) creating slivers.
        grid=pd.DataFrame([dict(cell_id=f'{size}:{ix}:{iy}',ix=ix,iy=iy,
            area_m2=float(size**2),geometry=box(west+ix*size,south+iy*size,
                west+(ix+1)*size,south+(iy+1)*size))
            for iy in range(1000//size) for ix in range(1000//size)])
        if len(grid)!=(1000//size)**2 or not np.allclose(grid.area_m2,size**2,rtol=0,atol=1e-6):
            raise ValueError('Unexpected partial grid')
        q=(frame[['x','y']].to_numpy()-[west,south])/size
        rounded=np.rint(q)
        q=np.where(np.abs(q-rounded)*size<=1e-8,rounded,q)
        indices=np.clip(np.floor(q).astype(int),0,1000//size-1)
        assigned=frame.copy()
        assigned['cell_id']=[f'{size}:{x}:{y}' for x,y in indices]
        cells,tables,_=summarize_grid(assigned,grid,groups)
        if cells.poi_count.sum()!=len(frame):raise ValueError('Assignment total mismatch')
        runs[size]=(cells,tables)
    fine,coarse=runs[250][0],runs[500][0]
    rolled=fine.assign(ix=fine.ix//2,iy=fine.iy//2).groupby(['ix','iy']).poi_count.sum()
    if not rolled.equals(coarse.set_index(['ix','iy']).poi_count.sort_index()):
        raise ValueError('Parent grid counts mismatch')
    return runs


def run_comparison(root=None):
    root=project_root(root)
    cfg=tomllib.loads((root/'configs/similar_regions.toml').read_text(encoding='utf8'))
    base=tomllib.loads((root/'configs/region_features.toml').read_text(encoding='utf8'))
    raw=root/cfg['input_dir']
    mp=raw/'manifest.json'
    if digest(mp)!=cfg['manifest_sha256']:raise ValueError('Pinned manifest mismatch')
    manifest=json.loads(mp.read_text(encoding='utf8'))
    if not manifest['coverage_complete'] or manifest['release']!='2026-09-23.0' or manifest['limit'] is not None:
        raise ValueError('Incomplete/incorrect acquisition')
    for name,h in manifest['output_sha256'].items():
        if digest(raw/name)!=h:raise ValueError('Input checksum mismatch')
    stations=pd.read_csv(raw/'stations.csv',dtype={'group_code':str,'member_codes':str,'railway_types':str})
    validate_acquisition(manifest,stations)
    out=root/cfg['output'];out.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(config={'extension_directory':str(root/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        frame=con.execute('''SELECT id, ST_X(geometry) longitude,ST_Y(geometry) latitude,
            basic_category,operating_status FROM read_parquet(?) ORDER BY id''',[str(raw/'places.parquet')]).df()
    if len(frame)!=manifest['row_count'] or frame.id.isna().any() or frame.id.duplicated().any():
        raise ValueError('Invalid full extraction')
    network.set_network_enabled(False)
    frame['x'],frame['y']=Transformer.from_crs(4326,6677,always_xy=True).transform(frame.longitude.to_numpy(),frame.latitude.to_numpy())
    if not np.isfinite(frame[['x','y']]).all().all():raise ValueError('Invalid coordinates')
    tree=STRtree(points(frame.x.to_numpy(),frame.y.to_numpy()))
    profiles=[];audits=[];all_cells=[];used=set();kichijoji_ids=None
    for station in stations.to_dict('records'):
        polygon=square_geometry(station)
        indices=tree.query(polygon,predicate='covers')
        selected=frame.iloc[np.sort(indices)]
        runs=square_runs(selected,station,base['display_groups'])
        profile=region_profile(runs,station['region_id'],station['region_label'])
        profiles.append(profile)
        used.update(indices.tolist())
        for size,(cells,_) in runs.items():
            all_cells.append(cells.drop(columns='geometry').assign(region_id=station['region_id'],size_m=size))
        audits.append(dict(region_id=station['region_id'],poi_count=len(selected),
            missing_category=int(selected.basic_category.fillna('').eq('').sum()),
            statuses=json.dumps(selected.operating_status.fillna('__MISSING__').value_counts().to_dict()),
            total_250=int(runs[250][0].poi_count.sum()),total_500=int(runs[500][0].poi_count.sum())))
        if station['region_id']=='n02-003584':kichijoji_ids=set(selected.id)
    profiles=pd.concat(profiles,ignore_index=True)
    # Reconcile identities and every numeric feature against the original saved input.
    old,_,oldcfg,_=load_inputs(root)
    old_runs=square_runs(old,stations.set_index('region_id').loc['n02-003584'].to_dict(),base['display_groups'])
    expected=region_profile(old_runs,oldcfg['region_id'],oldcfg['region_label'])
    previous=pd.read_csv(root/oldcfg['output']/'region_features.csv')
    numeric=list(REGION_COLUMNS[2:])
    actual=profiles.loc[profiles.region_id=='n02-003584',numeric]
    if kichijoji_ids!=set(old.id) or not np.allclose(actual,expected[numeric],rtol=0,atol=1e-10) or not np.allclose(actual,previous[numeric],rtol=0,atol=1e-10):
        raise ValueError('Kichijoji reconciliation failed; do not rank')
    profiles.to_csv(out/'region_features.csv',index=False)
    pd.concat(all_cells,ignore_index=True).to_csv(out/'cells.csv',index=False)
    pd.DataFrame(audits).to_csv(out/'feature_audit.csv',index=False)
    stations.to_csv(out/'stations.csv',index=False)
    rankings,stability,overlap,scaling=rank_regions(profiles,stations)
    for mode,table in rankings.items():table.to_csv(out/f'ranking_{mode}.csv',index=False)
    stability.to_csv(out/'stability.csv',index=False)
    overlap.to_csv(out/'overlap_audit.csv',index=False)
    report=dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),
        input_manifest_sha256=digest(mp),input_run=manifest['run_id'],release=manifest['release'],
        acquisition_utc=manifest['completed_at_utc'],station_count=len(stations),
        bounding_box_poi_count=len(frame),union_aoi_unique_poi_count=len(used),
        overlapping_assignment_count=int(profiles.poi_count.sum()),kichijoji_reconciled=True,
        schema_version=1,columns=list(REGION_COLUMNS),scaling=scaling,
        station_audit=dict(disconnected=int(stations.disconnected.sum()),same_name=int(stations.same_name_other_group.sum()),
            boundary_within_1m=int(stations.boundary_distance_m.le(1).sum())),
        python=platform.python_version(),packages={p:importlib.metadata.version(p) for p in ['duckdb','numpy','pandas','shapely','pyproj']},
        config_sha256=digest(root/'configs/similar_regions.toml'),
        category_config_sha256=digest(root/'configs/region_features.toml'),
        design_sha256=digest(root/'docs/similar-regions-design.md'),
        notebook_sha256=digest(root/'notebooks/06_similar_regions.ipynb'),
        environment_sha256={name:digest(root/name) for name in ['pyproject.toml','uv.lock']},
        code_sha256={p.name:digest(p) for p in (root/'src/geoai_open_lab').glob('*.py')},
        output_sha256={p.name:digest(p) for p in out.glob('*.csv')})
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return profiles,rankings,stability,report,out


if __name__=='__main__':
    profiles,rankings,stability,report,out=run_comparison()
    print(rankings['main'].dropna(subset=['rank']).head(10)[['station_name','rank','distance']].to_string(index=False))
