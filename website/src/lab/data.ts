export type SamplePose = [number, number, number, number];
export type Landmark = { id: string; x: number; y: number; covariance?: number[][] };
export type Statistics = { rmse: number; mean?: number; n?: number };
export type MetricReport = {
  ate_m: Statistics;
  orientation_error_deg?: Statistics;
  rpe?: { translation_m: Statistics; rotation_deg: Statistics; pairs: number } | null;
  association?: { matched: number; estimated_fraction: number; reference_fraction: number };
  landmark_map?: { rmse_m: number; matched: number };
  duration_s?: number;
  odometry_baseline_ate_m?: Statistics;
  experiment?: {
    algorithm: string;
    version: string;
    kind: string;
    environment: string;
    robot_count: number;
    dataset: string;
    configuration: unknown;
  };
};
export type RobotReplay = {
  id: string;
  estimate: SamplePose[];
  reference: SamplePose[];
  odometry?: SamplePose[];
  landmarks: Landmark[];
  metrics?: MetricReport;
  frames?: { t: number; pose: [number, number, number]; landmarks: Landmark[] }[];
};
export type Replay = {
  schema_version: number;
  id: string;
  algorithm: string;
  kind: string;
  world: string;
  robot_count: number;
  created_utc?: string;
  robots: RobotReplay[];
  reference_landmarks?: Landmark[];
  sensor_model?: string;
  initial_prior?: string;
  configuration?: unknown;
  versions?: Record<string, string>;
};
export type OccupancyMap = {
  schema_version: number;
  kind: string;
  width: number;
  height: number;
  resolution: number;
  origin: [number, number];
  cells: number[];
  frame?: string;
};

export const MAX_FILE_BYTES = 5 * 1024 * 1024;
const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;
const finite = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export function validatePoses(value: unknown): SamplePose[] {
  if (!Array.isArray(value) || value.length < 2 || value.length > 100000)
    throw new Error('Supply 2–100,000 trajectory poses.');
  const result = value.map((row) => {
    if (!Array.isArray(row) || row.length !== 4 || !row.every(finite))
      throw new Error('Each pose must contain finite timestamp, x, y and yaw values.');
    return row as SamplePose;
  });
  if (result.some((row, i) => i > 0 && row[0] <= result[i - 1][0]))
    throw new Error('Timestamps must be unique and strictly increasing.');
  return result;
}

function validateLandmarks(value: unknown): Landmark[] {
  if (!Array.isArray(value) || value.length > 10000)
    throw new Error('Landmark list is missing or too large.');
  return value.map((v) => {
    if (!record(v) || typeof v.id !== 'string' || !finite(v.x) || !finite(v.y))
      throw new Error('Landmarks need id, x and y.');
    if (
      v.covariance !== undefined &&
      (!Array.isArray(v.covariance) ||
        v.covariance.length !== 2 ||
        !v.covariance.every((row) => Array.isArray(row) && row.length === 2 && row.every(finite)))
    )
      throw new Error('Landmark covariance must be a finite 2×2 matrix.');
    return {
      id: v.id.slice(0, 100),
      x: v.x,
      y: v.y,
      ...(v.covariance !== undefined ? { covariance: v.covariance as number[][] } : {}),
    };
  });
}

