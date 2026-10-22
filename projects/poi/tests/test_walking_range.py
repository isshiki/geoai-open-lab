import json
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
from geoai_open_lab.walking_range import snap,routing,poi_distance,reachable_intervals,OUT,run

class WalkingTests(unittest.TestCase):
    def edges(self):
        return [dict(u=1,v=2,line=LineString([(0,0),(100,0)])),dict(u=2,v=3,line=LineString([(100,0),(100,100)])),dict(u=4,v=5,line=LineString([(0,30),(100,30)]))]
    def test_same_edge_direct_and_connectors(self):
        e=self.edges();d,p,o=routing(e,(40,-10))
        value,status=poi_distance(e,d,o,snap(e,[Point(60,-5)])[0])
        self.assertEqual(status,'connected');self.assertAlmostEqual(value,35)
    def test_turn_and_undirected_route(self):
        e=self.edges();d,p,o=routing(e,(0,0))
        self.assertEqual(poi_distance(e,d,o,(1,5,80))[0],185)
        d,p,o=routing(e,(100,100));self.assertEqual(poi_distance(e,d,o,(0,0,0))[0],200)
    def test_disconnected_not_moved_to_reachable_edge(self):
        e=self.edges();d,p,o=routing(e,(0,0));self.assertEqual(poi_distance(e,d,o,snap(e,[Point(50,29)])[0])[1],'disconnected')
    def test_limit_and_station_rejection(self):
        e=self.edges();d,p,o=routing(e,(0,0))
        self.assertEqual(poi_distance(e,d,o,(0,101,20))[1],'connector_over_limit')
        with self.assertRaises(ValueError):routing(e,(1000,1000))
    def test_tie_stable(self):
        self.assertEqual(snap(self.edges(),[Point(50,15)])[0][0],0)
    def test_partial_edge_union(self):
        edge=self.edges()[0]
        self.assertEqual(reachable_intervals(edge,{1:0,2:0},60),[(0,100)])
        self.assertEqual(reachable_intervals(edge,{},20,(5,50)),[(35,65)])
        self.assertEqual(reachable_intervals(edge,{1:0},40),[(0,40)])
        self.assertEqual(reachable_intervals(edge,{},20),[])
    def test_saved_replay_and_memberships(self):
        if not (OUT/'manifest.json').exists():self.skipTest('Local saved inputs absent')
        before=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory(dir=OUT.parent) as folder,patch('geoai_open_lab.walking_range.OUT',Path(folder)):
            s,o,m,out=run()
            self.assertEqual(before['output_sha256'],m['output_sha256'])
            f=pd.read_csv(out/'pois.csv')
            self.assertTrue(f.id.is_unique)
            self.assertTrue((~f.walk5|f.walk10).all())
            self.assertTrue((~f.walk5|f.circle).all())
            self.assertEqual(s.loc[s.condition.eq('square'),'poi_count'].iloc[0],3591)
            self.assertTrue(np.allclose(s.filter(like='_share').sum(axis=1),1))
            for r in o.itertuples():
                self.assertEqual(r.shared,int((f[r.first]&f[r.second]).sum()))
                self.assertAlmostEqual(r.jaccard,r.shared/r.union)
            for r in s.itertuples():self.assertEqual(r.poi_count,int(f[r.condition].sum()))


class FixedInputTests(unittest.TestCase):
    def test_row_indices_are_not_node_ids(self):
        from geoai_open_lab.walking_inputs import select_edges
        n=pd.DataFrame({'node_id':[901,100,777],'x':[-2000.,2000.,0.],'y':[0.,0.,5000.]})
        e=pd.DataFrame({'u':[0],'v':[1],'length_m':[4000.]})
        result,zero=select_edges(n,e,(0,0))
        self.assertEqual((result.u.iloc[0],result.v.iloc[0]),(100,901))
        self.assertEqual(len(result),1) # crossing edge: both endpoints outside still retained
        self.assertEqual(zero,0)
    def test_bad_indices_and_lengths_rejected(self):
        from geoai_open_lab.walking_inputs import select_edges
        n=pd.DataFrame({'node_id':[91,92],'x':[0.,100.],'y':[0.,0.]})
        with self.assertRaises(ValueError):select_edges(n,pd.DataFrame({'u':[91],'v':[92],'length_m':[100.]}),(0,0))
        with self.assertRaises(ValueError):select_edges(n,pd.DataFrame({'u':[0],'v':[1],'length_m':[99.]}),(0,0))
    def test_real_distances_against_subdivided_graph(self):
        import networkx as nx
        from geoai_open_lab.walking_inputs import load_fixed_roads
        if not (OUT/'manifest.json').exists():self.skipTest('Saved results absent')
        m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'));edges,_=load_fixed_roads(m['center'])
        f=pd.read_csv(OUT/'pois.csv');g=nx.Graph();physical=[]
        for i,e in enumerate(edges):
            points=[(0,e['u']),(e['line'].length,e['v'])]
            if i==m['source_edge_index']:points.append((m['source_position_m'],'origin'))
            for row in f[f.edge_index.eq(i)&f.connector_m.le(100)].itertuples():points.append((row.position_m,'poi-'+str(row.Index)))
            points.sort(key=lambda p:(p[0],str(p[1])))
            for a,b in zip(points,points[1:]):g.add_edge(a[1],b[1],weight=b[0]-a[0]);physical.append((a[1],b[1],b[0]-a[0]))
        g.add_edge('start','origin',weight=m['source_snap_m'])
        d=nx.single_source_dijkstra_path_length(g,'start',weight='weight')
        for r in f.itertuples():
            expected=d.get('poi-'+str(r.Index),np.inf)+r.connector_m
            if r.connector_m>100 or not np.isfinite(expected):self.assertTrue(np.isnan(r.road_distance_m))
            else:self.assertAlmostEqual(expected,r.road_distance_m,places=6)
        summary=pd.read_csv(OUT/'summary.csv').set_index('condition')
        for budget,condition in [(400,'walk5'),(800,'walk10')]:
            total=sum(min(length,max(0,budget-d.get(u,np.inf))+max(0,budget-d.get(v,np.inf))) for u,v,length in physical)
            self.assertAlmostEqual(total,summary.loc[condition,'road_length_m'],places=6)

    def test_article_values_and_public_notebook(self):
        from geoai_open_lab.walking_range import ROOT
        import xml.etree.ElementTree as ET
        import nbformat
        if not (OUT/'summary.csv').exists():self.skipTest('Saved results absent')
        summary=pd.read_csv(OUT/'summary.csv')
        handoff=(ROOT/'docs/walking-range-article-handoff.md').read_text(encoding='utf8')
        texts=[''.join(ET.parse(OUT/(n+'.svg')).getroot().itertext()) for n in ['ranges','composition','conditions','cover_1600x900']]
        for r in summary.itertuples():
            self.assertIn(f'{r.poi_count:,}',handoff)
            for t in texts:self.assertIn(f'{r.poi_count:,}',t)
        nb=nbformat.read(ROOT/'notebooks/11_walking_range.ipynb',4);nbformat.validate(nb)
        for cell in nb.cells:
            self.assertFalse(cell.get('outputs'));self.assertIsNone(cell.get('execution_count'));self.assertFalse(cell.get('attachments'))

if __name__=='__main__':unittest.main()
