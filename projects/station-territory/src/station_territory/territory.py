"""Independent analysis of existing 25m station territory grids; never edits inputs."""
from __future__ import annotations
import hashlib
import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.geometry import shape, box
from .grid import Grid
from .groups import merge_groups
from .grid import midpoints as _midpoints

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data'
RESULT = OUT / 'results'
TR = Transformer.from_crs('EPSG:4326', 'EPSG:6677', always_xy=True)


def metric(geom):
    return shapely.transform(geom, lambda a: np.column_stack(TR.transform(a[:, 0], a[:, 1])))


def area23():
    with zipfile.ZipFile(ROOT / 'data/raw/N03-20260101_13_GML.zip') as z:
        d = json.loads(z.read(next(n for n in z.namelist() if n.endswith('.geojson'))))
    wanted = {str(c) for c in range(13101, 13124)}
    features = [f for f in d['features'] if f['properties']['N03_007'] in wanted]
    assert {f['properties']['N03_007'] for f in features} == wanted
    return metric(shapely.union_all([shape(f['geometry']) for f in features]))


def boundary_distance(points, geometry):
    segments=[]
    boundary=geometry.boundary if geometry.geom_type in ('Polygon','MultiPolygon') else geometry
    for line in shapely.get_parts(boundary):
        xy=shapely.get_coordinates(line)
        if len(xy)>1:
            segments.extend(shapely.linestrings(np.stack([xy[:-1],xy[1:]],axis=1)))
    if not segments: return np.full(len(points),np.inf)
    tree=shapely.STRtree(segments)
    indexes,dist=tree.query_nearest(points,all_matches=False,return_distance=True)
    out=np.full(len(points),np.inf);out[indexes[0]]=dist
    return out


def station_groups(region):
    st = pq.read_table(ROOT / f'data/build/{region}/stations-base.parquet').to_pandas()
    mid = _midpoints(shapely.from_wkb(st['wkb'].to_numpy()))
    return merge_groups(st[['group', 'name', 'line', 'operator']].assign(x=mid[:, 0], y=mid[:, 1]), 600)


def rank(df, field, n=10):
    t = df.loc[df['eligible'] & df[field].notna()].copy()
    t['rank'] = t[field].rank(method='min', ascending=False).astype(int)
    t = t.sort_values([field, 'key'], ascending=[False, True])
    return t.head(n), t[t['rank'] <= (t.iloc[min(n, len(t))-1]['rank'] if len(t) else 0)]


