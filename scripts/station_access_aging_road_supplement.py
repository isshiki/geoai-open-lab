"""Bounded connector supplement plus offline reference reconciliation."""
import argparse
import io
import json
import time
from datetime import datetime, timezone
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.ops import transform
from station_access_aging_road_body import OUT as BODY, CACHE, LocalRanges, digest, groups, save_json
from station_access_aging_road_footers import RangeReader, safe_error_reason, BBOX
from station_access_aging_road_plan import COLUMNS, column_ranges, merge_ranges
from station_access_aging_road_references import GEOD, geodetic_at

OUT=CACHE/'road-reference-supplement'
BUDGET={'body_bytes':16*1024**2,'requests':2,'seconds':120}
STORAGE=32*1024**2


def check_scope(extras):
    if len(extras)!=1 or sum(len(f['row_groups']) for f in extras)!=2 or sum(len(f['ranges']) for f in extras)!=2:
        raise ValueError('Unapproved scope')
    if sum(b-a+1 for f in extras for a,b in f['ranges'])>BUDGET['body_bytes']:
        raise ValueError('Body budget exceeded')


def select_ids(table, ids):
    selected=table.filter(pc.is_in(table['id'],value_set=pa.array(sorted(ids),type=pa.string())))
    values=selected['id'].to_pylist()
    if len(set(values))!=len(values):raise ValueError('Duplicate supplemental IDs')
    return selected


