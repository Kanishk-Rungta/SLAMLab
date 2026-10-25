"""The display export must preserve evidence and contain paths within a run."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('experiment_export', ROOT / 'tools/export_experiment.py')
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class ExportBoundaryTests(unittest.TestCase):
    def test_decimation_retains_final_pose(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'poses.csv'
            file.write_text('timestamp,x,y,yaw\n' + ''.join(f'{i},{i},0,0\n' for i in range(19)))
            rows = export.poses(file, maximum=5)
            self.assertEqual(rows[0], [0., 0., 0., 0.])
            self.assertEqual(rows[-1], [18., 18., 0., 0.])
            self.assertLessEqual(len(rows), 6)

    def test_rejects_nonfinite_or_unordered_poses(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'poses.csv'
            for rows in ('0,nan,0,0\n1,1,0,0', '1,0,0,0\n0,1,0,0'):
                file.write_text('timestamp,x,y,yaw\n' + rows)
                with self.assertRaises(ValueError):
                    export.poses(file)

    def test_rejects_paths_outside_experiment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'run'
            root.mkdir()
            (Path(temporary) / 'outside.json').write_text('{}')
            with self.assertRaises(ValueError):
                export.safe_file(root, '../outside.json')


if __name__ == '__main__':
    unittest.main()
