"""Minimal safe connection helpers for the first Foursquare notebook.

The tutorial calls a few functions; SQL and validation stay here. Never log remote exception bodies:
they may contain authentication headers, SQL literals, or signed URLs.
"""

from pathlib import Path
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import tomllib

import duckdb
import pandas as pd
from dotenv import dotenv_values

ENDPOINT = "https://catalog.h3-hub.foursquare.com/iceberg"
TABLES = {
    "places": "places.datasets.places_os",
    "categories": "places.datasets.categories_os",
}


class FoursquareError(RuntimeError):
    """A message safe to show in a public notebook (no remote error text)."""


def connect(root: Path) -> duckdb.DuckDBPyConnection:
    """Use only the project .env or FSQ_OS_PLACES_TOKEN; never search parent folders."""
    token = os.environ.get("FSQ_OS_PLACES_TOKEN") or dotenv_values(
        root / ".env", interpolate=False
    ).get("FSQ_OS_PLACES_TOKEN")
    if not token or not token.strip():
        raise FoursquareError(
            "FSQ_OS_PLACES_TOKEN is missing. Set a personal Places Portal token in the "
            "project .env; do not paste it into this notebook or chat."
        )
    cache = root / "data" / "cache" / "duckdb"
    cache.mkdir(parents=True, exist_ok=True)
    connection = None
    try:
        connection = duckdb.connect(config={
            "extension_directory": str(cache / "extensions"),
            "temp_directory": str(cache / "tmp"),
            "memory_limit": "1GB",
            "threads": "2",
        })
        for extension in ("httpfs", "iceberg"):
            connection.execute(f"INSTALL {extension}")
            connection.execute(f"LOAD {extension}")
        # Quoting is necessary: CREATE SECRET does not accept bound parameters.
        # This SQL is never printed or saved; the secret is not PERSISTENT.
        escaped = token.replace("'", "''")
        connection.execute(
            "CREATE SECRET fsq_portal (TYPE iceberg, TOKEN '" + escaped + "')"
        )
        connection.execute(
            "ATTACH 'places' AS places (TYPE iceberg, SECRET fsq_portal, "
            f"ENDPOINT '{ENDPOINT}', READ_ONLY)"
        )
        return connection
    except Exception:
        if connection is not None:
            connection.close()
        raise FoursquareError(
            "Foursquare connection failed. Check network access, extension "
            "installation, token expiry and OS dataset permissions in the Portal. "
            "Remote error details are suppressed to protect credentials."
        ) from None


def query(connection, sql: str, parameters=None):
    """Run experiment SQL without exposing a remote exception in cell output."""
    try:
        return connection.execute(sql, parameters or [])
    except Exception:
        raise FoursquareError(
            "Query failed. Check Portal access, table schema and snapshot "
            "availability. Remote error details are suppressed."
        ) from None


def rows(cursor):
    """Return JSON-friendly column-keyed records without requiring pandas."""
    columns = [column[0] for column in cursor.description]
    try:
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        raise FoursquareError("Fetching rows failed; remote details suppressed.") from None


def pinned_table(kind: str, snapshot_id: str) -> str:
    """Only known tables and validated numeric Iceberg IDs enter SQL text."""
    if not isinstance(snapshot_id, str) or not snapshot_id.isascii() or not snapshot_id.isdigit():
        raise ValueError("Snapshot ID must be an ASCII decimal string.")
    if not 0 < int(snapshot_id) < 2**63:
        raise ValueError("Snapshot ID is outside the positive signed 64-bit range.")
    return f"{TABLES[kind]} AT (VERSION => {snapshot_id})"


@dataclass(repr=False)
class FoursquareSession:
    """One tutorial run: a DuckDB connection and safe provenance (no token)."""

    connection: duckdb.DuckDBPyConnection
    root: Path
    details: dict = field(default_factory=dict)
    records: dict = field(default_factory=dict)

    def close(self):
        self.connection.close()


def _root(root=None):
    path = Path(root or Path.cwd()).resolve()
    if path.name == "notebooks":
        path = path.parent
    if not (path / "pyproject.toml").is_file():
        raise ValueError("Run from this project root or notebooks/.")
    return path


def load_aoi(path="configs/aoi/kichijoji.toml", *, root=None):
    """Read the shared, provider-independent WGS84 study boundary."""
    aoi = tomllib.loads((_root(root) / path).read_text(encoding="utf-8"))
    _check_aoi(aoi, aoi["country"])
    return aoi


def _check_aoi(bbox, country):
    if bbox.get("crs") != "EPSG:4326" or bbox.get("country") != country:
        raise ValueError("AOI CRS/country must match the requested WGS84 study area.")
    bounds = [bbox[k] for k in ("west", "south", "east", "north")]
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in bounds):
        raise ValueError("AOI bounds must be finite numbers.")
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid AOI bounds.")


