"""Output-only overview of native D2SLAM local maps, in their estimated coordinate frame."""
import argparse
from pathlib import Path
import shutil
import time
import cv2
import numpy as np


def render(run, robots, final=False):
    columns = min(3, robots)
    rows = (robots+columns-1)//columns
    canvas = np.full((rows*360+50, columns*640, 3), 245, np.uint8)
    cv2.putText(canvas, 'Original D2SLAM (stereo + IMU) | estimated frames | ground-truth alignment in final report',
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, .5, (20, 20, 20), 1)
    for index in range(robots):
        path = run/('robot_%d' % (index+1))/'live_map.png'
        image = cv2.imread(str(path)) if path.exists() else None
        y, x = (index//columns)*360+50, (index % columns)*640
        if image is None:
            cv2.putText(canvas, 'Robot %d: awaiting native initialization' % (index+1), (x+15, y+40),
                        cv2.FONT_HERSHEY_SIMPLEX, .6, (40, 40, 40), 1)
        else:
            scale = min(640/image.shape[1], 360/image.shape[0])
            image = cv2.resize(image, None, fx=scale, fy=scale)
            canvas[y:y+image.shape[0], x:x+image.shape[1]] = image
    # overview.png is the AB3-layout overview from the benchmark recordings (run_outputs.py);
    # this tiled grid of the robots' own maps is kept as robots_overview.png with its own history.
    tmp = run/'robots_overview.tmp.png'
    if not cv2.imwrite(str(tmp), canvas):
        raise OSError('Could not write overview image')
    tmp.replace(run/'robots_overview.png')
    if final:
        shutil.copyfile(run/'robots_overview.png', run/'final_robots_overview.png')
    history = run/'robots_overview_history'
    history.mkdir(exist_ok=True)
    shutil.copyfile(run/'robots_overview.png', history/('robots_overview_%d.png' % time.time_ns()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--robots', type=int, required=True)
    parser.add_argument('--period', type=float, default=300)
    args = parser.parse_args()
    next_draw = 0.
    while not (args.run/'VIEW_STOP').exists():
        if time.monotonic() >= next_draw:
            render(args.run, args.robots)
            next_draw = time.monotonic()+args.period
        time.sleep(.5)
    render(args.run, args.robots, final=True)
