"""Execute the companion with saved inputs; keep public Notebook output-free."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter

root=Path(__file__).resolve().parents[1]
out=root/'data/cache/embedding/tokyo-v1'
source=root/'notebooks/08_region_embedding.ipynb'
nb=nbformat.read(source,as_version=4)
NotebookClient(nb,timeout=300,startup_timeout=60,kernel_name='python3',
    resources={'metadata':{'path':str(root)}}).execute()
nbformat.write(nb,out/'08_region_embedding.executed.ipynb')
html,_=HTMLExporter().from_notebook_node(nb)
html=html.replace('</head>','<style>.jp-RenderedSVG img{max-width:100%;height:auto}</style></head>')
html=html.replace('href="../docs/','href="https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/')
(out/'08_region_embedding.html').write_text(html,encoding='utf8')
print('Executed all 5 code cells; responsive HTML saved; public source unchanged.')
