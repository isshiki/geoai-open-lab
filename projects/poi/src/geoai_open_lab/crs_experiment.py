"""Notebook 14: fixed-input CRS measurements, independent of earlier results."""
from datetime import datetime, timezone
from importlib.metadata import version
from itertools import combinations
from pathlib import Path
import json
import math
import platform
import shutil
import tomllib

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
from pyproj import CRS, Geod, Proj, Transformer, database, network
from shapely.geometry import Point, Polygon, MultiPolygon, box
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union
from .region_clustering import ROOT, digest, load_inputs
from .walking_range import load_places

OUT = ROOT / 'data/cache/crs/kichijoji-v1'
WORLD = ROOT / 'data/raw/crs/natural-earth-5.1.1'
WORLD_HASH = '0f243aeac8ac6cf26f0417285b0bd33ac47f1b5bdb719fd3e0df37d03ea37110'
GEOD = Geod(ellps='WGS84')
EPSGS = (4326, 6668, 3857, 6677, 8857)
BUFFER_SEGMENTS = 512


def station():
    return tomllib.loads((ROOT/'configs/aoi/kichijoji_station_1km.toml').read_text(encoding='utf8'))


def transformer(target, source=4326):
    return Transformer.from_crs(source, target, always_xy=True)


def project(geometry, target):
    return transform(transformer(target).transform, geometry)


def crs_metadata():
    result = []
    for code in EPSGS:
        c = CRS(code)
        result.append(dict(epsg=code, name=c.name, type=c.type_name,
            axes=[dict(name=a.name, direction=a.direction, unit=a.unit_name) for a in c.axis_info],
            area_name=c.area_of_use.name, area_bounds=list(c.area_of_use.bounds),
            datum=c.datum.name, ellipsoid=c.ellipsoid.name,
            projection=c.coordinate_operation.method_name if c.coordinate_operation else None))
    return result


def distance_examples(lon, lat):
    rows=[]
    for label, azimuth, distance in [('north100',0,100),('east500',90,500),('northeast500',45,500),('south1000',180,1000)]:
        lo,la,_=GEOD.fwd(lon,lat,azimuth,distance)
        reference=GEOD.inv(lon,lat,lo,la)[2]
        for code in (6677,3857):
            t=transformer(code);x,y=t.transform(lon,lat);xx,yy=t.transform(lo,la)
            measured=math.hypot(xx-x,yy-y)
            rows.append(dict(point=label,longitude=lo,latitude=la,crs=code,
                geodesic_m=reference,projected_m=measured,error_m=measured-reference,
                error_pct=100*(measured/reference-1),raw_degree_distance=math.hypot(lo-lon,la-lat),
                invalid_degrees_as_m_error_m=math.hypot(lo-lon,la-lat)-reference,
                invalid_degrees_as_m_error_pct=100*(math.hypot(lo-lon,la-lat)/reference-1)))
    return pd.DataFrame(rows)


def poi_comparison(frame, lon, lat):
    """Covers includes boundaries; compare polygon approximation to exact radius."""
    f=frame.copy();n=len(f)
    f['geodesic_m']=GEOD.inv(np.full(n,lon),np.full(n,lat),f.lon.to_numpy(),f.lat.to_numpy())[2]
    f['geodesic']=f.geodesic_m.le(500)
    for code in (6677,3857):
        t=transformer(code);x,y=t.transform(lon,lat);xx,yy=t.transform(f.lon.to_numpy(),f.lat.to_numpy())
        f[f'distance_{code}_m']=np.hypot(xx-x,yy-y)
        circle=Point(x,y).buffer(500,quad_segs=BUFFER_SEGMENTS)
        mask=gpd.GeoSeries(gpd.points_from_xy(xx,yy),crs=code).covered_by(circle).to_numpy()
        f[str(code)]=mask
        if not np.array_equal(mask,f[f'distance_{code}_m'].le(500)):
            raise ValueError('Buffer discretization changed POI membership; increase resolution')
    methods=('geodesic','6677','3857')
    summary=pd.DataFrame([dict(method=m,poi_count=int(f[m].sum())) for m in methods])
    overlap=[]
    for a,b in combinations(methods,2):
        both=int((f[a]&f[b]).sum());union=int((f[a]|f[b]).sum())
        overlap.append(dict(a=a,b=b,intersection=both,union=union,jaccard=both/union if union else None,
            only_a=int((f[a]&~f[b]).sum()),only_b=int((~f[a]&f[b]).sum()),
            changed=int((f[a]^f[b]).sum()),boundary_within_1m=int(((f[a]^f[b]) & (f.geodesic_m-500).abs().le(1)).sum())))
    return f,summary,pd.DataFrame(overlap)


