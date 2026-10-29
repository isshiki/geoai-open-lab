"""Offline GeoJSON tutorial. Checks are deliberately limited to 2D examples."""
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import warnings

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import Point, LineString, Polygon, mapping, shape
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/cache/geojson/python-v1'
TOKYO_BOUNDS = (139.75, 35.67, 139.78, 35.69)


def example_frame():
    """Original synthetic examples near Tokyo Station, not surveyed features."""
    return gpd.GeoDataFrame(
        {'name': ['説明用の地点', '説明用の移動線', '説明用の範囲'],
         'fictional': [True, True, True], 'example_id': ['point', 'line', 'polygon']},
        geometry=[Point(139.767, 35.681),
                  LineString([(139.764, 35.679), (139.766, 35.680), (139.770, 35.682)]),
                  orient(Polygon([(139.768, 35.678), (139.772, 35.678),
                                  (139.772, 35.680), (139.768, 35.680)]), sign=1)],
        crs='EPSG:4326')


def example_collection():
    return json.loads(example_frame().to_json(to_wgs84=True, drop_id=True, ensure_ascii=False))


def strict_loads(text):
    def reject(value):
        raise ValueError(f'Non-JSON numeric constant: {value}')
    return json.loads(text, parse_constant=reject)


def basic_check(obj):
    """Article-only structure/range checks; not a complete RFC 7946 validator.

    Supports only FeatureCollection of non-null 2D Point/LineString/Polygon,
    finite coordinates, ring closure and winding. Geometry validity is separate.
    The crs/range checks are export-policy checks, not proof of geographic truth.
    """
    issues = []
    if not isinstance(obj, dict) or obj.get('type') != 'FeatureCollection':
        return ['FeatureCollection object required in this tutorial']
    if 'crs' in obj:
        issues.append('legacy crs member: do not use it to select a CRS in RFC 7946')
    features = obj.get('features')
    if not isinstance(features, list):
        return issues + ['features must be an array']

    def position(p):
        if not isinstance(p, list) or len(p) != 2:
            issues.append('only 2D positions supported'); return False
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in p):
            issues.append('position must contain finite numbers'); return False
        if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
            issues.append('longitude/latitude range violation')
        return True

    for f in features:
        if not isinstance(f, dict) or f.get('type') != 'Feature':
            issues.append('Feature object required'); continue
        if 'properties' not in f or not (f['properties'] is None or isinstance(f['properties'], dict)):
            issues.append('properties must be object or null')
        g = f.get('geometry')
        if not isinstance(g, dict):
            issues.append('non-null geometry required in this tutorial'); continue
        t, c = g.get('type'), g.get('coordinates')
        if t == 'Point':
            position(c)
        elif t in ('LineString', 'Polygon'):
            if not isinstance(c, list):
                issues.append('coordinates must be an array'); continue
            rings = [c] if t == 'LineString' else c
            if not rings:
                issues.append('empty coordinates unsupported')
            for index, ring in enumerate(rings):
                if not isinstance(ring, list) or len(ring) < (2 if t == 'LineString' else 4):
                    issues.append('insufficient positions'); continue
                good = [position(p) for p in ring]
                if t == 'Polygon':
                    if ring[0] != ring[-1]:
                        issues.append('ring is not closed in source JSON')
                    elif all(good):
                        area2 = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))
                        if (index == 0 and area2 < 0) or (index > 0 and area2 > 0):
                            issues.append('ring winding differs from right-hand rule')
        else:
            issues.append('geometry type outside tutorial scope')
    return issues


def content_check(obj, bounds=TOKYO_BOUNDS):
    """Example-specific plausibility only: cannot validate routes or reality."""
    try:
        frame = gpd.GeoDataFrame.from_features(obj, crs='EPSG:4326')
        xmin,ymin,xmax,ymax = frame.total_bounds
        a,b,c,d = bounds
        return [] if a <= xmin <= xmax <= c and b <= ymin <= ymax <= d else ['outside expected Tokyo example bounds']
    except (ValueError, TypeError, KeyError):
        return ['cannot evaluate content bounds']


def cases():
    normal = example_collection()
    swapped = deepcopy(normal)
    swapped['features'][0]['geometry']['coordinates'].reverse()
    unclosed = deepcopy(normal)
    unclosed['features'][2]['geometry']['coordinates'][0].pop()
    crossed = deepcopy(normal)
    crossed['features'][2]['geometry']['coordinates'] = [[
        [139.768,35.678],[139.772,35.680],[139.768,35.680],
        [139.772,35.678],[139.768,35.678]]]
    wrong_place = deepcopy(normal)
    wrong_place['features'][0]['geometry']['coordinates'] = [35.681, 45.0]
    bad_structure = {'type':'FeatureCollection', 'features':{}}
    result = {k:json.dumps(v,ensure_ascii=False,allow_nan=False) for k,v in [
        ('normal',normal),('swapped_lon_lat',swapped),('unclosed_polygon',unclosed),
        ('self_intersection',crossed),('wrong_place_valid_range',wrong_place),
        ('wrong_structure',bad_structure)]}
    result['broken_json'] = '{"type":"FeatureCollection" "features":[]}'
    return result