def _select_snapshots(connection, root, snapshot_ids):
    pins_path = root / "data/cache/foursquare/snapshots.json"
    if snapshot_ids is None and pins_path.is_file():
        saved = json.loads(pins_path.read_text(encoding="utf-8"))
        snapshot_ids = {kind: saved[kind]["snapshot_id"] for kind in TABLES}
    if snapshot_ids is not None:
        if set(snapshot_ids) != set(TABLES):
            raise ValueError("Specify both places and categories snapshot IDs.")
        for kind, value in snapshot_ids.items():
            pinned_table(kind, value)
    pins = {}
    for kind, table in TABLES.items():
        snapshots = rows(query(connection, f"""
            SELECT snapshot_id, timestamp_ms, sequence_number
            FROM iceberg_snapshots({table})
            ORDER BY timestamp_ms DESC, sequence_number DESC, snapshot_id DESC
        """))
        requested = None if snapshot_ids is None else snapshot_ids[kind]
        selected = next((s for s in snapshots if requested is None or
                         str(s["snapshot_id"]) == requested), None)
        if selected is None:
            raise FoursquareError(f"Requested {kind} snapshot unavailable; no latest fallback.")
        pins[kind] = {
            "snapshot_id": str(selected["snapshot_id"]),
            "snapshot_timestamp": str(selected["timestamp_ms"]),
            "sequence_number": selected["sequence_number"], "release_label": None,
            "selection": "newest_available_snapshot" if requested is None else "explicit_or_saved_id",
        }
    return pins_path, pins


def _schemas(connection, sources):
    schemas = {k: rows(query(connection, f"DESCRIBE SELECT * FROM {v}"))
               for k, v in sources.items()}
    types = {c["column_name"]: c["column_type"] for c in schemas["places"]}
    required = {"fsq_place_id", "name", "latitude", "longitude", "country",
                "locality", "region", "address", "fsq_category_ids", "date_closed"}
    columns = {c["column_name"] for c in schemas["categories"]}
    category_required = {"category_id", "category_name", "category_label"} | {
        f"level{i}_category_id" for i in range(1, 7)}
    if not required <= types.keys() or types.get("fsq_category_ids") != "VARCHAR[]":
        raise FoursquareError("Places schema changed; expected columns and category ID array.")
    if not category_required <= columns:
        raise FoursquareError("Categories schema changed; hierarchy columns missing.")
    return schemas


def connect_foursquare(*, root=None, snapshot_ids=None):
    """Connect using the project token, with snapshots and schema checks.

    Installs/loads httpfs and iceberg into data/cache, creates a temporary secret,
    and attaches the official read-only catalog. Reuses local snapshot pins or
    selects the newest available snapshot for each OS table on the first run.
    Validates the pinned schemas; empty catalog listings are not access failures.
    Explicit IDs: snapshot_ids={"places": "...", "categories": "..."}.
    Returns a small session, not a raw DuckDB connection. See docs/foursquare.md.
    """
    root = _root(root)
    started = datetime.now(timezone.utc).isoformat()
    connection = connect(root)
    try:
        available = rows(query(connection, """
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE table_catalog = 'places' ORDER BY table_schema, table_name
        """))
        pins_path, pins = _select_snapshots(connection, root, snapshot_ids)
        sources = {k: pinned_table(k, v["snapshot_id"]) for k, v in pins.items()}
        schemas = _schemas(connection, sources)
        pins_path.parent.mkdir(parents=True, exist_ok=True)
        pins_path.write_text(json.dumps(pins, indent=2), encoding="utf-8")
        return FoursquareSession(connection, root, {
            "started_at_utc": started, "snapshots": pins, "sources": sources,
            "schema": schemas, "available_tables": available, "executed_sql": {},
        })
    except Exception:
        connection.close()
        raise


def fetch_places(con, *, bbox, country="JP", limit=500):
    """Return a DataFrame of bounded, ID-ordered POIs; validate and retain provenance.

    Fetches one extra row to detect truncation. LIMIT bounds returned rows, not
    remote scan bytes. Starting another fetch invalidates previous category results.
    """
    _check_aoi(bbox, country)
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("This tutorial supports limits from 1 to 500.")
    con.records.clear()
    con.details.pop("checks", None)
    sql = f"""
        CREATE OR REPLACE TEMP TABLE sample_places AS
        SELECT fsq_place_id, name, latitude, longitude, country,
               locality, region, address, fsq_category_ids, date_closed
        FROM {con.details['sources']['places']}
        WHERE country = ? AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?
        ORDER BY fsq_place_id LIMIT ?
    """
    query(con.connection, sql, [country, bbox["west"], bbox["east"],
                              bbox["south"], bbox["north"], limit + 1])
    probe = rows(query(con.connection, "SELECT * FROM sample_places ORDER BY fsq_place_id"))
    truncated = len(probe) > limit
    records = probe[:limit]
    if not records:
        raise FoursquareError("No POIs returned; country access not demonstrated.")
    ids = [p["fsq_place_id"] for p in records]
    if None in ids or len(set(ids)) != len(ids):
        raise FoursquareError("Duplicate or null POI IDs in sample.")
    if not all(p["country"] == country and bbox["west"] <= p["longitude"] <= bbox["east"]
               and bbox["south"] <= p["latitude"] <= bbox["north"] for p in records):
        raise FoursquareError("POI country/AOI validation failed.")
    query(con.connection, "CREATE OR REPLACE TEMP TABLE sample_places AS SELECT * FROM sample_places ORDER BY fsq_place_id LIMIT ?", [limit])
    con.records["places"] = records
    con.details.update(aoi=dict(bbox), country=country, sample_limit=limit, checks={
        "sample_count": len(records), "japan_poi_observed": country == "JP",
        "truncated": truncated, "aoi_total_if_complete": None if truncated else len(records),
        "date_closed_present": sum(p["date_closed"] is not None for p in records),
        "date_closed_null": sum(p["date_closed"] is None for p in records),
        "category_ids_missing_or_empty": sum(not p["fsq_category_ids"] for p in records),
    })
    con.details["executed_sql"] = {"places": sql}
    return pd.DataFrame(records)


