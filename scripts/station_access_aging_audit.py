"""Offline input audit only: no road requests, age rates, distances or correlations.

Run after station_access_aging_acquire.py. Evidence is saved under ignored data/cache.
Mesh rules: https://www.stat.go.jp/data/mesh/m_tuite.html
"""

from __future__ import annotations

import csv
import io
import itertools
import json
import re
import unicodedata
import zipfile

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

from station_access_aging_acquire import ROOT, RAW, CACHE, sha256, inspect_zip, utc_now

LABELS = {
    'T001142001': '人口(総数)', 'T001142004': '0~14歳人口総数',
    'T001142010': '15~64歳人口総数', 'T001142019': '65歳以上人口総数',
    'T001142034': '世帯総数', 'T001142035': '一般世帯数',
}


def normalize_label(value):
    return ''.join(unicodedata.normalize('NFKC', value).split())


def mesh_center(code):
    """Return (longitude, latitude) of a JGD2011 250m mesh center."""
    if not re.fullmatch(r'\d{4}[0-7]{2}\d{2}[1-4]{2}', code):
        raise ValueError('Invalid 250m mesh code')
    lat = int(code[:2]) * 2 / 3 + int(code[4]) / 12 + int(code[6]) / 120
    lon = 100 + int(code[2:4]) + int(code[5]) / 8 + int(code[7]) / 80
    for q, lat_step, lon_step in [(int(code[8]) - 1, 1 / 240, 1 / 160),
                                   (int(code[9]) - 1, 1 / 480, 1 / 320)]:
        lat += (q // 2) * lat_step
        lon += (q % 2) * lon_step
    return lon + 1 / 640, lat + 1 / 960


def all_mesh_codes(prefix='5339'):
    for a, b, c, d, e, f in itertools.product(range(8), range(8), range(10), range(10), range(1, 5), range(1, 5)):
        yield f'{prefix}{a}{b}{c}{d}{e}{f}'


def read_population(path):
    with zipfile.ZipFile(path) as archive:
        files = [n for n in archive.namelist() if n.endswith('.txt')]
        if len(files) != 1:
            raise ValueError('Expected one census text file')
        text = archive.read(files[0]).decode('cp932')
    reader = csv.reader(io.StringIO(text))
    codes, labels = next(reader), next(reader)
    if len(codes) != len(set(codes)) or len(labels) != len(codes):
        raise ValueError('Header cardinality error')
    mapping = dict(zip(codes, labels))
    for code, label in LABELS.items():
        if normalize_label(mapping.get(code, '')) != label:
            raise ValueError(f'Unexpected census label for {code}')
    rows = list(reader)
    if any(len(row) != len(codes) for row in rows):
        raise ValueError('Ragged census rows')
    df = pd.DataFrame(rows, columns=codes)
    if df.KEY_CODE.duplicated().any() or not df.HTKSYORI.isin(['0', '1', '2']).all():
        raise ValueError('Invalid census key or secrecy code')
    for key in df.KEY_CODE:
        mesh_center(key)
    return df, {c: mapping[c] for c in LABELS}


def secrecy_links(df):
    """Check forward/reverse references without reconstructing suppressed values."""
    indexed = df.set_index('KEY_CODE')
    pairs = set()
    reverse = set()
    missing_targets = 0
    invalid_targets = 0
    for row in df[df.HTKSYORI == '2'].itertuples():
        pairs.add((row.KEY_CODE, row.HTKSAKI))
        if row.HTKSAKI not in indexed.index:
            missing_targets += 1
        elif indexed.loc[row.HTKSAKI, 'HTKSYORI'] != '1':
            invalid_targets += 1
    for row in df[df.HTKSYORI == '1'].itertuples():
        for origin in row.GASSAN.split(';'):
            reverse.add((origin, row.KEY_CODE))
    return {'origin_links': len(pairs), 'reverse_links': len(reverse),
            'missing_targets': missing_targets, 'target_status_errors': invalid_targets,
            'forward_reverse_mismatches': len(pairs.symmetric_difference(reverse)),
            'regular_rows_with_link_fields': int(((df.HTKSYORI == '0') & ((df.HTKSAKI != '') | (df.GASSAN != ''))).sum())}


def census_profile(df):
    numeric = df[list(LABELS)].apply(pd.to_numeric, errors='coerce')
    ordinary = df.HTKSYORI == '0'
    ages = numeric[['T001142004', 'T001142010', 'T001142019']].sum(axis=1, min_count=3)
    residual = numeric.T001142001 - ages
    households = numeric.T001142034 - numeric.T001142035
    symbols = {c: df.loc[~df[c].str.fullmatch(r'\d+'), c].value_counts().to_dict() for c in LABELS}
    suppressed = df.HTKSYORI == '2'
    return {'rows': len(df), 'columns': len(df.columns), 'duplicate_keys': int(df.KEY_CODE.duplicated().sum()),
            'secrecy_counts': df.HTKSYORI.value_counts().to_dict(), 'non_numeric_symbols': symbols,
            'age_suppression_pattern_errors': int(sum((df[c].eq('*') != suppressed).sum() for c in ['T001142004', 'T001142010', 'T001142019'])),
            'nonsecret_zero_age_denominator': int((ordinary & ages.eq(0)).sum()),
            'nonsecret_age_sum_above_total': int((ordinary & residual.lt(0)).sum()),
            'nonsecret_positive_total_minus_age_sum': int((ordinary & residual.gt(0)).sum()),
            'negative_institutional_households': int(households.lt(0).sum()),
            'institutional_households_present': int(households.gt(0).sum()),
            'imputation_method': 'unconfirmed; residual is not proof of imputation method'}


def shape_from_zip(path, suffix):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(suffix)]
    if len(names) != 1:
        raise ValueError('Expected one matching shapefile')
    frame = gpd.read_file('/vsizip/' + path.as_posix() + '/' + names[0], encoding='cp932')
    if frame.crs.to_epsg() != 6668:
        raise ValueError('Expected JGD2011 EPSG:6668')
    return frame


