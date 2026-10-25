import { describe, it, expect } from 'vitest';
import {
  random,
  odometry,
  occupancy,
  raycast,
  features,
  poseGraph,
  graphCost,
  optimizeGraph,
  alignPoints,
  multiRobot,
  type Point,
} from './models';
import { parseTrajectory, parseOccupancy, parseReplay, poseAt } from './data';

describe('deterministic educational models', () => {
  it('replays identical seeded odometry and exactly integrates noiseless motion', () => {
    expect(odometry(42, 0.1, 0.1)).toEqual(odometry(42, 0.1, 0.1));
    expect(odometry(42, 0, 0).every((f) => f.error === 0)).toBe(true);
    expect(odometry(42, 0.1, 0.1).at(-1)!.error).toBeGreaterThan(0.01);
  });
  it('keeps RNG results bounded', () => {
    const r = random(0);
    expect(Array.from({ length: 1000 }, r).every((v) => v >= 0 && v < 1)).toBe(true);
  });
  it('intersects geometric walls and updates free/occupied log odds', () => {
    expect(
      raycast([0, 0], 0, 10, [
        [
          [2, -1],
          [2, 1],
        ],
      ]),
    ).toBe(2);
    const map = occupancy(1).at(-1)!;
    expect(map.grid.some((v) => v > 0)).toBe(true);
    expect(map.grid.some((v) => v < 0)).toBe(true);
    expect(map.grid.every((v) => Math.abs(v) <= 4)).toBe(true);
    expect(occupancy(1, 2).at(-1)!.grid).not.toEqual(map.grid);
  });
  it('matches noiseless descriptors without using ground-truth identities', () => {
    const f = features(42, 0, 0.01);
    expect(f.matches.length).toBe(15);
    expect(f.matches.every((m) => m.correct)).toBe(true);
    expect(features(42, 0.8, 2, false).matches.some((m) => !m.correct)).toBe(true);
  });
  it('optimizes measurement residuals with an anchored pose, rather than snapping to truth', () => {
    const graph = poseGraph(42),
      result = optimizeGraph(graph.initial, graph.edges);
    expect(result.poses[0]).toEqual(graph.initial[0]);
    expect(graphCost(result.poses, graph.edges)).toBeLessThan(
      graphCost(graph.initial, graph.edges) * 0.3,
    );
    expect(result.costs.every((v, i) => i === 0 || v <= result.costs[i - 1])).toBe(true);
    expect(result.poses).not.toEqual(graph.truth);
  });
  it('recovers a rigid transform from shared observations', () => {
    const maps = multiRobot(42, 0),
      alignment = alignPoints(maps.b, maps.a);
    maps.b.forEach((p, i) => {
      const q = alignment.transform(p);
      expect(q[0]).toBeCloseTo(maps.a[i][0], 10);
      expect(q[1]).toBeCloseTo(maps.a[i][1], 10);
    });
    expect(() =>
      alignPoints(
        [
          [1, 1],
          [1, 1],
        ],
        [
          [0, 0],
          [0, 0],
        ],
      ),
    ).toThrow('distinct');
    expect(() => alignPoints([[0, 0]], [[1, 1]])).toThrow('two');
    const a: Point[] = [
      [0, 0],
      [1, 0],
      [0, 1],
    ];
    expect(alignPoints(a, a).angle).toBeCloseTo(0);
  });
});

