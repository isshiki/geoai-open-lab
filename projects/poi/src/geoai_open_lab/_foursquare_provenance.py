"""Local-only provenance writer for the Foursquare tutorial, not a public API."""

from datetime import datetime, timezone
from hashlib import sha256
import json
import platform
import uuid

import duckdb

from .foursquare import ENDPOINT, TABLES, query, rows


def save_results(session):
    if not {"places", "categories", "cafes"} <= session.records.keys():
        raise ValueError("Complete POI retrieval and category filtering before saving.")
    details = session.details
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = session.root / "data/raw/foursquare" / (stamp + "-" + uuid.uuid4().hex[:8])
    # Destination is fixed; callers cannot accidentally publish elsewhere.
    run_dir.mkdir(parents=True, exist_ok=False)
    output_hashes = {}
    for name, records in session.records.items():
        path = run_dir / f"{name}.json"
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        output_hashes[path.name] = sha256(path.read_bytes()).hexdigest()
    source_paths = ["notebooks/01_foursquare_places.ipynb", "src/geoai_open_lab/foursquare.py",
        "src/geoai_open_lab/_foursquare_provenance.py", "configs/aoi/kichijoji.toml",
        "pyproject.toml", "uv.lock"]
    extensions = rows(query(session.connection, """
        SELECT extension_name, extension_version FROM duckdb_extensions()
        WHERE extension_name IN ('httpfs', 'iceberg') ORDER BY extension_name
    """))
    # Explicit allowlist: never serialize the session, environment, or secrets.
    manifest = {
        "status": "completed", "started_at_utc": details["started_at_utc"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_endpoint": ENDPOINT, "tables": TABLES, "snapshots": details["snapshots"],
        "aoi": details["aoi"], "filters": {"country": details["country"],
            "bbox_inclusive": True, "closed_excluded": False},
        "sample_limit": details["sample_limit"], "sample_order": "fsq_place_id ASC",
        "checks": details["checks"], "schema": details["schema"],
        "available_tables": details["available_tables"],
        "cafe_root_categories": details["cafe_root_categories"],
        "category_names": details["category_names"],
        "unmatched_category_ids": details["unmatched_category_ids"],
        "runtime": {"python": platform.python_version(), "duckdb": duckdb.__version__,
            "extensions": extensions},
        "source_sha256": {p: sha256((session.root / p).read_bytes()).hexdigest() for p in source_paths},
        "executed_sql": details["executed_sql"], "output_sha256": output_hashes,
        "references": [
            "https://docs.foursquare.com/data-products/docs/access-fsq-os-places",
            "https://docs.foursquare.com/data-products/docs/places-os-data-schema",
            "https://docs.foursquare.com/data-products/docs/fsq-os-places-release-notes",
            "https://places.foursquare.com/dataset/OS%20Places/code",
            "https://places.foursquare.com/dataset/OS%20Categories/code",
            "https://opensource.foursquare.com/places-notice-txt/",
        ],
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
        indent=2, default=str), encoding="utf-8")
    return run_dir
