"""Execute the companion with saved inputs; keep public Notebook output-free."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

root=Path(__file__).resolve().parents[1]
out=root/'data/cache/similar_regions/tokyo-v1'
source=root/'notebooks/06_similar_regions.ipynb'
nb=nbformat.read(source,as_version=4)
NotebookClient(nb,timeout=300,startup_timeout=60,kernel_name='python3',
    resources={'metadata':{'path':str(root)}}).execute()
nbformat.write(nb,out/'06_similar_regions.executed.ipynb')
html,_=HTMLExporter().from_notebook_node(nb)
html=html.replace('</head>','<style>.jp-RenderedSVG img{max-width:100%;height:auto}</style></head>')
html=html.replace('href="../docs/','href="https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/')
(out/'06_similar_regions.html').write_text(html,encoding='utf8')
print('Executed all 6 code cells; responsive HTML saved; public source unchanged.')