def polygons(g):
    if g.geom_type=='Polygon':return [g]
    if g.geom_type in ('MultiPolygon','GeometryCollection'):
        return [p for part in g.geoms for p in polygons(part)]
    return []


def geodesic_area(g):
    # Orient each polygon separately to avoid signed cancellation between islands.
    return sum(abs(GEOD.geometry_area_perimeter(orient(p,sign=1))[0]) for p in polygons(g))


def densify_geodesic(g, step_m=10000):
    """Follow the same geodesic edges used by Geod's polygon-area reference."""
    def ring(coords):
        result=[]
        for a,b in zip(coords[:-1],coords[1:]):
            result.append(a[:2]);d=GEOD.inv(*a[:2],*b[:2])[2]
            count=max(0,math.ceil(d/step_m)-1)
            if count:result.extend(GEOD.npts(*a[:2],*b[:2],count))
        result.append(coords[-1][:2]);return result
    pp=[Polygon(ring(list(p.exterior.coords)),[ring(list(r.coords)) for r in p.interiors]) for p in polygons(g)]
    return pp[0] if len(pp)==1 else MultiPolygon(pp)


def load_world():
    path=WORLD/'ne_110m_admin_0_countries.zip'
    if digest(path)!=WORLD_HASH:raise ValueError('Natural Earth checksum mismatch')
    data=gpd.read_file(path)
    if data.crs!=CRS(4326) or len(data)!=177 or not data.geometry.is_valid.all():
        raise ValueError('Unexpected world source CRS/count/validity')
    return data


def world_areas(data):
    regions={'Africa':unary_union(data.loc[data.CONTINENT.eq('Africa'),'geometry']),
             'Greenland':data.loc[data.ADMIN.eq('Greenland'),'geometry'].iloc[0],
             'Japan':data.loc[data.ADMIN.eq('Japan'),'geometry'].iloc[0]}
    rows=[]
    for name,g in regions.items():
        reference=geodesic_area(g)
        dense=densify_geodesic(g)
        if abs(geodesic_area(dense)/reference-1)>1e-9:raise ValueError('Densification changed reference area')
        for code in (3857,8857):
            a=project(dense,code).area
            rows.append(dict(region=name,crs=code,geodesic_km2=reference/1e6,
                projected_km2=a/1e6,error_pct=100*(a/reference-1)))
    return pd.DataFrame(rows)


def equal_area_patch(lon,lat,area_m2=100_000_000):
    az=np.linspace(0,360,721)
    def circle(radius):
        x,y,_=GEOD.fwd(np.full(len(az),lon),np.full(len(az),lat),az,np.full(len(az),radius))
        return Polygon(zip(x,y))
    low,high=0.,20_000.
    for _ in range(50):
        r=(low+high)/2
        if geodesic_area(circle(r))<area_m2:low=r
        else:high=r
    return circle((low+high)/2)


def synthetic_density():
    rows=[]
    for label,lon,lat in [('Equator',139.58,0),('Tokyo',139.58,35.70),('High latitude',139.58,65)]:
        g=equal_area_patch(lon,lat);reference=geodesic_area(g)/1e6
        for code in (3857,8857):
            area=project(g,code).area/1e6
            t=transformer(code);base=np.array(t.transform(lon,lat));vectors=[]
            for azimuth in (0,90):
                lo,la,_=GEOD.fwd(lon,lat,azimuth,100)
                vectors.append(np.array(t.transform(lo,la))-base)
            north,east=vectors
            angle=np.degrees(np.arccos(np.clip(np.dot(north,east)/np.linalg.norm(north)/np.linalg.norm(east),-1,1)))
            rows.append(dict(location=label,latitude=lat,crs=code,synthetic_poi_count=1000,
                geodesic_area_km2=reference,projected_area_km2=area,
                true_density=1000/reference,apparent_density=1000/area,
                area_ratio=area/reference,north_100m_projected_m=float(np.linalg.norm(north)),
                east_100m_projected_m=float(np.linalg.norm(east)),projected_angle_deg=float(angle)))
    return pd.DataFrame(rows)


