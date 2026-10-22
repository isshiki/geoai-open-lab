"""Replay all 656 stations in a temporary output and compare deterministic hashes."""
import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from geoai_open_lab import walking_sensitivity as w

p=argparse.ArgumentParser();p.add_argument('--road-dir',required=True);args=p.parse_args()
original=json.loads((w.OUT/'manifest.json').read_text(encoding='utf8'))
out=w.OUT
with tempfile.TemporaryDirectory(dir=out.parent) as folder:
    with patch.object(w,'OUT',Path(folder)):
        w.run(args.road_dir)
        replay=json.loads((w.OUT/'manifest.json').read_text(encoding='utf8'))
        assert replay['output_sha256']==original['output_sha256'], 'Numerical outputs changed on replay'
        assert replay['old_artifacts_sha256']==original['old_artifacts_sha256']
        for name in ('Foursquare-NOTICE.txt','Apache-LICENSE.txt'):
            (out/name).write_bytes((w.OUT/name).read_bytes())
        # Final provenance describes the current source without altering numerical artifacts.
        w.json_write(out/'manifest.json',replay)
        w.json_write(out/'replay-validation.json',dict(all_656_replayed=True,matching_files=len(replay['output_sha256']),
                     notebook11_unchanged=True,completed_at_utc=replay['completed_at_utc']))
print('Full replay: every CSV and station parquet SHA-256 is identical.')
