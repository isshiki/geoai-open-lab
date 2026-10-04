"""Load region and scenario settings from configs/."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PlannedStation:
    name: str
    lon: float
    lat: float
    basis: str


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    note: str = ""
    stations: list[PlannedStation] = field(default_factory=list)


@dataclass(frozen=True)
class Region:
    name: str
    label: str
    crs: str
    display_prefixes: list[str]
    display_exclude_codes: list[str]
    compute_buffer_m: float
    bbox: tuple[float, float, float, float]
    n03_prefectures: list[str]
    osm_source: str
    cell_m: float
    walk_m_per_min: float
    levels_min: list[int]
    access_radius_m: float
    max_offroad_m: float
    smooth_sigma_cells: float
    simplify_m: float
    home_view: dict
    root: Path

    @property
    def levels_m(self) -> list[float]:
        return [m * self.walk_m_per_min for m in self.levels_min]

    @property
    def build_dir(self) -> Path:
        return self.root / "data" / "build" / self.name

    @property
    def web_dir(self) -> Path:
        return self.root / "web" / "data" / self.name


def _read(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルがありません: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)


def load_region(name: str, root: Path = ROOT) -> Region:
    d = _read(root / "configs" / "regions" / f"{name}.toml")
    d["bbox"] = tuple(d["bbox"])
    return Region(**d, root=root)


def load_scenario(name: str, root: Path = ROOT) -> Scenario:
    if name == "base":
        return Scenario(name="base", label="現在")
    d = _read(root / "configs" / "scenarios" / f"{name}.toml")
    stations = [PlannedStation(**s) for s in d.pop("stations", [])]
    return Scenario(**d, stations=stations)
