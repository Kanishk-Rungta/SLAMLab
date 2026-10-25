"""End-to-end check of the evaluator on a synthetic run with known answers (no Webots needed)."""
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import benchlog
import evaluate
import compare


def straight_then_back(t):
    """Ground truth: 10 m east along y=0 in 50 s, then back west, at 0.2 m/s (a revisit)."""
    x = np.where(t <= 50, .2*t, 10-.2*(t-50))
    yaw = np.where(t <= 50, 0., math.pi)
    return x, np.zeros_like(t), yaw


class SyntheticRun(object):
    def __init__(self, path, bias=0.1, lose=True):
        self.dir = path
        t = np.arange(0, 100.01, .1)
        x1, y1, yaw1 = straight_then_back(t)
        with open(os.path.join(path, 'ground_truth.jsonl'), 'w') as f:
            for k in range(len(t)):
                f.write(json.dumps({'t': t[k], 'p': {'r1': [x1[k], y1[k], 0.05, yaw1[k]],
                                                       'r2': [x1[k], y1[k]+1.0, 0.05, yaw1[k]]}})+'\n')
        with open(os.path.join(path, 'supervisor.jsonl'), 'w') as f:
            for k in range(1, 101):
                f.write(json.dumps({'type': 'rtf', 't': float(k), 'rtf': 0.5, 'wall': 1000.+2*k})+'\n')
            f.write(json.dumps({'type': 'collision', 't': 30., 'robot': 'r1', 'wall': 1060.})+'\n')
        json.dump({'robots': ['r1', 'r2'], 'scenario': {'name': 'baseline'}, 'start_wall': 1000.},
                  open(os.path.join(path, 'run_meta.json'), 'w'))
        os.environ['SLAM_BENCH_RUN_DIR'] = path
        for name, dy in (('r1', 0.), ('r2', 1.)):
            log = benchlog.BenchLog(name, 'Synthetic', frame='world', resource_period=0)
            log.initialized(1.0)
            for k in range(10, len(t), 2):                  # 5 Hz from t=1 s
                if lose and name == 'r1' and 40 <= t[k] < 45:
                    continue                                 # no output while lost
                log.pose(t[k], x1[k]+bias, y1[k]+dy, yaw1[k], odometry=(x1[k]+3*bias, y1[k]+dy, yaw1[k]))
                if k % 10 == 0:
                    log.frame(t[k], 0.02)
            if lose and name == 'r1':
                log.tracking(1.0, 'ok')
                log.tracking(40.0, 'lost')
                log.tracking(45.0, 'ok')
            log.optimization(60.0, 0.5)
            # Loop at t=90 (x=2) matching t=10 (x=2): a true loop; and a false one at t=70.
            if name == 'r1':
                log.loop(90.0, True, 'r1', 10.0, relative=(0., 0., math.pi))
                log.loop(70.0, True, 'r1', 20.0, relative=(0., 0., 0.))      # true relative is (2,0,pi): false
                log.loop(75.0, False, 'r1', 5.0, relative=(5., 0., 0.))      # rejected, also false: true negative
            # Messages: r1 sends 10; r2 receives 9 of them (one lost).
            for k in range(10):
                payload = ('msg-%s-%d' % (name, k)).encode()
                log.send(10.+k, payload)
                other = 'r2' if name == 'r1' else 'r1'
                if not (name == 'r1' and k == 3):
                    rx = benchlog.BenchLog(other, 'Synthetic', frame='world', resource_period=0)
                    rx.recv(10.2+k, payload, source=name)
                    rx.close()
            # A map snapshot: free floor along the corridor, walls at y = dy +/- 0.5.
            cells = np.full((40, 240), -1, np.int8)            # 0.05 m cells, origin (-1, dy-1)
            cells[12:29, 20:220] = 0
            cells[10, 20:220] = 1
            cells[30, 20:220] = 1
            log.map(100.0, cells, 0.05, (-1.0, dy-1.0))
            if name == 'r1':                                  # a retransmission of an earlier payload
                log.send(60.0, b'msg-r1-0')
                rx = benchlog.BenchLog('r2', 'Synthetic', frame='world', resource_period=0)
                rx.recv(60.2, b'msg-r1-0', source='r1')
                rx.close()
            log.close()


