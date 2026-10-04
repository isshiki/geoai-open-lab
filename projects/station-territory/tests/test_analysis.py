import unittest
import numpy as np
import pandas as pd
import shapely
from types import SimpleNamespace
from station_territory.territory import rank, boundary_distance
from station_territory.poi import category, way_geom
from station_territory.population import mesh_bounds, allocations_for_geometry, audit_secrecy
from station_territory.groups import merge_groups

class AnalysisTests(unittest.TestCase):
    def test_relation_requires_complete_supported_members(self):
        from station_territory.poi import relation_geometry
        nodes={1:(0.,0.),2:(2.,0.),3:(2.,2.),4:(0.,2.)}
        members={10:[1,2,3,4,1]}
        result=relation_geometry([10],['way'],['outer'],{'type':'multipolygon'},members,nodes)
        self.assertEqual(result.area,4.)
        self.assertIsNone(relation_geometry([11],['way'],['outer'],{'type':'multipolygon'},members,nodes))
        self.assertIsNone(relation_geometry([10],['relation'],['outer'],{'type':'multipolygon'},members,nodes))

    def test_station_access_fallback_is_not_a_100m_cap(self):
        from station_territory._upstream.shortest import solve
        distance, owner = solve(np.array([[0.,0.],[10.,0.]]), [0], [1], [10.],
                                [shapely.Point(0.,200.)], 100.)
        np.testing.assert_allclose(distance,[200.,210.])
        self.assertEqual(owner.tolist(),[0,0])

    def test_nonwalkable_motorway_and_private_access(self):
        from station_territory._upstream.osmtags import is_walkable
        self.assertFalse(is_walkable({'highway':'motorway'}))
        self.assertFalse(is_walkable({'highway':'service','access':'private'}))
        self.assertTrue(is_walkable({'highway':'service','access':'private','foot':'yes'}))

    def test_input_tamper_and_path_escape_stop(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from station_territory import provenance
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'data').mkdir()
            item=root/'data/input.bin'
            item.write_bytes(b'synthetic')
            record={'files':[{'target_relative':'data/input.bin','bytes':9,'sha256':provenance.digest(item)}]}
            receipt=root/'data/input-receipt.json'
            receipt.write_text(json.dumps(record))
            with patch.object(provenance,'ROOT',root):
                provenance.verify_inputs()
                item.write_bytes(b'altered!!')
                with self.assertRaises(ValueError):provenance.verify_inputs()
                record['files'][0]['target_relative']='../outside'
                receipt.write_text(json.dumps(record))
                with self.assertRaises(ValueError):provenance.verify_inputs()

    def test_ties_preserved_at_cutoff(self):
        d=pd.DataFrame({'key':['a','b','c'],'eligible':[True]*3,'value':[10,9,9]})
        top,ties=rank(d,'value',2)
        assert top.key.tolist()==['a','b']
        assert ties.key.tolist()==['a','b','c']
        assert ties['rank'].tolist()==[1,2,2]

    def test_boundary_distance_matches_exact(self):
        geometry=shapely.box(0,0,10,10)
        points=shapely.points([5,11,0],[5,5,3])
        np.testing.assert_allclose(boundary_distance(points,geometry),[5,1,0])
        np.testing.assert_allclose(boundary_distance(points,geometry.boundary),[5,1,0])

    def test_poi_priority_and_exclusions(self):
        assert category({'amenity':'restaurant','shop':'bakery'})=='food'
        assert category({'amenity':'bench'}) is None
        assert category({'shop':'no'}) is None
        assert category({'railway':'station','shop':'yes'}) is None
        assert category({'healthcare':'clinic','amenity':'school'})=='healthcare'

    def test_way_requires_complete_topology(self):
        nodes={1:(0,0),2:(1,0),3:(1,1)}
        assert way_geom([1,2,3,1],nodes).area==.5
        assert way_geom([1,99],nodes) is None
        assert way_geom([1,2],nodes).length==1

    def test_mesh_subdivision_is_complete_without_overlap(self):
        squares=[shapely.box(*mesh_bounds('53390000'+str(a)+str(b))) for a in range(1,5) for b in range(1,5)]
        whole=shapely.union_all(squares)
        np.testing.assert_allclose(whole.bounds,[139,35+1/3,139+1/80,35+1/3+1/120],atol=1e-12)
        assert abs(sum(s.area for s in squares)-whole.area)<1e-12
        sw=mesh_bounds('5339000011');ne=mesh_bounds('5339000044')
        assert sw[0]<ne[0] and sw[1]<ne[1]

    def test_partial_mesh_retains_unassigned_area(self):
        grid=SimpleNamespace(x0=0,y0=0,cell=1.,dist=np.array([[10.,np.inf],[20.,30.]]),station=np.array([[0,-1],[1,1]]))
        # 3 m² across four cells, 1 m² unreachable; no renormalization.
        clipped=shapely.box(0,0,2,1.5)
        owners,area,distance=allocations_for_geometry(clipped,grid,np.array([0,1]))
        assert area.sum()==3
        assert area[owners==-1].sum()==1
        assert area[owners==0].sum()==1
        assert area[owners==1].sum()==1

    def test_same_name_chain_and_different_name(self):
        rows=pd.DataFrame({'group':['a','b','c','d'],'name':['A','A','A','B'], 'x':[0.,600.,1200.,0.], 'y':[0.]*4,'line':['L']*4,'operator':['O']*4})
        owners, groups=merge_groups(rows,600)
        self.assertEqual(len(groups),2)
        self.assertEqual(len(set(owners[:3])),1)
        self.assertNotEqual(owners[0],owners[3])
        self.assertIn('a|b|c',groups.key.tolist())

    def test_missing_aggregation_target_stops(self):
        bad=pd.DataFrame({'KEY_CODE':['a'],'HTKSYORI':['2'],'HTKSAKI':['b'],'GASSAN':['']})
        with self.assertRaises(ValueError):audit_secrecy(bad)

    def test_population_distance_threshold_and_missing(self):
        d=pd.DataFrame({'key':['a','b','c'],'eligible':[True]*3,'population':[999.,1000.,0.], 'population_mean_m':[300.,200.,np.nan]})
        ranked=d.assign(eligible=d.eligible & (d.population>=1000))
        self.assertEqual(rank(ranked,'population_mean_m')[0].key.tolist(),['b'])

    def test_grid_extent_does_not_silently_drop_population(self):
        g=SimpleNamespace(x0=0,y0=0,cell=1.,dist=np.array([[1.]]),station=np.array([[0]]))
        with self.assertRaises(ValueError):allocations_for_geometry(shapely.box(0,0,2,2),g,np.array([0]))
