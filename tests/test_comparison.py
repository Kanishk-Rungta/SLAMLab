"""Refuse incompatible metric reports before presenting side-by-side values."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('slamlab_comparison', Path(__file__).resolve().parents[1] / 'benchmarks/evaluation/compare_reports.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class ComparisonTests(unittest.TestCase):
    def report(self):
        return {'experiment': {'algorithm': 'Synthetic', 'version': '1', 'kind': 'synthetic_fixture',
                'environment': 'analytic', 'robot_count': 1, 'dataset': 'square', 'configuration': {}},
                'alignment': {'mode': 'none'}, 'association': {'tolerance_s': .02, 'matched': 5,
                'estimated_fraction': 1., 'reference_fraction': 1.}, 'rpe_delta_s': 1., 'rpe_tolerance_s': .05,
                'inputs': {'reference': {'sha256': 'a' * 64}}, 'ate_m': {'rmse': .1}, 'rpe': None}

    def test_matching_reports_export_tables_with_missing_metric_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / 'a.json', root / 'b.json']
            for path in paths:
                path.write_text(json.dumps(self.report()))
            comparison.compare(paths, root / 'tables')
            self.assertIn('unavailable', (root / 'tables/comparison.csv').read_text())
            self.assertIn('No ranking is inferred', (root / 'tables/comparison.md').read_text())

    def test_changed_dataset_alignment_kind_or_configuration_is_rejected(self):
        for block, key, value in [('experiment', 'dataset', 'other'), ('alignment', 'mode', 'se2'),
                                   ('experiment', 'kind', 'simulation_measurement'),
                                   ('experiment', 'configuration', {'sensors': 'different'})]:
            with tempfile.TemporaryDirectory() as directory, self.subTest(key=key):
                root = Path(directory)
                original, changed = self.report(), copy.deepcopy(self.report())
                changed[block][key] = value
                paths = [root / 'a.json', root / 'b.json']
                paths[0].write_text(json.dumps(original))
                paths[1].write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    comparison.compare(paths, root / 'tables')
                self.assertFalse((root / 'tables').exists())


if __name__ == '__main__':
    unittest.main()
