"""Grid format from rail-gap-map 4176263; see NOTICE.md."""
from dataclasses import dataclass
import numpy as np

@dataclass
class Grid:
    dist: np.ndarray
    station: np.ndarray
    x0: float
    y0: float
    cell: float

    @staticmethod
    def load(path):
        with np.load(path, allow_pickle=False) as z:
            return Grid(z['dist'].astype(float), z['station'].copy(), float(z['x0']), float(z['y0']), float(z['cell']))

def midpoints(geometries):
    result=[]
    for geometry in geometries:
        try:
            point=geometry.interpolate(.5, normalized=True) if geometry.geom_type in ('LineString', 'MultiLineString') else geometry.centroid
        except Exception:
            point=geometry.centroid
        result.append((point.x,point.y))
    return np.array(result)
