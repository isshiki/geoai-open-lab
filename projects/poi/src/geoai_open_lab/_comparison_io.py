"""Local input validation, orchestration and provenance for experiment 04."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter
import uuid

import pandas as pd
import pyarrow.parquet as pq

from .aoi import load_aoi, project_root
from ._foursquare_full import validate_full_records
from .poi_comparison import (SOURCES, PAIRS, RULES, comparison_view, attribute_presence,
    candidate_pairs, classify_pairs, unmatched_records, three_way,
    exact_name_distances, distance_histogram)

PINS = {"places": "2325979374271449319", "categories": "5006175908264532092"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local_path(root, path):
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root / "data"):
        raise ValueError("Comparison inputs must be inside project-local data/.")
    return candidate


def verify_file(path, expected):
    if not expected or digest(path) != expected:
        raise ValueError("Saved input hash mismatch; comparison must stop.")


def prepare_inputs(*, root=None, paths=None, acquire_foursquare=False):
    root = project_root(root)
    aoi = load_aoi(root=root)
    folders = {"foursquare": "foursquare_full", "overture": "overture", "osm": "osm"}
    selected = {}
    for source in SOURCES:
        if paths and source in paths:
            path = local_path(root, paths[source])
            path = path / "manifest.json" if path.is_dir() else path
        else:
            available = sorted((root / "data/raw" / folders[source]).glob("*/manifest.json"))
            path = available[-1] if available else None
        if path is None and source == "foursquare" and acquire_foursquare:
            from .foursquare import connect_foursquare, fetch_all_places, save_all_results
            session = connect_foursquare(root=root, snapshot_ids=PINS)
            try:
                fetch_all_places(session, bbox=aoi, country="JP")
                path = save_all_results(session) / "manifest.json"
            finally:
                session.close()
        if path is None:
            raise ValueError(f"Missing saved {source} input; follow the provider guide first.")
        selected[source] = (path, read_json(path))
        m = selected[source][1]
        if any(m.get("aoi", {}).get(k) != aoi[k] for k in
               ("west", "south", "east", "north", "crs", "country")):
            raise ValueError("Input AOI does not match the shared Kichijoji definition.")
    path, fm = selected["foursquare"]
    check = fm.get("checks", {})
    if (fm.get("status") != "completed" or not check.get("full_aoi_gate_passed")
            or fm.get("limit") is not None or fm.get("country") != "JP"
            or any(fm.get("snapshots", {}).get(k, {}).get("snapshot_id") != v for k, v in PINS.items())):
        raise ValueError("Foursquare full-AOI gate / pins not satisfied.")
    for name in ("places.json", "categories.json"):
        verify_file(path.parent / name, fm["output_sha256"].get(name))
    fsq = read_json(path.parent / "places.json")
    validate_full_records(fsq, check["count_query"], aoi, "JP")
    if any(check.get(k) != len(fsq) for k in ("retrieved_rows", "unique_ids", "saved_rows")):
        raise ValueError("Foursquare saved gate counts disagree.")
    categories = read_json(path.parent / "categories.json")
    dictionary = {r["category_id"] for r in categories}
    if len(dictionary) != len(categories) or None in dictionary or not dictionary or any(
            c not in dictionary for r in fsq for c in r["fsq_category_ids"] or []):
        raise ValueError("Pinned category dictionary integrity failed.")
    op, om = selected["overture"]
    if om.get("release") != "2026-09-23.0" or om.get("limit") is not None:
        raise ValueError("Expected complete fixed Overture release.")
    verify_file(op.parent / "places.parquet", om["output_sha256"].get("places.parquet"))
    overture = pq.read_table(op.parent / "places.parquet").to_pylist()
    if len(overture) != om["row_count"]:
        raise ValueError("Overture row-count mismatch.")
    sp, sm = selected["osm"]
    if sm.get("osmnx_version") != "2.1.1":
        raise ValueError("Expected OSMnx 2.1.1 provenance.")
    verify_file(sp.parent / "places.parquet", sm["outputs"]["places.parquet"]["sha256"])
    osm = pq.read_table(sp.parent / "places.parquet").to_pylist()
    if len(osm) != sm["checks"]["final_count"]:
        raise ValueError("OSM accepted count mismatch.")
    raw_path = local_path(root, sm["raw_cache"])
    verify_file(raw_path, sm["raw_cache_sha256"])
    raw = read_json(raw_path)["response"]
    views = {"foursquare": comparison_view("foursquare", fsq, categories=categories),
             "overture": comparison_view("overture", overture),
             "osm": comparison_view("osm", osm, osm_raw=raw)}
    for frame in views.values():
        if not (frame.longitude.between(aoi["west"], aoi["east"])
                & frame.latitude.between(aoi["south"], aoi["north"])).all():
            raise ValueError("Comparison coordinate outside AOI.")
    saved_address_keys = ("addr:housenumber", "addr:street", "addr:city", "addr:postcode")
    before = sum(any(isinstance(r.get(k), str) and r[k].strip() for k in saved_address_keys) for r in osm)
    provenance = {}
    for source, (p, m) in selected.items():
        provenance[source] = {"manifest": p.relative_to(root).as_posix(), "manifest_sha256": digest(p),
            "saved_input_reused": True, "query": m.get("executed_sql", m.get("sql", m.get("query"))),
            "parameters": m.get("parameters"), "aoi": m["aoi"],
            "snapshots": m.get("snapshots"), "release": m.get("release"),
            "base_timestamp": m.get("osm_base_timestamp"),
            "acquisition_start_utc": m.get("started_at_utc", m.get("retrieval_start_utc")),
            "acquisition_end_utc": m.get("completed_at_utc", m.get("retrieval_end_utc")),
            "input_sha256": m.get("output_sha256", m.get("outputs")),
            "raw_cache_sha256": m.get("raw_cache_sha256"),
            "original_acquisition_cache_hit": m.get("cache_hit", m.get("cache_used", False))}
    return {"views": views, "provenance": provenance, "aoi": aoi,
            "foursquare_gate": check,
            "osm_address_audit": {"accepted_ids": len(osm), "address_present_before": before,
                "address_present_after": int(views["osm"].has_address.sum()),
                "no_new_raw_ids_added": len(views["osm"]) == len(osm)}}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str, allow_nan=False), encoding="utf-8")


def sensitivity(candidates):
    result = []
    for radius in (30, 50, 100):
        subset = candidates[candidates.distance_m <= radius]
        classified = classify_pairs(subset)
        exact = subset[subset.exact_name_match]
        lc, rc = Counter(exact.left_id), Counter(exact.right_id)
        result.append({"radius_m": radius, "candidate_pairs": len(subset),
            "exact_name_pairs": len(exact), "high_confidence_auto30": int((classified.status == "high_confidence").sum()),
            "ambiguous_pairs": int((classified.status == "ambiguous").sum()),
            "left_multiple_exact_ids": sum(n > 1 for n in lc.values()),
            "right_multiple_exact_ids": sum(n > 1 for n in rc.values()),
            "competing_candidate_pairs": int(((classified.status == "ambiguous") &
                classified.reasons.str.contains("competing_candidate")).sum())})
    return result


def run_comparison(inputs, *, root=None):
    root = project_root(root)
    # Revalidate files at each execution, rather than trusting mutable supplied views.
    paths = {s: p["manifest"] for s, p in inputs["provenance"].items()}
    inputs = prepare_inputs(root=root, paths=paths)
    views = inputs["views"]
    start = perf_counter()
    stamp = datetime.now(timezone.utc)
    run = root / "data/raw/comparison" / (stamp.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    for source, view in views.items():
        # pandas nullable string/brand columns may use NaN internally; JSON uses null.
        write_json(run / f"{source}_view.json", json.loads(view.to_json(orient="records", force_ascii=False)))
    presence = attribute_presence(views)
    presence.to_json(run / "presence.json", orient="records", force_ascii=False, indent=2)
    summary = {"records": {s: len(v) for s, v in views.items()}, "pairs": {},
               "foursquare_gate": inputs["foursquare_gate"], "osm_address_audit": inputs["osm_address_audit"]}
    accepted, samples = {}, {"high_confidence": [], "ambiguous": [], "unmatched_nearby": []}
    any_high = {s: set() for s in SOURCES}
    for left, right in PAIRS:
        key = left + "_" + right
        pair_start = perf_counter()
        candidates = candidate_pairs(views[left], views[right], radius=RULES["candidate_distance_m"])
        diagnostic = distance_histogram(exact_name_distances(views[left], views[right]))
        sens = sensitivity(candidates)
        pairs = classify_pairs(candidates, auto_distance=RULES["auto_distance_m"])
        high = pairs[pairs.status == "high_confidence"].copy()
        ambiguous = pairs[pairs.status == "ambiguous"]
        unmatched = unmatched_records(views[left], views[right], pairs)
        pairs.to_parquet(run / f"{key}_candidates.parquet", index=False)
        high.to_parquet(run / f"{key}_accepted.parquet", index=False)
        ambiguous.to_parquet(run / f"{key}_ambiguous.parquet", index=False)
        unmatched.to_parquet(run / f"{key}_unmatched.parquet", index=False)
        accepted[key] = high
        any_high[left].update(high.left_id)
        any_high[right].update(high.right_id)
        for name, frame in (("high_confidence", high), ("ambiguous", ambiguous),
                            ("unmatched_nearby", unmatched[unmatched.nearby])):
            # Pair-stratified deterministic pool; final cap applied across all pairs.
            pool = frame.sample(n=min(20, len(frame)), random_state=RULES["sample_seed"]).copy()
            if name == "unmatched_nearby":
                previews = []
                for record in pool.itertuples(index=False):
                    side = "left" if record.source == left else "right"
                    nearby = pairs[pairs[side + "_id"] == record.source_id]
                    # Ordering is for human review only; never resolves a match.
                    nearest = nearby.sort_values(["distance_m", "left_id", "right_id"]).head(3)
                    previews.append(nearest.to_json(orient="records", force_ascii=False))
                pool["nearby_candidates_for_review"] = previews
            pool["pair"] = key
            samples[name].extend(pool.to_dict("records"))
        unmatched_counts = {s: unmatched[unmatched.source == s].reason.value_counts().to_dict() for s in (left, right)}
        summary["pairs"][key] = {"candidate_pairs": len(pairs), "high_confidence": len(high),
            "ambiguous_pairs": len(ambiguous), "unmatched_records": unmatched_counts,
            "exact_name_distance_bins_all_aoi": diagnostic, "sensitivity": sens,
            "high_confidence_distance_bins": distance_histogram(high.distance_m),
            "seconds": perf_counter() - pair_start}
        del candidates, pairs, ambiguous
    groups = three_way(accepted)
    groups.to_parquet(run / "three_way.parquet", index=False)
    summary["three_way"] = len(groups)
    summary["no_high_confidence_in_either_other_source"] = {
        s: len(v) - len(any_high[s]) for s, v in views.items()}
    ov_flags = dict(zip(views["overture"].source_id, views["overture"].has_foursquare_source))
    audit = accepted["foursquare_overture"].copy()
    audit["has_foursquare_source"] = audit.right_id.map(ov_flags)
    audit.to_parquet(run / "foursquare_source_audit.parquet", index=False)
    summary["foursquare_source_audit"] = {
        "overture_pois_with_foursquare_source": sum(ov_flags.values()),
        "accepted_by_flag": {str(flag): {"count": int((audit.has_foursquare_source == flag).sum()),
            "distance_bins": distance_histogram(audit.loc[audit.has_foursquare_source == flag, "distance_m"])}
            for flag in (True, False)}}
    summary["samples"] = {}
    for name, maximum in (("high_confidence", 10), ("ambiguous", 20), ("unmatched_nearby", 10)):
        frame = pd.DataFrame(samples[name])
        if not frame.empty:
            frame = frame.sample(n=min(maximum, len(frame)), random_state=RULES["sample_seed"])
        frame["review_status"] = "pending"
        frame.to_csv(run / f"review_{name}.csv", index=False, encoding="utf-8-sig")
        summary["samples"][name] = {"count": len(frame), "review_status": "pending"}
    summary["seconds"] = perf_counter() - start
    write_json(run / "summary.json", summary)
    outputs = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size} for p in run.iterdir() if p.is_file()}
    sources = ["src/geoai_open_lab/poi_comparison.py", "src/geoai_open_lab/_comparison_io.py",
               "src/geoai_open_lab/_foursquare_full.py", "src/geoai_open_lab/foursquare.py",
               "src/geoai_open_lab/openstreetmap.py", "src/geoai_open_lab/overture.py",
               "notebooks/04_poi_comparison.ipynb", "configs/aoi/kichijoji.toml", "pyproject.toml", "uv.lock"]
    manifest = {"status": "completed", "started_at_utc": stamp.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "seconds": summary["seconds"],
        "aoi": inputs["aoi"], "inputs": inputs["provenance"], "rules": RULES,
        "normalization": "NFKC / strip / whitespace collapse / lowercase; no deletion",
        "strong_competitor": "nonempty exact name or symmetric similarity >= 0.90 within 100m",
        "threshold_decision": "Retain 100m search / 30m auto after all-three-pair exact-name distance and 30/50/100m sensitivity checks; not accuracy calibration.",
        "runtime": {"python": platform.python_version(), **{k: version(k) for k in
                    ("duckdb", "pandas", "pyarrow", "shapely", "pyproj", "osmnx")}},
        "source_sha256": {p: digest(root / p) for p in sources}, "outputs": outputs,
        "output_bytes": sum(p["bytes"] for p in outputs.values()),
        "network_bytes": None, "scanned_bytes": None, "peak_memory_bytes": None,
        "remote_queries_in_comparison": 0, "review_status": "pending",
        "limitations": ["Different snapshots and POI/geometry definitions.",
            "No common operating-status filter; missing status is unknown.",
            "High confidence means a rule-based candidate, not verified identity.",
            "No accuracy/coverage evaluation or provider ranking.",
            "Source lineage is audit-only and cannot corroborate independence.",
            "No correspondence does not establish absence in other data."]}
    write_json(run / "manifest.json", manifest)
    return {"path": run, "summary": summary, "presence": presence, "manifest": manifest}
