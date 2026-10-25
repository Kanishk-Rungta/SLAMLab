"""The occupancy output adapter: identical for every original-code entry, and behaving sensibly."""
import json
from pathlib import Path
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
from stereo_output import StereoMapper


def body(path):
    text = Path(path).read_text(encoding='utf-8')
    return text[text.index('"""', 3) + 3:]


class StereoOutputTests(unittest.TestCase):
    def test_all_copies_are_identical(self):
        reference = body(HERE / 'stereo_output.py')
        for pkg in ('D2 Slam', 'Door Slam'):
            self.assertEqual(body(HERE.parent / pkg / 'bridge/mapping.py'), reference, pkg)

    def test_depth_limit_follows_measured_noise(self):
        spec = json.loads((HERE.parent / 'Standard Environment/robot/robot_spec.json').read_text(encoding='utf-8-sig'))
        mapper = StereoMapper(spec['stereo'], {'map_resolution_m': .05, 'map_size_m': 4})
        mapper.sigma_d = .25
        z_quarter = mapper.max_depth()
        mapper.sigma_d = 1.
        self.assertAlmostEqual(z_quarter / mapper.max_depth(), 2., places=6)   # z ~ 1/sqrt(sigma_d)
        sigma_z = z_quarter ** 2 * .25 / mapper.fb
        self.assertAlmostEqual(sigma_z, .05, places=6)                          # one map cell

    def test_free_ray_and_hit_cell(self):
        spec = json.loads((HERE.parent / 'Standard Environment/robot/robot_spec.json').read_text(encoding='utf-8-sig'))
        mapper = StereoMapper(spec['stereo'], {'map_resolution_m': .1, 'map_size_m': 4})
        mapper.keyframes['a'] = [(0., 0., 1., 0., 1)]
        grid = mapper.rebuild({'a': [0., 0., 0.]})
        size = mapper.size
        self.assertEqual(grid[size // 2, size // 2 + 10], 1)                    # wall 1 m ahead
        self.assertEqual(grid[size // 2, size // 2 + 5], 0)                     # free in between
        self.assertEqual(grid[size // 2 + 5, size // 2], -1)                    # unseen stays unknown


if __name__ == '__main__':
    unittest.main()
