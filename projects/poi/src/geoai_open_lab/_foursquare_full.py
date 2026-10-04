"""Full-AOI acquisition gate, separate from the unchanged 500-row tutorial."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import platform
from threading import Event, Timer
from time import perf_counter
import uuid

import duckdb
import pandas as pd

from .aoi import validate_aoi
from .foursquare import FoursquareError, query, rows

FULL_COLUMNS = (
    "fsq_place_id", "name", "latitude", "longitude", "country", "address",
    "locality", "region", "postcode", "admin_region", "post_town", "po_box",
    "tel", "website", "fsq_category_ids", "fsq_category_labels", "date_closed",
    "date_created", "date_refreshed",
)


def validate_full_records(records, expected_count, bbox, country):
    """Pure offline-checkable gate. Do not infer completeness from absent LIMIT."""
    ids = [r.get("fsq_place_id") for r in records]
    if expected_count <= 0 or not expected_count == len(records) == len(set(ids)):
        raise FoursquareError("Full-AOI COUNT/row/unique-ID mismatch or empty result.")
    if any(not isinstance(v, str) or not v.strip() for v in ids):
        raise FoursquareError("Null or empty full-AOI POI ID.")
    for r in records:
        x, y = r.get("longitude"), r.get("latitude")
        if (not isinstance(x, (int, float)) or not isinstance(y, (int, float))
                or not math.isfinite(x) or not math.isfinite(y)
                or not bbox["west"] <= x <= bbox["east"]
                or not bbox["south"] <= y <= bbox["north"]
                or r.get("country") != country or r.get("has_geometry") is not True):
            raise FoursquareError("Full-AOI coordinate/geometry/country validation failed.")
    return {"count_query": expected_count, "retrieved_rows": len(records),
            "unique_ids": len(set(ids)), "duplicate_ids": 0, "null_geometry": 0,
            "invalid_coordinates": 0, "outside_aoi": 0, "wrong_country": 0}


def fetch_all(con, *, bbox, country, timeout_seconds):
    validate_aoi(bbox, country)
    if not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 1800:
        raise ValueError("Use a positive timeout of at most 1800 seconds.")
    con.records.pop("full_places", None)
    con.details.pop("full_acquisition", None)
    schema = {c["column_name"]: c["column_type"] for c in con.details["schema"]["places"]}
    if not set(FULL_COLUMNS) | {"geom"} <= schema.keys():
        raise FoursquareError("Full-AOI schema is missing comparison attributes.")
    if schema["fsq_category_ids"] != "VARCHAR[]" or schema["geom"] != "BLOB":
        raise FoursquareError("Full-AOI category/geometry schema changed.")
    predicate = "country = ? AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?"
    parameters = [country, bbox["west"], bbox["east"], bbox["south"], bbox["north"]]
    source = con.details["sources"]["places"]
    count_sql = f"SELECT COUNT(*) AS n FROM {source} WHERE {predicate}"
    places_sql = (f"SELECT {', '.join(FULL_COLUMNS)}, geom IS NOT NULL AS has_geometry "
                  f"FROM {source} WHERE {predicate} ORDER BY fsq_place_id")
    category_sql = f"SELECT * FROM {con.details['sources']['categories']} ORDER BY category_id"
    expired = Event()
    def interrupt():
        expired.set()
        con.connection.interrupt()
    timer = Timer(timeout_seconds, interrupt)
    timer.daemon = True
    started = datetime.now(timezone.utc).isoformat()
    start = perf_counter()
    timer.start()
    try:
        expected = rows(query(con.connection, count_sql, parameters))[0]["n"]
        records = rows(query(con.connection, places_sql, parameters))
        checks = validate_full_records(records, expected, bbox, country)
        categories = rows(query(con.connection, category_sql))
        category_ids = [r["category_id"] for r in categories]
        if not category_ids or None in category_ids or len(set(category_ids)) != len(category_ids):
            raise FoursquareError("Invalid full-AOI category dictionary.")
        unknown = {c for r in records for c in r["fsq_category_ids"] or []} - set(category_ids)
        if unknown:
            raise FoursquareError("Full-AOI category IDs are missing from pinned dictionary.")
        if expired.is_set() or perf_counter() - start > timeout_seconds:
            raise FoursquareError("Full-AOI time budget exceeded; comparison must stop.")
    finally:
        timer.cancel()
        timer.join()
    if expired.is_set():
        raise FoursquareError("Full-AOI time budget exceeded; comparison must stop.")
    checks.update(schema_valid=True, unmatched_category_ids=0, categories_count=len(categories))
    con.records.update(full_places=records, full_categories=categories)
    con.details["full_acquisition"] = {
        "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_seconds": perf_counter() - start, "timeout_seconds": timeout_seconds,
        "aoi": dict(bbox), "country": country, "limit": None, "checks": checks,
        "executed_sql": {"count": count_sql, "places": places_sql, "categories": category_sql},
        "parameters": parameters,
    }
    return pd.DataFrame(records)


def save_all(con):
    details = con.details.get("full_acquisition")
    if details is None or not {"full_places", "full_categories"} <= con.records.keys():
        raise FoursquareError("Complete full acquisition before saving.")
    checks = validate_full_records(con.records["full_places"], details["checks"]["count_query"],
                                   details["aoi"], details["country"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = con.root / "data/raw/foursquare_full" / (stamp + "-" + uuid.uuid4().hex[:8])
    path.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in ("places", "categories"):
        target = path / f"{name}.json"
        target.write_text(json.dumps(con.records[f"full_{name}"], ensure_ascii=False,
                                     default=str), encoding="utf-8")
        hashes[target.name] = sha256(target.read_bytes()).hexdigest()
    saved = json.loads((path / "places.json").read_text(encoding="utf-8"))
    validate_full_records(saved, checks["count_query"], details["aoi"], details["country"])
    code_paths = ["src/geoai_open_lab/foursquare.py", "src/geoai_open_lab/_foursquare_full.py",
                  "configs/aoi/kichijoji.toml", "uv.lock"]
    safe_details = {k: details[k] for k in ("started_at_utc", "completed_at_utc",
        "acquisition_seconds", "timeout_seconds", "aoi", "country", "limit", "executed_sql", "parameters")}
    manifest = {**safe_details, "status": "completed", "provider": "foursquare",
        "cache_used": False, "snapshots": con.details["snapshots"],
        "schema": con.details["schema"],
        "checks": {**details["checks"], "saved_rows": len(saved), "full_aoi_gate_passed": True},
        "runtime": {"python": platform.python_version(), "duckdb": duckdb.__version__},
        "source_sha256": {p: sha256((con.root / p).read_bytes()).hexdigest() for p in code_paths},
        "references": ["https://docs.foursquare.com/data-products/docs/access-fsq-os-places",
                       "https://places.foursquare.com/dataset/OS%20Places/code",
                       "https://opensource.foursquare.com/places-notice-txt/"],
        "output_sha256": hashes,
        "output_bytes": {name: (path / name).stat().st_size for name in hashes},
        "limitations": ["Full means this pinned country/bbox query, not all real-world POIs.",
                         "No common operating-status filter; NULL does not mean open.",
                         "Null coordinates cannot satisfy the bbox predicate."]}
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                                 default=str), encoding="utf-8")
    return path
