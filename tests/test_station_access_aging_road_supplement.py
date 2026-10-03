import sys
import unittest
from pathlib import Path
import pyarrow as pa
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from station_access_aging_road_supplement import check_scope,select_ids,BUDGET
class SupplementTests(unittest.TestCase):
    def test_scope_limits(self):
        check_scope([{'row_groups':[0,1],'ranges':[[4,10],[20,30]]}])
        for v in [[],[{'row_groups':[0],'ranges':[[4,10],[20,30]]}],
                  [{'row_groups':[0,1],'ranges':[[4,BUDGET['body_bytes']+4],[20,30]]}]]:
            with self.assertRaises(ValueError):check_scope(v)
    def test_id_filter_and_duplicates(self):
        t=pa.table({'id':['a','b','c'],'value':[1,2,3]})
        self.assertEqual(select_ids(t,{'b','missing'})['id'].to_pylist(),['b'])
        with self.assertRaises(ValueError):select_ids(pa.table({'id':['a','a']}),{'a'})
if __name__=='__main__':unittest.main()
