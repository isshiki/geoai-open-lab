"""Bounded anonymous S3 inventory only; never reads Parquet objects.

Default prints the plan. --fetch inventories the two fixed public prefixes once.
Existing results are reused; partial/failed runs require manual inspection.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/cache/station_access_aging/road-inventory'
BASE = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/'
RELEASE = '2026-09-23.1'
PREFIXES = [f'release/{RELEASE}/theme=transportation/type={kind}/' for kind in ('segment', 'connector')]
BUDGET = {'body_bytes': 8 * 1024**2, 'requests': 20, 'seconds': 120}
NS = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}


def parse_page(body, prefix):
    root = ET.fromstring(body)
    if root.tag != '{'+NS['s']+'}ListBucketResult' or root.findtext('s:Prefix', namespaces=NS) != prefix:
        raise ValueError('Unexpected listing')
    rows = []
    for item in root.findall('s:Contents', NS):
        key = item.findtext('s:Key', namespaces=NS)
        size = int(item.findtext('s:Size', namespaces=NS))
        if not key or not key.startswith(prefix) or size < 0:
            raise ValueError('Unexpected object')
        rows.append({'key': key, 'bytes': size, 'etag': item.findtext('s:ETag', namespaces=NS),
                     'last_modified': item.findtext('s:LastModified', namespaces=NS)})
    truncated = root.findtext('s:IsTruncated', namespaces=NS)
    continuation = root.findtext('s:NextContinuationToken', namespaces=NS)
    if truncated not in ('true', 'false') or (truncated == 'true' and not continuation):
        raise ValueError('Invalid pagination')
    return rows, continuation if truncated == 'true' else None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Unexpected redirect')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    args = parser.parse_args()
    if not args.fetch:
        print(json.dumps({'release': RELEASE, 'prefixes': PREFIXES, 'budget': BUDGET}))
        return
    if OUT.exists():
        raise ValueError('Inventory directory already exists; inspect saved results, do not repeat')
    OUT.mkdir(parents=True)
    start = time.monotonic()
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'release': RELEASE,
              'base_url': BASE, 'budget': BUDGET, 'requests': 0, 'body_bytes': 0,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'complete': False, 'objects': [], 'pages': [], 'summaries': {}}
    opener = urllib.request.build_opener(NoRedirect)
    try:
        seen_keys = set()
        for prefix in PREFIXES:
            continuation, seen_tokens = None, set()
            while True:
                remaining = BUDGET['seconds'] - (time.monotonic() - start)
                if remaining <= 0 or report['requests'] >= BUDGET['requests']:
                    raise ValueError('Request/time budget exhausted')
                params = {'list-type': '2', 'prefix': prefix, 'max-keys': '1000'}
                if continuation:
                    params['continuation-token'] = continuation
                # Pagination tokens are used in memory, never written to logs/provenance.
                url = BASE + '?' + urllib.parse.urlencode(params)
                report['requests'] += 1
                with opener.open(url, timeout=min(10, remaining)) as response:
                    if response.status != 200:
                        raise ValueError('Unexpected response')
                    chunks = []
                    while True:
                        room = BUDGET['body_bytes'] - report['body_bytes']
                        if room <= 0 or time.monotonic() - start > BUDGET['seconds']:
                            raise ValueError('Body/time budget exhausted')
                        block = response.read1(min(65536, room))
                        report['body_bytes'] += len(block)
                        if not block:
                            break
                        chunks.append(block)
                body = b''.join(chunks)
                rows, continuation = parse_page(body, prefix)
                for row in rows:
                    if row['key'] in seen_keys:
                        raise ValueError('Duplicate object across pages')
                    seen_keys.add(row['key'])
                report['objects'].extend(rows)
                report['pages'].append({'prefix': prefix, 'bytes': len(body),
                                        'sha256': hashlib.sha256(body).hexdigest(), 'objects': len(rows)})
                if not continuation:
                    break
                if continuation in seen_tokens:
                    raise ValueError('Repeated pagination cursor')
                seen_tokens.add(continuation)
            objects = [r for r in report['objects'] if r['key'].startswith(prefix)]
            report['summaries'][prefix] = {'objects': len(objects), 'bytes': sum(r['bytes'] for r in objects),
                                          'parquet_objects': sum(r['key'].endswith('.parquet') for r in objects)}
        if time.monotonic() - start > BUDGET['seconds']:
            raise ValueError('Time budget exceeded')
        report['complete'] = True
    except Exception as exc:
        report['error_type'] = type(exc).__name__  # No remote URL/error text persisted.
        raise RuntimeError('Inventory incomplete; inspect local report') from None
    finally:
        report['elapsed_seconds'] = round(time.monotonic() - start, 3)
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (OUT / 'inventory.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('complete','requests','body_bytes','elapsed_seconds','summaries')}))


if __name__ == '__main__':
    main()