export function parseReplay(text: string): Replay {
  const value: unknown = JSON.parse(text);
  if (
    !record(value) ||
    value.schema_version !== 1 ||
    typeof value.id !== 'string' ||
    typeof value.algorithm !== 'string' ||
    !Array.isArray(value.robots) ||
    value.robots.length < 1 ||
    value.robots.length > 10
  ) {
    throw new Error('Expected a SLAMLab schema_version 1 replay with 1–10 robots.');
  }
  if (
    value.versions !== undefined &&
    (!record(value.versions) ||
      Array.isArray(value.versions) ||
      !Object.values(value.versions).every((version) => typeof version === 'string'))
  )
    throw new Error('Version metadata must contain named version strings.');
  const robots = value.robots.map((row) => {
    if (!record(row) || typeof row.id !== 'string')
      throw new Error('Every robot needs an identifier.');
    let metrics: MetricReport | undefined;
    if (row.metrics !== undefined) {
      if (
        !record(row.metrics) ||
        !record(row.metrics.ate_m) ||
        !finite(row.metrics.ate_m.rmse) ||
        row.metrics.ate_m.rmse < 0
      )
        throw new Error('ATE metrics need a finite, nonnegative RMSE.');
      metrics = row.metrics as unknown as MetricReport;
      if (
        metrics.rpe &&
        (!finite(metrics.rpe.translation_m?.rmse) || !finite(metrics.rpe.rotation_deg?.rmse))
      )
        throw new Error('RPE values must be finite.');
      if (
        metrics.landmark_map &&
        (!finite(metrics.landmark_map.rmse_m) || !finite(metrics.landmark_map.matched))
      )
        throw new Error('Map metrics must be finite.');
      if (metrics.odometry_baseline_ate_m && !finite(metrics.odometry_baseline_ate_m.rmse))
        throw new Error('Odometry metrics must be finite.');
      if (
        metrics.association &&
        ![
          metrics.association.matched,
          metrics.association.estimated_fraction,
          metrics.association.reference_fraction,
        ].every(finite)
      )
        throw new Error('Coverage metrics must be finite.');
    }
    let frames: RobotReplay['frames'];
    if (row.frames !== undefined) {
      if (!Array.isArray(row.frames) || row.frames.length > 200)
        throw new Error(
          'Supply at most 200 map checkpoints; downsample while keeping the final state.',
        );
      frames = row.frames.map((frame) => {
        if (
          !record(frame) ||
          !finite(frame.t) ||
          !Array.isArray(frame.pose) ||
          frame.pose.length !== 3 ||
          !frame.pose.every(finite)
        )
          throw new Error('Invalid map checkpoint.');
        return {
          t: frame.t,
          pose: frame.pose as [number, number, number],
          landmarks: validateLandmarks(frame.landmarks),
        };
      });
      if (frames.some((frame, i) => i > 0 && frame.t <= frames![i - 1].t))
        throw new Error('Map checkpoint timestamps must be unique and strictly increasing.');
    }
    return {
      id: row.id.slice(0, 80),
      estimate: validatePoses(row.estimate),
      reference:
        Array.isArray(row.reference) && !row.reference.length ? [] : validatePoses(row.reference),
      odometry: row.odometry ? validatePoses(row.odometry) : undefined,
      landmarks: validateLandmarks(row.landmarks),
      metrics,
      frames,
    };
  });
  if (new Set(robots.map((robot) => robot.id)).size !== robots.length)
    throw new Error('Robot identifiers must be unique.');
  return {
    schema_version: 1,
    id: value.id.slice(0, 120),
    algorithm: value.algorithm.slice(0, 120),
    kind: typeof value.kind === 'string' ? value.kind : 'local_file',
    world: typeof value.world === 'string' ? value.world : 'Local import',
    robot_count: robots.length,
    robots,
    reference_landmarks: value.reference_landmarks
      ? validateLandmarks(value.reference_landmarks)
      : [],
    sensor_model: typeof value.sensor_model === 'string' ? value.sensor_model : undefined,
    initial_prior: typeof value.initial_prior === 'string' ? value.initial_prior : undefined,
    created_utc: typeof value.created_utc === 'string' ? value.created_utc : undefined,
    configuration: value.configuration,
    versions: value.versions as Record<string, string> | undefined,
  };
}

export function parseTrajectory(text: string): SamplePose[] {
  const lines = text
    .trim()
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.trim().startsWith('#'));
  if (lines[0]?.replace(/\s/g, '') === 'timestamp,x,y,yaw') {
    return validatePoses(
      lines.slice(1).map((line) => {
        const fields = line.split(',');
        if (fields.length !== 4 || fields.some((v) => !v.trim()))
          throw new Error('CSV rows require timestamp,x,y,yaw.');
        return fields.map(Number);
      }),
    );
  }
  let height: number | undefined;
  return validatePoses(
    lines.map((line) => {
      const values = line.trim().split(/\s+/).map(Number);
      if (values.length !== 8 || !values.every(finite))
        throw new Error('Use CSV timestamp,x,y,yaw or planar TUM timestamp tx ty tz qx qy qz qw.');
      const [t, x, y, z, qx, qy, qz, qw] = values;
      if (
        Math.abs(Math.hypot(qx, qy, qz, qw) - 1) > 0.001 ||
        Math.abs(qx) > 1e-6 ||
        Math.abs(qy) > 1e-6 ||
        (height !== undefined && Math.abs(z - height) > 1e-5)
      )
        throw new Error(
          'This 2D viewer requires planar TUM poses with constant height and a unit yaw quaternion.',
        );
      height = z;
      return [t, x, y, 2 * Math.atan2(qz, qw)];
    }),
  );
}

export function parseOccupancy(text: string): OccupancyMap {
  const value: unknown = JSON.parse(text);
  if (
    !record(value) ||
    !Number.isInteger(value.width) ||
    !Number.isInteger(value.height) ||
    !finite(value.width) ||
    !finite(value.height) ||
    value.width < 1 ||
    value.height < 1 ||
    value.width * value.height > 65536 ||
    !finite(value.resolution) ||
    value.resolution <= 0 ||
    !Array.isArray(value.origin) ||
    value.origin.length !== 2 ||
    !value.origin.every(finite) ||
    !Array.isArray(value.cells) ||
    value.cells.length !== value.width * value.height ||
    !value.cells.every((v) => v === -1 || v === 0 || v === 1)
  ) {
    throw new Error(
      'Map needs width×height ≤65,536 cells (-1 unknown, 0 free, 1 occupied), positive resolution and [x,y] origin.',
    );
  }
  return {
    schema_version: 1,
    kind: typeof value.kind === 'string' ? value.kind : 'local_file',
    width: value.width,
    height: value.height,
    resolution: value.resolution,
    origin: value.origin as [number, number],
    cells: value.cells as number[],
    frame: typeof value.frame === 'string' ? value.frame : 'Imported map frame',
  };
}

export function poseAt(poses: SamplePose[], t: number) {
  let lo = 0,
    hi = poses.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (poses[mid][0] <= t) lo = mid + 1;
    else hi = mid;
  }
  return poses[Math.max(0, lo - 1)];
}

export function download(name: string, value: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }),
  );
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