def load_analysis():
    aoi = area23()
    g = Grid.load(ROOT / 'data/build/tokyo/grid-base.npz')
    row_group, groups = station_groups('tokyo')
    h, w = g.dist.shape
    minx, miny, maxx, maxy = aoi.bounds
    r0 = max(0, int((miny-g.y0)//g.cell)-1); r1 = min(h, int((maxy-g.y0)//g.cell)+2)
    c0 = max(0, int((minx-g.x0)//g.cell)-1); c1 = min(w, int((maxx-g.x0)//g.cell)+2)
    rr, cc = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing='ij')
    x = g.x0 + (cc.ravel()+.5)*g.cell; y = g.y0 + (rr.ravel()+.5)*g.cell
    shapely.prepare(aoi)
    mask = shapely.intersects_xy(aoi, x, y)
    r, c, x, y = rr.ravel()[mask], cc.ravel()[mask], x[mask], y[mask]
    d = g.dist[r, c]; s = g.station[r, c]
    valid = np.isfinite(d) & (s >= 0)
    owner = np.full(len(s), -1, dtype=np.int32); owner[valid] = row_group[s[valid]]
    return aoi, g, groups, r, c, x, y, d, owner


def run():
    RESULT.mkdir(parents=True, exist_ok=True)
    aoi, g, groups, r, c, x, y, d, owner = load_analysis()
    pts = shapely.points(x, y); valid = owner >= 0
    bbox = metric(shapely.segmentize(box(138.90, 35.47, 140.00, 35.93), .005))
    danger = valid & (boundary_distance(pts,bbox) <= d + 100)
    edge_dist=boundary_distance(pts,aoi)
    all_land=shapely.union_all([shapely.from_wkb((ROOT/f'data/build/{region}/display.wkb').read_bytes()) for region in ('tokyo','saitama','chiba','kanagawa')])
    land_cut=shapely.difference(aoi.boundary,shapely.buffer(all_land.boundary,1))
    near_border = boundary_distance(pts,land_cut) <= g.cell*1.5
    df = groups[['key', 'name', 'x', 'y']].copy()
    df['station_in_23'] = shapely.covers(aoi, shapely.points(df.x, df.y))
    df['bbox_flag'] = np.isin(df.index, np.unique(owner[danger]))
    df['boundary_cut'] = np.isin(df.index, np.unique(owner[valid & near_border]))
    df['eligible'] = df.station_in_23 & ~df.bbox_flag
    cells = pd.DataFrame({'g': owner[valid], 'd': d[valid]})
    stats = cells.groupby('g').d.agg(cells='size', mean_m='mean', median_m='median',
                                   p90_m=lambda a: a.quantile(.9), max_m='max',
                                   over15_share=lambda a: float((a > 1200).mean()))
    df = df.join(stats); df['area_km2'] = df.cells.fillna(0)*g.cell**2/1e6
    # Exact intersection area for cells crossing the AOI boundary, including centres just outside.
    weights = np.full(len(x), g.cell**2)
    close = edge_dist <= g.cell / np.sqrt(2)
    weights[close] = shapely.area(shapely.intersection(
        shapely.box(x[close]-g.cell/2, y[close]-g.cell/2, x[close]+g.cell/2, y[close]+g.cell/2), aoi))
    weighted = pd.DataFrame({'g':owner[valid], 'a':weights[valid], 'ad':weights[valid]*d[valid]}).groupby('g').sum()
    # Outside-centre cells whose squares intersect AOI; excluded from main grid-centre metrics.
    h,w=g.dist.shape
    idx = np.concatenate([np.arange(max(0,int((aoi.bounds[1]-g.y0)//25)-1),min(h,int((aoi.bounds[3]-g.y0)//25)+2))])
    # Reuse the full grid AOI envelope and evaluate only outside centres near the boundary.
    ir,ic=np.meshgrid(idx,np.arange(max(0,int((aoi.bounds[0]-g.x0)//25)-1),min(w,int((aoi.bounds[2]-g.x0)//25)+2)),indexing='ij')
    ox=g.x0+(ic.ravel()+.5)*25; oy=g.y0+(ir.ravel()+.5)*25
    outside=~shapely.intersects_xy(aoi,ox,oy)
    ids=np.flatnonzero(outside); points=shapely.points(ox[ids],oy[ids])
    ids=ids[boundary_distance(points,aoi)<=25/np.sqrt(2)]
    od=g.dist[ir.ravel()[ids],ic.ravel()[ids]]; os=g.station[ir.ravel()[ids],ic.ravel()[ids]]
    keep=np.isfinite(od)&(os>=0); ids=ids[keep]; od=od[keep]; os=os[keep]
    row_group,_=station_groups('tokyo')
    wa=shapely.area(shapely.intersection(shapely.box(ox[ids]-12.5,oy[ids]-12.5,ox[ids]+12.5,oy[ids]+12.5),aoi))
    ext=pd.DataFrame({'g':row_group[os],'a':wa,'ad':wa*od}).groupby('g').sum()
    weighted=weighted.add(ext,fill_value=0)
    df['intersection_area_km2']=weighted.a.reindex(df.index,fill_value=0)/1e6
    df['intersection_mean_m']=weighted.ad/weighted.a
    cross={}
    for region in ('saitama','chiba','kanagawa'):
        other=Grid.load(ROOT/f'data/build/{region}/grid-base.npz'); rg,gs=station_groups(region)
        rr=np.floor((y-other.y0)/other.cell).astype(int); cc=np.floor((x-other.x0)/other.cell).astype(int)
        ok=valid&(rr>=0)&(cc>=0)&(rr<other.dist.shape[0])&(cc<other.dist.shape[1])
        ii=np.flatnonzero(ok); dd=other.dist[rr[ii],cc[ii]]; ss=other.station[rr[ii],cc[ii]]
        ii2=ii[np.isfinite(dd)&(ss>=0)]; dd=dd[np.isfinite(dd)&(ss>=0)]; ss=ss[np.isfinite(other.dist[rr[ii],cc[ii]])&(ss>=0)]
        keys=gs.key.to_numpy()[rg[ss]]; base=groups.key.to_numpy()[owner[ii2]]
        delta=np.abs(dd-d[ii2]); changed=keys!=base
        cross[region]={'comparable_cells':len(ii2),'max_distance_diff_m':float(delta.max()) if len(delta) else None,
                       'different_key_cells':int(changed.sum()),'material_diff_cells':int((delta>.5).sum())}
    df = df.drop(columns=['mean_m', 'median_m', 'p90_m', 'max_m', 'over15_share', 'intersection_mean_m'])
    df.to_csv(RESULT/'all_stations.csv',index=False,encoding='utf-8-sig')
    df.to_parquet(RESULT/'all_stations.parquet',index=False)
    np.savez_compressed(RESULT/'analysis_cells.npz',row=r,col=c,x=x,y=y,d=d,owner=owner,
                        x0=g.x0,y0=g.y0,cell=g.cell,shape=g.dist.shape)
    (RESULT/'aoi.wkb').write_bytes(shapely.to_wkb(aoi))
    for field in ('area_km2',):
        top,ties=rank(df,field);top.to_csv(RESULT/f'top10_{field}.csv',index=False,encoding='utf-8-sig')
        ties.to_csv(RESULT/f'with_cutoff_ties_{field}.csv',index=False,encoding='utf-8-sig')
        rank(df.assign(eligible=df.eligible&~df.boundary_cut),field)[0].to_csv(RESULT/f'interior_top10_{field}.csv',index=False,encoding='utf-8-sig')
    audit={'aoi_area_km2':aoi.area/1e6,'aoi_center_cells':len(x),'valid_cells':int(valid.sum()),
           'unassigned_center_area_km2':float((~valid).sum()*625/1e6),
           'bbox_flag_cells':int(danger.sum()),'eligible_stations':int(df.eligible.sum()),
           'outside_station_assigned_area_km2':float(df.loc[~df.station_in_23,'area_km2'].sum()),
           'neighbor_comparison':cross,'neighbor_comparison_status':'unavailable if zero comparable cells; not a passed comparison',
           'boundary_cut_definition':'valid cell within 37.5m of AOI land cut; shared 4-region coastline removed with 1m tolerance','definition_sha256':hashlib.sha256((ROOT/'docs/migration-plan.md').read_bytes()).hexdigest()}
    assert int(df.cells.sum())==int(valid.sum())
    (RESULT/'validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__': run()
