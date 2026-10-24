"""Snapshot/verify previous public notebooks and result artifacts, without editing them."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
record=root/'data/cache/crs/protected-before.json'
folders=('aoi_sensitivity','clustering','comparison','embedding','maup','mesh_systems',
         'region_features','regional_mesh','similar_regions','station_range_methods',
         'walking_range','walking_sensitivity')
files=[p for folder in folders for p in (root/'data/cache'/folder).rglob('*') if p.is_file()]
files += [p for p in (root/'notebooks').glob('*.ipynb') if not p.name.startswith('14_')]
files += [root/'uv.lock',root/'pyproject.toml']
current={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
if sys.argv[-1]=='snapshot':
    if record.exists():raise SystemExit('Baseline already exists')
    record.parent.mkdir(parents=True,exist_ok=True)
    record.write_text(json.dumps(current,indent=2),encoding='utf8');print('Recorded',len(current),'protected files')
else:
    old=json.loads(record.read_text(encoding='utf8'))
    changed=[p for p,h in old.items() if current.get(p)!=h]
    if changed:raise SystemExit('Changed protected files: '+str(changed))
    print('Unchanged:',len(old),'protected files')
