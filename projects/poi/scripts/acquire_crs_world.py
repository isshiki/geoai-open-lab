from pathlib import Path
from datetime import datetime,timezone
import urllib.request,zipfile,io,json,hashlib
url='https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip'
root=Path(__file__).resolve().parents[1];out=root/'data/raw/crs/natural-earth-5.1.1';out.mkdir(parents=True,exist_ok=True)
p=out/'ne_110m_admin_0_countries.zip'
if p.exists():raise SystemExit('Already present: verify existing manifest instead of overwriting')
b=urllib.request.urlopen(url,timeout=60).read()
z=zipfile.ZipFile(io.BytesIO(b));versions=[n for n in z.namelist() if 'VERSION' in n.upper()]
assert len(versions)==1,versions
v=z.read(versions[0]).decode().strip();assert v=='5.1.1',v
expected='0f243aeac8ac6cf26f0417285b0bd33ac47f1b5bdb719fd3e0df37d03ea37110'
if hashlib.sha256(b).hexdigest()!=expected:raise SystemExit('Distribution changed: review before adopting')
p.write_bytes(b)
meta={'source_url':url,'version':v,'retrieved_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'license':'Public domain','terms_url':'https://www.naturalearthdata.com/about/terms-of-use/'}
(out/'manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf8');print(json.dumps(meta,indent=2))
