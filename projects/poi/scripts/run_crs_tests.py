"""Run the complete existing suite with MAUP's legacy writer isolated."""
from pathlib import Path
from unittest.mock import patch
import shutil
import tempfile
import unittest
from geoai_open_lab import maup
from geoai_open_lab.crs_experiment import ROOT

scratch=ROOT/'data/cache/crs'
scratch.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(dir=scratch) as temp:
    isolated=Path(temp)/'maup'
    if maup.OUT.exists():shutil.copytree(maup.OUT,isolated)
    else:isolated.mkdir()
    with patch.object(maup,'OUT',isolated):
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