def geometry_profile(frame):
    return {'rows': len(frame), 'crs': str(frame.crs), 'columns': list(frame.columns),
            'geometry_types': frame.geom_type.value_counts().to_dict(),
            'missing': int(frame.geometry.isna().sum()), 'empty': int(frame.geometry.is_empty.sum()),
            'invalid': int((~frame.geometry.is_valid).sum())}


def main():
    manifest = json.loads((CACHE / 'acquisition-manifest.json').read_text(encoding='utf-8'))
    for source in manifest['sources']:
        path = ROOT / source['path']
        if sha256(path) != source['sha256']:
            raise ValueError('Input checksum mismatch')
        inspect_zip(path)
    df, labels = read_population(RAW / 'tblT001142Q5339.zip')
    boundary = shape_from_zip(RAW / 'N03-20200101_13_GML.zip', '.shp')
    stations = shape_from_zip(RAW / 'N02-20_GML.zip', '_Station.shp')
    cities = boundary[boundary.N03_007.isin(['13203', '13204'])].copy()
    for code, name in [('13203', '武蔵野市'), ('13204', '三鷹市')]:
        if set(cities.loc[cities.N03_007 == code, 'N03_004']) != {name}:
            raise ValueError('City code/name mismatch')
    if (~cities.is_valid).any() or cities.geometry.is_empty.any():
        raise ValueError('Invalid city geometry; no silent repair')
    projected = cities.to_crs(6677)
    union = projected.geometry.union_all()
    buffer = union.buffer(5000)
    transformer = Transformer.from_crs(6677, 4326, always_xy=True)
    bbox = list(transformer.transform_bounds(*buffer.bounds, densify_pts=101))
    # Enumerate all 250m cells in 5339 independently of census row presence.
    all_codes = list(all_mesh_codes())
    coords = [mesh_center(k) for k in all_codes]
    centers = gpd.GeoDataFrame({'KEY_CODE': all_codes}, geometry=gpd.points_from_xy([c[0] for c in coords], [c[1] for c in coords]), crs=6668).to_crs(6677)
    adopted = centers[centers.geometry.covered_by(union)].copy()
    adopted['city_code'] = ''
    membership = pd.Series(0, index=adopted.index)
    for code in ['13203', '13204']:
        city = projected.loc[projected.N03_007 == code].geometry.union_all()
        mask = adopted.geometry.covered_by(city)
        membership += mask.astype(int)
        adopted.loc[mask & adopted.city_code.eq(''), 'city_code'] = code
    joined = adopted.merge(df, on='KEY_CODE', how='left', validate='one_to_one', indicator=True)
    matched = joined[joined['_merge'] == 'both']
    area = df[df.KEY_CODE.isin(matched.KEY_CODE)]
    adopted_keys = set(adopted.KEY_CODE)
    origins = df[df.HTKSYORI == '2']
    crosses_aoi = origins.KEY_CODE.isin(adopted_keys) != origins.HTKSAKI.isin(adopted_keys)
    geo_stations = stations.to_crs(6677)
    valid = geo_stations.geometry.notna() & ~geo_stations.geometry.is_empty & geo_stations.geometry.is_valid & geo_stations.geom_type.eq('LineString')
    mids = geo_stations[valid].copy()
    mids.geometry = mids.geometry.interpolate(0.5, normalized=True)
    nearby = mids[mids.geometry.covered_by(buffer)].copy()
    allowed = nearby.N02_001.isin(['11', '12', '14', '15', '16', '21', '22', '23', '24']) & nearby.N02_002.isin(['2', '3', '4', '5'])
    candidates = nearby[allowed].copy()
    candidates['midpoint_wkb'] = candidates.geometry.to_wkb(hex=True)
    # Coordinate duplicates are counted, not irreversibly merged at this audit stage.
    code_counts = nearby.groupby(['N02_001', 'N02_002']).size()
    report = {
        'audited_utc': utc_now(), 'script_sha256': sha256(__file__),
        'acquisition_manifest_sha256': sha256(CACHE / 'acquisition-manifest.json'),
        'population_all': census_profile(df), 'census_labels_verified': labels,
        'secrecy_links_all': secrecy_links(df), 'population_aoi': census_profile(area),
        'secrecy_links_crossing_aoi': int(crosses_aoi.sum()),
        'aoi': {'city_codes': ['13203', '13204'], 'city_rows': len(cities),
                'city_geometry': geometry_profile(cities), 'area_km2': float(union.area / 1e6),
                'city_bbox_jgd2011': cities.total_bounds.tolist(),
                'buffer_metres': 5000, 'road_fetch_bbox_wgs84': bbox,
                'expected_center_meshes': len(adopted), 'matched_meshes': len(matched),
                'missing_census_meshes': int((joined['_merge'] == 'left_only').sum()),
                'multiple_city_memberships': int(membership.gt(1).sum()),
                'by_city': matched.groupby('city_code').size().to_dict(),
                'missing_by_city': joined[joined['_merge'] == 'left_only'].groupby('city_code').size().to_dict(),
                'within_5339': bool(box(139, 53 * 2 / 3, 140, 54 * 2 / 3).covers(cities.geometry.union_all()))},
        'boundary_all': geometry_profile(boundary), 'stations_all': geometry_profile(stations),
        'stations_buffer': {'midpoint_rows': len(nearby), 'allowed_rows': len(candidates),
                            'excluded_by_code': int((~allowed).sum()),
                            'distinct_midpoint_coordinates': int(candidates.midpoint_wkb.nunique()),
                            'code_counts': {f'{a}/{b}': int(n) for (a,b),n in code_counts.items()},
                            'group_code_present': any(c in stations for c in ['N02_005c','N02_005g'])},
        'limits': ['No roads, route distances, age rates or correlations computed.',
                   'N03 boundary date difference and imputation method remain unconfirmed.',
                   'Coordinate duplicate counts do not define station groups.'],
    }
    # Keep row-level audit flags private, with no age counts copied into this table.
    joined[['KEY_CODE', 'city_code', 'HTKSYORI', 'HTKSAKI', 'GASSAN', '_merge']].to_csv(CACHE / 'mesh-audit.csv', index=False)
    candidates.drop(columns='midpoint_wkb').to_parquet(CACHE / 'station-candidates.parquet', index=False)
    (CACHE / 'input-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['aoi', 'population_aoi', 'secrecy_links_all', 'stations_buffer']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
