"""Small OSMnx 2.1.1 tutorial with bounded transport and replayable responses.

The private OSMnx transport hook is version-pinned and scoped to one synchronous
call. Do not call this helper concurrently: OSMnx settings are process-global.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch
import copy
import platform
import pandas as pd
import json
import time
import uuid
import geopandas as gpd
import osmnx as ox
from osmnx import _overpass
import requests
from shapely.geometry import box
from .aoi import load_aoi, project_root, validate_aoi

TAG_KEYS = ('amenity','shop','tourism','leisure','office','craft','healthcare','historic')
ENDPOINT = 'https://overpass-api.de/api'
KEEP_TAGS = ('name', *TAG_KEYS, 'brand','operator','addr:housenumber','addr:street',
    'addr:city','addr:postcode','phone','contact:phone','website','contact:website',
    'opening_hours','cafe')
RELATED = [('amenity',v) for v in ('cafe','internet_cafe','restaurant','fast_food','ice_cream','bar','pub')] + [('shop','coffee'),('cafe','yes')]

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def poi_tags():
    return dict.fromkeys(TAG_KEYS, True)

def _validate_response(data):
    if not isinstance(data,dict) or not isinstance(data.get('elements'),list) or 'remark' in data:
        raise ValueError('Incomplete/error Overpass response; not cached.')

def _bounded_download(query):
    """One anonymous POST, no retries; no environmental auth/netrc or cookies."""
    with requests.Session() as client:
        client.trust_env = False
        client.headers['User-Agent'] = 'geoai-open-lab/0.1 (https://github.com/isshiki/geoai-open-lab)'
        status = client.get(ENDPOINT+'/status', timeout=(10,20))
        status.raise_for_status()
        if 'available now' not in status.text:
            raise RuntimeError('No available Overpass slot; retry manually later.')
        started = utc_now()
        clock = time.monotonic()
        with client.post(ENDPOINT+'/interpreter', data={'data':query},
                         timeout=(10,90), stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 64*1024*1024 or time.monotonic()-clock > 120:
                    raise RuntimeError('Overpass response exceeded tutorial resource guardrail.')
                chunks.append(chunk)
        data = json.loads(b''.join(chunks))
        _validate_response(data)
        return data, {'retrieval_start_utc':started,'retrieval_end_utc':utc_now(),
                      'download_seconds':time.monotonic()-clock,'response_body_bytes':size}

def _cached_response(root, query, refresh=False):
    key = sha256((ENDPOINT+'\n'+query).encode()).hexdigest()
    folder = root/'data/cache/osm'; folder.mkdir(parents=True,exist_ok=True)
    path = folder/(key+'.json')
    if path.exists() and not refresh:
        record = json.loads(path.read_text(encoding='utf-8'))
        if record['query'] != query or record['endpoint'] != ENDPOINT:
            raise ValueError('Cache query/endpoint mismatch.')
        _validate_response(record['response'])
        return record, path, True
    data, timing = _bounded_download(query)
    record = {'query':query,'endpoint':ENDPOINT,'response':data,**timing}
    # A successful refresh gets a new response archive; do not overwrite old evidence.
    if path.exists():
        path = folder/(key+'-'+uuid.uuid4().hex[:8]+'.json')
    path.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
    return record, path, False

def normalize_osm_features(gdf, bbox):
    """Keep original geometry; use its representative point, then inclusive AOI.

    Counts describe OSMnx output, after its own geometry repair/filtering.
    Unsupported lines and collections are recorded, never silently pointified.
    """
    validate_aoi(bbox,bbox['country'])
    if gdf.crs is None or gdf.crs.to_epsg()!=4326:
        raise ValueError('Expected EPSG:4326 features.')
    if gdf.index.nlevels != 2 or gdf.index.has_duplicates:
        raise ValueError('Expected unique (osm_type, osm_id) index.')
    data=gdf.copy()
    data.index=data.index.set_names(['osm_type','osm_id'])
    data=data.reset_index()
    if not data.osm_type.isin(['node','way','relation']).all():
        raise ValueError('Unknown OSM element type.')
    if data.osm_id.isna().any() or not all(isinstance(v,int) and v>0 for v in data.osm_id.tolist()):
        raise ValueError('OSM IDs must be positive integers.')
    counts={'duplicate_osm_keys':0,'osmnx_features':len(data),'null_geometry':int(data.geometry.isna().sum()),
        'empty_geometry':int(data.geometry.is_empty.sum())}
    valid=~data.geometry.isna() & ~data.geometry.is_empty
    counts['invalid_geometry']=int((valid & ~data.geometry.is_valid).sum())
    valid &= data.geometry.is_valid
    supported=data.geometry.geom_type.isin(['Point','Polygon','MultiPolygon'])
    counts['unsupported_geometry']=int((valid & ~supported).sum())
    counts['unsupported_geometry_types']=dict(Counter(data.loc[valid & ~supported].geometry.geom_type))
    data=data.loc[valid & supported].copy()
    counts['geometry_accepted']=len(data)
    rep=data.geometry.representative_point()
    region=box(bbox['west'],bbox['south'],bbox['east'],bbox['north'])
    inside=pd.Series([region.covers(p) for p in rep], index=data.index, dtype=bool)
    counts['representative_point_outside']=int((~inside).sum())
    data['longitude']=rep.x;data['latitude']=rep.y
    # Surface areas are descriptive checks, never a hidden area filter.
    surfaces=data.loc[data.geometry.geom_type.isin(['Polygon','MultiPolygon'])]
    areas=surfaces.to_crs(32654).geometry.area
    counts['surface_area_m2']={'count':len(areas),'max':float(areas.max()) if len(areas) else None,
        'over_aoi_area':int((areas>gpd.GeoSeries([region],crs=4326).to_crs(32654).area.iloc[0]).sum())}
    data=data.loc[inside].copy()
    for tag in KEEP_TAGS:
        if tag not in data: data[tag]=None
    data=data[['osm_type','osm_id','geometry','longitude','latitude',*KEEP_TAGS]]
    data=data.sort_values(['osm_type','osm_id']).reset_index(drop=True)
    counts['final_count']=len(data)
    counts['final_representative_point_outside']=int((~data.longitude.between(bbox['west'],bbox['east']) | ~data.latitude.between(bbox['south'],bbox['north'])).sum())
    return data,counts

def _relation_audit(raw, gdf, final):
    matched={e['id']:e for e in raw['elements'] if e['type']=='relation' and any(k in e.get('tags',{}) for k in TAG_KEYS)}
    converted=set(gdf.index.get_level_values(1)[gdf.index.get_level_values(0)=='relation'])
    accepted=set(final.loc[final.osm_type=='relation','osm_id'])
    unsupported={i for i,e in matched.items() if e.get('tags',{}).get('type') not in ('multipolygon','boundary')}
    return {'raw_tag_matching':len(matched),'raw_relation_types':dict(Counter(e.get('tags',{}).get('type','<missing>') for e in matched.values())),
        'osmnx_geometry_and_spatial_filter':len(set(matched)&converted),
        'final_accepted':len(set(matched)&accepted),
        'unsupported_type':len(unsupported),
        'absent_after_osmnx':len(set(matched)-converted),
        'supported_but_absent_reason_unresolved':len(set(matched)-converted-unsupported),
        'not_finally_accepted':len(set(matched)-accepted)}

def fetch_osm_pois(*, bbox, root=None, refresh=False):
    """Fetch once with OSMnx or replay cached JSON; return normalized GeoDataFrame.

    OSMnx 2.1.1 builds queries/geometries. A bounded transport replaces only its
    recursive retry path. Raw response is cached before geometry conversion.
    """
    if ox.__version__!='2.1.1': raise RuntimeError('This experiment requires OSMnx 2.1.1.')
    validate_aoi(bbox,bbox['country']);root=project_root(root)
    region=box(bbox['west'],bbox['south'],bbox['east'],bbox['north'])
    if gpd.GeoSeries([region],crs=4326).to_crs(32654).area.iloc[0]>4_000_000:
        raise ValueError('Tutorial restricted to a small AOI (<=4 km2).')
    calls=[];started=utc_now();clock=time.perf_counter()
    def request(data):
        if calls: raise RuntimeError('Unexpected split query; no second request sent.')
        record,path,hit=_cached_response(root,data['data'],refresh)
        calls.append((record,path,hit));return copy.deepcopy(record['response'])
    settings={'overpass_settings':'[out:json][timeout:60][maxsize:67108864]',
        'overpass_url':ENDPOINT,'cache_only_mode':False,'log_console':False,'log_file':False,
        'default_crs':'epsg:4326'}
    old={key:getattr(ox.settings,key) for key in settings}
    try:
        for key,value in settings.items():setattr(ox.settings,key,value)
        with patch.object(_overpass,'_overpass_request',side_effect=request):
            gdf=ox.features.features_from_bbox((bbox['west'],bbox['south'],bbox['east'],bbox['north']),poi_tags())
    finally:
        for key,value in old.items():setattr(ox.settings,key,value)
    result,checks=normalize_osm_features(gdf,bbox)
    record,path,hit=calls[0]
    raw=record['response']
    result.attrs['osm_provenance']={'provider':'OpenStreetMap','method':'OSMnx features_from_bbox + bounded public Overpass transport',
        'endpoint':ENDPOINT+'/interpreter','osmnx_version':ox.__version__,
        'retrieval_start_utc':record['retrieval_start_utc'],'retrieval_end_utc':record['retrieval_end_utc'],
        'osm_base_timestamp':raw.get('osm3s',{}).get('timestamp_osm_base'),
        'processing_start_utc':started,'processing_end_utc':utc_now(),'processing_seconds':time.perf_counter()-clock,
        'download_seconds':record['download_seconds'],'response_body_bytes':record['response_body_bytes'],
        'cache_hit':hit,'raw_cache':str(path.relative_to(root)),'raw_cache_sha256':sha256(path.read_bytes()).hexdigest(),
        'raw_cache_bytes':path.stat().st_size,'query':record['query'],'tag_keys':list(TAG_KEYS),
        'aoi':dict(bbox),'crs':'EPSG:4326','checks':checks,'relations':_relation_audit(raw,gdf,result),
        'raw_tag_matching_elements':sum(any(k in e.get('tags',{}) for k in TAG_KEYS) for e in raw['elements']),
        'cafe_yes_scope':'Only candidates retrieved by the eight-key OR query; no cafe=yes-only query',
        'aoi_rule':'Representative point inside inclusive AOI; original geometry not clipped'}
    return result

def filter_osm_cafes(places):
    """Exact amenity=cafe; do not expand using cafe=yes or shop=coffee."""
    return places.loc[places.amenity.eq('cafe')].copy()

def summarize_osm(places):
    def counts(series):return {str(k):int(v) for k,v in series.dropna().value_counts().items()}
    related=[{'key':k,'value':v,'count':int(places[k].eq(v).sum())} for k,v in RELATED if places[k].eq(v).any()]
    return {'row_count':len(places),'osm_types':counts(places.osm_type),
        'geometry_types':counts(places.geometry.geom_type),'cafe_count':len(filter_osm_cafes(places)),
        'cafe_definition':"amenity == 'cafe'",'tag_values':{k:counts(places[k]) for k in TAG_KEYS},
        'related_tags':related,'cafe_yes_within_candidates':int(places['cafe'].eq('yes').sum())}

def save_osm_results(places, *, root=None):
    """Save normalized/cafe GeoParquet and manifest under ignored data/raw/osm."""
    root=project_root(root)
    if 'osm_provenance' not in places.attrs:raise ValueError('Missing acquisition provenance.')
    manifest=dict(places.attrs['osm_provenance'])
    if len(places)!=manifest['checks']['final_count']:raise ValueError('Acquired frame was modified.')
    run=root/'data/raw/osm'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    run.mkdir(parents=True)
    outputs={}
    for name,frame in [('places',places),('cafes',filter_osm_cafes(places))]:
        path=run/(name+'.parquet');frame=frame.copy();frame.attrs={};frame.to_parquet(path,index=False)
        outputs[path.name]={'sha256':sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
    manifest.update(summary=summarize_osm(places),outputs=outputs,
        python_version=platform.python_version(),
        command='uv run --locked --group notebooks --group osm jupyter nbconvert --execute --to notebook notebooks/03_openstreetmap_poi.ipynb',
        versions={p:version(p) for p in ['osmnx','geopandas','shapely','pyarrow','pandas']},
        attribution='© OpenStreetMap contributors; ODbL 1.0',
        references=['https://www.openstreetmap.org/copyright','https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL',
        'https://github.com/gboeing/osmnx/tree/v2.1.1/osmnx'])
    paths=['src/geoai_open_lab/openstreetmap.py','src/geoai_open_lab/aoi.py','configs/aoi/kichijoji.toml',
           'notebooks/03_openstreetmap_poi.ipynb','pyproject.toml','uv.lock']
    manifest['source_sha256']={p:sha256((root/p).read_bytes()).hexdigest() for p in paths}
    (run/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return run
