"""Fixed 4km square MAUP demonstration; offline, no previous outputs modified."""
import itertools
import json
import platform
import shutil
import tomllib
from datetime import datetime, timezone
from importlib.metadata import version
import duckdb
import numpy as np
import pandas as pd
from pyproj import Transformer, network
from scipy.stats import spearmanr
from .region_clustering import ROOT, digest
from .region_features import SHARE_GROUPS, MISSING, OTHER

OUT=ROOT/'data/cache/maup/kichijoji-v1'
RAW=ROOT/'data/raw/similar_regions/20261015T080101Z-tokyo'
SCHEMES={'square250':(250,250),'square500':(500,500),'square1000':(1000,1000),'wide':(1000,250),'tall':(250,1000)}
GROUPS=SHARE_GROUPS[:6]


def partition(frame,center,width,height):
    """Complete SW-anchored partition; internal boundary goes east/north.

    Outer east/north edges belong to last cell. No out-of-frame clipping.
    Empty cells have zero counts/density but undefined shares (NaN).
    """
    if width<=0 or height<=0 or 4000%width or 4000%height:raise ValueError('Non-tiling cell size')
    local=frame[['x','y']].to_numpy()-np.asarray(center)+2000
    if not np.isfinite(local).all() or (local<0).any() or (local>4000).any():raise ValueError('Outside fixed frame')
    nx,ny=4000//width,4000//height
    q=local/np.array([width,height]);near=np.rint(q)
    q=np.where(abs(q-near)*np.array([width,height])<=1e-8,near,q)
    ij=np.minimum(np.floor(q).astype(int),[nx-1,ny-1]);ids=ij[:,1]*nx+ij[:,0]
    table=pd.DataFrame({'cell_id':np.arange(nx*ny)})
    table['west']=center[0]-2000+(table.cell_id%nx)*width
    table['south']=center[1]-2000+(table.cell_id//nx)*height
    table['width_m']=width;table['height_m']=height;table['area_km2']=width*height/1e6
    table['poi_count']=np.bincount(ids,minlength=nx*ny)
    table['density_per_km2']=table.poi_count/table.area_km2
    for group in SHARE_GROUPS:
        name={OTHER:'other',MISSING:'missing'}.get(group,group)
        table[name+'_count']=np.bincount(ids[frame.group.eq(group)],minlength=nx*ny)
        table[name+'_share']=table[name+'_count']/table.poi_count.replace(0,np.nan)
    assert table.poi_count.sum()==len(frame)
    assert np.isclose(table.area_km2.sum(),16)
    assert (table[[{OTHER:'other',MISSING:'missing'}.get(g,g)+'_count' for g in SHARE_GROUPS]].sum(axis=1)==table.poi_count).all()
    return table,ids


def summaries(cells):
    stats=[];correlations=[]
    for scheme,t in cells.groupby('scheme',sort=False):
        for col in ['poi_count','density_per_km2']+[n+s for n in (*GROUPS,'other','missing') for s in ('_count','_share')]:
            v=t[col].dropna()
            stats.append(dict(scheme=scheme,metric=col,n=len(t),valid_n=len(v),undefined_n=int(t[col].isna().sum()),mean=v.mean(),median=v.median(),p90=v.quantile(.9,interpolation='linear'),maximum=v.max()))
        for a,b in itertools.combinations(GROUPS,2):
            x,y=t[a+'_count'],t[b+'_count']
            rho=float(spearmanr(x,y).statistic) if x.nunique()>1 and y.nunique()>1 else np.nan
            correlations.append(dict(scheme=scheme,first=a,second=b,n=len(t),rho=rho,status='defined' if np.isfinite(rho) else 'constant'))
    cor=pd.DataFrame(correlations)
    baseline=cor[cor.scheme=='square500'].set_index(['first','second']).rho
    cor['delta_from_square500']=[r.rho-baseline.loc[r.first,r.second] for r in cor.itertuples()]
    return pd.DataFrame(stats),cor


def run():
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    cfg=tomllib.loads((ROOT/'configs/region_features.toml').read_text(encoding='utf8'))
    station_path=ROOT/'configs/aoi/kichijoji_station_1km.toml'
    station=tomllib.loads(station_path.read_text(encoding='utf8'));center=(station['center_x'],station['center_y'])
    assert station['crs']=='EPSG:6677' and m['release']=='2026-09-23.0' and m['coverage_complete']
    assert all(m[key] is None for key in ('limit','country_filter','status_filter','confidence_filter'))
    for name,h in m['output_sha256'].items():assert digest(RAW/name)==h,name
    network.set_network_enabled(False)
    inverse=Transformer.from_crs(6677,4326,always_xy=True)
    bounds=[center[0]-2000,center[1]-2000,center[0]+2000,center[1]+2000]
    w,s,e,n=inverse.transform_bounds(*bounds,densify_pts=100)
    bbox=m['acquisition_bbox']
    if not(bbox['west']<=w and bbox['south']<=s and bbox['east']>=e and bbox['north']>=n):raise ValueError('Saved acquisition does not cover 4km square; do not download automatically')
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as con:
        con.execute('LOAD spatial')
        frame=con.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat, basic_category, operating_status FROM read_parquet(?) ORDER BY id',[str(RAW/'places.parquet')]).df()
    assert len(frame)==m['row_count'] and frame.id.notna().all() and frame.id.is_unique
    trans=Transformer.from_crs(4326,6677,always_xy=True)
    frame['x'],frame['y']=trans.transform(frame.lon.to_numpy(),frame.lat.to_numpy())
    frame=frame[frame.x.between(bounds[0],bounds[2]) & frame.y.between(bounds[1],bounds[3])].copy()
    mapping={cat:g for g,cats in cfg['display_groups'].items() for cat in cats}
    assert len(mapping)==sum(map(len,cfg['display_groups'].values()))
    frame['group']=frame.basic_category.fillna('').map(lambda c:MISSING if not c else mapping.get(c,OTHER))
    tables=[]
    for scheme,(width,height) in SCHEMES.items():
        t,ids=partition(frame,center,width,height);tables.append(t.assign(scheme=scheme))
    cells=pd.concat(tables,ignore_index=True);stats,cor=summaries(cells)
    OUT.mkdir(parents=True,exist_ok=True)
    for name,t in [('cells',cells),('distribution',stats),('correlations',cor),('operating_status',frame.operating_status.fillna('__MISSING__').value_counts().rename_axis('status').reset_index(name='count'))]:t.to_csv(OUT/(name+'.csv'),index=False)
    manifest=dict(release=m['release'],acquisition_utc=m['completed_at_utc'],completed_at_utc=datetime.now(timezone.utc).isoformat(),center=list(center),crs='EPSG:6677',bounds=bounds,area_km2=16,poi_count=len(frame),coverage_complete=True,required_lonlat_bbox=[w,s,e,n],acquisition_bbox=bbox,
        input_manifest_sha256=digest(RAW/'manifest.json'),input_schema=m['input_schema'],source_uri=m['source_uri'],input_sha256=m['output_sha256'],selected_ids_sha256=__import__('hashlib').sha256('\n'.join(frame.id).encode()).hexdigest(),
        station_config_sha256=digest(station_path),category_config_sha256=digest(ROOT/'configs/region_features.toml'),code_sha256=digest(__file__),lock_sha256=digest(ROOT/'uv.lock'),schemes=SCHEMES,
        environment={'python':platform.python_version(),**{p:version(p) for p in ['duckdb','numpy','pandas','scipy','pyproj']}},output_sha256={p.name:digest(p) for p in OUT.glob('*.csv')})
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    source=ROOT/'data/cache/embedding/tokyo-v1'
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):shutil.copyfile(source/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as f:f.write('\n2026-10-22: Fixed-frame MAUP aggregates and figures.\n')
    return cells,stats,cor,manifest,OUT

if __name__=='__main__':
    c,s,r,m,o=run();print('POI',m['poi_count']);print(s[s.metric=='density_per_km2'].to_string(index=False));print(r[(r['first']=='restaurant')&(r.second=='cafe')].to_string(index=False))
