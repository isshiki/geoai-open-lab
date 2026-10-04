"""Local immutable-input receipts and output manifests; no network access."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import platform
from .territory import ROOT, RESULT


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_inputs():
    receipt = json.loads((ROOT / 'data/input-receipt.json').read_text(encoding='utf-8'))
    for entry in receipt['files']:
        path = (ROOT / entry['target_relative']).resolve()
        if not path.is_relative_to((ROOT / 'data').resolve()):
            raise ValueError('Input receipt escapes project data directory')
        if not path.is_file() or path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('Input hash or size mismatch: ' + entry['target_relative'])
    return receipt


def write_manifest(started):
    inputs = verify_inputs()
    paths = sorted((ROOT / 'src').rglob('*.py')) + sorted(p for p in (ROOT / 'configs').rglob('*') if p.is_file()) + [ROOT / 'uv.lock']
    manifest = {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
                'python': platform.python_version(), 'packages': {name: importlib.metadata.version(name) for name in
                    ['duckdb', 'numpy', 'pandas', 'pyarrow', 'pyproj', 'shapely', 'scipy', 'matplotlib']},
                'input_receipt': inputs, 'source_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for p in paths},
                'output_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(RESULT.glob('*')) if p.is_file() and p.name != 'manifest.json'},
                'artifact_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for directory in ('data/figures', 'data/cache/notebook') for p in sorted((ROOT / directory).glob('*')) if p.is_file()},
                'road_grid_replay': json.loads((ROOT / 'data/replay/validation.json').read_text(encoding='utf-8')) if (ROOT / 'data/replay/validation.json').exists() else None,
                'reproduction_scope': 'saved road grid onward; Tokyo road-grid replay reported separately',
                'code_state': 'working tree; source hashes identify implementation before commit',
                'new_data_downloads': False}
    (RESULT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest
