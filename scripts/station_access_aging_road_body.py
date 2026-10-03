"""Fetch the approved road column ranges, then audit saved data offline."""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.ops import transform
from station_access_aging_road_footers import CACHE, BBOX, RELEASE, RangeReader, safe_error_reason
from station_access_aging_road_plan import COLUMNS

OUT = CACHE / 'road-body'
LIMIT = {'body_bytes':160*1024**2, 'requests':120, 'seconds':600}
STORAGE = 512*1024**2


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LocalRanges(io.RawIOBase):
    """Virtual original file. Uncached byte reads fail; never fills holes with zeros."""
    def __init__(self, size, pieces):
        self.size, self.position = size, 0
        self.pieces = sorted(pieces)
        self.starts = [p[0] for p in self.pieces]
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self, offset, whence=0):
        position = offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if whence not in (0,1,2) or position<0: raise ValueError('Invalid seek')
        self.position=position
        return position
    def read(self, size=-1):
        end=self.size if size<0 else min(self.size,self.position+size)
        result=[]
        while self.position<end:
            index=bisect_right(self.starts,self.position)-1
            if index<0: raise ValueError('Read outside cached ranges')
            start,data=self.pieces[index]
            stop=min(end,start+len(data))
            if stop<=self.position: raise ValueError('Read outside cached ranges')
            result.append(data[self.position-start:stop-start]); self.position=stop
        return b''.join(result)
    def readinto(self,b):
        data=self.read(len(b)); b[:len(data)]=data; return len(data)


def save_json(path, value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temp.replace(path)


def usage():
    return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())


def fetch(plan, plan_path):
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=OUT/'acquisition.json'
    if manifest_path.exists():
        report=json.loads(manifest_path.read_text())
        if report['plan_sha256']!=digest(plan_path):raise ValueError('Plan changed')
    else:
        report={'plan_sha256':digest(plan_path),'release':RELEASE,'started_utc':datetime.now(timezone.utc).isoformat(),
                'script_sha256':digest(__file__),'budget':LIMIT,'storage_bytes_limit':STORAGE,
                'requests':0,'body_bytes':0,'elapsed_seconds':0,'parts':{},'complete':False}
    reader=RangeReader(report,dict(LIMIT,seconds=max(0,LIMIT['seconds']-report['elapsed_seconds'])))
    previous_elapsed=report['elapsed_seconds']
    try:
        for fi,f in enumerate(plan['files']):
            obj={'key':f['key'],'etag':f['etag'],'bytes':f['file_bytes']}
            for ri,(a,b) in enumerate(f['ranges']):
                name=f'{fi:02d}-{ri:03d}.bin';path=OUT/name
                if name in report['parts']:
                    if not path.exists() or digest(path)!=report['parts'][name]['sha256']:raise ValueError('Cached range mismatch')
                    continue
                if path.exists():raise ValueError('Unrecorded range file')
                if usage()+b-a+1+1024*1024>STORAGE:raise ValueError('Storage budget exhausted')
                report['pending_part']=name
                data=reader.get(obj,a,b)
                path.write_bytes(data)
                report['parts'][name]={'sha256':digest(path),'bytes':len(data),'start':a,'end':b}
                save_json(manifest_path,report)
        report['complete']=True
    except Exception as exc:
        report['error_type']=type(exc).__name__; report['error_reason']=safe_error_reason(exc)
        raise RuntimeError('Road range acquisition incomplete; inspect saved manifest') from None
    finally:
        report['elapsed_seconds']=previous_elapsed+round(time.monotonic()-reader.started,3)
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        save_json(manifest_path,report)
    print(json.dumps({k:report[k] for k in ('complete','requests','body_bytes','elapsed_seconds')}),flush=True)


def groups(plan,kind,acquisition):
    for fi,f in enumerate(plan['files']):
        if f['kind']!=kind:continue
        envelope=(CACHE/f['saved_footer']).read_bytes()
        metadata=pq.read_metadata(io.BytesIO(envelope))
        pieces=[(0,b'PAR1'),(f['file_bytes']-len(envelope)+4,envelope[4:])]
        for ri,(a,b) in enumerate(f['ranges']):
            name=f'{fi:02d}-{ri:03d}.bin';path=OUT/name
            if digest(path)!=acquisition['parts'][name]['sha256']:raise ValueError('Range checksum mismatch')
            pieces.append((a,path.read_bytes()))
        source=LocalRanges(f['file_bytes'],pieces)
        parquet=pq.ParquetFile(source,metadata=metadata,pre_buffer=False,buffer_size=0)
        for index in f['row_groups']:
            yield parquet.read_row_group(index,columns=COLUMNS[kind],use_threads=False)


def save_table(table,name):
    # Encode locally before writing so storage ceiling is checked before publication to disk.
    sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd')
    data=sink.getvalue()
    previous=(OUT/name).stat().st_size if (OUT/name).exists() else 0
    if usage()-previous+len(data)+1024*1024>STORAGE:raise ValueError('Storage budget exhausted')
    (OUT/name).write_bytes(data.to_pybytes())


