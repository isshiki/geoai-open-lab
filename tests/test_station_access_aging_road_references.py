import io
import sys
import unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import LineString
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from station_access_aging_road_references import geodetic_at,matches,GEOD

class ReferenceTests(unittest.TestCase):
    def test_geodetic_endpoints_and_midpoint(self):
        line=LineString([(139,35),(139.1,35)])
        self.assertLess(GEOD.inv(139,35,*geodetic_at(line,0).coords[0])[2],0.001)
        self.assertLess(GEOD.inv(139.1,35,*geodetic_at(line,1).coords[0])[2],0.001)
        p=geodetic_at(line,0.5)
        self.assertAlmostEqual(GEOD.inv(139,35,p.x,p.y)[2],GEOD.geometry_length(line)/2,places=5)
        for at in [-1,2,float('nan')]:
            with self.assertRaises(ValueError):geodetic_at(line,at)

    def test_degenerate_line(self):
        with self.assertRaises(ValueError):geodetic_at(LineString([(139,35),(139,35)]),0.5)

    def test_envelope_selection_and_missing_stats(self):
        for stats in [True,False]:
            sink=io.BytesIO();pq.write_table(pa.Table.from_pylist([{'bbox':{'xmin':139.,'xmax':140.,'ymin':35.,'ymax':36.}}]),sink,write_statistics=stats)
            m=pq.read_metadata(io.BytesIO(sink.getvalue()))
            self.assertTrue(matches(m,0,[(139.5,35.5,139.6,35.6)]))
            self.assertEqual(matches(m,0,[(141,37,142,38)]),not stats)

if __name__=='__main__':unittest.main()
