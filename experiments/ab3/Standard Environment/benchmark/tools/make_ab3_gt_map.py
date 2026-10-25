"""Convert the AB3 layout raster (bstem_slam/worlds/ab3_layout.npz) into a benchmark ground-truth map.

Walls, partitions, parapets and stair blocks are the structure every algorithm must map ("occupied");
furniture is "ignore" (camera-height dependent: neither rewarded nor penalised); floor is the
first-floor slab. Output origin is the lower-left corner of cell [0, 0] in world coordinates.

    python tools/make_ab3_gt_map.py --layout ../bstem_slam/worlds/ab3_layout.npz --out ab3_gt_map.npz
"""
import argparse
import json
import os
import numpy as np


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', default=os.path.join(here, '..', 'bstem_slam', 'worlds', 'ab3_layout.npz'))
    ap.add_argument('--out', default=os.path.join(here, 'ground_truth', 'ab3_gt_map.npz'))
    args = ap.parse_args()
    d = np.load(args.layout)
    res = float(d['resolution'])
    center = np.asarray(d['origin'], float)          # layout grids are centred on map_origin_world
    h, w = d['floor'].shape
    origin = center-np.array([w//2, h//2])*res
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.savez_compressed(args.out, occupied=d['walls'], floor=d['floor'], ignore=d['furniture'],
                        resolution=res, origin=origin)
    print('wrote %s: %dx%d cells at %.2f m, origin %s, floor %.0f m2' %
          (args.out, w, h, res, origin.round(3).tolist(), d['floor'].sum()*res*res))


if __name__ == '__main__':
    main()
