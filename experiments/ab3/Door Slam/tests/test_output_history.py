"""Archive checks without Webots or native ROS."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tools/live_view.py'
spec = importlib.util.spec_from_file_location('door_original_live_view', SOURCE)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class OutputHistoryTests(unittest.TestCase):
    def test_final_refresh_retains_both_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            viewer.render(run, 1)
            viewer.render(run, 1, final=True)
            self.assertEqual(len(list((run/'robots_overview_history').glob('*.png'))), 2)
            self.assertEqual((run/'robots_overview.png').read_bytes(),
                             (run/'final_robots_overview.png').read_bytes())
