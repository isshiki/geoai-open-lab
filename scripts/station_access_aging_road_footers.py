"""Inspect fixed-release Parquet footers only, after explicit --fetch approval."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import time
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import pyarrow.parquet as pq
from station_access_aging_road_inventory import ROOT, BASE, RELEASE, PREFIXES, NoRedirect

CACHE = ROOT / 'data/cache/station_access_aging'
BUDGET = {'body_bytes': 64 * 1024**2, 'requests': 320, 'seconds': 300, 'footer_bytes': 8 * 1024**2}
BBOX = (139.46886937455685, 35.614716614327996, 139.65092107448837, 35.767230073944035)


def safe_error_reason(exc):
    """Persist only fixed local diagnostics, never remote exception text."""
    allowed = {'Range request budget exhausted', 'Invalid Parquet trailer',
               'Footer exceeds file or budget', 'Range or object identity mismatch; body not read',
               'Time budget exceeded', 'Truncated range'}
    message = str(exc)
    return message if message in allowed else 'Details suppressed'


def footer_length(tail, size):
    if len(tail) != 8 or tail[4:] != b'PAR1':
        raise ValueError('Invalid Parquet trailer')
    length = int.from_bytes(tail[:4], 'little')
    if length <= 0 or length > BUDGET['footer_bytes'] or length + 12 > size:
        raise ValueError('Footer exceeds file or budget')
    return length


def candidate_groups(metadata):
    """Conservative bbox exclusion; missing statistics retain the row group."""
    west, south, east, north = BBOX
    groups = []
    for i in range(metadata.num_row_groups):
        group = metadata.row_group(i)
        cols = {group.column(j).path_in_schema: group.column(j) for j in range(group.num_columns)}
        constraints = [('bbox.xmin', 'min', east, True), ('bbox.xmax', 'max', west, False),
                       ('bbox.ymin', 'min', north, True), ('bbox.ymax', 'max', south, False)]
        excluded, missing = False, False
        for name, which, bound, upper in constraints:
            col = cols.get(name)
            stats = col.statistics if col else None
            if stats is None or not stats.has_min_max or stats.null_count != 0:
                missing = True
                continue
            value = getattr(stats, which)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                missing = True
                continue
            if (value > bound if upper else value < bound):
                excluded = True
        if not excluded:
            groups.append({'index': i, 'rows': group.num_rows,
                           'compressed_column_bytes': sum(c.total_compressed_size for c in cols.values()),
                           'missing_bbox_stats': missing})
    return groups


class RangeReader:
    def __init__(self, report, budget=None):
        self.budget = dict(BUDGET if budget is None else budget)
        self.report = report
        self.started = time.monotonic()
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, obj, start, end):
        count = end - start + 1
        remaining = self.budget['seconds'] - (time.monotonic() - self.started)
        if remaining <= 0 or self.report['requests'] >= self.budget['requests'] or self.report['body_bytes'] + count > self.budget['body_bytes']:
            raise ValueError('Range request budget exhausted')
        self.report['requests'] += 1
        request = urllib.request.Request(BASE + urllib.parse.quote(obj['key'], safe='/='),
                   headers={'Range': f'bytes={start}-{end}', 'If-Match': obj['etag']})
        with self.opener.open(request, timeout=min(10, remaining)) as response:
            if response.status != 206 or response.headers.get('Content-Range') != f"bytes {start}-{end}/{obj['bytes']}" or response.headers.get('ETag') != obj['etag']:
                raise ValueError('Range or object identity mismatch; body not read')
            data = bytearray()
            while len(data) < count:
                if time.monotonic() - self.started > self.budget['seconds']:
                    raise ValueError('Time budget exceeded')
                chunk = response.read1(min(65536, count - len(data)))
                self.report['body_bytes'] += len(chunk)
                if not chunk:
                    raise ValueError('Truncated range')
                data.extend(chunk)
        if time.monotonic() - self.started > self.budget['seconds']:
            raise ValueError('Time budget exceeded')
        return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if not args.fetch:
        print(json.dumps({'release': RELEASE, 'budget': BUDGET, 'bbox': BBOX, 'data_pages': False}))
        return
    inventory_path = CACHE / 'road-inventory/inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    if not inventory['complete'] or inventory['release'] != RELEASE:
        raise ValueError('Incomplete or wrong-release inventory')
    objects = inventory['objects']
    if any(not any(o['key'].startswith(p) for p in PREFIXES) or not o['key'].endswith('.parquet') or not o.get('etag') for o in objects):
        raise ValueError('Unexpected inventory object')
    if len({o['key'] for o in objects}) != len(objects):
        raise ValueError('Duplicate inventory object')
    output = CACHE / 'road-footers'
    if output.exists():
        raise ValueError('Existing footer run; inspect and reuse, do not repeat automatically')
    output.mkdir()
    report = {'release': RELEASE, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'budget': BUDGET, 'bbox': BBOX, 'complete': False, 'requests': 0, 'body_bytes': 0,
              'inventory_sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'files': []}
    reader = RangeReader(report)
    try:
        for i, obj in enumerate(objects):
            report['pending_file_index'] = i
            report['stage'] = 'trailer'
            size = obj['bytes']
            tail = reader.get(obj, size - 8, size - 1)
            report['stage'] = 'validate_trailer'
            length = footer_length(tail, size)
            report['pending_footer_bytes'] = length
            report['stage'] = 'footer'
            footer = reader.get(obj, size - 8 - length, size - 9)
            report['stage'] = 'parse_and_save'
            # Metadata-only envelope; no column data pages are read or fabricated.
            envelope = b'PAR1' + footer + tail
            metadata = pq.read_metadata(io.BytesIO(envelope))
            (output / f'{i:03d}.footer').write_bytes(envelope)
            report['files'].append({'key': obj['key'], 'footer_bytes': length,
                'footer_sha256': hashlib.sha256(envelope).hexdigest(), 'schema': str(metadata.schema),
                'row_groups': metadata.num_row_groups, 'candidates': candidate_groups(metadata)})
        report['complete'] = True
        report['stage'] = 'complete'
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        report['error_reason'] = safe_error_reason(exc)
        raise RuntimeError('Footer run incomplete; inspect saved report; no automatic retries') from None
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        report['elapsed_seconds'] = round(time.monotonic() - reader.started, 3)
        (output / 'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('complete','requests','body_bytes','elapsed_seconds')}))


if __name__ == '__main__':
    main()