def audit(plan,plan_path):
    acquisition=json.loads((OUT/'acquisition.json').read_text())
    if not acquisition['complete'] or acquisition['plan_sha256']!=digest(plan_path):raise ValueError('Incomplete acquisition or plan mismatch')
    bounds=shapely.box(*BBOX); kept=[]; counts=Counter()
    for table in groups(plan,'segment',acquisition):
        counts['candidate_segment_rows']+=len(table)
        road=table.filter(pc.equal(table['subtype'],'road'))
        counts['road_rows_before_geometry_filter']+=len(road)
        geoms=shapely.from_wkb(road['geometry'].to_pylist(),on_invalid='ignore')
        valid=~shapely.is_missing(geoms)&~shapely.is_empty(geoms)&shapely.is_valid(geoms)&(shapely.get_type_id(geoms)==1)
        counts['invalid_or_unsupported_road_geometry']+=int((~valid).sum())
        mask=valid&shapely.intersects(geoms,bounds)
        kept.append(road.filter(pa.array(mask)))
    roads=pa.concat_tables(kept);records=roads.to_pylist()
    ids=[r['id'] for r in records]
    counts['roads']=len(roads); counts['duplicate_segment_ids']=len(ids)-len(set(ids))
    if None in ids or counts['duplicate_segment_ids']:raise ValueError('Nonunique/missing segment ID')
    refs=set(); transition_refs=set();transition_segments=set();invalid_at=0
    for r in records:
        for c in r['connectors'] or []:
            if not c['connector_id'] or c['at'] is None or not 0<=c['at']<=1:invalid_at+=1
            if c['connector_id']:refs.add(c['connector_id'])
        for rule in r['prohibited_transitions'] or []:
            for c in rule['sequence'] or []:
                if c.get('connector_id'):transition_refs.add(c['connector_id'])
                if c.get('segment_id'):transition_segments.add(c['segment_id'])
    needed=refs|transition_refs; connectors=[]
    for table in groups(plan,'connector',acquisition):
        counts['candidate_connector_rows']+=len(table)
        connectors.append(table.filter(pc.is_in(table['id'],value_set=pa.array(sorted(needed),type=pa.string()))))
    connectors=pa.concat_tables(connectors); cr=connectors.to_pylist()
    cids=[r['id'] for r in cr];counts['duplicate_connector_ids']=len(cids)-len(set(cids))
    if None in cids or counts['duplicate_connector_ids']:raise ValueError('Nonunique/missing connector ID')
    cgeoms={r['id']:shapely.from_wkb(r['geometry'],on_invalid='ignore') for r in cr}
    validpoints={k:g for k,g in cgeoms.items() if g is not None and not g.is_empty and g.is_valid and g.geom_type=='Point'}
    project=Transformer.from_crs(4326,6677,always_xy=True).transform
    points={k:transform(project,g) for k,g in validpoints.items()}
    distances=[]
    for r in records:
        line=transform(project,shapely.from_wkb(r['geometry']))
        for c in r['connectors'] or []:
            if c['connector_id'] in points:distances.append(line.distance(points[c['connector_id']]))
    counts.update({'connectors':len(connectors),'required_connector_ids':len(refs),
        'missing_connector_ids':len(refs-set(cids)), 'invalid_connector_geometry':len(cgeoms)-len(validpoints),
        'missing_transition_connector_ids':len(transition_refs-set(cids)),
        'missing_transition_segment_ids':len(transition_segments-set(ids)),
        'invalid_connector_at_or_id':invalid_at,
        'connectors_outside_bbox':sum(not bounds.covers(g) for g in validpoints.values()),
        'connector_line_checks':len(distances),'connector_line_distance_over_1m':sum(d>1 for d in distances),
        'roads_with_access_restrictions':sum(bool(r['access_restrictions']) for r in records),
        'roads_with_prohibited_transitions':sum(bool(r['prohibited_transitions']) for r in records)})
    save_table(roads,'segments.parquet');save_table(connectors,'connectors.parquet')
    report={'audited_utc':datetime.now(timezone.utc).isoformat(),'release':RELEASE,'bbox':BBOX,
        'plan_sha256':digest(plan_path),'acquisition_sha256':digest(OUT/'acquisition.json'),
        'script_sha256':digest(__file__),'counts':dict(counts),
        'max_connector_line_distance_m':max(distances,default=None),
        'class_counts':dict(Counter(r['class'] for r in records)),
        'source_licenses':dict(Counter(s.get('license') or 'unspecified' for r in records for s in r['sources'] or [])),
        'normalized_bytes':{n:(OUT/n).stat().st_size for n in ['segments.parquet','connectors.parquet']},
        'limitations':['Not a walkable graph or an age/distance analysis.','1m is an audit tolerance, not an accessibility guarantee.',
            'Connector at-to-coordinate equality and all conditional restrictions remain unvalidated.','No automatic missing-reference download.']}
    save_json(OUT/'audit.json',report)
    print(json.dumps(report,ensure_ascii=True),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    plan_path=CACHE/'road-body-plan.json';plan=json.loads(plan_path.read_text())
    if plan['release']!=RELEASE or plan['bbox']!=list(BBOX) or plan['columns']!=COLUMNS:raise ValueError('Plan scope mismatch')
    if sum(f['range_bytes'] for f in plan['files'])>LIMIT['body_bytes'] or sum(f['requests'] for f in plan['files'])>LIMIT['requests']:raise ValueError('Plan exceeds budget')
    if args.fetch:fetch(plan,plan_path)
    audit(plan,plan_path)

if __name__=='__main__':main()
