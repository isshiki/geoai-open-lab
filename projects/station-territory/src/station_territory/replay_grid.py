"""Rebuild Tokyo road grid in isolated data/replay; never overwrite imported inputs."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import time
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree
from .territory import ROOT
from .provenance import verify_inputs, digest
from ._upstream import admin, network, water, stations, shortest, surface
from ._upstream.config import load_region, load_scenario


def audit_access(region):
    nodes = pd.read_parquet(region.build_dir / 'nodes.parquet')
    st = pd.read_parquet(region.build_dir / 'stations-base.parquet')
    xy = nodes[['x', 'y']].to_numpy()
    tree = cKDTree(xy)
    records = []
    for i, geometry in enumerate(shapely.from_wkb(st.wkb.to_numpy())):
        left, bottom, right, top = geometry.bounds
        center = [(left + right) / 2, (bottom + top) / 2]
        radius = np.hypot(right - left, top - bottom) / 2 + region.access_radius_m
        candidates = tree.query_ball_point(center, radius)
        distances = shapely.distance(shapely.points(xy[candidates]), geometry)
        count = int((distances <= region.access_radius_m).sum())
        if not count:
            point = geometry.interpolate(.5, normalized=True) if geometry.geom_type == 'LineString' else geometry
            _, nearest = tree.query([point.x, point.y])
            records.append({'station_row': i, 'name': st.iloc[i]['name'],
                            'access_m': float(shapely.distance(shapely.Point(xy[nearest]), geometry))})
    return {'station_rows': len(st), 'fallback_count': len(records), 'fallbacks': records,
            'rule': 'all nodes within 100m; if none, nearest node without a distance cap'}


def run():
    verify_inputs()
    started = datetime.now(timezone.utc).isoformat()
    region = replace(load_region('tokyo', ROOT), root=ROOT / 'data/replay')
    base = load_scenario('base', ROOT)
    region.build_dir.mkdir(parents=True, exist_ok=True)
    pbf = ROOT / 'data/raw/kanto-261001.osm.pbf'
    steps = {}
    for name, action in (
        ('admin', lambda: admin.run(region, sorted((ROOT / 'data/raw').glob('N03-*.zip')))),
        ('network', lambda: network.run(region, pbf)),
        ('water', lambda: water.run(region, pbf)),
        ('stations', lambda: stations.run(region, base, ROOT / 'data/raw/N02-25_GML.zip')),
        ('shortest', lambda: shortest.run(region, base)),
        ('surface', lambda: surface.run(region, base)),
    ):
        start = time.perf_counter()
        print('Replay:', name, flush=True)
        action()
        steps[name] = time.perf_counter() - start
    access = audit_access(region)
    old = surface.Grid.load(ROOT / 'data/build/tokyo/grid-base.npz')
    new = surface.Grid.load(region.build_dir / 'grid-base.npz')
    geometry_equal = old.dist.shape == new.dist.shape and (old.x0, old.y0, old.cell) == (new.x0, new.y0, new.cell)
    comparison = {'grid_geometry_equal': geometry_equal}
    if geometry_equal:
        valid = np.isfinite(old.dist) & np.isfinite(new.dist)
        comparison.update({'finite_mask_equal': bool(np.array_equal(np.isfinite(old.dist), np.isfinite(new.dist))),
                           'max_distance_delta_m': float(np.abs(old.dist[valid] - new.dist[valid]).max()) if valid.any() else None,
                           'station_row_equal': bool(np.array_equal(old.station, new.station))})
    report = {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
              'stage_seconds': steps, 'access': access, 'comparison': comparison,
              'raw_grid_sha256': digest(region.build_dir / 'grid-base.npz')}
    (ROOT / 'data/replay/validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(comparison), flush=True)
    return report


if __name__ == '__main__':
    run()