def probe(name, text, output):
    """Record different readers, validity and warnings without repairing input."""
    row = {'case':name,'json_ok':False,'from_features_ok':None,'read_file_ok':None,
           'shapely_valid':None,'from_features_changed':None,'read_file_changed':None,
           'basic_issues':None,'content_issues':None}
    path = output / f'case_{name}.geojson'
    path.write_text(text,encoding='utf8')
    try:
        obj = json.loads(text)
        row['json_ok'] = True
    except json.JSONDecodeError as exc:
        row['json_error'] = type(exc).__name__
        try:
            gpd.read_file(path,engine='pyogrio')
            row['read_file_ok'] = True
        except Exception as read_error:
            row['read_file_ok'] = False
            row['read_file_error'] = type(read_error).__name__
        return row
    row['basic_issues'] = basic_check(obj)
    row['content_issues'] = content_check(obj)
    try:
        if not isinstance(obj.get('features'),list):
            raise TypeError('features must be list')
        geometries = [shape(f['geometry']) for f in obj['features']]
        row['shapely_valid'] = [bool(g.is_valid) for g in geometries]
        row['shapely_reasons'] = [shapely.is_valid_reason(g) for g in geometries]
    except (ValueError, TypeError, KeyError) as exc:
        row['shapely_error'] = type(exc).__name__
    for key, reader in [('from_features', lambda:gpd.GeoDataFrame.from_features(obj,crs='EPSG:4326')),
                        ('read_file',lambda:gpd.read_file(path,engine='pyogrio'))]:
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                frame = reader()
                valid = frame.geometry.is_valid.tolist()
            row[key+'_ok'] = True
            row[key+'_valid'] = valid
            row[key+'_warnings'] = [str(w.message) for w in caught]
            original = [f['geometry'] for f in obj['features']]
            restored = [json.loads(json.dumps(mapping(g))) for g in frame.geometry]
            row[key+'_changed'] = restored != original
        except Exception as exc:  # diagnostic matrix must retain rejected cases
            row[key+'_ok'] = False
            row[key+'_error'] = type(exc).__name__
    return row


def run(output=OUT):
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    frame = example_frame()
    collection = example_collection()
    assert not basic_check(collection)
    canonical = output/'example.geojson'
    canonical.write_text(frame.to_json(to_wgs84=True,drop_id=True,ensure_ascii=False,allow_nan=False),encoding='utf8')
    restored = gpd.read_file(canonical,engine='pyogrio')
    geometry_ok = all(a.equals_exact(b,0) for a,b in zip(frame.geometry,restored.geometry))
    properties_ok = frame.drop(columns='geometry').equals(restored.drop(columns='geometry'))
    assert geometry_ok and properties_ok
    projected = frame.to_crs(6677)
    methods = {
        'to_json_wgs84': json.loads(frame.to_json()),
        'to_json_projected_default': json.loads(projected.to_json()),
        'to_json_projected_to_wgs84': json.loads(projected.to_json(to_wgs84=True)),
    }
    for name,kwargs in [('to_file_default',{}),('to_file_rfc7946',{'RFC7946':'YES'})]:
        target=output/f'{name}.geojson'
        frame.to_file(target,driver='GeoJSON',engine='pyogrio',index=False,**kwargs)
        methods[name]=json.loads(target.read_text(encoding='utf8'))
    exports=[]
    for name,obj in methods.items():
        exports.append({'method':name,'has_crs':'crs' in obj,'crs':obj.get('crs'),
                        'first_coordinates':obj['features'][0]['geometry']['coordinates'],
                        'basic_issues':basic_check(obj)})
    results=[probe(name,text,output) for name,text in cases().items()]
    versions={name:importlib.metadata.version(name) for name in ('geopandas','shapely','pyogrio','pandas','pyproj','nbclient')}
    import pyogrio
    versions.update(python=platform.python_version(),geos=shapely.geos_version_string,gdal=pyogrio.__gdal_version_string__)
    report={'versions':versions,'source':'Original fictional teaching data; no external dataset',
            'feature_count':len(frame),'crs':str(frame.crs),'geometry_types':frame.geom_type.tolist(),
            'geometry_exact_roundtrip':geometry_ok,'properties_exact_roundtrip':properties_ok,
            'exports':exports,'cases':results,
            'example_sha256':hashlib.sha256(canonical.read_bytes()).hexdigest()}
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    pd.DataFrame(results).to_csv(output/'validation.csv',index=False)
    pd.DataFrame(exports).to_csv(output/'exports.csv',index=False)
    return report


if __name__ == '__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
