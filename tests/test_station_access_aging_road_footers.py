import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_access_aging_road_footers import footer_length, candidate_groups, RangeReader, BUDGET, safe_error_reason

class RoadFooterTests(unittest.TestCase):
    def test_safe_diagnostics(self):
        self.assertEqual(safe_error_reason(ValueError('Range request budget exhausted')), 'Range request budget exhausted')
        self.assertEqual(safe_error_reason(RuntimeError('https://example.invalid/?credential=synthetic')), 'Details suppressed')

    def metadata(self, bbox, stats=True):
        table = pa.Table.from_pylist([{'bbox': bbox}])
        buffer = io.BytesIO()
        pq.write_table(table, buffer, write_statistics=stats)
        return pq.read_metadata(io.BytesIO(buffer.getvalue()))

    def test_bbox_candidates_and_missing_stats(self):
        inside = dict(xmin=139.5, xmax=139.6, ymin=35.65, ymax=35.7)
        outside = dict(xmin=140.0, xmax=141.0, ymin=36.0, ymax=37.0)
        self.assertEqual(len(candidate_groups(self.metadata(inside))), 1)
        self.assertEqual(candidate_groups(self.metadata(outside)), [])
        result = candidate_groups(self.metadata(outside, False))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['missing_bbox_stats'])

    def test_footer_envelope(self):
        buffer = io.BytesIO()
        pq.write_table(pa.table({'synthetic': [1, 2]}), buffer)
        body = buffer.getvalue()
        length = footer_length(body[-8:], len(body))
        metadata = pq.read_metadata(io.BytesIO(b'PAR1' + body[-8-length:]))
        self.assertEqual(metadata.num_rows, 2)
        for tail, size in [(b'invalid!', 100), ((100).to_bytes(4,'little')+b'PAR1', 20), ((BUDGET['footer_bytes']+1).to_bytes(4,'little')+b'PAR1', 100000000)]:
            with self.assertRaises(ValueError):
                footer_length(tail, size)

    def test_full_response_refused_before_read(self):
        report = {'requests': 0, 'body_bytes': 0}
        reader = RangeReader(report)
        response = Mock(status=200)
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        reader.opener = Mock()
        reader.opener.open.return_value = context
        with self.assertRaises(ValueError):
            reader.get({'key':'synthetic','etag':'synthetic','bytes':100}, 92, 99)
        response.read1.assert_not_called()
        self.assertEqual(report['body_bytes'], 0)

    def test_budget_refuses_request(self):
        reader = RangeReader({'requests': BUDGET['requests'], 'body_bytes': 0})
        reader.opener = Mock()
        with self.assertRaises(ValueError):
            reader.get({'key':'synthetic','etag':'synthetic','bytes':100}, 92, 99)
        reader.opener.open.assert_not_called()

if __name__ == '__main__':
    unittest.main()
