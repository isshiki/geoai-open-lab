"""Explicit optional acquisition of the pinned public external reference (16.68 MB).

Read docs/urban-function-sources.md first. Analysis never calls this script.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

NAME='L03-b-u-21_5339-jgd2011_GML.zip'
URL='https://nlftp.mlit.go.jp/ksj/gml/data/L03-b-u/L03-b-u-21/'+NAME
SHA='f53b124d2ae83703db62c42a92d82f7db10886cf11ddb9a9f66afa176a2e4c39'


def main():
    out=Path(__file__).resolve().parents[1]/'data/raw/urban_function'
    out.mkdir(parents=True,exist_ok=True)
    p=out/NAME
    if p.exists():
        if hashlib.sha256(p.read_bytes()).hexdigest()!=SHA:raise ValueError('Existing reference differs')
        print('Verified existing pinned reference; no download')
        return
    with urlopen(URL,timeout=60) as r:data=r.read()
    if hashlib.sha256(data).hexdigest()!=SHA:raise ValueError('Provider content changed; do not silently substitute')
    p.write_bytes(data)
    (out/'manifest.json').write_text(json.dumps(dict(url=URL,file=NAME,sha256=SHA,bytes=len(data),
        acquired_utc=datetime.now(timezone.utc).isoformat(),license='CC-BY-4.0',version='2021 JGD2011'),indent=2),encoding='utf8')


if __name__=='__main__':main()
