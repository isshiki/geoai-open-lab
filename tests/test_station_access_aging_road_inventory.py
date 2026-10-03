import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_access_aging_road_inventory import parse_page, PREFIXES

class RoadInventoryTests(unittest.TestCase):
    def page(self, truncated='false', extra=''):
        return (f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                f'<Prefix>{PREFIXES[0]}</Prefix><IsTruncated>{truncated}</IsTruncated>'
                f'<Contents><Key>{PREFIXES[0]}example.parquet</Key><Size>123</Size></Contents>'
                f'{extra}</ListBucketResult>').encode()

    def test_complete_and_pagination(self):
        rows, cursor = parse_page(self.page(), PREFIXES[0])
        self.assertEqual(rows[0]['bytes'], 123)
        self.assertIsNone(cursor)
        _, cursor = parse_page(self.page('true', '<NextContinuationToken>synthetic</NextContinuationToken>'), PREFIXES[0])
        self.assertEqual(cursor, 'synthetic')

    def test_refuses_missing_cursor_and_wrong_prefix(self):
        with self.assertRaises(ValueError):
            parse_page(self.page('true'), PREFIXES[0])
        with self.assertRaises(ValueError):
            parse_page(self.page(), PREFIXES[1])

    def test_refuses_negative_size_and_non_listing(self):
        with self.assertRaises(ValueError):
            parse_page(self.page().replace(b'<Size>123', b'<Size>-1'), PREFIXES[0])
        with self.assertRaises(ValueError):
            parse_page(b'<Error/>', PREFIXES[0])

if __name__ == '__main__':
    unittest.main()