def filter_places_by_category(con, places, *, categories=("Cafe", "Coffee Shop")):
    """Match exact category names (Cafe also matches Café) and their descendants.

    Checks the dictionary and unmatched POI category IDs before using EXISTS to
    avoid multiplying POIs. Only the unchanged sample from fetch_places is accepted.
    """
    if "places" not in con.records or not places.equals(pd.DataFrame(con.records["places"])):
        raise ValueError("Use the unchanged DataFrame returned by fetch_places for this session.")
    con.records.pop("cafes", None)
    if not categories or isinstance(categories, str) or any(not isinstance(v, str) or not v.strip() for v in categories):
        raise ValueError("Provide a non-empty list of category names.")
    names = {name.strip().lower() for name in categories}
    if names & {"cafe", "café"}:
        names.update(("cafe", "café"))
    category_sql = f"""
        CREATE OR REPLACE TEMP TABLE sample_categories AS
        SELECT * FROM {con.details['sources']['categories']} ORDER BY category_id LIMIT 5001
    """
    query(con.connection, category_sql)
    dictionary = rows(query(con.connection, "SELECT * FROM sample_categories ORDER BY category_id"))
    ids = [c["category_id"] for c in dictionary]
    if not 0 < len(ids) <= 5000:
        raise FoursquareError("Category dictionary empty or exceeds the guardrail.")
    if None in ids or len(set(ids)) != len(ids):
        raise FoursquareError("Duplicate or null category IDs.")
    join_sql = """
        SELECT DISTINCT t.category_id FROM sample_places p
        CROSS JOIN UNNEST(p.fsq_category_ids) AS t(category_id)
        LEFT JOIN sample_categories c ON t.category_id = c.category_id
        WHERE c.category_id IS NULL ORDER BY t.category_id
    """
    unmatched = rows(query(con.connection, join_sql))
    roots_sql = """
        CREATE OR REPLACE TEMP TABLE cafe_roots AS
        SELECT category_id, category_name, category_label FROM sample_categories
        WHERE lower(category_name) IN (SELECT UNNEST(?))
    """
    query(con.connection, roots_sql, [sorted(names)])
    roots = rows(query(con.connection, "SELECT * FROM cafe_roots ORDER BY category_id"))
    if not roots:
        raise FoursquareError("Requested category names not found; cannot infer zero matching POIs.")
    hierarchy_sql = """
        CREATE OR REPLACE TEMP TABLE cafe_categories AS
        SELECT DISTINCT c.category_id FROM sample_categories c WHERE EXISTS (
            SELECT 1 FROM cafe_roots r WHERE r.category_id IN (c.category_id,
            c.level1_category_id, c.level2_category_id, c.level3_category_id,
            c.level4_category_id, c.level5_category_id, c.level6_category_id))
    """
    query(con.connection, hierarchy_sql)
    cafe_sql = """
        SELECT p.* FROM sample_places p WHERE EXISTS (
            SELECT 1 FROM UNNEST(p.fsq_category_ids) AS t(category_id)
            JOIN cafe_categories c ON c.category_id = t.category_id)
        ORDER BY fsq_place_id
    """
    cafes = rows(query(con.connection, cafe_sql))
    if len({p["fsq_place_id"] for p in cafes}) != len(cafes):
        raise FoursquareError("Duplicate POI IDs after category filtering.")
    con.records.update(categories=dictionary, cafes=cafes)
    con.details.update(cafe_root_categories=roots, unmatched_category_ids=unmatched,
                       category_names=sorted(names))
    con.details["checks"].update(unmatched_category_id_count=len(unmatched),
        categories_count=len(dictionary), cafe_root_category_count=len(roots),
        cafe_pois_in_sample=len(cafes))
    con.details["executed_sql"].update(categories=category_sql, join=join_sql,
        cafe_roots=roots_sql, hierarchy=hierarchy_sql, cafes=cafe_sql)
    if unmatched:
        print(f"カテゴリ辞書に未対応のIDが {len(unmatched)} 件あります。詳細は実行記録を確認してください。")
    return pd.DataFrame(cafes, columns=places.columns)


def save_results(con):
    """Save validated local extracts and manifest under ignored data/, return path."""
    from ._foursquare_provenance import save_results as save
    return save(con)
