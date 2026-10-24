"""Fixed-input regression, output equality, figures and clean Notebook checks."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from geoai_open_lab.crs_experiment import ROOT,OUT,run

before={p.name:p.read_bytes() for p in OUT.glob('*.csv')}
run()
assert before and all((OUT/n).read_bytes()==b for n,b in before.items()),'Numerical outputs changed on rerun'
summary=pd.read_csv(OUT/'poi_summary.csv').set_index('method')
assert summary.poi_count.to_dict()=={'geodesic':3481,'6677':3481,'3857':3111}
overlap=pd.read_csv(OUT/'poi_overlap.csv')
assert overlap.changed.tolist()==[0,370,370]
assert np.allclose(overlap.jaccard,[1,3111/3481,3111/3481])
world=pd.read_csv(OUT/'world_areas.csv')
assert world[world.crs.eq(8857)].error_pct.abs().max()<.001
audit=pd.read_csv(OUT/'station_audit.csv')
assert len(audit)==656 and audit.region_id.is_unique and audit.inside_epsg_bbox.all()
assert audit.whole_aoi_inside_epsg_bbox.all() and audit.projected_area_error_pct.abs().max()<.021
assert ((audit.meridional_scale-1).abs()<.00011).all()
nb=json.loads((ROOT/'notebooks/14_crs.ipynb').read_text(encoding='utf8'))
assert all(not c.get('outputs') and c.get('execution_count') is None and not c.get('attachments') for c in nb['cells'])
for name in ('overview','coordinates','world_projections','poi_500m','features_flow','selection','cover_1600x900'):
    assert (OUT/(name+'.svg')).exists() and (OUT/(name+'.png')).exists()
print('Fixed inputs, CSV byte equality, counts, areas, 656 stations, clean Notebook and 7 figure pairs: PASS')