def ground_truth_map(path):
    occupied = np.zeros((80, 300), bool)                       # origin (-2, -2), 0.05 m
    floor = np.zeros_like(occupied)
    for dy in (0., 1.):
        r0 = int((dy-.5+2)/.05)
        r1 = int((dy+.5+2)/.05)
        occupied[r0, 20:260] = True
        occupied[r1, 20:260] = True
        floor[r0+1:r1, 20:260] = True
    np.savez(path, occupied=occupied, floor=floor, resolution=0.05, origin=np.array([-2., -2.]))


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.run_dir = os.path.join(cls.tmp, 'run_a')
        os.makedirs(cls.run_dir)
        SyntheticRun(cls.run_dir)
        cls.gt = os.path.join(cls.tmp, 'gt.npz')
        ground_truth_map(cls.gt)
        cls.m = evaluate.evaluate(cls.run_dir, cls.gt)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_ate_equals_known_bias(self):
        self.assertAlmostEqual(self.m['summary']['ate_rmse_m'], 0.1, places=3)
        self.assertAlmostEqual(self.m['summary']['improvement_over_odometry_x'], 3.0, places=2)

    def test_rpe_of_constant_bias_is_zero(self):
        self.assertLess(self.m['summary']['rpe_1m_trans_pct'], 1e-6)

    def test_tracking_loss_and_recovery(self):
        r1 = self.m['tracking']['per_robot']['r1']
        self.assertEqual(r1['tracking_losses'], 1)
        self.assertAlmostEqual(r1['recovery_time_s']['mean'], 5.0)
        self.assertAlmostEqual(r1['initialization_time_s'], 1.0)

    def test_success_rate_counts_lost_time(self):
        r1 = self.m['trajectory']['per_robot']['r1']['localization_success_rate']
        r2 = self.m['trajectory']['per_robot']['r2']['localization_success_rate']
        self.assertLess(r1, r2)
        self.assertGreater(r2, .95)

    def test_loop_precision_and_accuracy(self):
        lc = self.m['loop_closure']
        self.assertEqual(lc['true_positives'], 1)
        self.assertEqual(lc['false_positives'], 1)
        self.assertAlmostEqual(lc['precision'], .5)
        self.assertAlmostEqual(lc['detection_accuracy'], 2/3.)
        self.assertIsNotNone(lc['recall'])
        self.assertAlmostEqual(lc['correction']['mean_gain_m'], 0., places=6)   # constant bias: nothing corrected

    def test_packet_loss_and_latency(self):
        cm = self.m['communication']
        self.assertAlmostEqual(cm['packet_loss_rate'], 1/20.)
        self.assertAlmostEqual(cm['latency_s']['mean'], 0.2, places=6)

    def test_map_metrics(self):
        sw = self.m['mapping']['swarm']
        self.assertGreater(sw['occupied_precision'], .9)
        self.assertGreater(sw['coverage_m2'], 10)
        self.assertLess(sw['reconstruction_error_m']['chamfer_m'], .1)

    def test_rtf_collisions_and_failures(self):
        s = self.m['summary']
        self.assertAlmostEqual(self.m['real_time']['rtf_samples']['mean'], .5)
        self.assertEqual(self.m['stability']['collisions_total'], 1)
        self.assertEqual(s['slam_failure_rate'], 0.)

    def test_compare_writes_tables(self):
        out = os.path.join(self.tmp, 'cmp')
        sys.argv = ['compare.py', self.run_dir, '--out', out]
        compare.main()
        for name in ('comparison.md', 'comparison.csv', 'robustness.md', 'scalability.md'):
            self.assertTrue(os.path.exists(os.path.join(out, name)))


if __name__ == '__main__':
    unittest.main()
