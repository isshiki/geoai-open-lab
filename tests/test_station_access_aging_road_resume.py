import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_access_aging_road_resume import validate_saved, digest, RESUME_BUDGET
from station_access_aging_road_footers import CACHE, RELEASE, BBOX, RangeReader

class ResumeTests(unittest.TestCase):
    def fixture(self, directory):
        p=Path(directory)
        buffer=io.BytesIO()
        pq.write_table(pa.table({'synthetic':[1,2]}),buffer)
        body=buffer.getvalue(); length=int.from_bytes(body[-8:-4],'little')
        envelope=b'PAR1'+body[-8-length:]
        (p/'000.footer').write_bytes(envelope)
        inventory=p/'inventory.json'
        inventory.write_text(json.dumps({'complete':True,'release':RELEASE,'objects':[{'key':'synthetic','bytes':len(body)}]}))
        (p/'report.json').write_text(json.dumps({'release':RELEASE,'bbox':BBOX,'inventory_sha256':digest(inventory),'files':[{'key':'synthetic','footer_bytes':length,'footer_sha256':digest(p/'000.footer'),'row_groups':1}]}))
        return inventory,p

    def test_reuse_and_corruption_refusal(self):
        CACHE.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            inventory,p=self.fixture(d)
            objects,reused=validate_saved(inventory,p)
            self.assertEqual(len(reused),1)
            self.assertTrue(reused[0]['reused'])
            (p/'000.footer').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):validate_saved(inventory,p)

    def test_unrecorded_footer_and_inventory_change(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            inventory,p=self.fixture(d)
            (p/'001.footer').write_bytes(b'unrecorded')
            with self.assertRaises(ValueError):validate_saved(inventory,p)
        with tempfile.TemporaryDirectory(dir=CACHE) as d:
            inventory,p=self.fixture(d)
            inventory.write_text(inventory.read_text()+' ')
            with self.assertRaises(ValueError):validate_saved(inventory,p)

    def test_resume_byte_budget_before_network(self):
        report={'requests':0,'body_bytes':RESUME_BUDGET['body_bytes']-7}
        reader=RangeReader(report,RESUME_BUDGET)
        reader.opener=Mock()
        with self.assertRaises(ValueError):reader.get({'key':'synthetic','etag':'synthetic','bytes':100},92,99)
        reader.opener.open.assert_not_called()

if __name__=='__main__':unittest.main()
