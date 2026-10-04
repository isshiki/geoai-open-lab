"""Copy authorized local inputs from eki-walk, recording hashes without downloads."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from .territory import ROOT
from .provenance import digest


def run(source):
    source = Path(source).resolve()
    artifact = source / 'artifacts/station-ranking-20261004'
    items = []
    for name in ['kanto-261001.osm.pbf', 'N02-25_GML.zip'] + [f'N03-20260101_{p}_GML.zip' for p in ('11', '12', '13', '14')]:
        items.append((source / 'data/raw' / name, ROOT / 'data/raw' / name))
    items.append((artifact / 'raw/tblT001142Q5339.zip', ROOT / 'data/raw/tblT001142Q5339.zip'))
    for region in ('tokyo', 'saitama', 'chiba', 'kanagawa'):
        for name in ('grid-base.npz', 'stations-base.parquet', 'display.wkb'):
            items.append((source / 'data/build' / region / name, ROOT / 'data/build' / region / name))
    for name in ('inventory.json', 'execution-manifest.json', 'population-manifest.json', 'definition-lock.json', 'article_scope.json'):
        if (artifact / name).is_file():
            items.append((artifact / name, ROOT / 'data/reference' / name))
    for name in ('all_stations.parquet', 'validation.json', 'population_validation.json', 'poi_validation.json'):
        items.append((artifact / 'results' / name, ROOT / 'data/reference/results' / name))
    receipt = []
    for original, target in items:
        if not original.resolve().is_relative_to(source):
            raise ValueError('Source path escapes the authorized project')
        checksum = digest(original)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) != checksum:
            raise ValueError('Existing input differs: ' + target.relative_to(ROOT).as_posix())
        if not target.exists():
            shutil.copy2(original, target)
        if digest(target) != checksum:
            raise ValueError('Copy verification failed')
        receipt.append({'source_relative': original.relative_to(source).as_posix(),
                        'target_relative': target.relative_to(ROOT).as_posix(),
                        'bytes': target.stat().st_size, 'sha256': checksum})
    document = {'copied_utc': datetime.now(timezone.utc).isoformat(), 'files': receipt}
    (ROOT / 'data/input-receipt.json').write_text(json.dumps(document, indent=2), encoding='utf-8')
    return document


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    run(parser.parse_args().source)
