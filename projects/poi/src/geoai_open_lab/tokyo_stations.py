"""Pinned official station groups; no name-based merging or guessed centers."""
from collections import defaultdict
from pathlib import Path
import json
import zipfile

import pandas as pd
from pyproj import Transformer, network
from shapely.geometry import shape, Point
from shapely.ops import transform, unary_union, linemerge

from .region_features import digest
from .station_square import N02_SHA256

N03_SHA256 = '94f10b26256566db970dd74b09d614f059c1e8a432f9244ac9c4add76c32ff16'


def representative(lines):
    line = unary_union(lines)
    if line.geom_type == 'MultiLineString':
        line = linemerge(line)
    disconnected = line.geom_type == 'MultiLineString'
    if disconnected:
        line = sorted(line.geoms, key=lambda g: (-g.length, g.wkt))[0]
    if line.geom_type != 'LineString' or line.is_empty or not line.is_valid or line.length <= 0:
        raise ValueError('Invalid representative line')
    return line.interpolate(.5, normalized=True), disconnected


def select_stations(features, boundary):
    """Full N02 population -> groups whose projected representative is covered."""
    network.set_network_enabled(False)
    project = Transformer.from_crs(6668, 6677, always_xy=True)
    inverse = Transformer.from_crs(6677, 4326, always_xy=True)
    groups = defaultdict(list)
    for f in features:
        groups[f['properties']['N02_005g']].append(f)
    rows = []
    for code, members in sorted(groups.items()):
        selected = [f for f in members if f['properties']['N02_005c'] == code]
        if not selected:
            raise ValueError(f'Missing official representative: {code}')
        point, disconnected = representative([transform(project.transform, shape(f['geometry'])) for f in selected])
        if not boundary.covers(point):
            continue
        names = sorted({f['properties']['N02_005'] for f in selected})
        if len(names) != 1 or not names[0] or '\ufffd' in names[0]:
            raise ValueError(f'Invalid representative name: {code}')
        lon, lat = inverse.transform(point.x, point.y)
        rows.append(dict(region_id=f'n02-{code}', group_code=code, station_name=names[0],
            region_label=names[0]+'駅周辺1km四方', x=point.x, y=point.y,
            longitude=lon, latitude=lat, disconnected=disconnected,
            member_codes=';'.join(sorted({f['properties']['N02_005c'] for f in members})),
            railway_types=';'.join(sorted({f['properties']['N02_001'] for f in members})),
            member_names=';'.join(sorted({f['properties']['N02_005'] for f in members})),
            boundary_distance_m=point.distance(boundary.boundary),
            on_boundary=boundary.boundary.covers(point)))
    frame = pd.DataFrame(rows)
    if frame.empty or frame.region_id.duplicated().any():
        raise ValueError('Invalid target station population')
    frame['same_name_other_group'] = frame.station_name.duplicated(keep=False)
    return frame.sort_values('region_id').reset_index(drop=True)


def load_stations(n02, n03):
    if digest(n02) != N02_SHA256 or digest(n03) != N03_SHA256:
        raise ValueError('Official input hash mismatch')
    with zipfile.ZipFile(n02) as z:
        features = json.loads(z.read('N02-25_GML/UTF-8/N02-25_Station.geojson'))['features']
    with zipfile.ZipFile(n03) as z:
        areas = json.loads(z.read('N03-20260101_13.geojson'))['features']
    if not all(f['properties']['N03_001'] == '東京都' for f in areas):
        raise ValueError('Unexpected administrative boundary')
    project = Transformer.from_crs(6668, 6677, always_xy=True)
    boundary = unary_union([transform(project.transform, shape(f['geometry'])) for f in areas])
    if not boundary.is_valid:
        raise ValueError('Invalid Tokyo boundary')
    return select_stations(features, boundary)
