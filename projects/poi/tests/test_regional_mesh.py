"""Standard mesh arithmetic, conservation and fixed-input regression."""
import json
import unittest
import pandas as pd
from shapely.ops import unary_union
from geoai_open_lab import regional_mesh as m


class RegionalMeshTests(unittest.TestCase):
    def test_official_example(self):
        # Statistics Bureau m-kukaku.pdf: 5339-46-00 southwest=35d40m,139d45m.
        self.assertEqual(m.mesh_bounds('53394600'),(139.75,35+2/3,139.7625,35.675))
        self.assertEqual(m.encode_mesh(35.67,139.752,8),'53394600')

    def test_roundtrip(self):
        for code in ('53394446','533944461','5339444611','5339444614','5339460032'):
            w,s,e,n=m.mesh_bounds(code)
            self.assertEqual(m.encode_mesh((s+n)/2,(w+e)/2,len(code)),code)

    def test_children_partition(self):
        for code in ('53394446','533944461'):
            parent=m.mesh_polygon(code)
            children=[m.mesh_polygon(code+str(q)) for q in range(1,5)]
            self.assertLess(parent.symmetric_difference(unary_union(children)).area,1e-15)
            self.assertAlmostEqual(sum(c.area for c in children),parent.area,places=14)

    def test_boundary(self):
        w,s,e,n=m.mesh_bounds('533944461')
        self.assertEqual(m.encode_mesh(s,w),'533944461')
        self.assertNotEqual(m.encode_mesh(n,e),'533944461')
        self.assertEqual(m.encode_mesh((s+n)/2,e),'533944462')
        self.assertEqual(m.encode_mesh((s+n)/2,e-1e-8),'533944461')

    def test_invalid(self):
        for code in ('53394846','533944460','abcdefghi','5339'):
            with self.assertRaises(ValueError):m.mesh_bounds(code)
        for coords in [(float('nan'),139),(35,float('inf'))]:
            with self.assertRaises(ValueError):m.encode_mesh(*coords)

    def test_population_and_flags(self):
        data=pd.DataFrame({'KEY_CODE':['533944461'+str(q) for q in range(1,5)],'HTKSYORI':['0','1','2','0'],m.POP:['10','20','3','0']})
        out=m.aggregate_population(data,['533944461']).iloc[0]
        self.assertEqual(out.population_2020,33)
        self.assertEqual(out.suppressed_children,1)
        self.assertEqual(out.aggregate_children,1)

    def test_missing_is_not_zero(self):
        data=pd.DataFrame({'KEY_CODE':['5339444611'],'HTKSYORI':['0'],m.POP:['0']})
        out=m.aggregate_population(data,['533944461']).iloc[0]
        self.assertFalse(out.population_complete)
        self.assertTrue(pd.isna(out.population_2020))

    def test_duplicate_rejected(self):
        data=pd.DataFrame({'KEY_CODE':['5339444611']*2,'HTKSYORI':['0']*2,m.POP:['0']*2})
        with self.assertRaises(ValueError):m.aggregate_population(data,['533944461'])

    def test_projected_area(self):
        self.assertTrue(260000<m.mesh_polygon('533944461',True).area<263000)
        self.assertTrue(all(a.unit_name=='metre' for a in m.PROJECT.target_crs.axis_info))
        # Zone IX origin: latitude 36, longitude 139d50m; always_xy normalizes axes.
        x,y=m.PROJECT.transform(139+50/60,36)
        self.assertAlmostEqual(x,0,places=6);self.assertAlmostEqual(y,0,places=6)

    def test_saved_conservation(self):
        if not (m.OUT/'manifest.json').exists():self.skipTest('Private fixed input run unavailable')
        table=pd.read_csv(m.OUT/'mesh500.csv',dtype={'mesh_code':str})
        children=pd.read_csv(m.OUT/'population250_audit.csv')
        points=pd.read_parquet(m.OUT/'poi_assignments.parquet')
        self.assertEqual(len(table),9);self.assertEqual(len(children),36)
        self.assertEqual(table.population_2020.sum(),pd.to_numeric(children[m.POP]).sum())
        self.assertEqual(table.population_2020.sum(),28487)
        self.assertTrue(points.id.is_unique)
        self.assertEqual(table.poi_count.sum(),len(points));self.assertEqual(len(points),4057)
        self.assertTrue(points.mesh_code.isin(table.mesh_code).all())

    def test_provenance(self):
        if not (m.OUT/'manifest.json').exists():self.skipTest('Private fixed input run unavailable')
        manifest=json.loads((m.OUT/'manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['poi_release'],'2026-09-23.0')
        self.assertEqual(manifest['census']['reference_date'],'2020-10-01')
        for name,h in manifest['output_sha256'].items():self.assertEqual(m.digest(m.OUT/name),h)

    def test_notebook_clean(self):
        nb=json.loads((m.ROOT/'notebooks/12_regional_mesh.ipynb').read_text(encoding='utf8'))
        for cell in nb['cells']:
            self.assertFalse(cell.get('attachments'))
            if cell['cell_type']=='code':
                self.assertEqual(cell['outputs'],[]);self.assertIsNone(cell['execution_count'])


if __name__=='__main__':unittest.main()
