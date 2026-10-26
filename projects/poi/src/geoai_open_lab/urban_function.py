"""Transparent partial reproduction of DOI 10.3390/ijgi15110482.

S=1 and equal driving weights are OUR baseline, not unverified supplement S1.
No import-time execution, downloads, or writes to earlier experiments.
"""
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
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist
from scipy.special import expit
from scipy.stats import spearmanr
from .region_clustering import ROOT, digest

OUT = ROOT/'data/cache/urban_function/kichijoji-v1'
RAW = ROOT/'data/raw/similar_regions/20261015T080101Z-tokyo'
LAND = ROOT/'data/raw/urban_function'
FUNCTIONS = ('commercial', 'green')
RESIDENTIAL = ('apartment', 'residential', 'housing_development', 'condominium')
GREEN = ('park','garden','playground','public_plaza','skate_park','sport_court',
         'sport_field','sport_or_fitness_facility','sports_and_recreation',
         'swimming_pool','stadium_arena','zoo','amusement_park')


def grid(center, size):
    if size <= 0 or 4000 % size: raise ValueError('Grid must tile 4000m')
    a = np.arange(-2000+size/2,2000,size)
    xx,yy=np.meshgrid(a+center[0],a+center[1])
    return pd.DataFrame({'x':xx.ravel(),'y':yy.ravel()})


def minmax(a):
    a=np.asarray(a,dtype=float)
    if not np.isfinite(a).all(): raise ValueError('Nonfinite input')
    span=np.ptp(a,axis=0)
    return np.divide(a-a.min(axis=0),span,out=np.zeros_like(a),where=span>0)


def memberships(z):
    """Paper Eq 1 then Eq 8. Constant columns -> 0, all-zero row -> NaN."""
    z=minmax(z)
    den=z.sum(axis=1,keepdims=True)
    return np.divide(z,den,out=np.full_like(z,np.nan),where=den>0)


def radii(points,k=5,weight_s=.5):
    points=np.asarray(points,float)
    if len(points)<=k or k<1: raise ValueError('Insufficient same-category neighbors')
    if not 0<=weight_s<=1: raise ValueError('Invalid driving weight')
    # Co-located records are retained in the field; KNN uses distinct locations.
    # This explicitly differs from unqualified POI-neighbor counting in the paper.
    unique,inverse=np.unique(points,axis=0,return_inverse=True)
    if len(unique)<=k: raise ValueError('Insufficient distinct locations')
    d=cKDTree(unique).query(unique,k=k+1)[0][:,-1][inverse]
    if np.any(d<=0): raise ValueError('Zero kth distance: audit coincident POIs; do not invent radius')
    density=k/(np.pi*d*d)
    dn=minmax(density)
    composite=weight_s+(1-weight_s)*dn  # S=1
    lo,hi=np.quantile(d,[.25,.75],method='linear')
    h=lo+(hi-lo)*expit(4*(composite-.5))
    return pd.DataFrame({'knn_distance_m':d,'density':density,'D_normalized':dn,
                         'S':1.,'C':composite,'h_min':lo,'h_max':hi,'h_m':h})


def field(points, samples, h):
    points=np.asarray(points,float); samples=np.asarray(samples,float)
    h=np.broadcast_to(np.asarray(h,float),(len(points),))
    if not len(points) or not np.isfinite(h).all() or np.any(h<=0): raise ValueError('Invalid bandwidth')
    z=np.zeros(len(samples))
    for start in range(0,len(points),256):
        d2=cdist(samples,points[start:start+256],'sqeuclidean')
        z+=np.exp(-d2/(2*h[start:start+256]**2)).sum(axis=1)
    return z  # no KDE mass normalization and no hard cutoff: paper Eq 6/7


def fixed_counts(points,center,size):
    local=(np.asarray(points)-np.asarray(center)+2000)/size
    if np.any(local<0) or np.any(local>4000/size): raise ValueError('Outside AOI')
    n=4000//size
    ij=np.minimum(np.floor(local).astype(int),n-1)
    return np.bincount(ij[:,1]*n+ij[:,0],minlength=n*n).astype(float)


