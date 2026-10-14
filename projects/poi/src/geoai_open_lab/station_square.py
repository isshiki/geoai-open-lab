"""Official N02 representative -> metric station square; no POI station averaging."""
import json
import zipfile
from pathlib import Path
from hashlib import sha256
from pyproj import Transformer, network
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union, linemerge

N02_SHA256 = 'aaf76af133b2e771e538fabc4646d2e443dc1d5a67b221382a28d744e706cc9f'


def station_center(zip_path, group='003584'):
    """Use official group's representative station code; midpoint in EPSG:6677."""
    p=Path(zip_path)
    if sha256(p.read_bytes()).hexdigest()!=N02_SHA256:
        raise ValueError('N02 input hash mismatch')
    with zipfile.ZipFile(p) as z:
        data=json.loads(z.read('N02-25_GML/UTF-8/N02-25_Station.geojson'))
    members=[f for f in data['features'] if f['properties']['N02_005g']==group]
    selected=[f for f in members if f['properties']['N02_005c']==group]
    if not selected:raise ValueError('Official representative station code missing')
    network.set_network_enabled(False)
    t=Transformer.from_crs(6668,6677,always_xy=True)
    line=unary_union([transform(t.transform,shape(f['geometry'])) for f in selected])
    if line.geom_type=='MultiLineString':line=linemerge(line)
    disconnected=line.geom_type=='MultiLineString'
    if disconnected:line=sorted(line.geoms,key=lambda g:(-g.length,g.wkt))[0]
    point=line.interpolate(.5,normalized=True)
    lon,lat=Transformer.from_crs(6677,4326,always_xy=True).transform(point.x,point.y)
    return dict(x=point.x,y=point.y,longitude=lon,latitude=lat,group_code=group,
        station_code=group,station_label='吉祥寺駅',source='国土数値情報 N02-25',
        source_sha256=N02_SHA256,source_retrieved_utc='2026-10-03T09:28:23Z',
        source_url='https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-25/N02-25_GML.zip',
        source_crs='EPSG:6668',source_reference_date='2025-12-31',license='CC-BY-4.0',
        member_codes=sorted({f['properties']['N02_005c'] for f in members}),
        rule='official group representative code; projected line midpoint',
        disconnected_representative=disconnected,modified_date='2026-10-14')


def square_geometry(center):
    x,y=center['x'],center['y']
    return box(x-500,y-500,x+500,y+500)


def acquisition_bbox(center):
    """Densified inverse bounds + 1cm geographic margin for the metric square."""
    t=Transformer.from_crs(6677,4326,always_xy=True)
    west,south,east,north=t.transform_bounds(*square_geometry(center).bounds,densify_pts=1000)
    return dict(west=west-1e-7,south=south-1e-7,east=east+1e-7,north=north+1e-7)
