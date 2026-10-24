"""Execute in the existing uv environment; keep the public Notebook clean."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

root=Path(__file__).resolve().parents[1]
out=root/'data/cache/crs/kichijoji-v1'
nb=nbformat.read(root/'notebooks/14_crs.ipynb',as_version=4)
NotebookClient(nb,timeout=300,startup_timeout=60,kernel_name='python3',resources={'metadata':{'path':str(root)}}).execute()
nbformat.write(nb,out/'14_crs.executed.ipynb')
html,_=HTMLExporter().from_notebook_node(nb)
html=html.replace('</head>','<style>.jp-RenderedSVG img{max-width:100%;height:auto}</style></head>')
html=html.replace('href="../docs/','href="https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/')
(out/'14_crs.html').write_text(html,encoding='utf8')
print('All Notebook cells executed; HTML saved; public source untouched.')