def comparison(a,b):
    valid=np.isfinite(a).all(axis=1)&np.isfinite(b).all(axis=1)
    if not valid.any(): return {'valid_cells':0,'mae':None,'spearman':None,'dominant_agreement':None}
    a,b=a[valid],b[valid]
    rho=spearmanr(a.ravel(),b.ravel()).statistic if np.ptp(a)>0 and np.ptp(b)>0 else np.nan
    return dict(valid_cells=int(valid.sum()),mae=float(abs(a-b).mean()),spearman=float(rho),
                spearman_commercial=float(spearmanr(a[:,0],b[:,0]).statistic) if np.ptp(a[:,0]) and np.ptp(b[:,0]) else np.nan,
                spearman_green=float(spearmanr(a[:,1],b[:,1]).statistic) if np.ptp(a[:,1]) and np.ptp(b[:,1]) else np.nan,
                dominant_agreement=float((a.argmax(1)==b.argmax(1)).mean()))


def load_input():
    network.set_network_enabled(False)
    m=json.loads((RAW/'manifest.json').read_text(encoding='utf8'))
    if m['release']!='2026-09-23.0' or not m['coverage_complete']: raise ValueError('Unpinned/incomplete input')
    for key in ('limit','country_filter','status_filter','confidence_filter'):
        if m[key] is not None: raise ValueError('Unexpected acquisition filter')
    for name,sha in m['output_sha256'].items():
        if digest(RAW/name)!=sha: raise ValueError('Input checksum mismatch')
    cfg=tomllib.loads((ROOT/'configs/aoi/kichijoji_station_1km.toml').read_text(encoding='utf8'))
    center=np.array([cfg['center_x'],cfg['center_y']])
    w,s,e,n=Transformer.from_crs(6677,4326,always_xy=True).transform_bounds(*(list(center-2000)+list(center+2000)),densify_pts=100)
    b=m['acquisition_bbox']
    if not (b['west']<=w and b['east']>=e and b['south']<=s and b['north']>=n): raise ValueError('Coverage gap')
    with duckdb.connect(config={'extension_directory':str(ROOT/'data/cache/duckdb/extensions')}) as c:
        c.execute('LOAD spatial')
        f=c.execute('SELECT id, ST_X(geometry) lon, ST_Y(geometry) lat, basic_category, taxonomy.primary AS category, operating_status FROM read_parquet(?) WHERE ST_X(geometry) BETWEEN ? AND ? AND ST_Y(geometry) BETWEEN ? AND ? ORDER BY id',[str(RAW/'places.parquet'),w,e,s,n]).df()
    f['x'],f['y']=Transformer.from_crs(4326,6677,always_xy=True).transform(f.lon,f.lat)
    f=f[(abs(f.x-center[0])<=2000)&(abs(f.y-center[1])<=2000)].copy()
    if not f.id.is_unique or f.id.isna().any(): raise ValueError('Invalid POI IDs')
    groups=tomllib.loads((ROOT/'configs/region_features.toml').read_text(encoding='utf8'))['display_groups']
    commercial={cat for cats in groups.values() for cat in cats}
    f['function']=f.basic_category.map(lambda v:'commercial' if v in commercial else 'green' if v in GREEN else 'residential' if v in RESIDENTIAL else 'excluded')
    return f,center,m,commercial


