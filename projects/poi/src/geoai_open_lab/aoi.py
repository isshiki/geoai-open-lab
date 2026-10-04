"""Shared WGS84 study area; no provider dependencies."""
from pathlib import Path
import math
import tomllib

def project_root(root=None):
    path = Path(root or Path.cwd()).resolve()
    if path.name == "notebooks":
        path = path.parent
    if not (path / "pyproject.toml").is_file():
        raise ValueError("Run from this project root or notebooks/.")
    return path


def load_aoi(path="configs/aoi/kichijoji.toml", *, root=None):
    """Read the shared, provider-independent WGS84 study boundary."""
    aoi = tomllib.loads((project_root(root) / path).read_text(encoding="utf-8"))
    validate_aoi(aoi, aoi["country"])
    return aoi


def validate_aoi(bbox, country):
    if bbox.get("crs") != "EPSG:4326" or bbox.get("country") != country:
        raise ValueError("AOI CRS/country must match the requested WGS84 study area.")
    bounds = [bbox[k] for k in ("west", "south", "east", "north")]
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in bounds):
        raise ValueError("AOI bounds must be finite numbers.")
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid AOI bounds.")
