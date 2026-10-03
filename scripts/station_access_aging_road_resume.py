"""Validate saved footers offline; --fetch explicitly resumes missing metadata only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
from datetime import datetime, timezone
import pyarrow.parquet as pq
from station_access_aging_road_footers import CACHE, RELEASE, BBOX, RangeReader, footer_length, candidate_groups, safe_error_reason

RESUME_BUDGET = {'body_bytes': 512 * 1024**2, 'requests': 254, 'seconds': 600, 'footer_bytes': 8 * 1024**2}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_saved(inventory_path, previous_dir):
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    previous = json.loads((previous_dir / 'report.json').read_text(encoding='utf-8'))
    if not inventory['complete'] or inventory['release'] != RELEASE or previous['release'] != RELEASE:
        raise ValueError('Inventory/release mismatch')
    if previous['inventory_sha256'] != digest(inventory_path) or previous['bbox'] != list(BBOX):
        raise ValueError('Inventory hash or AOI mismatch')
    objects, files = inventory['objects'], previous['files']
    if len(files) > len(objects) or len({o['key'] for o in objects}) != len(objects):
        raise ValueError('Invalid inventory cardinality')
    expected = {f'{i:03d}.footer' for i in range(len(files))}
    if {p.name for p in previous_dir.glob('*.footer')} != expected:
        raise ValueError('Unrecorded or missing footer; manual inspection required')
    reused = []
    for i, record in enumerate(files):
        path = previous_dir / f'{i:03d}.footer'
        if record['key'] != objects[i]['key'] or digest(path) != record['footer_sha256']:
            raise ValueError('Saved footer identity/hash mismatch')
        body = path.read_bytes()
        length = footer_length(body[-8:], objects[i]['bytes'])
        if body[:4] != b'PAR1' or len(body) != length + 12 or length != record['footer_bytes']:
            raise ValueError('Invalid saved footer envelope')
        metadata = pq.read_metadata(io.BytesIO(body))
        if metadata.num_row_groups != record['row_groups']:
            raise ValueError('Saved metadata mismatch')
        reused.append(dict(record, candidates=candidate_groups(metadata), reused=True,
                           saved_file=f'road-footers/{i:03d}.footer'))
    return objects, reused


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    inventory_path = CACHE / 'road-inventory/inventory.json'
    previous_dir = CACHE / 'road-footers'
    objects, reused = validate_saved(inventory_path, previous_dir)
    pending = len(objects) - len(reused)
    plan = {'reused_files': len(reused), 'pending_files': pending, 'budget': RESUME_BUDGET,
            'minimum_remaining_requests': pending * 2, 'network_requested': args.fetch}
    print(json.dumps(plan))
    if not args.fetch:
        return
    if pending * 2 > RESUME_BUDGET['requests']:
        raise ValueError('Pending scope exceeds approved request budget')
    output = CACHE / 'road-footers-resume-01'
    if output.exists():
        raise ValueError('Resume output already exists; do not repeat')
    output.mkdir()
    report = {'release': RELEASE, 'bbox': BBOX, 'budget': RESUME_BUDGET, 'complete': False,
              'started_utc': datetime.now(timezone.utc).isoformat(), 'requests': 0, 'body_bytes': 0,
              'inventory_sha256': digest(inventory_path), 'previous_report_sha256': digest(previous_dir / 'report.json'),
              'script_sha256': digest(__file__),
              'reader_script_sha256': digest(Path(__file__).with_name('station_access_aging_road_footers.py')),
              'reused_files': len(reused), 'files': reused}
    reader = RangeReader(report, RESUME_BUDGET)
    try:
        for i in range(len(reused), len(objects)):
            obj = objects[i]
            report['pending_file_index'], report['stage'] = i, 'trailer'
            tail = reader.get(obj, obj['bytes'] - 8, obj['bytes'] - 1)
            report['stage'] = 'validate_trailer'
            length = footer_length(tail, obj['bytes'])
            report['pending_footer_bytes'], report['stage'] = length, 'footer'
            footer = reader.get(obj, obj['bytes'] - 8 - length, obj['bytes'] - 9)
            report['stage'] = 'parse_and_save'
            envelope = b'PAR1' + footer + tail
            metadata = pq.read_metadata(io.BytesIO(envelope))
            path = output / f'{i:03d}.footer'
            path.write_bytes(envelope)
            report['files'].append({'key': obj['key'], 'footer_bytes': length, 'footer_sha256': digest(path),
                'schema': str(metadata.schema), 'row_groups': metadata.num_row_groups,
                'candidates': candidate_groups(metadata), 'reused': False,
                'saved_file': f'road-footers-resume-01/{i:03d}.footer'})
        report['complete'], report['stage'] = True, 'complete'
    except Exception as exc:
        report['error_type'], report['error_reason'] = type(exc).__name__, safe_error_reason(exc)
        raise RuntimeError('Resume incomplete; inspect report; no automatic retry') from None
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - reader.started, 3)
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (output / 'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('complete','requests','body_bytes','elapsed_seconds')}))


if __name__ == '__main__':
    main()