def external_validation(cells, center, size, model):
    """Area overlay with independent 2021 reference; green is only a proxy match."""
    import geopandas as gpd
    from shapely.geometry import box
    from shapely.ops import unary_union
    lm=json.loads((LAND/'manifest.json').read_text(encoding='utf8'))
    p=LAND/lm['file']
    if digest(p)!=lm['sha256']: raise ValueError('Land checksum mismatch')
    land=gpd.read_file(p).to_crs(6677)
    aoi=box(*(list(center-2000)+list(center+2000)))
    land=land[land.intersects(aoi)].copy()
    land.geometry=land.geometry.intersection(aoi)
    code=land['L03b_u_002'].astype(str).str.zfill(4)
    land.assign(code=code,area_m2=land.area).groupby('code').area_m2.sum().to_csv(OUT/'land_reference_audit.csv')
    ref=unary_union(land.loc[code.eq('1003')].geometry)
    coverage=unary_union(land.geometry)
    if coverage.area/aoi.area < .999: raise ValueError('Land reference coverage incomplete')
    good=np.isfinite(cells[['mu_commercial','mu_green']]).all(axis=1)
    pred=cells[good & (cells.mu_green>cells.mu_commercial)]
    shape=unary_union([box(r.x-size/2,r.y-size/2,r.x+size/2,r.y+size/2) for r in pred.itertuples()])
    inter=shape.intersection(ref).area
    return dict(model=model,reference='2021 park/green code 1003',reference_area_m2=ref.area,
                predicted_area_m2=shape.area,intersection_m2=inter,coverage_ratio=coverage.area/aoi.area,
                completeness=inter/ref.area if ref.area else np.nan,
                consistency=inter/shape.area if shape.area else np.nan)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    f,center,m,commercial=load_input()
    audit=f.groupby(['basic_category','category','function'],dropna=False).agg(count=('id','size'),x_min=('x','min'),x_max=('x','max'),y_min=('y','min'),y_max=('y','max')).reset_index()
    audit['rule']=audit.function.map({'commercial':'existing six display groups','green':'explicit recreation list','residential':'explicit residential category','excluded':'not mapped; no inference'})
    audit.to_csv(OUT/'category_audit.csv',index=False)
    f[f.function.eq('residential')].to_csv(OUT/'residential_audit.csv',index=False)
    f[f.function.ne('excluded')][['x','y','function']].to_csv(OUT/'mapped_locations.csv',index=False)
    f.operating_status.fillna('__MISSING__').value_counts().to_csv(OUT/'operating_status.csv')
    # All models use the same supported functions. One residential POI cannot define KNN.
    points={g:f[f.function.eq(g)][['x','y']].to_numpy() for g in FUNCTIONS}
    rr={k:{g:radii(p,k) for g,p in points.items()} for k in (3,5,7,10)}
    pd.concat([t.assign(function=g,k=k) for k,gs in rr.items() for g,t in gs.items()],ignore_index=True).to_csv(OUT/'radii.csv',index=False)
    h_common=float(np.median(np.concatenate([rr[5][g].knn_distance_m for g in FUNCTIONS])))
    tables={}; metrics=[]
    for size in (100,250):
        samples=grid(center,size)
        for model in ('fixed_cells','common_gaussian','adaptive'):
            z=np.column_stack([fixed_counts(points[g],center,size) if model=='fixed_cells' else field(points[g],samples[['x','y']],h_common if model=='common_gaussian' else rr[5][g].h_m.to_numpy()) for g in FUNCTIONS])
            mu=memberships(z)
            t=samples.copy()
            for j,g in enumerate(FUNCTIONS): t['z_'+g]=z[:,j];t['mu_'+g]=mu[:,j]
            t['mu_residential']=np.nan  # unavailable, never "no residential function"
            t['valid']=np.isfinite(mu).all(1)
            t['dominant']=np.where(t.valid,np.array(FUNCTIONS)[np.nan_to_num(mu).argmax(1)],'undefined')
            t['entropy']=-(np.where(mu>0,mu*np.log(np.maximum(mu,1e-300)),0)).sum(1)/np.log(2)
            t.loc[~t.valid,'entropy']=np.nan
            t.to_csv(OUT/f'{model}_{size}.csv',index=False);tables[model,size]=t
        base=tables['adaptive',size][['mu_'+g for g in FUNCTIONS]].to_numpy()
        for model in ('fixed_cells','common_gaussian'):
            other=tables[model,size][['mu_'+g for g in FUNCTIONS]].to_numpy()
            metrics.append(dict(kind='model',size=size,condition=model,**comparison(base,other)))
        for k in (3,5,7,10):
            for factor in ((.6,.8,1.,1.2,1.4) if k==5 else (1.,)):
                z=np.column_stack([field(points[g],samples[['x','y']],rr[k][g].h_m.to_numpy()*factor) for g in FUNCTIONS])
                mu=memberships(z)
                metrics.append(dict(kind='radius',size=size,condition=f'k={k},factor={factor}',**comparison(base,mu)))
                pd.DataFrame(mu,columns=FUNCTIONS).to_csv(OUT/f'sensitivity_{size}_k{k}_f{factor}.csv',index=False)
    # Align both resolutions at common 50m subcell centers (exact area weights).
    aligned={}
    for size in (100,250):
        t=tables['adaptive',size];n=4000//size;repeat=size//50
        aligned[size]=np.repeat(np.repeat(t[['mu_'+g for g in FUNCTIONS]].to_numpy().reshape(n,n,2),repeat,0),repeat,1).reshape(-1,2)
    metrics.append(dict(kind='resolution_area_aligned',size=50,condition='100 vs 250',**comparison(aligned[100],aligned[250])))
    # Post-audit diagnostics: a 19m common radius is undersampled at 100m.
    # These are exploratory alternatives, not a result-selected replacement.
    samples=grid(center,100)
    base=tables['adaptive',100][['mu_'+g for g in FUNCTIONS]].to_numpy()
    for h in (100.,250.,500.):
        z=np.column_stack([field(points[g],samples[['x','y']],h) for g in FUNCTIONS])
        metrics.append(dict(kind='exploratory_common_radius',size=100,condition=f'h={h}',**comparison(base,memberships(z))))
    for ws in (.25,.75):
        z=np.column_stack([field(points[g],samples[['x','y']],radii(points[g],5,ws).h_m.to_numpy()) for g in FUNCTIONS])
        metrics.append(dict(kind='driving_weight',size=100,condition=f'weight_s={ws}',**comparison(base,memberships(z))))
    stats=pd.DataFrame(metrics);stats.to_csv(OUT/'comparison.csv',index=False)
    external=pd.DataFrame([external_validation(tables[model,100],center,100,model) for model in ('fixed_cells','common_gaussian','adaptive')])
    external.to_csv(OUT/'external_validation.csv',index=False)
    report=dict(release=m['release'],acquisition_utc=m['completed_at_utc'],completed_utc=datetime.now(timezone.utc).isoformat(),
        center=center.tolist(),crs='EPSG:6677',area_km2=16,poi_count=len(f),function_counts=f.function.value_counts().to_dict(),
        common_h_m=h_common,commercial_categories=sorted(commercial),green_categories=list(GREEN),residential_categories=list(RESIDENTIAL),
        input_manifest_sha256=digest(RAW/'manifest.json'),input_sha256=m['output_sha256'],input_schema=m['input_schema'],
        input_source=m['source_uri'],land_manifest=json.loads((LAND/'manifest.json').read_text(encoding='utf8')),
        station_sha256=digest(ROOT/'configs/aoi/kichijoji_station_1km.toml'),code_sha256=digest(__file__),lock_sha256=digest(ROOT/'uv.lock'),
        environment={'python':platform.python_version(),**{p:version(p) for p in ('numpy','scipy','pandas','duckdb','pyproj','geopandas')}},
        parameters={'S':1,'weight_s':.5,'weight_D':.5,'theta':.5,'r':4,'k':5,'grid_sizes':[100,250],
                    'KNN_category':'mapped function (commercial / green); distinct coordinate neighbors','boundary':'input clipped to 4km square, no external buffer',
                    'normalization':'function-wise minmax over grid, then row sum','zero_span':'0','all_zero':'NaN'},
        csv_sha256={p.name:digest(p) for p in OUT.glob('*.csv')})
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(ROOT/'data/cache/embedding/tokyo-v1'/name,OUT/name)
    with (OUT/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as dest:dest.write('\n2026-10-26: Urban functional influence partial reproduction.\n')
    return report,stats,external


if __name__=='__main__':
    report,stats,external=run()
    print(report['function_counts']);print(stats.to_string(index=False));print(external.to_string(index=False))
