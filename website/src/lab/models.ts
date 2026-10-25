export type Pose = [number, number, number];
export type Point = [number, number];
export const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

export function random(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function gaussian(rng: () => number) {
  return Math.sqrt(-2 * Math.log(Math.max(rng(), 1e-12))) * Math.cos(2 * Math.PI * rng());
}

export function move(p: Pose, distance: number, turn: number): Pose {
  const heading = p[2] + turn / 2;
  return [
    p[0] + distance * Math.cos(heading),
    p[1] + distance * Math.sin(heading),
    wrap(p[2] + turn),
  ];
}

export function odometry(
  seed: number,
  translationNoise = 0.04,
  rotationNoise = 0.035,
  speed = 0.45,
) {
  const rng = random(seed),
    frames = [];
  let truth: Pose = [-2.2, -1.1, 0.3],
    estimate: Pose = [...truth],
    length = 0;
  const dt = 0.08;
  for (let i = 0; i <= 280; i++) {
    frames.push({
      truth,
      estimate,
      t: i * dt,
      error: Math.hypot(estimate[0] - truth[0], estimate[1] - truth[1]),
      length,
    });
    const turn = (0.25 + 0.22 * Math.sin(i * 0.025)) * dt,
      distance = speed * dt;
    truth = move(truth, distance, turn);
    estimate = move(
      estimate,
      distance + gaussian(rng) * translationNoise * Math.sqrt(dt),
      turn + gaussian(rng) * rotationNoise * Math.sqrt(dt),
    );
    length += distance;
  }
  return frames;
}

export type Segment = [Point, Point];
export const walls: Segment[] = [
  [
    [-3.6, -3.6],
    [3.6, -3.6],
  ],
  [
    [3.6, -3.6],
    [3.6, 3.6],
  ],
  [
    [3.6, 3.6],
    [-3.6, 3.6],
  ],
  [
    [-3.6, 3.6],
    [-3.6, -3.6],
  ],
  [
    [-1.1, -0.8],
    [-1.1, 1],
  ],
  [
    [-1.1, 1],
    [0.4, 1],
  ],
  [
    [1.8, -2],
    [2.8, -2],
  ],
  [
    [2.8, -2],
    [2.8, -0.8],
  ],
];

export function raycast(p: Point, angle: number, maximum: number, segments = walls) {
  const direction: Point = [Math.cos(angle), Math.sin(angle)];
  let best = maximum;
  for (const [a, b] of segments) {
    const v: Point = [b[0] - a[0], b[1] - a[1]],
      q: Point = [a[0] - p[0], a[1] - p[1]];
    const cross = direction[0] * v[1] - direction[1] * v[0];
    if (Math.abs(cross) < 1e-9) continue;
    const t = (q[0] * v[1] - q[1] * v[0]) / cross;
    const u = (q[0] * direction[1] - q[1] * direction[0]) / cross;
    if (t >= 0 && u >= 0 && u <= 1) best = Math.min(best, t);
  }
  return best;
}

export function gridLine(x0: number, y0: number, x1: number, y1: number): Point[] {
  const cells: Point[] = [],
    dx = Math.abs(x1 - x0),
    sx = x0 < x1 ? 1 : -1,
    dy = -Math.abs(y1 - y0),
    sy = y0 < y1 ? 1 : -1;
  let error = dx + dy;
  for (let guard = 0; guard < 1000; guard++) {
    cells.push([x0, y0]);
    if (x0 === x1 && y0 === y1) break;
    const twice = 2 * error;
    if (twice >= dy) {
      error += dy;
      x0 += sx;
    }
    if (twice <= dx) {
      error += dx;
      y0 += sy;
    }
  }
  return cells;
}

export function occupancy(seed: number, maximum = 4, noise = 0.03, resolution = 0.2) {
  const rng = random(seed),
    width = Math.round(8 / resolution),
    actualResolution = 8 / width;
  const grid = new Float64Array(width * width),
    frames = [];
  const cell = (v: number) => Math.floor((v + 4) / actualResolution);
  for (let i = 0; i < 80; i++) {
    const a = i * 0.065,
      pose: Pose = [1.5 * Math.cos(a), 1.5 * Math.sin(a), a + Math.PI / 2];
    const rays = [];
    for (let beam = 0; beam < 36; beam++) {
      const angle = pose[2] + (beam / 36) * Math.PI * 2;
      const distance = raycast([pose[0], pose[1]], angle, maximum);
      const measured = Math.max(0.05, Math.min(maximum, distance + gaussian(rng) * noise));
      const end: Point = [
        pose[0] + measured * Math.cos(angle),
        pose[1] + measured * Math.sin(angle),
      ];
      const cells = gridLine(cell(pose[0]), cell(pose[1]), cell(end[0]), cell(end[1]));
      cells.forEach(([x, y], j) => {
        if (x < 0 || x >= width || y < 0 || y >= width) return;
        const occupied = j === cells.length - 1 && distance < maximum - 0.01;
        grid[y * width + x] = Math.max(
          -4,
          Math.min(4, grid[y * width + x] + (occupied ? 0.85 : -0.62)),
        );
      });
      rays.push(end);
    }
    frames.push({ pose, rays, grid: Array.from(grid), width, resolution: actualResolution });
  }
  return frames;
}

export type Feature = { point: Point; descriptor: number[]; identity: number };
export const featureScene: { point: Point; name: string }[] = [
  { point: [0.12, 0.18], name: 'Left window, upper-left corner' },
  { point: [0.34, 0.18], name: 'Left window, upper-right corner' },
  { point: [0.34, 0.48], name: 'Left window, lower-right corner' },
  { point: [0.12, 0.48], name: 'Left window, lower-left corner' },
  { point: [0.66, 0.18], name: 'Right window, upper-left corner' },
  { point: [0.88, 0.18], name: 'Right window, upper-right corner' },
  { point: [0.88, 0.48], name: 'Right window, lower-right corner' },
  { point: [0.66, 0.48], name: 'Right window, lower-left corner' },
  { point: [0.42, 0.5], name: 'Door, upper-left corner' },
  { point: [0.59, 0.5], name: 'Door, upper-right corner' },
  { point: [0.59, 0.94], name: 'Door, lower-right corner' },
  { point: [0.42, 0.94], name: 'Door, lower-left corner' },
  { point: [0.12, 0.68], name: 'Wall panel, upper-left corner' },
  { point: [0.31, 0.68], name: 'Wall panel, upper-right corner' },
  { point: [0.31, 0.84], name: 'Wall panel, lower-right corner' },
  { point: [0.12, 0.84], name: 'Wall panel, lower-left corner' },
  { point: [0.72, 0.75], name: 'Notice board, left corner' },
  { point: [0.89, 0.75], name: 'Notice board, right corner' },
];
export const descriptorDistance = (a: Feature, b: Feature) =>
  Math.hypot(...a.descriptor.map((v, i) => v - b.descriptor[i]));
export function features(seed: number, noise = 0.2, threshold = 0.65, mutual = true) {
  const rng = random(seed);
  const left: Feature[] = Array.from({ length: 18 }, (_, i) => ({
    point: [...featureScene[i].point] as Point,
    descriptor: Array.from({ length: 6 }, () => rng()),
    identity: i,
  }));
  const right = left
    .filter((_, i) => i % 6 !== 0)
    .map((f) => ({
      point: [
        Math.min(0.96, Math.max(0.04, f.point[0] - 0.045 + gaussian(rng) * noise * 0.035)),
        Math.min(0.96, Math.max(0.04, f.point[1] + 0.015 + gaussian(rng) * noise * 0.035)),
      ] as Point,
      descriptor: f.descriptor.map((d) => d + gaussian(rng) * noise),
      identity: f.identity,
    }));
  for (let i = 0; i < 6; i++)
    right.push({
      point: [rng(), rng()],
      descriptor: left[i].descriptor.map((d) => d + gaussian(rng) * 0.13),
      identity: -i - 1,
    });
  const nearest = (f: Feature, candidates: Feature[]) =>
    candidates.map((c, i) => ({ i, d: descriptorDistance(f, c) })).sort((a, b) => a.d - b.d)[0];
  const candidates = left.map((f, i) => {
    const candidate = nearest(f, right);
    const reciprocal = nearest(right[candidate.i], left).i === i;
    return {
      left: i,
      right: candidate.i,
      correct: f.identity === right[candidate.i].identity,
      distance: candidate.d,
      reciprocal,
      accepted: candidate.d <= threshold && (!mutual || reciprocal),
      reason: candidate.d > threshold ? 'threshold' : mutual && !reciprocal ? 'mutual' : 'accepted',
    };
  });
  const matches = candidates.filter((candidate) => candidate.accepted);
  return { left, right, matches, candidates };
}

export function relative(a: Pose, b: Pose): Pose {
  const dx = b[0] - a[0],
    dy = b[1] - a[1],
    c = Math.cos(a[2]),
    s = Math.sin(a[2]);
  return [c * dx + s * dy, -s * dx + c * dy, wrap(b[2] - a[2])];
}

export function compose(a: Pose, b: Pose): Pose {
  return [
    a[0] + Math.cos(a[2]) * b[0] - Math.sin(a[2]) * b[1],
    a[1] + Math.sin(a[2]) * b[0] + Math.cos(a[2]) * b[1],
    wrap(a[2] + b[2]),
  ];
}

export type Edge = { i: number; j: number; z: Pose; loop?: boolean };
export function poseGraph(seed: number, noise = 0.045) {
  const rng = random(seed),
    truth: Pose[] = Array.from({ length: 18 }, (_, i) => {
      const a = (i * 2 * Math.PI) / 18;
      return [2 * Math.sin(a), 2 - 2 * Math.cos(a), a];
    });
  const edges: Edge[] = truth.slice(1).map((_, k) => {
    const z = relative(truth[k], truth[k + 1]);
    return {
      i: k,
      j: k + 1,
      z: [
        z[0] + gaussian(rng) * noise,
        z[1] + gaussian(rng) * noise,
        wrap(z[2] + 0.025 + gaussian(rng) * noise),
      ],
    };
  });
  const initial: Pose[] = [[...truth[0]]];
  edges.forEach((edge) => initial.push(compose(initial[edge.i], edge.z)));
  const z = relative(truth[truth.length - 1], truth[0]);
  edges.push({
    i: truth.length - 1,
    j: 0,
    loop: true,
    z: [
      z[0] + gaussian(rng) * noise * 0.25,
      z[1] + gaussian(rng) * noise * 0.25,
      z[2] + gaussian(rng) * noise * 0.25,
    ],
  });
  return { initial, edges, truth };
}

function residual(a: Pose, b: Pose, z: Pose): Pose {
  const predicted = relative(a, b);
  const c = Math.cos(z[2]),
    s = Math.sin(z[2]),
    dx = predicted[0] - z[0],
    dy = predicted[1] - z[1];
  return [c * dx + s * dy, -s * dx + c * dy, wrap(predicted[2] - z[2])];
}

export function graphCost(poses: Pose[], edges: Edge[]) {
  return edges.reduce(
    (sum, edge) =>
      sum +
      residual(poses[edge.i], poses[edge.j], edge.z).reduce(
        (a, b, i) => a + b * b * (i === 2 ? 3 : 1),
        0,
      ),
    0,
  );
}

function solve(matrix: number[][], vector: number[]) {
  const a = matrix.map((row, i) => [...row, vector[i]]),
    n = a.length;
  for (let k = 0; k < n; k++) {
    let pivot = k;
    for (let i = k + 1; i < n; i++) if (Math.abs(a[i][k]) > Math.abs(a[pivot][k])) pivot = i;
    [a[k], a[pivot]] = [a[pivot], a[k]];
    if (Math.abs(a[k][k]) < 1e-12) throw new Error('Graph system is singular');
    for (let i = k + 1; i < n; i++) {
      const scale = a[i][k] / a[k][k];
      for (let j = k; j <= n; j++) a[i][j] -= scale * a[k][j];
    }
  }
  const result = Array(n).fill(0) as number[];
  for (let i = n - 1; i >= 0; i--)
    result[i] =
      (a[i][n] - result.reduce((sum, v, j) => (j > i ? sum + a[i][j] * v : sum), 0)) / a[i][i];
  return result;
}

export function optimizeGraph(initial: Pose[], edges: Edge[], iterations = 15) {
  let poses = initial.map((p) => [...p] as Pose);
  const dimension = 3 * (poses.length - 1),
    epsilon = 1e-5;
  const costs = [graphCost(poses, edges)];
  for (let iteration = 0; iteration < iterations; iteration++) {
    const h = Array.from({ length: dimension }, () => Array(dimension).fill(0) as number[]),
      gradient = Array(dimension).fill(0) as number[];
    for (const edge of edges) {
      const r = residual(poses[edge.i], poses[edge.j], edge.z),
        columns: { index: number; derivative: Pose }[] = [];
      for (const node of [edge.i, edge.j]) {
        if (node === 0) continue; // Anchor the first pose: no access to a truth path.
        for (let axis = 0; axis < 3; axis++) {
          const plus = poses.map((p) => [...p] as Pose),
            minus = poses.map((p) => [...p] as Pose);
          plus[node][axis] += epsilon;
          minus[node][axis] -= epsilon;
          const rp = residual(plus[edge.i], plus[edge.j], edge.z),
            rm = residual(minus[edge.i], minus[edge.j], edge.z);
          columns.push({
            index: (node - 1) * 3 + axis,
            derivative: rp.map(
              (v, k) => (k === 2 ? wrap(v - rm[k]) : v - rm[k]) / (2 * epsilon),
            ) as Pose,
          });
        }
      }
      for (const a of columns) {
        gradient[a.index] += a.derivative.reduce(
          (sum, v, k) => sum + v * r[k] * (k === 2 ? 3 : 1),
          0,
        );
        for (const b of columns)
          h[a.index][b.index] += a.derivative.reduce(
            (sum, v, k) => sum + v * b.derivative[k] * (k === 2 ? 3 : 1),
            0,
          );
      }
    }
    h.forEach((row, i) => (row[i] += 1e-5));
    const delta = solve(
      h,
      gradient.map((v) => -v),
    );
    let accepted = false;
    for (let scale = 1; scale >= 1 / 64; scale /= 2) {
      const candidate = poses.map((p, i) =>
        i === 0
          ? p
          : ([
              p[0] + scale * delta[(i - 1) * 3],
              p[1] + scale * delta[(i - 1) * 3 + 1],
              wrap(p[2] + scale * delta[(i - 1) * 3 + 2]),
            ] as Pose),
      );
      const cost = graphCost(candidate, edges);
      if (cost <= costs[costs.length - 1]) {
        poses = candidate;
        costs.push(cost);
        accepted = true;
        break;
      }
    }
    if (!accepted || Math.hypot(...delta) < 1e-7) break;
  }
  return { poses, costs };
}

export function alignPoints(source: Point[], target: Point[]) {
  if (source.length < 2 || source.length !== target.length)
    throw new Error('At least two shared landmarks are required');
  const center = (points: Point[]): Point => [
    points.reduce((s, p) => s + p[0], 0) / points.length,
    points.reduce((s, p) => s + p[1], 0) / points.length,
  ];
  const a = center(source),
    b = center(target);
  let dot = 0,
    cross = 0,
    variance = 0;
  source.forEach((p, i) => {
    const x = p[0] - a[0],
      y = p[1] - a[1],
      u = target[i][0] - b[0],
      v = target[i][1] - b[1];
    dot += x * u + y * v;
    cross += x * v - y * u;
    variance += x * x + y * y;
  });
  if (variance < 1e-10) throw new Error('Shared landmarks must be distinct');
  const angle = Math.atan2(cross, dot),
    c = Math.cos(angle),
    s = Math.sin(angle);
  const translation: Point = [b[0] - c * a[0] + s * a[1], b[1] - s * a[0] - c * a[1]];
  const transform = (p: Point): Point => [
    c * p[0] - s * p[1] + translation[0],
    s * p[0] + c * p[1] + translation[1],
  ];
  return { angle, translation, transform };
}

export function multiRobot(seed: number, noise = 0.05) {
  const rng = random(seed),
    angle = 0.7,
    translation: Point = [1.4, -1.1];
  const shared: Point[] = Array.from({ length: 10 }, (_, i) => [
    2.3 * Math.cos(i * 0.65),
    2 * Math.sin(i * 0.65),
  ]);
  const a = shared.map(
    (p) => [p[0] + gaussian(rng) * noise, p[1] + gaussian(rng) * noise] as Point,
  );
  const b = shared.map((p) => {
    const dx = p[0] - translation[0],
      dy = p[1] - translation[1];
    return [
      Math.cos(angle) * dx + Math.sin(angle) * dy + gaussian(rng) * noise,
      -Math.sin(angle) * dx + Math.cos(angle) * dy + gaussian(rng) * noise,
    ] as Point;
  });
  return { a, b };
}
