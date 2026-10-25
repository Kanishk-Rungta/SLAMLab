"""Derive an algorithm's run world from the standard world, changing only the robots' controller.

    python make_algorithm_world.py --controller custom_slam [--robots 10]

Writes webots/worlds/ab3_standard__<controller>.wbt. Everything else is byte-identical to
ab3_standard.wbt (checked), so every algorithm runs in exactly the same environment. With
--robots N < 10, robots N+1..10 are removed (for scalability runs); their start poses are unchanged.
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--controller', required=True)
    ap.add_argument('--robots', type=int, default=10)
    args = ap.parse_args()
    src = os.path.join(ROOT, 'webots', 'worlds', 'ab3_standard.wbt')
    text = open(src, 'rb').read().decode('utf8')
    nl = '\r\n' if '\r\n' in text else '\n'
    blocks = list(re.finditer(r'DEF BSTEM(\d+) BstemRobot \{.*?\n\}\r?\n', text, re.S))
    if not blocks:
        raise SystemExit('no BstemRobot found in the standard world')
    out_text = text
    for b in reversed(blocks):
        number = int(b.group(1))
        block = b.group(0)
        if number > args.robots:
            new = ''
        else:
            new = block.replace('  name "bstem%d"%s' % (number, nl),
                                '  name "bstem%d"%s  controller "%s"%s' % (number, nl, args.controller, nl), 1)
            assert new != block
        out_text = out_text[:b.start()]+new+out_text[b.end():]
    # Safety: removing the inserted controller lines must give back the standard world (minus removed robots).
    check = re.sub(r'  controller "%s"\r?\n' % re.escape(args.controller), '', out_text)
    kept = text
    for b in reversed(blocks):
        if int(b.group(1)) > args.robots:
            kept = kept[:b.start()]+kept[b.end():]
    assert check == kept, 'derived world differs from the standard world'
    out = os.path.join(ROOT, 'webots', 'worlds', 'ab3_standard__%s.wbt' % args.controller)
    open(out, 'wb').write(out_text.encode('utf8'))
    print(out)


if __name__ == '__main__':
    main()
