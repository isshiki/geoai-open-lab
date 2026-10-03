"""Offline diagnosis of missing road references; never downloads data."""
import io
import json
import math
from datetime import datetime, timezone
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pyproj import Geod
import shapely
from station_access_aging_road_body import OUT, CACHE, BBOX, groups, digest, save_json
from station_access_aging_road_plan import COLUMNS, column_ranges, merge_ranges

GEOD=Geod(ellps='WGS84')


def geodetic_at(line, at):
    if not math.isfinite(at) or not 0<=at<=1:raise ValueError('Invalid at')
    coords=list(line.coords)
    legs=[GEOD.inv(*a[:2],*b[:2]) for a,b in zip(coords,coords[1:])]
    total=sum(x[2] for x in legs)
    if total<=0:raise ValueError('Zero length')
    target=at*total;acc=0
    for i,(azimuth,_,length) in enumerate(legs):
        if target<=acc+length or i==len(legs)-1:
            lon,lat,_=GEOD.fwd(*coords[i][:2],azimuth,max(0,min(length,target-acc)))
            return shapely.Point(lon,lat)
        acc+=length


def matches(metadata,index,envelopes):
    g=metadata.row_group(index);cols={g.column(i).path_in_schema:g.column(i) for i in range(g.num_columns)}
    for west,south,east,north in envelopes:
        excluded=False
        for name,which,bound,upper in [('bbox.xmin','min',east,True),('bbox.xmax','max',west,False),('bbox.ymin','min',north,True),('bbox.ymax','max',south,False)]:
            c=cols.get(name);s=c.statistics if c else None
            if s is None or not s.has_min_max or s.null_count!=0:continue
            value=getattr(s,which)
            if not isinstance(value,(int,float)) or not math.isfinite(value):continue
            if (value>bound if upper else value<bound):excluded=True
        if not excluded:return True
    return False


def main():
    plan_path=CACHE/'road-body-plan.json';plan=json.loads(plan_path.read_text())
    acq=json.loads((OUT/'acquisition.json').read_text())
    if not acq['complete'] or acq['plan_sha256']!=digest(plan_path):raise ValueError('Acquisition mismatch')
    rows=pq.read_table(OUT/'segments.parquet',columns=['id','geometry','connectors','prohibited_transitions']).to_pylist()
    ids=set(pq.read_table(OUT/'connectors.parquet',columns=['id'])['id'].to_pylist());sids={r['id'] for r in rows};bounds=shapely.box(*BBOX)
    missing=[];tids=set()
    for row in rows:
        for c in row['connectors'] or []:
            if c['connector_id'] not in ids:
                line=shapely.from_wkb(row['geometry']); point=geodetic_at(line,c['at'])
                missing.append({'id':c['connector_id'],'owner':row['id'],'at':c['at'],'estimated_lon':point.x,'estimated_lat':point.y,
                                'estimated_outside_bbox':not bounds.covers(point),'owner_bounds':list(line.bounds)})
        for rule in row['prohibited_transitions'] or []:
            for c in rule['sequence'] or []:
                if c.get('segment_id') and c['segment_id'] not in sids:tids.add(c['segment_id'])
    found=[]
    for table in groups(plan,'segment',acq):
        selected=table.filter(pc.is_in(table['id'],value_set=pa.array(sorted(tids),type=pa.string())))
        for row in selected.to_pylist():
            geometry=shapely.from_wkb(row['geometry'],on_invalid='ignore')
            found.append({'id':row['id'],'subtype':row['subtype'],'valid':geometry is not None and geometry.is_valid,
                          'intersects_bbox':bool(geometry is not None and geometry.intersects(bounds))})
    footer_report=json.loads((CACHE/'road-footers-resume-01/report.json').read_text())
    inventory=json.loads((CACHE/'road-inventory/inventory.json').read_text())
    if digest(CACHE/'road-inventory/inventory.json')!=footer_report['inventory_sha256']:raise ValueError('Inventory hash mismatch')
    objects={o['key']:o for o in inventory['objects']}
    oldgroups={f['key']:set(f['row_groups']) for f in plan['files'] if f['kind']=='connector'}
    # Whole owner-line bounds rather than uncertain interpolated points determine candidates.
    envelopes=[m['owner_bounds'] for m in missing];extras=[]
    for f in footer_report['files']:
        if '/type=connector/' not in f['key']:continue
        file=CACHE/f['saved_file']
        if digest(file)!=f['footer_sha256']:raise ValueError('Footer checksum mismatch')
        meta=pq.read_metadata(io.BytesIO(file.read_bytes()))
        indices=[i for i in range(meta.num_row_groups) if i not in oldgroups.get(f['key'],set()) and matches(meta,i,envelopes)]
        if not indices:continue
        obj=objects[f['key']]
        ranges=merge_ranges(column_ranges(meta,indices,COLUMNS['connector'],obj['bytes']-f['footer_bytes']-8))
        extras.append({'key':f['key'],'row_groups':indices,'ranges':ranges,'etag':obj['etag'],
                       'range_bytes':sum(b-a+1 for a,b in ranges),'requests':len(ranges)})
    summary={'missing_connector_ids':len({m['id'] for m in missing}),'estimated_positions_outside_bbox':sum(m['estimated_outside_bbox'] for m in missing),
             'transition_ids_missing_normalized':len(tids),'transition_ids_found_in_cached_candidates':len(found),
             'found_transition_rows_outside_bbox':sum(not r['intersects_bbox'] for r in found),
             'extra_connector_files':len(extras),'extra_connector_row_groups':sum(len(e['row_groups']) for e in extras),
             'extra_range_requests':sum(e['requests'] for e in extras),'extra_range_bytes':sum(e['range_bytes'] for e in extras)}
    save_json(OUT/'reference-diagnosis.json',{'audited_utc':datetime.now(timezone.utc).isoformat(),'summary':summary,
              'missing_connectors':missing,'cached_transition_rows':found,'extra_connector_candidates':extras,
              'script_sha256':digest(__file__),'plan_sha256':digest(plan_path),
              'limitations':['Interpolated connector coordinates are estimates, not retrieved connector records.',
                             'Owner-line envelopes are a search scope, not proof the missing IDs exist there.',
                             'No network access or normalized-result modification.']})
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
