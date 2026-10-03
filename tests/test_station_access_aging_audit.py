"""Offline checks use synthetic records and archives only."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_access_aging_audit import mesh_center, secrecy_links, census_profile, LABELS
from station_access_aging_acquire import inspect_zip, CACHE


class InputAuditTests(unittest.TestCase):
    def test_mesh_quadrants(self):
        southwest = mesh_center('5339000011')
        northeast = mesh_center('5339000044')
        self.assertAlmostEqual(southwest[0], 139 + 1 / 640)
        self.assertAlmostEqual(southwest[1], 53 * 2 / 3 + 1 / 960)
        self.assertAlmostEqual(northeast[0] - southwest[0], 3 / 320)
        self.assertAlmostEqual(northeast[1] - southwest[1], 3 / 480)
        with self.assertRaises(ValueError):
            mesh_center('5339800011')

    def test_secrecy_reference_mismatch(self):
        frame = pd.DataFrame([
            ['a', '2', 'b', ''], ['b', '1', '', 'a'],
        ], columns=['KEY_CODE', 'HTKSYORI', 'HTKSAKI', 'GASSAN'])
        self.assertEqual(secrecy_links(frame)['forward_reverse_mismatches'], 0)
        frame.loc[1, 'GASSAN'] = 'c'
        self.assertEqual(secrecy_links(frame)['forward_reverse_mismatches'], 2)
        frame.loc[0, 'HTKSAKI'] = 'missing'
        self.assertEqual(secrecy_links(frame)['missing_targets'], 1)

    def test_suppressed_age_is_not_zero(self):
        row = dict(zip(LABELS, ['20', '*', '*', '*', '8', '7']))
        row.update(KEY_CODE='5339000011', HTKSYORI='2')
        profile = census_profile(pd.DataFrame([row]))
        self.assertEqual(profile['age_suppression_pattern_errors'], 0)
        self.assertEqual(profile['nonsecret_zero_age_denominator'], 0)
        self.assertEqual(profile['institutional_households_present'], 1)

    def test_zip_paths_and_duplicate_names(self):
        CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            path = Path(directory) / 'synthetic.zip'
            for names in [['../escape.txt'], ['CON.txt'], ['a.txt', 'A.txt']]:
                with zipfile.ZipFile(path, 'w') as archive:
                    for name in names:
                        archive.writestr(name, 'synthetic')
                with self.assertRaises(ValueError):
                    inspect_zip(path)
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('nested/example.txt', 'synthetic')
            self.assertEqual(inspect_zip(path)[1], len('synthetic'))


if __name__ == '__main__':
    unittest.main()
