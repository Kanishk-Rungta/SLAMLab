"""Fingerprint of the standard environment, recorded with every run so comparisons can be trusted.

    python standard_manifest.py --write          # (re)create standard_manifest.json after a deliberate change
    python standard_manifest.py --check OUT.json # write the current fingerprint to OUT.json; exit 1 if it differs

Covers the world, protos, robot spec, calibration, start poses, sensor model, ground truth and the
benchmark code. A run whose fingerprint differs from the manifest is not comparable with the others.
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ['webots/worlds/ab3_standard.wbt', 'webots/protos', 'robot', 'sensors/bstem_sensors.py', 'ground_truth',
         'benchmark/benchlog.py', 'benchmark/bench_supervisor.py', 'benchmark/evaluate.py', 'benchmark/evaluation',
         'benchmark/scenarios']


def digest(rel):
    path = os.path.join(ROOT, rel)
    files = [path] if os.path.isfile(path) else sorted(
        os.path.join(dp, f) for dp, _, fs in os.walk(path) for f in fs if '__pycache__' not in dp)
    h = hashlib.sha256()
    for f in files:
        h.update(os.path.relpath(f, ROOT).replace('\\', '/').encode())
        data = open(f, 'rb').read()
        if f.endswith(('.py', '.json', '.yaml', '.wbt', '.proto', '.md')):
            data = data.replace(b'\r\n', b'\n')           # line endings differ between git checkouts
        h.update(data)
    return h.hexdigest()


def current():
    return {rel: digest(rel) for rel in PARTS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', default=None)
    args = ap.parse_args()
    manifest = os.path.join(ROOT, 'standard_manifest.json')
    now = current()
    if args.write:
        json.dump(now, open(manifest, 'w'), indent=1)
        print('wrote', manifest)
        return
    ref = json.load(open(manifest)) if os.path.exists(manifest) else {}
    changed = sorted(k for k in now if ref.get(k) != now[k])
    if args.check:
        json.dump({'fingerprint': now, 'matches_standard': not changed, 'changed': changed}, open(args.check, 'w'), indent=1)
    if changed:
        print('WARNING: standard environment differs from standard_manifest.json in: %s' % ', '.join(changed))
        sys.exit(1)
    print('standard environment verified')


if __name__ == '__main__':
    main()