def write_table(table,name):
    sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd');data=sink.getvalue()
    old=(OUT/name).stat().st_size if (OUT/name).exists() else 0
    used=sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    if used-old+len(data)+1024**2>STORAGE:raise ValueError('Storage budget exceeded')
    (OUT/name).write_bytes(data.to_pybytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    diagnosis_path=BODY/'reference-diagnosis.json';d=json.loads(diagnosis_path.read_text())
    plan_path=CACHE/'road-body-plan.json';plan=json.loads(plan_path.read_text())
    if d['plan_sha256']!=digest(plan_path):raise ValueError('Diagnosis/plan mismatch')
    extras=d['extra_connector_candidates'];check_scope(extras)
    inventory_path=CACHE/'road-inventory/inventory.json';inventory=json.loads(inventory_path.read_text())
    footer_report=json.loads((CACHE/'road-footers-resume-01/report.json').read_text())
    if digest(inventory_path)!=footer_report['inventory_sha256']:raise ValueError('Inventory changed')
    objects={f['key']:f for f in inventory['objects']};footers={f['key']:f for f in footer_report['files']}
    extra=extras[0];obj=objects[extra['key']];fr=footers[extra['key']];envelope=(CACHE/fr['saved_file']).read_bytes()
    if digest(CACHE/fr['saved_file'])!=fr['footer_sha256'] or extra['etag']!=obj['etag']:raise ValueError('Metadata changed')
    metadata=pq.read_metadata(io.BytesIO(envelope))
    expected=merge_ranges(column_ranges(metadata,extra['row_groups'],COLUMNS['connector'],obj['bytes']-fr['footer_bytes']-8))
    if expected!=extra['ranges']:raise ValueError('Range plan changed')
    source_hashes={n:digest(BODY/n) for n in ['segments.parquet','connectors.parquet','audit.json']}
    if args.fetch:
        if OUT.exists():raise ValueError('Supplement exists; use offline mode, no automatic refetch')
        OUT.mkdir()
        report={'diagnosis_sha256':digest(diagnosis_path),'budget':BUDGET,'storage_limit':STORAGE,
                'source_hashes':source_hashes,'script_sha256':digest(__file__),
                'started_utc':datetime.now(timezone.utc).isoformat(),'complete':False,'requests':0,'body_bytes':0,'parts':[]}
        reader=RangeReader(report,BUDGET)
        try:
            for i,(a,b) in enumerate(extra['ranges']):
                data=reader.get(obj,a,b);path=OUT/f'{i:02d}.bin';path.write_bytes(data)
                report['parts'].append({'file':path.name,'start':a,'end':b,'sha256':digest(path)})
            report['complete']=True
        except Exception as exc:
            report['error_type']=type(exc).__name__;report['error_reason']=safe_error_reason(exc)
            raise RuntimeError('Supplement incomplete; no automatic retry') from None
        finally:
            report['elapsed_seconds']=round(time.monotonic()-reader.started,3)
            report['finished_utc']=datetime.now(timezone.utc).isoformat()
            save_json(OUT/'acquisition.json',report)
    report=json.loads((OUT/'acquisition.json').read_text())
    if not report['complete'] or report['diagnosis_sha256']!=digest(diagnosis_path) or report['source_hashes']!=source_hashes:raise ValueError('Acquisition/source mismatch')
    pieces=[(0,b'PAR1'),(obj['bytes']-len(envelope)+4,envelope[4:])]
    for part in report['parts']:
        path=OUT/part['file']
        if digest(path)!=part['sha256']:raise ValueError('Range checksum mismatch')
        pieces.append((part['start'],path.read_bytes()))
    pqfile=pq.ParquetFile(LocalRanges(obj['bytes'],pieces),metadata=metadata,pre_buffer=False,buffer_size=0)
    table=pqfile.read_row_groups(extra['row_groups'],columns=COLUMNS['connector'],use_threads=False)
    missing={m['id'] for m in d['missing_connectors']};added=select_ids(table,missing)
    target_segments={r['id'] for r in d['cached_transition_rows']}
    acquisition=json.loads((BODY/'acquisition.json').read_text())
    if not acquisition['complete'] or acquisition['plan_sha256']!=digest(plan_path):raise ValueError('Original acquisition mismatch')
    support=pa.concat_tables([select_ids(t,target_segments) for t in groups(plan,'segment',acquisition)])
    support=select_ids(support,target_segments)
    write_table(added,'connectors.parquet');write_table(support,'reference-segments.parquet')
    original=pq.read_table(BODY/'segments.parquet',columns=['id','geometry','connectors']).to_pylist()
    owner={r['id']:r for r in original};newrows=added.to_pylist()
    points={r['id']:shapely.from_wkb(r['geometry']) for r in newrows}
    project=Transformer.from_crs(4326,6677,always_xy=True).transform
    errors=[];distance=[]
    for m in d['missing_connectors']:
        if m['id'] not in points:continue
        point=points[m['id']];line=shapely.from_wkb(owner[m['owner']]['geometry'])
        if point.geom_type!='Point' or not point.is_valid or point.is_empty:raise ValueError('Invalid connector geometry')
        estimated=geodetic_at(line,m['at'])
        errors.append(GEOD.inv(estimated.x,estimated.y,point.x,point.y)[2])
        distance.append(transform(project,line).distance(transform(project,point)))
    all_connector_ids=set(pq.read_table(BODY/'connectors.parquet',columns=['id'])['id'].to_pylist())|set(points)
    support_refs={c['connector_id'] for r in support.to_pylist() for c in r['connectors'] or []}
    if any(digest(BODY/n)!=h for n,h in source_hashes.items()):raise ValueError('Original output modified')
    result={'audited_utc':datetime.now(timezone.utc).isoformat(),'acquisition_sha256':digest(OUT/'acquisition.json'),
        'candidate_rows':len(table),'requested_connector_ids':len(missing),'matched_connector_ids':len(points),
        'remaining_original_connector_ids':len(missing-set(points)),
        'matched_reference_segments':len(support),'remaining_original_reference_segments':len(target_segments-set(support['id'].to_pylist())),
        'supplemental_points_outside_bbox':sum(not shapely.box(*BBOX).covers(p) for p in points.values()),
        'max_connector_line_distance_m':max(distance,default=None),'max_geodetic_at_error_m':max(errors,default=None),
        'support_segment_connector_ids_unresolved':len(support_refs-all_connector_ids),
        'original_outputs_unchanged':True,'normalized_bytes':{n:(OUT/n).stat().st_size for n in ['connectors.parquet','reference-segments.parquet']},
        'limitations':['Resolves original references only; no recursive network expansion.',
                      'Support segment is not added to analysis AOI. Walking rules and graph remain unvalidated.']}
    save_json(OUT/'audit.json',result)
    print(json.dumps({'acquisition':{k:report[k] for k in ['requests','body_bytes','elapsed_seconds','started_utc','finished_utc']},'audit':result}))

if __name__=='__main__':main()
