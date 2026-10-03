"""Offline column/range plan using cached metadata; does not fetch data pages."""
import hashlib
import io
import json
from pathlib import Path
import pyarrow.parquet as pq
from station_access_aging_road_footers import CACHE, BBOX, RELEASE, candidate_groups

COLUMNS = {
 'segment': ['id','version','sources','geometry','bbox','subtype','class','subclass',
             'subclass_rules','connectors','road_surface','road_flags','level_rules',
             'access_restrictions','prohibited_transitions'],
 'connector': ['id','version','sources','geometry','bbox'],
}


def merge_ranges(ranges, gap=4096):
    """Inclusive ranges, merged with bounded optional gap overfetch."""
    result=[]
    for start,end in sorted(ranges):
        if start<4 or end<start:
            raise ValueError('Invalid column range')
        if result and start<=result[-1][1]+1+gap:
            result[-1][1]=max(result[-1][1],end)
        else:
            result.append([start,end])
    return result


def column_ranges(metadata, indices, columns, data_end):
    available=set(metadata.schema.to_arrow_schema().names)
    if not set(columns)<=available:
        raise ValueError('Missing requested columns')
    result=[]
    for index in indices:
        group=metadata.row_group(index)
        for j in range(group.num_columns):
            col=group.column(j)
            if col.path_in_schema.split('.')[0] not in columns:
                continue
            offsets=[v for v in (col.dictionary_page_offset,col.data_page_offset) if v is not None and v>0]
            if not offsets or col.total_compressed_size<=0:
                raise ValueError('Invalid page offsets/size')
            start=min(offsets);end=start+col.total_compressed_size-1
            if start<4 or end>=data_end:
                raise ValueError('Column outside data section')
            result.append((start,end))
    return result


def main():
    report_path=CACHE/'road-footers-resume-01/report.json'
    inventory_path=CACHE/'road-inventory/inventory.json'
    r=json.loads(report_path.read_text()); inventory=json.loads(inventory_path.read_text())
    if not r['complete'] or r['release']!=RELEASE or r['bbox']!=list(BBOX):
        raise ValueError('Incomplete metadata or scope mismatch')
    if hashlib.sha256(inventory_path.read_bytes()).hexdigest()!=r['inventory_sha256']:
        raise ValueError('Inventory checksum mismatch')
    objects={o['key']:o for o in inventory['objects']}
    if len(r['files'])!=len(objects) or {f['key'] for f in r['files']}!=set(objects):
        raise ValueError('Metadata inventory coverage mismatch')
    plan={'release':RELEASE,'bbox':BBOX,'columns':COLUMNS,'merge_gap_bytes':4096,
          'metadata_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'network_requested':False,'files':[],'summary':{}}
    for f in r['files']:
        data=(CACHE/f['saved_file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=f['footer_sha256']:
            raise ValueError('Footer checksum mismatch')
        metadata=pq.read_metadata(io.BytesIO(data)); groups=candidate_groups(metadata)
        if groups!=f['candidates']:
            raise ValueError('Candidate selection changed')
        if not groups:
            continue
        kind='segment' if '/type=segment/' in f['key'] else 'connector'
        obj=objects[f['key']]
        ranges=column_ranges(metadata,[g['index'] for g in groups],COLUMNS[kind],obj['bytes']-f['footer_bytes']-8)
        merged=merge_ranges(ranges)
        plan['files'].append({'key':f['key'],'kind':kind,'etag':obj['etag'],'file_bytes':obj['bytes'],
            'saved_footer':f['saved_file'],'row_groups':[g['index'] for g in groups],
            'column_chunks':len(ranges),'selected_column_bytes':sum(b-a+1 for a,b in ranges),
            'requests':len(merged),'range_bytes':sum(b-a+1 for a,b in merged),'ranges':merged})
    for kind in COLUMNS:
        files=[f for f in plan['files'] if f['kind']==kind]
        plan['summary'][kind]={k:sum(f[k] for f in files) for k in ['column_chunks','selected_column_bytes','requests','range_bytes']}
        plan['summary'][kind]['files']=len(files)
    (CACHE/'road-body-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps(plan['summary'],indent=2))

if __name__=='__main__':main()
