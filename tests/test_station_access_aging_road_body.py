import io
import sys
import unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from station_access_aging_road_body import LocalRanges
from station_access_aging_road_plan import column_ranges,merge_ranges

class RoadBodyTests(unittest.TestCase):
    def test_decode_selected_columns_without_holes(self):
        table=pa.table({'id':['a','b','c','d'],'keep':[1,2,3,4],'omit':['private-synthetic']*4})
        sink=io.BytesIO();pq.write_table(table,sink,row_group_size=2)
        raw=sink.getvalue();length=int.from_bytes(raw[-8:-4],'little');start=len(raw)-length-8
        envelope=b'PAR1'+raw[start:];meta=pq.read_metadata(io.BytesIO(envelope))
        ranges=merge_ranges(column_ranges(meta,[1],['id','keep'],start),gap=0)
        source=LocalRanges(len(raw),[(0,b'PAR1'),(start,raw[start:])]+[(a,raw[a:b+1]) for a,b in ranges])
        reader=pq.ParquetFile(source,metadata=meta,pre_buffer=False,buffer_size=0)
        result=reader.read_row_group(1,columns=['id','keep'],use_threads=False)
        self.assertEqual(result.to_pydict(),{'id':['c','d'],'keep':[3,4]})

    def test_hole_is_error(self):
        stream=LocalRanges(20,[(0,b'abcd'),(10,b'xyz')])
        self.assertEqual(stream.read(4),b'abcd')
        with self.assertRaises(ValueError):stream.read(1)
        stream.seek(10);self.assertEqual(stream.read(3),b'xyz')
        stream.seek(0);self.assertEqual(stream.read(0),b'')
        with self.assertRaises(ValueError):stream.seek(-1)

if __name__=='__main__':unittest.main()
