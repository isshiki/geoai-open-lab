"""Acquire only the three approved experiment-05 ZIPs; never download roads.

Default is offline verification. --download explicitly permits missing ZIPs.
No retries or replacement of existing files. Sources/terms: docs/station-access-aging.md.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import time
from datetime import datetime, timezone
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/station_access_aging'
CACHE = ROOT / 'data/cache/station_access_aging'
MIB = 1024 * 1024
SOURCES = [
    ('population', 'tblT001142Q5339.zip',
     'https://www.e-stat.go.jp/gis/statmap-search/data?statsId=T001142&code=5339&downloadType=2',
     '2020-10-01', 'T001142; JGD2011; 250m; 5339; published 2024-03-14'),
    ('stations', 'N02-20_GML.zip',
     'https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-20/N02-20_GML.zip',
     '2020-12-31', 'N02 product specification 2.3'),
    ('boundaries', 'N03-20200101_13_GML.zip',
     'https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2020/N03-20200101_13_GML.zip',
     '2020-01-01', 'N03 product specification 2.4; Tokyo'),
]


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def inspect_zip(path):
    """Validate member paths, duplication, symlinks, size and CRC; do not extract."""
    with zipfile.ZipFile(path) as archive:
        entries, seen, total = [], set(), 0
        for item in archive.infolist():
            name = item.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith('/') or '\\' in name or ':' in name
                    or '..' in parts or '\x00' in name
                    or any(p.endswith((' ', '.')) for p in parts)
                    or any(re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p) for p in parts)):
                raise ValueError('Unsafe ZIP member path')
            normalized = '/'.join(parts).casefold()
            if normalized in seen or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Duplicate ZIP member or symlink')
            seen.add(normalized)
            total += item.file_size
            if total > 512 * MIB or item.flag_bits & 1:
                raise ValueError('ZIP expansion budget exceeded or encrypted member')
            entries.append({'name': name, 'bytes': item.file_size, 'crc32': f'{item.CRC:08x}'})
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
    return entries, total


def save_manifest(manifest):
    target = CACHE / 'acquisition-manifest.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    manifest_path = CACHE / 'acquisition-manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    else:
        manifest = {
            'created_utc': utc_now(), 'python': platform.python_version(),
            'packages': {p: importlib.metadata.version(p) for p in ['duckdb', 'pandas', 'geopandas', 'shapely', 'pyproj']},
            'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'script_sha256': sha256(__file__), 'lock_sha256': sha256(ROOT / 'uv.lock'),
            'command': 'python scripts/station_access_aging_acquire.py --download',
            'scope': 'T001142/5339; N02 nationwide ZIP; N03 Tokyo ZIP; local audit only',
            'budgets': {'per_zip_bytes': 32 * MIB, 'total_zip_bytes': 64 * MIB,
                        'uncompressed_bytes': 512 * MIB, 'per_download_seconds': 300,
                        'total_download_seconds': 900},
            'transport_bytes_including_headers': None, 'sources': [],
        }
    start = time.monotonic()
    total_downloaded = 0
    expanded_total = 0
    for key, filename, url, reference_date, version in SOURCES:
        target = RAW / filename
        previous = next((s for s in manifest['sources'] if s['id'] == key), None)
        if target.exists():
            if not previous or sha256(target) != previous['sha256']:
                raise ValueError('Existing ZIP has no matching manifest; do not overwrite')
            record = previous
            total_downloaded += record['bytes']
        else:
            if not args.download:
                raise ValueError('Missing ZIP; explicit download approval required')
            if previous:
                raise ValueError('Previously downloaded ZIP is missing; no automatic re-download')
            part = target.with_suffix('.zip.part')
            if part.exists():
                raise ValueError('Partial download exists; inspect before retrying')
            begun = time.monotonic()
            began_utc = utc_now()
            count = 0
            with urllib.request.urlopen(url, timeout=30) as response, part.open('xb') as out:
                # Refuse an unexpected redirect; never record a signed/credential URL.
                if response.geturl() != url or response.status != 200:
                    raise ValueError('Unexpected download response')
                content_type = response.headers.get('Content-Type', '')
                if 'html' in content_type.lower():
                    raise ValueError('HTML instead of ZIP')
                length = response.headers.get('Content-Length')
                if length is not None and int(length) > 32 * MIB:
                    raise ValueError('Declared size exceeds per-ZIP budget')
                while True:
                    if time.monotonic() - begun > 300 or time.monotonic() - start > 900:
                        raise TimeoutError('Download deadline exceeded')
                    block = response.read1(65536)
                    if not block:
                        break
                    count += len(block)
                    if count > 32 * MIB or total_downloaded + count > 64 * MIB:
                        raise ValueError('Download size budget exceeded')
                    out.write(block)
                if length is not None and count != int(length):
                    raise ValueError('Content-Length mismatch')
                last_modified = response.headers.get('Last-Modified')
            elapsed = time.monotonic() - begun
            if elapsed > 300 or time.monotonic() - start > 900:
                raise TimeoutError('Download deadline exceeded')
            members, expanded = inspect_zip(part)
            if expanded_total + expanded > 512 * MIB:
                raise ValueError('Combined expansion budget exceeded')
            record = {'id': key, 'path': target.relative_to(ROOT).as_posix(), 'url': url,
                      'reference_date': reference_date, 'version': version,
                      'retrieved_start_utc': began_utc, 'retrieved_end_utc': utc_now(),
                      'download_seconds': round(elapsed, 3), 'bytes': count,
                      'content_length': int(length) if length else None,
                      'last_modified': last_modified, 'content_type': content_type,
                      'sha256': sha256(part), 'members': members, 'uncompressed_bytes': expanded}
            part.rename(target)
            manifest['sources'].append(record)
            save_manifest(manifest)
            total_downloaded += count
        members, expanded = inspect_zip(target)
        expanded_total += expanded
        if expanded_total > 512 * MIB or sum(s['bytes'] for s in manifest['sources']) > 64 * MIB:
            raise ValueError('Combined archive budget exceeded')
        print(json.dumps({'source': key, 'bytes': record['bytes'], 'members': len(members),
                          'uncompressed_bytes': expanded, 'sha256': record['sha256']}, ensure_ascii=False))
    manifest['last_verified_utc'] = utc_now()
    save_manifest(manifest)
    print('Verified three ZIPs. No roads requested. No files extracted.')


if __name__ == '__main__':
    main()
