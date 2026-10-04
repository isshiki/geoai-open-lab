"""Conservative, local POI comparison; not coverage or accuracy evaluation.

Acquisition SQL belongs to providers. This module preserves native categories,
uses all spatial candidates, and never uses source lineage to decide matches.
"""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
import json
import math
import re
import unicodedata
from urllib.parse import urlsplit

import pandas as pd
from pyproj import Transformer
from shapely import Point, STRtree, from_wkb

from .openstreetmap import TAG_KEYS

SOURCES = ("foursquare", "overture", "osm")
PAIRS = (("foursquare", "overture"), ("foursquare", "osm"), ("overture", "osm"))
RULES = {"candidate_distance_m": 100, "auto_distance_m": 30,
         "similarity_for_review": 0.90, "crs": "EPSG:32654", "sample_seed": 42}
DISTANCE_BINS = (5, 10, 20, 30, 50, 100)


def normalize_name(value):
    """NFKC, strip, whitespace collapse, lowercase; keep words and punctuation."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip()).lower()


def present(value):
    if isinstance(value, dict):
        return any(present(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(present(v) for v in value)
    return isinstance(value, str) and bool(value.strip())


def values(*items):
    return sorted({x.strip() for item in items for x in
                   (item if isinstance(item, list) else [item]) if present(x) and isinstance(x, str)})


def phone_keys(items):
    result = set()
    for item in items:
        for part in item.split(";"):
            text = unicodedata.normalize("NFKC", part)
            text = re.sub(r"[\s()\-‐‑–ー]", "", text)
            if text.startswith("+81"):
                text = "0" + text[3:]
            if re.fullmatch(r"0[0-9]{9,10}", text):
                result.add(text)
    return result


def domain_keys(items):
    result = set()
    for item in items:
        try:
            host = urlsplit(item if "://" in item else "https://" + item).hostname
            if host and "." in host and not re.search(r"\s", host):
                result.add(host.lower().removeprefix("www.").rstrip("."))
        except ValueError:
            pass
    return result


def evidence(left, right):
    if not left or not right:
        return "unavailable"
    return "supporting" if left & right else "conflicting"


def address_evidence(left, right):
    """Only a differing comparable postcode is a clear address conflict.

    Freeform differences can be formatting differences; country/locality alone
    are not store-level supporting evidence. No geocoding or address model.
    """
    def components(parts, keys):
        return {normalize_name(v) for p in parts for k, v in p.items()
                if k in keys and present(v)}
    a, b = (components(p, {"postcode", "addr:postcode"}) for p in (left, right))
    pa, pb = ({n for x in items if re.fullmatch(r"[0-9]{7}", n := re.sub(r"[-\s]", "", x))}
              for items in (a, b))
    if pa and pb and pa.isdisjoint(pb):
        return "conflicting"
    a, b = (components(p, {"freeform", "address", "addr:full"}) for p in (left, right))
    if a and b and a & b:
        return "supporting"
    return "not_comparable" if present(left) and present(right) else "unavailable"


def has_foursquare_source(sources):
    return any(str(s.get(k) or "").lower() == "foursquare"
               for s in sources or [] for k in ("provider", "dataset"))


def comparison_view(source, records, *, osm_raw=None, categories=None):
    """Adapt saved provider output, keeping ID grain and native category data.

    OSM address enrichment looks up only the accepted IDs. Other raw elements
    cannot become comparison rows. Brand is unavailable in the FSQ schema.
    """
    if source not in SOURCES:
        raise ValueError("Unknown provider.")
    category_names = {r["category_id"]: r["category_name"] for r in categories or []}
    raw = {}
    if source == "osm":
        if osm_raw is None:
            raise ValueError("Saved OSM response is required for address enrichment.")
        for r in osm_raw["elements"]:
            key = (r["type"], r["id"])
            if key in raw:
                raise ValueError("Duplicate raw OSM key.")
            raw[key] = r.get("tags", {})
    output = []
    for r in records:
        if source == "foursquare":
            ident, name, x, y = r["fsq_place_id"], r.get("name"), r["longitude"], r["latitude"]
            address = [{k: r.get(k) for k in ("address", "locality", "region", "postcode",
                       "admin_region", "post_town", "po_box", "country")}]
            phones, websites, brand = values(r.get("tel")), values(r.get("website")), None
            ids = r.get("fsq_category_ids") or []
            category = {"ids": ids, "names": [category_names.get(c) for c in ids]}
            category_present = bool(ids)
            status = {"date_closed": r.get("date_closed"), "date_refreshed": r.get("date_refreshed")}
            lineage = None
        elif source == "overture":
            point = from_wkb(r["geometry"])
            if point.geom_type != "Point" or point.is_empty:
                raise ValueError("Expected a nonempty Overture Point.")
            ident, name, x, y = r["id"], (r.get("names") or {}).get("primary"), point.x, point.y
            address = r.get("addresses") or []
            phones, websites, brand = values(r.get("phones")), values(r.get("websites")), r.get("brand")
            category = {"basic_category": r.get("basic_category"), "taxonomy": r.get("taxonomy")}
            category_present = present(category)
            status = {"operating_status": r.get("operating_status")}
            lineage = has_foursquare_source(r.get("sources"))
        else:
            key = (r["osm_type"], r["osm_id"])
            if key not in raw:
                raise ValueError("Accepted OSM ID missing from saved raw response.")
            ident, name, x, y = f"{key[0]}/{key[1]}", r.get("name"), r["longitude"], r["latitude"]
            address = [{k: v for k, v in raw[key].items() if k.startswith("addr:")}]
            phones = values(r.get("phone"), r.get("contact:phone"))
            websites = values(r.get("website"), r.get("contact:website"))
            brand = r.get("brand")
            category = {k: r.get(k) for k in TAG_KEYS if present(r.get(k))}
            category_present = present(category)
            status = {k: v for k, v in raw[key].items() if k == "opening_hours" or
                      k.startswith(("disused:", "abandoned:", "was:", "demolished:"))}
            lineage = None
        if not isinstance(ident, str) or not ident or not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("Invalid comparison ID or coordinate.")
        address_present = any(present(v) for p in address for k, v in p.items()
                              if k not in ("country", "addr:country"))
        output.append(dict(source=source, source_id=ident, name=name,
            name_normalized=normalize_name(name), longitude=x, latitude=y,
            address_parts=address, phones=phones, websites=websites,
            raw_category=category, brand=brand, status_raw=status,
            has_name=present(name), has_address=address_present, has_phone=bool(phones),
            has_website=bool(websites), has_category=category_present,
            has_brand=None if source == "foursquare" else present(brand),
            has_foursquare_source=lineage))
    frame = pd.DataFrame(output)
    if frame.empty or frame.source_id.duplicated().any():
        raise ValueError("Empty or duplicate-ID comparison view.")
    return frame.sort_values("source_id").reset_index(drop=True)


def attribute_presence(views):
    rows = []
    for source, view in views.items():
        for field in ("name", "address", "phone", "website", "category", "brand"):
            available = not view[f"has_{field}"].isna().all()
            count = int(view[f"has_{field}"].fillna(False).sum()) if available else None
            rows.append(dict(source=source, attribute=field, denominator=len(view),
                             count=count, percent=100 * count / len(view) if available else None))
    return pd.DataFrame(rows)


@lru_cache(maxsize=100000)
def name_similarity(left, right):
    if not left or not right:
        return None
    if left == right:
        return 1.0
    return (SequenceMatcher(None, left, right, autojunk=False).ratio()
            + SequenceMatcher(None, right, left, autojunk=False).ratio()) / 2


def projected_points(view):
    transform = Transformer.from_crs(4326, 32654, always_xy=True)
    return [Point(*transform.transform(x, y)) for x, y in zip(view.longitude, view.latitude)]


def distance_histogram(distances):
    counts = {str(n): 0 for n in DISTANCE_BINS}
    counts[">100"] = 0
    for d in distances:
        key = next((str(n) for n in DISTANCE_BINS if d <= n), ">100")
        counts[key] += 1
    return counts


def exact_name_distances(left, right):
    """AOI-wide exact-name diagnostics, including >100 m (not matching edges).

    Index by nonempty name first. Only equal-name groups are paired, avoiding
    the full provider Cartesian product. No such distant edge is auto-matched.
    """
    lp, rp = projected_points(left), projected_points(right)
    index = defaultdict(list)
    for j, name in enumerate(right.name_normalized):
        if name:
            index[name].append(j)
    return [lp[i].distance(rp[j]) for i, name in enumerate(left.name_normalized)
            if name for j in index[name]]


def candidate_pairs(left, right, *, radius=100):
    """All STRtree dwithin candidates; no nearest-only or Cartesian pairing."""
    if not 0 < radius <= 1000:
        raise ValueError("Invalid candidate radius.")
    lp, rp = projected_points(left), projected_points(right)
    indexes = STRtree(rp).query(lp, predicate="dwithin", distance=radius)
    lrows, rrows = left.to_dict("records"), right.to_dict("records")
    lphone, rphone = ([phone_keys(r["phones"]) for r in data] for data in (lrows, rrows))
    lweb, rweb = ([domain_keys(r["websites"]) for r in data] for data in (lrows, rrows))
    result = []
    for i, j in zip(*indexes):
        a, b = lrows[i], rrows[j]
        ln, rn = a["name_normalized"], b["name_normalized"]
        result.append(dict(left_source=a["source"], left_id=a["source_id"], left_name=a["name"],
            right_source=b["source"], right_id=b["source_id"], right_name=b["name"],
            left_normalized=ln, right_normalized=rn, distance_m=lp[i].distance(rp[j]),
            exact_name_match=bool(ln and rn and ln == rn), name_similarity=name_similarity(ln, rn),
            phone_evidence=evidence(lphone[i], rphone[j]),
            website_evidence=evidence(lweb[i], rweb[j]),
            address_evidence=address_evidence(a["address_parts"], b["address_parts"])))
    columns = ["left_source", "left_id", "left_name", "right_source", "right_id", "right_name",
               "left_normalized", "right_normalized", "distance_m", "exact_name_match",
               "name_similarity", "phone_evidence", "website_evidence", "address_evidence"]
    return (pd.DataFrame(result, columns=columns)
            .astype({"exact_name_match": "bool", "name_similarity": "float64", "distance_m": "float64"})
            .sort_values(["left_id", "right_id"]).reset_index(drop=True))


def classify_pairs(candidates, *, auto_distance=30, similarity=0.90):
    """Conservative reciprocal uniqueness, with all plausible competitors kept.

    Provider lineage is absent from this function's inputs. Supporting contact
    attributes never promote a nonexact name to high confidence.
    """
    out = candidates.copy()
    # A shared chain domain/building address alone is not a strong competitor.
    # Such supporting-only edges remain ambiguous, never promoted to high.
    strong = out.exact_name_match | out.name_similarity.ge(similarity)
    edges = out[strong]
    lc, rc = Counter(edges.left_id), Counter(edges.right_id)
    exact = out[out.exact_name_match]
    le, re_ = Counter(exact.left_id), Counter(exact.right_id)
    status, reasons = [], []
    for r in out.itertuples(index=False):
        reason = []
        has_names = bool(r.left_normalized and r.right_normalized)
        if not has_names:
            reason.append("missing_name")
        if not r.exact_name_match and has_names:
            reason.append("similar_name_only" if r.name_similarity >= similarity else "no_name_evidence")
        if r.distance_m > auto_distance:
            reason.append("distance_over_auto_threshold")
        if le[r.left_id] > 1 or re_[r.right_id] > 1:
            reason.append("multiple_exact_name_candidates")
        if lc[r.left_id] > 1 or rc[r.right_id] > 1:
            reason.append("competing_candidate")
        for attr in ("phone", "website", "address"):
            if getattr(r, attr + "_evidence") == "conflicting":
                reason.append("conflicting_" + attr)
        supported = (r.exact_name_match or (has_names and r.name_similarity >= similarity)
                     or "supporting" in (r.phone_evidence, r.website_evidence, r.address_evidence))
        accepted = r.exact_name_match and not reason
        status.append("high_confidence" if accepted else "ambiguous" if supported else "unmatched")
        reasons.append(";".join(reason))
    out["status"] = pd.Series(status, index=out.index, dtype="str")
    out["reasons"] = pd.Series(reasons, index=out.index, dtype="str")
    accepted = out[out.status == "high_confidence"]
    if accepted.left_id.duplicated().any() or accepted.right_id.duplicated().any():
        raise ValueError("One-to-one invariant failed.")
    return out


def unmatched_records(left, right, pairs):
    rows = []
    for view, side in ((left, "left"), (right, "right")):
        column = side + "_id"
        all_ids = set(pairs[column])
        high = set(pairs.loc[pairs.status == "high_confidence", column])
        ambiguous = set(pairs.loc[pairs.status == "ambiguous", column])
        for r in view.itertuples(index=False):
            if r.source_id in high:
                continue
            reason = ("no_spatial_candidate" if r.source_id not in all_ids else
                      "ambiguous_candidate_exists" if r.source_id in ambiguous else
                      "insufficient_evidence" if not r.name_normalized else
                      "spatial_candidate_but_no_name_evidence")
            rows.append(dict(source=r.source, source_id=r.source_id, name=r.name,
                             reason=reason, nearby=r.source_id in all_ids))
    return pd.DataFrame(rows, columns=["source", "source_id", "name", "reason", "nearby"]).astype({"nearby": "bool"})


def three_way(accepted):
    if any(p.left_id.duplicated().any() or p.right_id.duplicated().any() for p in accepted.values()):
        raise ValueError("Pairwise one-to-one invariant required before three-way grouping.")
    fo = dict(zip(accepted["foursquare_overture"].left_id, accepted["foursquare_overture"].right_id))
    fs = dict(zip(accepted["foursquare_osm"].left_id, accepted["foursquare_osm"].right_id))
    os_ = set(zip(accepted["overture_osm"].left_id, accepted["overture_osm"].right_id))
    groups = [(f, o, fs[f]) for f, o in fo.items() if f in fs and (o, fs[f]) in os_]
    frame = pd.DataFrame(groups, columns=list(SOURCES))
    if any(frame[c].duplicated().any() for c in SOURCES):
        raise ValueError("Three-way one-per-provider invariant failed.")
    return frame.sort_values(list(SOURCES)).reset_index(drop=True)


def prepare_inputs(*, root=None, paths=None, acquire_foursquare=False):
    """Verify completed full FSQ gate and local hashes; never query Overture/OSM.

    First-time users may allow FSQ acquisition explicitly; existing full results
    are reused. Missing Overture/OSM extracts require the provider tutorials.
    """
    from ._comparison_io import prepare_inputs as prepare
    return prepare(root=root, paths=paths, acquire_foursquare=acquire_foursquare)


def run_comparison(inputs, *, root=None):
    """Analyze local verified views and save local-only evidence and summaries."""
    from ._comparison_io import run_comparison as run
    return run(inputs, root=root)