def station_audit():
    _,stations,_,_=load_inputs();rows=[];area=CRS(6677).area_of_use
    inverse=transformer(4326,6677)
    for r in stations.itertuples():
        factors=Proj(CRS(6677)).get_factors(r.longitude,r.latitude)
        square=box(r.x-500,r.y-500,r.x+500,r.y+500).segmentize(25)
        geographic=transform(inverse.transform,square)
        ground_area=geodesic_area(geographic)
        west,south,east,north=geographic.bounds
        rows.append(dict(region_id=r.region_id,station_name=r.station_name,
            inside_epsg_bbox=area.west<=r.longitude<=area.east and area.south<=r.latitude<=area.north,
            whole_aoi_inside_epsg_bbox=area.west<=west and east<=area.east and area.south<=south and north<=area.north,
            meridional_scale=factors.meridional_scale,parallel_scale=factors.parallel_scale,
            areal_scale=factors.areal_scale,geodesic_aoi_area_m2=ground_area,
            projected_area_error_pct=100*(1e6/ground_area-1)))
    return pd.DataFrame(rows)


def run(out=OUT):
    """Recompute all measurements offline. Writes only Notebook 14's output folder."""
    network.set_network_enabled(False);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cfg=station();lon,lat=cfg['longitude'],cfg['latitude'];center=(cfg['center_x'],cfg['center_y'])
    f,poi_manifest=load_places(center)
    selected,summary,overlap=poi_comparison(f,lon,lat)
    tables={'distances':distance_examples(lon,lat),'poi_summary':summary,'poi_overlap':overlap,
            'world_areas':world_areas(load_world()),'synthetic_density':synthetic_density(),'station_audit':station_audit()}
    for name,frame in tables.items():frame.to_csv(out/(name+'.csv'),index=False,lineterminator='\n')
    selected.to_csv(out/'poi_membership.csv',index=False,lineterminator='\n')
    notices=ROOT/'data/cache/embedding/tokyo-v1'
    for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
        shutil.copyfile(notices/name,out/name)
    with (out/'Foursquare-NOTICE.txt').open('a',encoding='utf8') as handle:
        handle.write('\n2026-10-24: CRS distance, area and POI membership comparison; no raw POI redistribution.\n')
    x,y=transformer(6677).transform(lon,lat);lo,la=transformer(4326,6677).transform(x,y)
    series=gpd.GeoSeries([Point(lon,lat)]);labeled=series.set_crs(4326);converted=labeled.to_crs(6677)
    assert series.iloc[0].equals(labeled.iloc[0]) and not labeled.iloc[0].equals(converted.iloc[0])
    operation=transformer(6677);operation.transform(lon,lat)
    metadata=dict(created_utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),
        packages={p:version(p) for p in ('pyproj','geopandas','shapely','pandas','numpy','duckdb')},
        code_sha256=digest(__file__),lock_sha256=digest(ROOT/'uv.lock'),
        proj_version=pyproj.proj_version_str,epsg_database_version=database.get_database_metadata('EPSG.VERSION'),
        epsg_database_date=database.get_database_metadata('EPSG.DATE'),crs=crs_metadata(),
        station=cfg,station_config_sha256=digest(ROOT/'configs/aoi/kichijoji_station_1km.toml'),
        roundtrip_geodesic_error_m=GEOD.inv(lon,lat,lo,la)[2],xy_6677=[x,y],xy_3857=list(transformer(3857).transform(lon,lat)),
        operation_description=operation.description,operation_accuracy_m=operation.accuracy,
        buffer_quad_segs=BUFFER_SEGMENTS,max_buffer_radial_deficit_m=500*(1-math.cos(math.pi/(4*BUFFER_SEGMENTS))),
        poi_input=poi_manifest,world_input=json.loads((WORLD/'manifest.json').read_text(encoding='utf8')),
        local_candidate_count=len(f),world_countries=177,world_invalid_geometries=0,
        world_display='same geometries in all panels; Antarctica omitted; native split dateline parts; no inferred borders',
        command='uv run --no-sync python -m geoai_open_lab.crs_experiment',
        output_sha256={p.name:digest(p) for p in sorted(out.glob('*.csv'))})
    (out/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    return tables


if __name__=='__main__':
    result=run()
    for name,table in result.items():
        if name!='station_audit':print(name+'\n'+table.to_string(index=False))
