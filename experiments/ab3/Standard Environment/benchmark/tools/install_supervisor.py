"""Add the benchmark supervisor to a Webots project (and optionally to a world).

    python tools/install_supervisor.py --project PATH/TO/WEBOTS_PROJECT [--world worlds/x.wbt]

Creates PROJECT/controllers/bench_supervisor/bench_supervisor.py (a wrapper that runs this
package's bench_supervisor.py) and, with --world, writes worlds/x_bench.wbt: the same world with
`DEF BENCH_SUPERVISOR Robot { name "bench_supervisor" controller "bench_supervisor" supervisor TRUE }`
appended. The original world is not modified.
"""
import argparse
import os

WRAPPER = '''r"""Wrapper: runs the SLAM benchmark supervisor from {package}."""
import os
import sys
import traceback
sys.path.insert(0, r"{package}")
try:
    from bench_supervisor import Collector
    Collector().run()
except Exception:
    # Webots hides controller output in batch mode: keep the traceback with the run.
    run_dir = os.environ.get('SLAM_BENCH_RUN_DIR', os.getcwd())
    with open(os.path.join(run_dir, 'supervisor_error.txt'), 'a') as f:
        f.write(traceback.format_exc())
    raise
'''
NODE = 'DEF BENCH_SUPERVISOR Robot {{{nl}  name "bench_supervisor"{nl}  controller "bench_supervisor"{nl}  supervisor TRUE{nl}  translation 0 0 -100{nl}}}{nl}'


def main():
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--world', default=None, help='world file relative to the project')
    args = ap.parse_args()
    ctrl = os.path.join(args.project, 'controllers', 'bench_supervisor')
    os.makedirs(ctrl, exist_ok=True)
    with open(os.path.join(ctrl, 'bench_supervisor.py'), 'w') as f:
        f.write(WRAPPER.format(package=package))
    print('wrote', os.path.join(ctrl, 'bench_supervisor.py'))
    if args.world:
        src = os.path.join(args.project, args.world)
        text = open(src, 'rb').read().decode('utf8')
        if 'controller "bench_supervisor"' not in text:
            nl = '\r\n' if '\r\n' in text else '\n'
            text = text.rstrip()+nl+NODE.format(nl=nl)
        out = src[:-4]+'_bench.wbt'
        open(out, 'wb').write(text.encode('utf8'))
        print('wrote', out)


if __name__ == '__main__':
    main()