describe('local-file boundaries', () => {
  const replay = {
    schema_version: 1,
    id: 'audit',
    algorithm: 'local',
    versions: { python: '3.10' },
    robots: [
      {
        id: 'r',
        estimate: [
          [0, 0, 0, 0],
          [2, 10, 0, 0],
        ],
        reference: [],
        landmarks: [
          {
            id: 'a',
            x: 1,
            y: 2,
            covariance: [
              [0.1, 0],
              [0, 0.2],
            ],
          },
        ],
      },
    ],
  };
  it('holds the last recorded pose instead of revealing a future sample', () => {
    const poses = parseTrajectory('timestamp,x,y,yaw\n0,0,0,0\n2,10,0,0');
    expect(poseAt(poses, 0.5)).toEqual(poses[0]);
    expect(poseAt(poses, 2)).toEqual(poses[1]);
    expect(poseAt(poses, -1)).toEqual(poses[0]);
    expect(poseAt(poses, 3)).toEqual(poses[1]);
  });
  it('retains covariance and version metadata when a replay is downloaded again', () => {
    const result = parseReplay(JSON.stringify(replay));
    expect(result.robots[0].landmarks[0].covariance).toEqual([
      [0.1, 0],
      [0, 0.2],
    ]);
    expect(result).toHaveProperty('versions', { python: '3.10' });
  });
  it('rejects invalid primary metrics and unordered map checkpoints', () => {
    expect(() =>
      parseReplay(
        JSON.stringify({
          ...replay,
          robots: [{ ...replay.robots[0], metrics: { ate_m: { rmse: 'wrong' } } }],
        }),
      ),
    ).toThrow();
    expect(() =>
      parseReplay(
        JSON.stringify({
          ...replay,
          robots: [
            {
              ...replay.robots[0],
              frames: [
                { t: 2, pose: [1, 0, 0], landmarks: [] },
                { t: 1, pose: [0, 0, 0], landmarks: [] },
              ],
            },
          ],
        }),
      ),
    ).toThrow();
  });
  it('accepts the documented CSV and planar TUM formats', () => {
    expect(parseTrajectory('timestamp,x,y,yaw\n0,0,0,0\n1,1,0,0')).toHaveLength(2);
    expect(parseTrajectory('0 0 0 0 0 0 0 1\n1 1 0 0 0 0 0 1')).toHaveLength(2);
  });
  it('rejects empty, nonfinite, unordered and nonplanar data', () => {
    for (const text of [
      '',
      'timestamp,x,y,yaw\n0,0,0,0\n0,1,0,0',
      'timestamp,x,y,yaw\n0,0,0,0\n1,NaN,0,0',
      '0 0 0 0 0 0 0 1\n1 1 0 1 0 0 0 1',
    ])
      expect(() => parseTrajectory(text)).toThrow();
  });
  it('validates map shape and rejects oversized arrays', () => {
    expect(
      parseOccupancy(
        JSON.stringify({ width: 2, height: 1, resolution: 0.1, origin: [0, 0], cells: [-1, 1] }),
      ).cells,
    ).toEqual([-1, 1]);
    expect(() =>
      parseOccupancy(
        JSON.stringify({ width: 99999, height: 99999, resolution: 1, origin: [0, 0], cells: [] }),
      ),
    ).toThrow();
  });
  it('requires structured finite replay trajectories', () => {
    expect(() => parseReplay('{}')).toThrow('schema_version');
    expect(() =>
      parseReplay(
        JSON.stringify({
          schema_version: 1,
          id: 'bad',
          algorithm: 'bad',
          robots: [{ id: 'r', estimate: [[0, 1, 1, 0]], reference: [], landmarks: [] }],
        }),
      ),
    ).toThrow();
  });
  it('round trips a local trajectory without inventing reference data and rejects malformed metrics', () => {
    const value = {
      schema_version: 1,
      id: 'local',
      algorithm: 'local',
      robots: [
        {
          id: 'r',
          estimate: [
            [0, 0, 0, 0],
            [1, 1, 0, 0],
          ],
          reference: [],
          landmarks: [],
        },
      ],
    };
    expect(parseReplay(JSON.stringify(value)).robots[0].reference).toEqual([]);
    expect(() =>
      parseReplay(
        JSON.stringify({
          ...value,
          robots: [
            {
              ...value.robots[0],
              metrics: { ate_m: { rmse: 0.1 }, landmark_map: { rmse_m: 'wrong', matched: 1 } },
            },
          ],
        }),
      ),
    ).toThrow('finite');
  });
});
