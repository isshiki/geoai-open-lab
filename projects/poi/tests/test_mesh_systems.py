import json
import tempfile
import unittest
from pathlib import Path
import h3
import mgrs
import s2sphere as s2
from shapely.geometry import Point, shape, box
from shapely.ops import unary_union
from pyproj import Transformer
from geoai_open_lab import mesh_systems as m
from geoai_open_lab import standard_mesh_guide as g

class MeshSystemsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[r for city in m.POINTS for r in m.compare_point(city)]

    def test_all_boundaries_contain_source_and_area(self):
        self.assertEqual(len(self.rows),23)
        for r in self.rows:
            lat,lon=m.POINTS[r['city']];p=shape(r['geometry'])
            self.assertTrue(p.is_valid and p.covers(Point(lon,lat)))
            self.assertAlmostEqual(abs(m.GEOD.geometry_area_perimeter(p)[0])/1e6,r['area_km2'],places=10)
            self.assertGreater(r['area_km2'],0)

    def test_unique_neighbors_children(self):
        for r in self.rows:
            self.assertEqual(len(set(r['neighbors'])),r['neighbor_count'])
            self.assertNotIn(r['cell_id'],r['neighbors'])
            self.assertEqual(len(set(r['child_ids'])),r['child_count'])

    def test_h3_relationships(self):
        for r in self.rows:
            if r['scheme']!='H3':continue
            self.assertEqual(h3.cell_to_parent(r['cell_id']),r['parent_id'])
            self.assertTrue(all(h3.cell_to_parent(c)==r['cell_id'] for c in r['child_ids']))
            self.assertTrue(all(h3.are_neighbor_cells(r['cell_id'],n) for n in r['neighbors']))

    def test_s2_relationships(self):
        for r in self.rows:
            if r['scheme']!='S2':continue
            sid=s2.CellId.from_token(r['cell_id'])
            self.assertEqual(sid.parent().to_token(),r['parent_id'])
            self.assertTrue(all(s2.CellId.from_token(c).parent()==sid for c in r['child_ids']))
            self.assertEqual(set(r['neighbors']),{c.to_token() for c in sid.get_edge_neighbors()})

    def test_geohash_known_example_roundtrip_hierarchy(self):
        self.assertEqual(m.geohash_encode(57.64911,10.40744,11),'u4pruydqqvj')
        for r in self.rows:
            if r['scheme']!='Geohash':continue
            cell=box(*m.geohash_bounds(r['cell_id']))
            kids=[box(*m.geohash_bounds(c)) for c in r['child_ids']]
            self.assertLess(unary_union(kids).symmetric_difference(cell).area,1e-12)
            self.assertAlmostEqual(sum(p.area for p in kids),cell.area)
            for n in r['neighbors']:self.assertTrue(box(*m.geohash_bounds(n)).touches(cell))

    def test_quadkey_official_example_and_same_geometry(self):
        self.assertEqual(m.quadkey(3,3,5),'213')
        self.assertEqual(m.quad_decode('213'),(3,3,5))
        for city in m.POINTS:
            a=next(r for r in self.rows if r['city']==city and r['scheme']=='XYZ')
            b=next(r for r in self.rows if r['city']==city and r['scheme']=='Quadkey')
            self.assertEqual(a['geometry'],b['geometry'])
            self.assertEqual(m.quad_decode(b['cell_id']),tuple(map(int,a['cell_id'].split('/'))))
            z,x,y=m.quad_decode(b['cell_id'])
            self.assertEqual(m.quad_decode(b['parent_id']),(z-1,x//2,y//2))
            self.assertTrue(all(m.quad_decode(c)[0]==z+1 for c in b['child_ids']))

    def test_mgrs_decode_encode(self):
        engine=mgrs.MGRS()
        for r in self.rows:
            if r['scheme']!='MGRS':continue
            self.assertEqual(r['child_count'],100)
            lat,lon=m.POINTS[r['city']]
            self.assertEqual(engine.toMGRS(lat,lon,MGRSPrecision=2),r['cell_id'])
            # Every child interior maps to the recorded parent cell.
            zone=int(r['cell_id'][:2]);f=Transformer.from_crs(4326,32600+zone,always_xy=True);inv=Transformer.from_crs(32600+zone,4326,always_xy=True)
            for c in r['child_ids']:
                la,lo=engine.toLatLon(c);x,y=f.transform(lo,la);lo,la=inv.transform(x+50,y+50)
                self.assertEqual(engine.toMGRS(la,lo,MGRSPrecision=2),r['cell_id'])
            self.assertAlmostEqual(r['area_km2'],1.,delta=.002)

    def test_projected_custom_areas(self):
        f=Transformer.from_crs(4326,6677,always_xy=True)
        for r in self.rows:
            if r['scheme'] not in ('独自正方形','独自六角形'):continue
            from shapely.ops import transform
            p=transform(f.transform,shape(r['geometry']))
            expected=250000 if r['scheme']=='独自正方形' else 3*m.math.sqrt(3)/2*300**2
            self.assertAlmostEqual(p.area,expected,delta=.01)

    def test_standard_all_hierarchies_tile_and_roundtrip(self):
        for lat,lon in m.POINTS.values():
            for digits in g.LENGTHS:
                code=g.encode(lat,lon,digits);w,s,e,n=g.bounds(code)
                self.assertTrue(w<=lon<e and s<=lat<n)
                self.assertEqual(g.encode((s+n)/2,(w+e)/2,digits),code)
                kids=g.children(code)
                if kids:
                    polygons=[box(*g.bounds(c)) for c in kids]
                    self.assertLess(unary_union(polygons).symmetric_difference(box(w,s,e,n)).area,1e-10)
                    self.assertAlmostEqual(sum(p.area for p in polygons),(e-w)*(n-s),places=10)
                    self.assertTrue(all(g.parent(c)==code for c in kids))

    def test_standard_known_codes_and_boundary(self):
        la,lo=m.POINTS['東京・吉祥寺']
        self.assertEqual(g.encode(la,lo,10),'5339444614')
        w,s,e,n=g.bounds('5339444614')
        self.assertEqual(g.encode(s,w,10),'5339444614')
        self.assertNotEqual(g.encode(n,e,10),'5339444614')

    def test_invalid_inputs(self):
        for code in ['533944465','53394446145','bad']:
            with self.assertRaises(ValueError):g.bounds(code)
        with self.assertRaises(ValueError):m.tile(90,0)
        with self.assertRaises(ValueError):m.geohash_bounds('a')
        with self.assertRaises(ValueError):m.quad_decode('4')

    def test_square_parent_children_and_neighbors_geometry(self):
        for r in self.rows:
            if r['scheme'] not in ('XYZ','独自正方形','標準地域メッシュ'):
                continue
            def decode(code):
                if r['scheme']=='XYZ':return box(*m.tile_bounds(*map(int,code.split('/'))))
                if r['scheme']=='標準地域メッシュ':return box(*g.bounds(code))
                _,width,i,j=code.split(':');width=float(width);i=int(i);j=int(j)
                return box(i*width,j*width,(i+1)*width,(j+1)*width)
            cell=decode(r['cell_id'])
            kids=[decode(c) for c in r['child_ids']]
            self.assertLess(unary_union(kids).symmetric_difference(cell).area,1e-9)
            self.assertTrue(decode(r['parent_id']).buffer(1e-10).covers(cell))
            for neighbor in r['neighbors']:
                other=decode(neighbor)
                self.assertAlmostEqual(cell.intersection(other).area,0,places=9)
                self.assertLess(cell.distance(other),1e-10)

    def test_hex_neighbors_share_an_edge(self):
        r=next(r for r in self.rows if r['scheme']=='独自六角形')
        def polygon(code):
            q,b=map(int,code.split(':')[-2:]);x=450*q;y=300*m.math.sqrt(3)*(b+q/2)
            from shapely.geometry import Polygon
            return Polygon([(x+300*m.math.cos(k*m.math.pi/3),y+300*m.math.sin(k*m.math.pi/3)) for k in range(6)])
        cell=polygon(r['cell_id'])
        for code in r['neighbors']:
            other=polygon(code)
            self.assertLess(cell.intersection(other).area,1e-6)
            self.assertLess(cell.distance(other),1e-7)
            self.assertGreater(cell.boundary.intersection(other.buffer(1e-7)).length,299)

    def test_reproducible_results(self):
        with tempfile.TemporaryDirectory() as d:
            m.run(d);first=Path(d,'cells.json').read_bytes();csv=Path(d,'comparison.csv').read_bytes()
            m.run(d)
            self.assertEqual(first,Path(d,'cells.json').read_bytes())
            self.assertEqual(csv,Path(d,'comparison.csv').read_bytes())

    def test_public_notebook_clean(self):
        nb=json.loads((m.ROOT/'notebooks/13_mesh_systems_comparison.ipynb').read_text(encoding='utf8'))
        for cell in nb['cells']:
            self.assertFalse(cell.get('outputs'));self.assertIsNone(cell.get('execution_count'));self.assertFalse(cell.get('attachments'))

if __name__=='__main__':unittest.main()
