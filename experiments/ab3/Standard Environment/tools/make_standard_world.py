"""Build the standard benchmark world: webots/worlds/ab3_standard.wbt.

AB3 first floor (tools/reference/ab3_first_floor.wbt, from the team's AB3_Webots generator), with:
  * the reference robot and gt_logger replaced by 10 BstemRobot (bstem1..bstem10) at
    robot/start_poses.json, cameras at the robot/robot_spec.json size, no controller;
  * WorldInfo.basicTimeStep = robot_spec timing.physics_step_ms;
  * the benchmark supervisor (controller "bench_supervisor").
Regenerate only if the standard itself changes (then earlier results are no longer comparable).
Algorithms never edit this world: tools/make_algorithm_world.py derives their run world from it.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    spec = json.load(open(os.path.join(ROOT, 'robot', 'robot_spec.json')))
    poses = json.load(open(os.path.join(ROOT, 'robot', 'start_poses.json')))['poses']
    text = open(os.path.join(ROOT, 'tools', 'reference', 'ab3_first_floor.wbt'), 'rb').read().decode('utf8')
    nl = '\r\n' if '\r\n' in text else '\n'
    robot = re.search(r'DEF BENCHBOT AB3BenchBot \{.*?\n\}\r?\n', text, re.S).group(0)
    st = spec['stereo']
    names = sorted(poses, key=lambda n: int(re.search(r'\d+$', n).group(0)))
    robots = ''.join('DEF %s BstemRobot {%s  translation %.3f %.3f %.3f rotation 0 0 1 %.4f%s  name "%s"%s'
                     '  cameraWidth %d cameraHeight %d%s  radioRange %.1f radioChannel %d%s}%s'
                     % (n.upper(), nl, poses[n][0], poses[n][1], spec['body']['base_origin_height_above_floor_m'],
                        poses[n][2], nl, n, nl, st['width'], st['height'], nl, spec['radio']['range_m'],
                        spec['radio']['channel'], nl, nl) for n in names)
    text = text.replace(robot, robots)
    text, n = re.subn(r'DEF GT_LOGGER Robot \{[^\n]*\n', '', text)
    assert n == 1
    text = text.replace('EXTERNPROTO "../protos/AB3BenchBot.proto"', 'EXTERNPROTO "../protos/BstemRobot.proto"')
    text, n = re.subn(r'basicTimeStep \d+', 'basicTimeStep %d' % spec['timing']['physics_step_ms'], text)
    assert n == 1
    text = text.rstrip()+nl+('DEF BENCH_SUPERVISOR Robot {%s  name "bench_supervisor"%s  controller "bench_supervisor"%s'
                             '  supervisor TRUE%s  translation 0 0 -100%s}%s' % (nl, nl, nl, nl, nl, nl))
    out = os.path.join(ROOT, 'webots', 'worlds', 'ab3_standard.wbt')
    open(out, 'wb').write(text.encode('utf8'))
    print('wrote %s with %d robots' % (out, len(names)))


if __name__ == '__main__':
    main()
