import { memo, useMemo, useState } from 'react';
import {
  download,
  MAX_FILE_BYTES,
  parseOccupancy,
  parseReplay,
  parseTrajectory,
  poseAt,
  type OccupancyMap,
  type Replay,
} from '../lab/data';
import { occupancy, type Pose } from '../lab/models';
import {
  BASE,
  Icon,
  Legend,
  Link,
  PageHeader,
  PathLine,
  Playback,
  Plot,
  Robot,
  Stat,
  Toggle,
  usePlayback,
  useReplay,
} from '../components/ui';

const MapCells = memo(function MapCells({ map }: { map: OccupancyMap }) {
  const stride = Math.max(1, Math.ceil(Math.sqrt(map.cells.length / 16000)));
  return (
    <>
      {map.cells.map((v, i) => {
        const x = i % map.width,
          y = Math.floor(i / map.width);
        if (v === -1 || x % stride || y % stride) return null;
        return (
          <rect
            key={i}
            x={map.origin[0] + x * map.resolution}
            y={map.origin[1] + y * map.resolution}
            width={map.resolution * stride}
            height={map.resolution * stride}
            fill={v ? 'var(--occupied)' : 'var(--free)'}
            opacity=".6"
          />
        );
      })}
    </>
  );
});

function Viewer({ data, map }: { data: Replay; map: OccupancyMap | null }) {
  const player = usePlayback(301),
    [estimate, setEstimate] = useState(true),
    [reference, setReference] = useState(true),
    [odom, setOdom] = useState(false),
    [landmarks, setLandmarks] = useState(true),
    [error, setError] = useState(false),
    [mapVisible, setMapVisible] = useState(true),
    [selected, setSelected] = useState(0),
    [hidden, setHidden] = useState<string[]>([]);
  const first = Math.min(...data.robots.map((r) => r.estimate[0][0])),
    last = Math.max(...data.robots.map((r) => r.estimate.at(-1)![0]));
  const t = first + ((last - first) * player.frame) / 300;
  const bounds = useMemo(() => {
    const points = data.robots.flatMap((r) => [
      ...r.estimate.map((p) => [p[1], p[2]]),
      ...r.landmarks.map((p) => [p.x, p.y]),
    ]);
    if (map)
      points.push(map.origin, [
        map.origin[0] + map.width * map.resolution,
        map.origin[1] + map.height * map.resolution,
      ]);
    const box = points.reduce(
      (b, p) => [
        Math.min(b[0], p[0]),
        Math.min(b[1], p[1]),
        Math.max(b[2], p[0]),
        Math.max(b[3], p[1]),
      ],
      [Infinity, Infinity, -Infinity, -Infinity],
    );
    return [box[0] - 0.7, box[1] - 0.7, box[2] + 0.7, box[3] + 0.7];
  }, [data, map]);
  const robot = data.robots[selected] || data.robots[0],
    metrics = robot.metrics;
  const colors = ['var(--teal)', 'var(--orange)', 'var(--purple)'];
  const points = (rows: number[][]) =>
    rows.filter((p) => p[0] <= t).map((p) => [p[1], p[2], p[3]] as Pose);
  const errors = robot.estimate.map((p) => {
    if (!robot.reference.length) return [p[0], 0];
    const ref = poseAt(robot.reference, p[0]);
    return [p[0], Math.hypot(p[1] - ref[1], p[2] - ref[2])];
  });
  const maxError = errors.reduce((maximum, e) => Math.max(maximum, e[1]), 0.01);
  return (
    <>
      <div className="experiment-layout studio-layout">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>
              <i className="live-dot" />
              {data.algorithm}
            </span>
            <span className="subtle">
              {data.kind === 'simulation_measurement'
                ? 'Recorded Webots experiment'
                : 'Local / educational data'}
            </span>
          </div>
          <Plot
            label="Replay of estimated and reference trajectories, robot headings and landmark maps"
            bounds={bounds}
            interactive
          >
            {map && mapVisible && <MapCells map={map} />}
            {data.robots
              .filter((r) => !hidden.includes(r.id))
              .map((r, i) => {
                const color = colors[i % colors.length],
                  pose = poseAt(r.estimate, t);
                const checkpoint = r.frames?.filter((f) => f.t <= t).at(-1);
                const currentLandmarks = r.frames?.length
                  ? checkpoint?.landmarks || []
                  : r.landmarks;
                return (
                  <g key={r.id}>
                    {reference && (
                      <PathLine points={points(r.reference)} color="var(--slate)" dashed />
                    )}
                    {odom && r.odometry && (
                      <PathLine points={points(r.odometry)} color="var(--purple)" dashed />
                    )}
                    {estimate && (
                      <>
                        <PathLine points={points(r.estimate)} color={color} />
                        <Robot pose={[pose[1], pose[2], pose[3]]} color={color} />
                      </>
                    )}
                    {landmarks &&
                      currentLandmarks.map((p) => (
                        <circle key={p.id} cx={p.x} cy={p.y} r=".065" fill={color} opacity=".9" />
                      ))}
                    {error &&
                      r.reference.length > 0 &&
                      (() => {
                        const ref = poseAt(r.reference, t);
                        return (
                          <line
                            x1={pose[1]}
                            y1={pose[2]}
                            x2={ref[1]}
                            y2={ref[2]}
                            stroke="var(--orange)"
                            strokeWidth=".05"
                          />
                        );
                      })()}
                  </g>
                );
              })}
          </Plot>
          <Legend
            items={[
              ['EKF estimate / landmarks', 'var(--teal)'],
              ['Reference', 'var(--slate)'],
              ...(data.robots.length > 1
                ? ([['Robot 2', 'var(--orange)']] as [string, string][])
                : []),
            ]}
          />
          <Playback player={player} total={301} label={t.toFixed(2) + ' s'} />
        </section>
        <aside className="panel controls">
          <h2>Replay layers</h2>
          <p>Drag to pan. Use zoom controls or arrow keys to inspect the map.</p>
          <Toggle label="Estimated trajectories" checked={estimate} onChange={setEstimate} />
          <Toggle label="Reference trajectories" checked={reference} onChange={setReference} />
          <Toggle label="Wheel-only odometry" checked={odom} onChange={setOdom} />
          <Toggle label="Estimated landmarks" checked={landmarks} onChange={setLandmarks} />
          <Toggle label="Position error connector" checked={error} onChange={setError} />
          {map && (
            <Toggle label="Occupancy map layer" checked={mapVisible} onChange={setMapVisible} />
          )}
          {data.robots.length > 1 && (
            <fieldset>
              <legend>Robots</legend>
              {data.robots.map((r) => (
                <Toggle
                  key={r.id}
                  label={r.id}
                  checked={!hidden.includes(r.id)}
                  onChange={(show) =>
                    setHidden(show ? hidden.filter((id) => id !== r.id) : [...hidden, r.id])
                  }
                />
              ))}
            </fieldset>
          )}
          <button className="button secondary" onClick={() => download(data.id + '.json', data)}>
            <Icon name="download" size={17} /> Download replay
          </button>
          <p className="help">
            Final metrics come from Python. Playback positions use the recorded samples; the error
            connector is a visual separation, not a new benchmark score.
          </p>
        </aside>
      </div>
      <section className="panel metric-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PYTHON EVALUATION</p>
            <h2>Read the result in context.</h2>
          </div>
          <label className="select-label">
            Metric robot
            <select value={selected} onChange={(e) => setSelected(Number(e.target.value))}>
              {data.robots.map((r, i) => (
                <option value={i} key={r.id}>
                  {r.id}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="metric-grid">
          <Stat
            label="Position ATE · RMSE"
            value={metrics?.ate_m.rmse.toFixed(4) || '—'}
            unit="m"
          />
          <Stat
            label="Translation RPE · RMSE"
            value={metrics?.rpe?.translation_m.rmse.toFixed(4) || '—'}
            unit="m"
          />
          <Stat
            label="Rotation RPE · RMSE"
            value={metrics?.rpe?.rotation_deg.rmse.toFixed(3) || '—'}
            unit="°"
          />
          <Stat label="Estimated landmarks" value={robot.landmarks.length} />
        </div>
        {robot.reference.length > 0 && (
          <div className="error-chart">
            <div>
              <span>Sample-wise reference separation</span>
              <small>Metres · playback samples</small>
            </div>
            <svg
              viewBox="0 0 800 110"
              role="img"
              aria-label="Position separation from the recorded reference across time"
            >
              {[0, 0.5, 1].map((v) => (
                <line
                  key={v}
                  x1="0"
                  x2="800"
                  y1={100 - v * 90}
                  y2={100 - v * 90}
                  stroke="var(--grid)"
                />
              ))}
              <path
                d={errors
                  .map(
                    ([stamp, value], i) =>
                      `${i ? 'L' : 'M'}${((stamp - first) / Math.max(0.001, last - first)) * 800},${100 - (value / maxError) * 90}`,
                  )
                  .join(' ')}
                fill="none"
                stroke="var(--teal)"
                strokeWidth="2"
              />
              <line
                x1={(player.frame / 300) * 800}
                x2={(player.frame / 300) * 800}
                y1="0"
                y2="110"
                stroke="var(--orange)"
                strokeWidth="1.5"
              />
            </svg>
            <div className="chart-axis">
              <span>{first.toFixed(1)} s</span>
              <span>Scale 0–{maxError.toFixed(3)} m</span>
              <span>{last.toFixed(1)} s</span>
            </div>
          </div>
        )}
        {!metrics && (
          <p className="help">
            Load a Python-exported replay to include evaluated ATE/RPE and reference coverage.
          </p>
        )}
        {map && (
          <p className="help">
            Map: {map.width} × {map.height} cells · {map.resolution} m/cell · origin [
            {map.origin.join(', ')}] · {map.frame}. Large displays are decimated for responsiveness.
          </p>
        )}
      </section>
    </>
  );
}

export default function Studio() {
  const initial =
    new URLSearchParams(location.search).get('sample') === 'two'
      ? 'landmark-two-robots'
      : 'landmark-reference';
  const [sample, setSample] = useState(initial),
    { data, error } = useReplay(sample),
    [local, setLocal] = useState<Replay | null>(null),
    [map, setMap] = useState<OccupancyMap | null>(null),
    [message, setMessage] = useState('');
  async function load(file: File | undefined, kind: 'replay' | 'map') {
    if (!file) return;
    try {
      if (file.size > MAX_FILE_BYTES)
        throw new Error(
          'File exceeds the 5 MiB browser limit. Downsample or export a compact replay.',
        );
      const text = await file.text();
      if (kind === 'map') {
        setMap(parseOccupancy(text));
        setMessage('Loaded map locally: ' + file.name);
      } else if (file.name.toLowerCase().endsWith('.json')) {
        setLocal(parseReplay(text));
        setMessage('Loaded replay locally: ' + file.name);
      } else {
        setLocal({
          schema_version: 1,
          id: file.name,
          algorithm: 'Local trajectory',
          world: 'Imported coordinates',
          kind: 'local_file',
          robot_count: 1,
          robots: [
            { id: 'local-robot', estimate: parseTrajectory(text), reference: [], landmarks: [] },
          ],
        });
        setMessage(
          'Loaded local trajectory. Use a replay JSON to include reference layers and evaluated metrics.',
        );
      }
    } catch (e) {
      setMessage('Could not load file: ' + (e as Error).message);
    }
  }
  function sampleMap() {
    const frame = occupancy(42, 4, 0.03, 0.2).at(-1)!;
    setMap({
      schema_version: 1,
      kind: 'educational_model',
      width: frame.width,
      height: frame.width,
      resolution: frame.resolution,
      origin: [-4, -4],
      cells: frame.grid.map((v) => (v === 0 ? -1 : v > 0.5 ? 1 : 0)),
      frame: 'Educational mapping world, rows along +Y',
    });
    setMessage(
      'Loaded the educational occupancy layer. Its coordinate frame is separate from the recorded marker lab.',
    );
  }
  return (
    <>
      <PageHeader
        eyebrow="VISUALIZATION STUDIO"
        title="Every trajectory tells a story."
        description="Replay recorded experiments, inspect maps, or open your own files. Everything stays in your browser."
      />
      <section className="studio-toolbar panel">
        <label className="select-label">
          Example recording
          <select
            value={local ? 'local' : sample}
            onChange={(e) => {
              setSample(e.target.value);
              setLocal(null);
              setMap(null);
              setMessage('');
            }}
          >
            <option value="landmark-reference">Landmark Lab · one robot</option>
            <option value="landmark-two-robots">Landmark Lab · two robots</option>
            {local && <option value="local">{local.id}</option>}
          </select>
        </label>
        <label className="button secondary file-button">
          <Icon name="studio" size={17} /> Open replay / trajectory
          <input
            aria-label="Open local replay or trajectory"
            type="file"
            accept=".json,.csv,.tum,.txt"
            onChange={(e) => {
              void load(e.target.files?.[0], 'replay');
              e.target.value = '';
            }}
          />
        </label>
        <label className="button secondary file-button">
          <Icon name="simulation" size={17} /> Open occupancy map
          <input
            aria-label="Open local occupancy map"
            type="file"
            accept=".json"
            onChange={(e) => {
              void load(e.target.files?.[0], 'map');
              e.target.value = '';
            }}
          />
        </label>
        <button className="text-link" onClick={sampleMap}>
          Try a sample grid
        </button>
        {map && (
          <button className="text-link" onClick={() => setMap(null)}>
            Remove grid
          </button>
        )}
      </section>
      {(message || error) && (
        <p
          className={message.startsWith('Could not') || error ? 'notice error' : 'notice'}
          role={message.startsWith('Could not') || error ? 'alert' : 'status'}
        >
          {message || error}
        </p>
      )}
      {local || data ? (
        <Viewer key={(local || data)!.id} data={(local || data)!} map={map} />
      ) : (
        <p role="status">Loading the recorded experiment…</p>
      )}
      <section className="lesson-note compact">
        <div>
          <h2>Bring an experiment into the browser.</h2>
          <p>
            Use{' '}
            <code>python -B tools/slam.py visualize EXPERIMENT --output outputs/replay.json</code>.
            The bundle carries metadata, maps and computed metrics into this viewer.
          </p>
          <Link to="documentation/landmark-lab/" className="text-link">
            Export format & tutorial <Icon name="arrow" size={16} />
          </Link>
        </div>
        <a className="button secondary" href={BASE + 'generated/landmark-reference.json'} download>
          <Icon name="download" size={17} /> Download sample JSON
        </a>
      </section>
    </>
  );
}
