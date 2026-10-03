import io
import sys
import unittest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from station_access_aging_road_plan import merge_ranges,column_ranges

class RoadPlanTests(unittest.TestCase):
    def test_merge_budget_gap(self):
        self.assertEqual(merge_ranges([(20,29),(4,9),(10,19),(40,45)],gap=0),[[4,29],[40,45]])
        self.assertEqual(merge_ranges([(4,9),(14,19)],gap=4),[[4,19]])
        self.assertEqual(merge_ranges([(4,9),(15,19)],gap=4),[[4,9],[15,19]])

    def test_selected_dictionary_chunks(self):
        out=io.BytesIO()
        pq.write_table(pa.table({'id':['a','b','a','c'],'omit':[1,2,3,4]}),out,row_group_size=2)
        raw=out.getvalue(); footer=int.from_bytes(raw[-8:-4],'little')
        metadata=pq.read_metadata(io.BytesIO(raw))
        ranges=column_ranges(metadata,[1],['id'],len(raw)-footer-8)
        col=metadata.row_group(1).column(0)
        self.assertEqual(ranges,[(col.dictionary_page_offset,col.dictionary_page_offset+col.total_compressed_size-1)])
        with self.assertRaises(ValueError):column_ranges(metadata,[0],['absent'],len(raw))
        with self.assertRaises(ValueError):column_ranges(metadata,[0],['id'],4)

    def test_invalid_ranges(self):
        for ranges in [[(0,3)],[(10,9)]]:
            with self.assertRaises(ValueError):merge_ranges(ranges)

if __name__=='__main__':unittest.main()
