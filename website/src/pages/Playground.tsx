import { useContext, useMemo, useState } from 'react';
import katex from 'katex';
import {
  odometry,
  occupancy,
  optimizeGraph,
  graphCost,
  poseGraph,
  multiRobot,
  alignPoints,
  type Point,
} from '../lab/models';
import { download } from '../lab/data';
import { FeatureExperiment } from '../components/FeatureExperiment';
import { ExperimentTools, useExperimentComparison } from '../components/ExperimentComparison';
import { playgroundGuides, type ModuleId } from '../lab/playgroundGuide';
import { plotBounds } from '../lab/plotBounds';
import {
  Icon,
  Navigation,
  Legend,
  Link,
  PageHeader,
  PathLine,
  Playback,
  Plot,
  Range,
  Robot,
  Stat,
  Toggle,
  usePlayback,
} from '../components/ui';

const modules: [ModuleId, string, string, string][] = [
  ['odometry', '01', 'Odometry drift', 'Motion & uncertainty'],
  ['occupancy', '02', 'Occupancy mapping', 'A probabilistic map'],
  ['features', '03', 'Feature matching', 'Finding correspondences'],
  ['graph', '04', 'Pose graph', 'Closing the loop'],
  ['multi', '05', 'Multi-robot alignment', 'From local to shared'],
];

const quickTry: Record<ModuleId, string> = {
  odometry: 'Set both noise controls to zero. Then add turning noise and compare the paths.',
  occupancy: 'Play to reveal the map. Shorten the sensor range and see what stays unknown.',
  features: 'Try a clean match, then confusing details. Inspect why one pair was accepted.',
  graph: 'Optimize with the revisit on, then off. Compare how the path changes.',
  multi: 'Choose two shared points and align the maps. Then add observation noise.',
};
function ExperimentGuide({ module }: { module: ModuleId }) {
  const guide = playgroundGuides[module];
  return (
    <section
      className="experiment-guide panel compact-guide"
      aria-labelledby="experiment-guide-title"
    >
      <div className="guide-essential">
        <h2 id="experiment-guide-title">{guide.title}</h2>
        <p>{guide.explanation}</p>
      </div>
      <p className="quick-try">
        <strong>Try this</strong>
        {quickTry[module]}
      </p>
      <div className="guide-disclosures">
        <details>
          <summary>How to read the picture</summary>
          <p>{guide.readout}</p>
          <ol>
            {guide.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </details>
        <details className="guide-glossary">
          <summary>Words used in this experiment</summary>
          <dl>
            {guide.terms.map(([term, definition]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{definition}</dd>
              </div>
            ))}
          </dl>
        </details>
        <details>
          <summary>Assumptions and playback</summary>
          <p>{guide.scope}</p>
          <p>{guide.example}</p>
          {module !== 'features' && <p>x and y are positions on the map, in metres.</p>}
          {module !== 'features' && module !== 'graph' && (
            <p>
              Play starts the animation. Pause or drag the slider to inspect a moment. Reset returns
              to the start; playback speed changes only the animation rate.
            </p>
          )}
        </details>
      </div>
    </section>
  );
}

function Equation({ tex, label }: { tex: string; label: string }) {
  return (
    <div
      className="equation"
      role="math"
      aria-label={label}
      dangerouslySetInnerHTML={{
        __html: katex.renderToString(tex, {
          throwOnError: false,
          displayMode: true,
          output: 'html',
        }),
      }}
    />
  );
}

function Lesson({
  title,
  children,
  formula,
  label,
  link,
  meaning,
  symbols,
}: {
  title: string;
  children: React.ReactNode;
  formula: string;
  label: string;
  link: string;
  meaning: string;
  symbols: string;
}) {
  return (
    <section className="lesson-note compact-lesson">
      <div>
        <p className="eyebrow">THE KEY IDEA</p>
        <h2>{title}</h2>
        <Link to={'documentation/' + link + '/'} className="text-link">
          See the visual lesson <Icon name="arrow" size={16} />
        </Link>
      </div>
      <div className="advanced-folds">
        <details>
          <summary>What happens underneath?</summary>
          {children}
        </details>
        <details>
          <summary>Explore the equation</summary>
          <p>{meaning}</p>
          <Equation tex={formula} label={label} />
          <p>{symbols}</p>
        </details>
      </div>
    </section>
  );
}

function Odometry({ seed }: { seed: number }) {
  const [trans, setTrans] = useState(0.04),
    [rotation, setRotation] = useState(0.035),
    [speed, setSpeed] = useState(0.45);
  const [truthVisible, setTruthVisible] = useState(true),
    [estimateVisible, setEstimateVisible] = useState(true);
  const frames = useMemo(
    () => odometry(seed, trans, rotation, speed),
    [seed, trans, rotation, speed],
  );
  const player = usePlayback(frames.length, frames.length - 1),
    current = frames[player.frame];
  const result = `At ${current.t.toFixed(1)} s, the estimated position is ${current.error.toFixed(3)} m from the reference.`;
  const bounds = plotBounds(frames.flatMap((frame) => [frame.truth, frame.estimate]));
  const comparison = useExperimentComparison({
    bounds,
    settings: `Seed ${seed}; speed ${speed} m/s; movement noise ${trans}; turning noise ${rotation}; time ${current.t.toFixed(1)} s`,
    result,
    graphic: (
      <Plot label="Odometry comparison snapshot" bounds={bounds}>
        <PathLine
          points={frames.slice(0, player.frame + 1).map((f) => f.truth)}
          color="var(--slate)"
          dashed
        />
        <PathLine points={frames.slice(0, player.frame + 1).map((f) => f.estimate)} />
      </Plot>
    ),
  });
  return (
    <>
      <div className="experiment-layout">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>
              <i className="live-dot" />
              Motion model
            </span>
            <span className="subtle">Seed {seed} · 2D unicycle</span>
          </div>
          <Plot label="Ground-truth and noisy odometry trajectories" bounds={bounds}>
            {truthVisible && (
              <PathLine
                points={frames.slice(0, player.frame + 1).map((f) => f.truth)}
                color="var(--slate)"
                dashed
              />
            )}
            {estimateVisible && (
              <>
                <PathLine points={frames.slice(0, player.frame + 1).map((f) => f.estimate)} />
                <Robot pose={current.estimate} />
              </>
            )}
            {truthVisible && <Robot pose={current.truth} color="var(--slate)" size={0.1} />}
          </Plot>
          <Legend
            items={[
              ['Reference motion', 'var(--slate)'],
              ['Wheel odometry', 'var(--teal)'],
            ]}
          />
          <Playback player={player} total={frames.length} label={current.t.toFixed(1) + ' s'} />
          <p className="result-note" aria-live="polite">
            {result}
          </p>
        </section>
        <aside className="panel controls">
          <h2>Experiment controls</h2>
          <p>Change the noise model, then replay the same motion.</p>
          <ExperimentTools
            save={comparison.save}
            saved={comparison.saved}
            examples={[
              {
                label: 'No movement errors',
                run: () => {
                  setTrans(0);
                  setRotation(0);
                  setSpeed(0.45);
                  player.setRunning(false);
                  player.setFrame(frames.length - 1);
                },
              },
              {
                label: 'Add turning errors',
                run: () => {
                  setTrans(0);
                  setRotation(0.12);
                  setSpeed(0.45);
                  player.setRunning(false);
                  player.setFrame(frames.length - 1);
                },
              },
            ]}
          />
          <Range
            label="Robot speed"
            value={speed}
            min={0.15}
            max={0.65}
            unit="m/s"
            help="How far the robot moves each second. Faster motion covers more distance in the same simulated time."
            onChange={setSpeed}
          />
          <Range
            label="Translation noise"
            value={trans}
            min={0}
            max={0.15}
            step={0.005}
            unit="m/√s"
            help="Random error in estimated forward movement. Zero removes this source of drift."
            onChange={setTrans}
          />
          <Range
            label="Rotation noise"
            value={rotation}
            min={0}
            max={0.15}
            step={0.005}
            unit="rad/√s"
            help="Random error in estimated turns. A wrong heading can send later steps in the wrong direction."
            onChange={setRotation}
          />
          <fieldset>
            <legend>Visible layers</legend>
            <Toggle
              label="Reference trajectory"
              checked={truthVisible}
              onChange={setTruthVisible}
            />
            <Toggle
              label="Estimated trajectory"
              checked={estimateVisible}
              onChange={setEstimateVisible}
            />
          </fieldset>
          <div className="small-stats">
            <Stat
              label="Position error"
              value={current.error.toFixed(3)}
              unit="m"
              detail="Gap between the estimated and reference positions now."
            />
            <Stat
              label="Distance travelled"
              value={current.length.toFixed(2)}
              unit="m"
              detail="Length of the reference path so far."
            />
          </div>
        </aside>
      </div>
      {comparison.panel}
      <Lesson
        title="Small errors travel with you."
        formula={String.raw`x_{t+1}=x_t+d\cos(\theta_t+\Delta\theta/2)`}
        label="Midpoint planar motion update"
        link="frames"
        meaning="The next position is the current position plus a step in the direction the robot is facing. An error in that direction changes where the step lands."
        symbols="x is the horizontal position, t labels a time step, d is the distance moved, θ is the heading and Δθ is the turn during the step. cos gives the horizontal part of that movement."
      >
        <p>
          A heading error changes the direction of every later step. Set both noise terms to zero to
          make the paths agree, then increase rotation noise and watch the position error grow.
        </p>
        <p>
          The seed makes the random errors repeatable: keep the same seed and settings to replay the
          same example. This model does not use a map to correct its motion estimate.
        </p>
      </Lesson>
    </>
  );
}

function Occupancy({ seed }: { seed: number }) {
  const [range, setRange] = useState(4),
    [noise, setNoise] = useState(0.03),
    [resolution, setResolution] = useState(0.2),
    [visible, setVisible] = useState(true),
    [raysVisible, setRaysVisible] = useState(true);
  const frames = useMemo(
    () => occupancy(seed, range, noise, resolution),
    [seed, range, noise, resolution],
  );
  const player = usePlayback(frames.length, frames.length - 1),
    frame = frames[player.frame];
  const known = frame.grid.filter((v) => v !== 0).length;
  const result = `${known} of ${frame.grid.length} cells have observation evidence at step ${player.frame + 1}. Unseen cells remain unknown.`;
  const comparison = useExperimentComparison({
    settings: `Seed ${seed}; range ${range} m; noise ${noise} m; cell ${resolution} m; step ${player.frame + 1}`,
    result,
    graphic: (
      <Plot label="Occupancy comparison snapshot">
        {frame.grid.map((v, i) => (
          <rect
            key={i}
            x={-4 + (i % frame.width) * frame.resolution}
            y={-4 + Math.floor(i / frame.width) * frame.resolution}
            width={frame.resolution}
            height={frame.resolution}
            fill={v === 0 ? 'var(--unknown)' : v > 0.5 ? 'var(--occupied)' : 'var(--free)'}
          />
        ))}
      </Plot>
    ),
  });
  const exportMap = () =>
    download('educational-occupancy-map.json', {
      schema_version: 1,
      kind: 'educational_model',
      width: frame.width,
      height: frame.width,
      resolution: frame.resolution,
      origin: [-4, -4],
      frame: 'World XY; rows along +Y',
      cells: frame.grid.map((v) => (v === 0 ? -1 : v > 0.5 ? 1 : 0)),
    });
  return (
    <>
      <div className="experiment-layout">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>
              <i className="live-dot" />
              Inverse sensor model
            </span>
            <button className="text-link" onClick={exportMap}>
              <Icon name="download" size={15} /> Map JSON
            </button>
          </div>
          <Plot label="Incremental log-odds occupancy grid with simulated range beams">
            {visible &&
              frame.grid.map((v, i) => (
                <rect
                  key={i}
                  x={-4 + (i % frame.width) * frame.resolution}
                  y={-4 + Math.floor(i / frame.width) * frame.resolution}
                  width={frame.resolution * 0.98}
                  height={frame.resolution * 0.98}
                  fill={v === 0 ? 'var(--unknown)' : v > 0.5 ? 'var(--occupied)' : 'var(--free)'}
                  opacity={v === 0 ? 0.45 : Math.min(0.95, 0.4 + Math.abs(v) * 0.12)}
                />
              ))}
            {raysVisible &&
              frame.rays.map((p, i) => (
                <line
                  key={i}
                  x1={frame.pose[0]}
                  y1={frame.pose[1]}
                  x2={p[0]}
                  y2={p[1]}
                  stroke="var(--orange)"
                  strokeWidth=".012"
                  opacity=".55"
                />
              ))}
            <Robot pose={frame.pose} />
          </Plot>
          <Legend
            items={[
              ['Occupied', 'var(--occupied)'],
              ['Free', 'var(--free)'],
              ['Unknown', 'var(--unknown)'],
              ['Range beams', 'var(--orange)'],
            ]}
          />
          <Playback player={player} total={frames.length} />
          <p className="result-note" aria-live="polite">
            {result}
          </p>
        </section>
        <aside className="panel controls">
          <h2>Sensor & map</h2>
          <p>Every range beam contributes free-space and hit evidence.</p>
          <ExperimentTools
            save={comparison.save}
            saved={comparison.saved}
            examples={[
              {
                label: 'Look farther',
                run: () => {
                  setRange(4);
                  setNoise(0);
                  setResolution(0.2);
                  player.setRunning(false);
                  player.setFrame(frames.length - 1);
                },
              },
              {
                label: 'Shorten the view',
                run: () => {
                  setRange(1.5);
                  setNoise(0);
                  setResolution(0.2);
                  player.setRunning(false);
                  player.setFrame(frames.length - 1);
                },
              },
            ]}
          />
          <Range
            label="Sensor range"
            value={range}
            min={1}
            max={6}
            step={0.25}
            unit="m"
            help="Maximum distance a simulated sensor beam can reach."
            onChange={setRange}
          />
          <Range
            label="Range noise"
            value={noise}
            min={0}
            max={0.2}
            step={0.01}
            unit="m"
            help="Random error in measured distance. Higher values make wall observations less consistent."
            onChange={setNoise}
          />
          <Range
            label="Cell resolution"
            value={resolution}
            min={0.1}
            max={0.5}
            step={0.05}
            unit="m"
            help="Side length of one grid square. A lower value gives a more detailed, larger grid."
            onChange={setResolution}
          />
          <Toggle label="Occupancy map" checked={visible} onChange={setVisible} />
          <Toggle label="Sensor beams" checked={raysVisible} onChange={setRaysVisible} />
          <Stat
            label="Observed cells"
            value={known}
            detail={`${frame.width} × ${frame.width} grid · unknown is not free`}
          />
        </aside>
      </div>
      {comparison.panel}
      <Lesson
        title="A map is accumulated evidence."
        formula={String.raw`l_t=l_{t-1}+\log\frac{p(m\mid z_t,x_t)}{1-p(m\mid z_t,x_t)}`}
        label="Log odds occupancy update"
        link="mapping"
        meaning="Start with the evidence already stored for a square, then add what the latest observation suggests about whether it contains an obstacle."
        symbols="l is stored log-odds evidence, t is the current step, m is a map cell, z is a sensor observation and x is the supplied robot pose. p is an occupancy probability; log converts it into evidence that can be added."
      >
        <p>
          Beams reduce occupancy belief along their path and increase it at measured hits. Smaller
          cells reveal detail but require more memory and updates.
        </p>
        <p>
          The robot pose is supplied in this mapping lesson. Estimating pose and map together is the
          next step in a SLAM system.
        </p>
      </Lesson>
    </>
  );
}

function Features({ seed }: { seed: number }) {
  return (
    <>
      <FeatureExperiment seed={seed} />
      <Lesson
        title="A match is a hypothesis."
        formula={String.raw`d(a,b)=\sqrt{\sum_i(a_i-b_i)^2}`}
        label="Euclidean descriptor distance"
        link="association"
        meaning="Compare two features by combining the differences between the numbers in their descriptions. A smaller distance means more similar descriptions."
        symbols="a and b are feature descriptors, i selects a number in each descriptor and d is their Euclidean difference score. The sum adds squared differences; the square root converts that sum into a distance."
      >
        <p>
          Loose thresholds accept more candidates, including outliers. Tight thresholds can reject
          useful observations. Mutual matching helps, but geometry is still needed to verify a real
          scene correspondence.
        </p>
      </Lesson>
    </>
  );
}

function Graph({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(0.045),
    [loop, setLoop] = useState(true);
  const graph = useMemo(() => poseGraph(seed, noise), [seed, noise]);
  const [solution, setSolution] = useState<ReturnType<typeof optimizeGraph> | null>(null);
  const edges = graph.edges.filter((e) => !e.loop || loop);
  const display = solution?.poses || graph.initial;
  const cost = solution?.costs.at(-1) ?? graphCost(graph.initial, edges);
  const result = `Measurement disagreement is ${cost.toFixed(4)}${solution ? ' after adjustment' : ' before adjustment'}. ${loop ? 'The revisit connection is included.' : 'There is no revisit connection.'}`;
  const comparison = useExperimentComparison({
    settings: `Seed ${seed}; noise ${noise}; revisit ${loop ? 'on' : 'off'}; ${solution ? 'adjusted' : 'initial'}`,
    result,
    graphic: (
      <Plot label="Pose graph comparison snapshot" bounds={[-3, -1, 4, 6]}>
        <PathLine points={graph.initial} color="var(--slate)" dashed />
        <PathLine points={display} />
        {loop && <PathLine points={[display.at(-1)!, display[0]]} color="var(--orange)" dashed />}
      </Plot>
    ),
  });
  return (
    <>
      <div className="experiment-layout">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>SE(2) pose graph</span>
            <span className="subtle">18 nodes · pose 0 anchored</span>
          </div>
          <Plot
            label="Drifted pose graph, loop constraint and optimized trajectory"
            bounds={[-3, -1, 4, 6]}
          >
            <PathLine points={graph.initial} color="var(--slate)" dashed />
            {edges.map((e, i) => (
              <line
                key={i}
                x1={display[e.i][0]}
                y1={display[e.i][1]}
                x2={display[e.j][0]}
                y2={display[e.j][1]}
                stroke={e.loop ? 'var(--orange)' : 'var(--teal)'}
                strokeWidth={e.loop ? 0.055 : 0.035}
                strokeDasharray={e.loop ? '.12 .08' : undefined}
              />
            ))}
            {display.map((p, i) => (
              <circle
                key={i}
                cx={p[0]}
                cy={p[1]}
                r={i === 0 ? 0.095 : 0.065}
                fill={i === 0 ? 'var(--orange)' : 'var(--teal)'}
              />
            ))}
          </Plot>
          <Legend
            items={[
              ['Initial odometry', 'var(--slate)'],
              ['Optimized graph', 'var(--teal)'],
              ['Loop edge / anchor', 'var(--orange)'],
            ]}
          />
          <p className="result-note" aria-live="polite">
            {result}
          </p>
        </section>
        <aside className="panel controls">
          <h2>Graph constraints</h2>
          <ExperimentTools
            save={comparison.save}
            saved={comparison.saved}
            examples={[
              {
                label: 'Correct with a revisit',
                run: () => {
                  const g = poseGraph(seed, 0.045);
                  setNoise(0.045);
                  setLoop(true);
                  setSolution(optimizeGraph(g.initial, g.edges));
                },
              },
              {
                label: 'Without a revisit',
                run: () => {
                  const g = poseGraph(seed, 0.045);
                  setNoise(0.045);
                  setLoop(false);
                  setSolution(
                    optimizeGraph(
                      g.initial,
                      g.edges.filter((e) => !e.loop),
                    ),
                  );
                },
              },
            ]}
          />
          <p>
            Adjust the saved positions and headings so the movement and revisit measurements agree
            more closely.
          </p>
          <Range
            label="Measurement noise"
            value={noise}
            min={0}
            max={0.12}
            step={0.005}
            help="Random error added to movement measurements. The example also has a fixed turning bias."
            onChange={(v) => {
              setNoise(v);
              setSolution(null);
            }}
          />
          <Toggle
            label="Include loop closure"
            checked={loop}
            onChange={(v) => {
              setLoop(v);
              setSolution(null);
            }}
          />
          <button
            className="button primary"
            onClick={() => setSolution(optimizeGraph(graph.initial, edges))}
          >
            <Icon name="algorithms" size={17} /> Optimize graph
          </button>
          <button className="button secondary" onClick={() => setSolution(null)}>
            <Icon name="reset" size={16} /> Reset graph
          </button>
          <Stat
            label="Weighted objective"
            value={
              solution
                ? solution.costs.at(-1)!.toFixed(4)
                : graphCost(graph.initial, edges).toFixed(4)
            }
            detail={
              solution
                ? `Started at ${solution.costs[0].toFixed(4)} · ${solution.costs.length - 1} accepted iterations (adjustment steps). Lower means a closer fit to the selected measurements.`
                : 'Measurement disagreement score. Lower means a closer fit, not proven map accuracy.'
            }
          />
        </aside>
      </div>
      {comparison.panel}
      <Lesson
        title="One revisit connects the whole path."
        formula={String.raw`\min_{T}\sum_{(i,j)}e_{ij}^{T}\Omega_{ij}e_{ij}`}
        label="Weighted pose graph objective"
        link="graphs"
        meaning="Find the set of robot poses with the smallest combined disagreement with all the selected movement and revisit measurements."
        symbols="T represents the poses being adjusted, i and j identify connected poses, e is their measurement disagreement and Ω sets how strongly different parts of that disagreement are weighted. min asks for the smallest total score."
      >
        <p>
          A loop edge links poses that local odometry treats as distant in time. Optimization
          distributes its correction across the graph while keeping the first position and heading
          fixed as a reference.
        </p>
        <p>
          Adding noisy constraints can also harm a graph. The displayed objective measures
          consistency with these observations, not accuracy against a hidden reference.
        </p>
      </Lesson>
    </>
  );
}

function Multi({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(0.05),
    [shared, setShared] = useState(5),
    [connected, setConnected] = useState(true);
  const maps = useMemo(() => multiRobot(seed, noise), [seed, noise]);
  const [aligned, setAligned] = useState(false),
    player = usePlayback(120);
  const alignment =
    aligned && connected && shared >= 2
      ? alignPoints(maps.b.slice(0, shared), maps.a.slice(0, shared))
      : null;
  const b = maps.b.map((p) => (alignment ? alignment.transform(p) : p));
  const phase = (player.frame / 120) * Math.PI * 2;
  const localB: Point = [Math.cos(phase + 1), Math.sin(phase + 1)];
  const robotB = alignment ? alignment.transform(localB) : localB;
  const gap = Math.sqrt(
    b.reduce(
      (sum, p, index) => sum + (p[0] - maps.a[index][0]) ** 2 + (p[1] - maps.a[index][1]) ** 2,
      0,
    ) / b.length,
  );
  const result = `The gap across all ${b.length} known point pairs is ${gap.toFixed(3)} m (RMS). ${alignment ? 'Map B has been aligned.' : 'Map B is still in its local frame.'}`;
  const comparison = useExperimentComparison({
    settings: `Seed ${seed}; noise ${noise} m; ${shared} shared pairs; communication ${connected ? 'on' : 'off'}; ${alignment ? 'aligned' : 'unaligned'}`,
    result,
    graphic: (
      <Plot label="Map alignment comparison snapshot" bounds={[-5, -4, 4, 4]}>
        {maps.a.map((p, i) => (
          <circle key={'a' + i} cx={p[0]} cy={p[1]} r=".085" fill="var(--teal)" />
        ))}
        {b.map((p, i) => (
          <rect
            key={i}
            x={p[0] - 0.07}
            y={p[1] - 0.07}
            width=".14"
            height=".14"
            fill="var(--orange)"
          />
        ))}
      </Plot>
    ),
  });
  return (
    <>
      <div className="experiment-layout">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>Two local map frames</span>
            <span className="subtle">Known shared landmark identities</span>
          </div>
          <Plot
            label="Two independently moving robots and local maps aligned from shared landmarks"
            bounds={[-5, -4, 4, 4]}
          >
            {maps.a.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r=".085" fill="var(--teal)" />
            ))}
            {b.map((p, i) => (
              <rect
                key={i}
                x={p[0] - 0.07}
                y={p[1] - 0.07}
                width=".14"
                height=".14"
                fill="var(--orange)"
              />
            ))}
            {connected &&
              b
                .slice(0, shared)
                .map((p, i) => (
                  <line
                    key={i}
                    x1={maps.a[i][0]}
                    y1={maps.a[i][1]}
                    x2={p[0]}
                    y2={p[1]}
                    stroke="var(--slate)"
                    strokeWidth=".018"
                    strokeDasharray=".08 .08"
                  />
                ))}
            <Robot pose={[Math.cos(phase), Math.sin(phase), phase + Math.PI / 2]} />
            <Robot
              pose={[robotB[0], robotB[1], phase + 1 + Math.PI / 2 + (alignment?.angle || 0)]}
              color="var(--orange)"
            />
          </Plot>
          <Legend
            items={[
              ['Robot A / map A', 'var(--teal)'],
              ['Robot B / map B', 'var(--orange)'],
              ['Shared correspondence', 'var(--slate)'],
            ]}
          />
          <Playback player={player} total={120} />
          <p className="result-note" aria-live="polite">
            {result}
          </p>
        </section>
        <aside className="panel controls">
          <h2>Share & align</h2>
          <ExperimentTools
            save={comparison.save}
            saved={comparison.saved}
            examples={[
              {
                label: 'Align clear observations',
                run: () => {
                  setNoise(0);
                  setShared(5);
                  setConnected(true);
                  setAligned(true);
                },
              },
              {
                label: 'Align noisy observations',
                run: () => {
                  setNoise(0.25);
                  setShared(5);
                  setConnected(true);
                  setAligned(true);
                },
              },
            ]}
          />
          <p>
            Rotate and shift map B to line up its shared landmarks with map A. Each map begins with
            its own coordinate system.
          </p>
          <Range
            label="Shared landmarks"
            value={shared}
            min={0}
            max={10}
            step={1}
            help="Number of point pairs used to fit the maps. At least two distinct pairs are needed in this example."
            onChange={(v) => {
              setShared(v);
              setAligned(false);
            }}
          />
          <Range
            label="Observation noise"
            value={noise}
            min={0}
            max={0.3}
            step={0.01}
            unit="m"
            help="Random error in landmark positions. More noise can leave larger gaps after alignment."
            onChange={(v) => {
              setNoise(v);
              setAligned(false);
            }}
          />
          <Toggle
            label="Communication enabled"
            checked={connected}
            onChange={(v) => {
              setConnected(v);
              setAligned(false);
            }}
          />
          <button
            className="button primary"
            disabled={!connected || shared < 2}
            onClick={() => setAligned(true)}
          >
            <Icon name="algorithms" size={17} /> Align shared landmarks
          </button>
          <button
            className="button secondary"
            onClick={() => {
              setAligned(false);
              player.reset();
            }}
          >
            Reset alignment
          </button>
          <p className="help">
            {!connected
              ? 'Enable communication to share observations.'
              : shared < 2
                ? 'Choose at least two distinct shared landmarks.'
                : alignment
                  ? `Recovered rotation ${((alignment.angle * 180) / Math.PI).toFixed(1)}°; translation ${alignment.translation.map((v) => v.toFixed(2)).join(', ')} m.`
                  : 'The fit will use the chosen pairs of observations of the same landmarks.'}
          </p>
        </aside>
      </div>
      {comparison.panel}
      <Lesson
        title="Shared observations connect local frames."
        formula={String.raw`\min_{R\in SO(2),t}\sum_i\|Rp_i+t-q_i\|^2`}
        label="Rigid map alignment objective"
        link="multi-robot"
        meaning="Turn and shift one map until the total squared gap between observations of the same landmarks is as small as possible."
        symbols="R is a 2D rotation, t is a shift, p and q are a shared point’s coordinates in the two maps, and i selects a pair. The squared norm measures their squared gap after transforming the first point."
      >
        <p>
          Each robot begins with its own starting point and directions. Matching shared landmarks
          reveals how to turn and shift one map into the other’s coordinates. More shared points can
          help the fit cope with noisy observations.
        </p>
        <p>
          This is an introductory alignment model. The research collection explores full distributed
          estimation and communication protocols.
        </p>
      </Lesson>
    </>
  );
}

export default function Playground() {
  const requested = new URLSearchParams(location.search).get('module');
  const active: ModuleId = modules.some((module) => module[0] === requested)
    ? (requested as ModuleId)
    : 'odometry';
  const [seed, setSeed] = useState(42);
  const navigate = useContext(Navigation);
  const nextModule = modules[modules.findIndex((module) => module[0] === active) + 1];
  const handoff: Record<ModuleId, string> = {
    odometry: 'Movement can drift. Next, see how observations build a map.',
    occupancy: 'A map needs observations. How does a camera recognise the same detail twice?',
    features:
      'Useful observations can connect places. See what happens when the robot revisits one.',
    graph: 'One robot can connect its path. Now connect the maps from two robots.',
    multi: 'You have explored the pieces. Run a complete local experiment next.',
  };
  return (
    <>
      <PageHeader
        eyebrow="THE INTERACTIVE PLAYGROUND"
        title="Learn by changing the experiment."
        description="SLAM helps a robot locate itself while building a map. Change one thing and watch what happens."
        action={<span className="badge">Educational models · browser-local</span>}
      />
      <nav className="module-tabs" aria-label="Playground modules">
        {modules.map(([id, n, title, subtitle]) => (
          <button
            key={id}
            className={active === id ? 'active' : ''}
            aria-pressed={active === id}
            onClick={() => navigate('playground/?module=' + id)}
          >
            <span>{n}</span>
            <strong>{title}</strong>
            <small>{subtitle}</small>
          </button>
        ))}
      </nav>
      <label className="mobile-module-select">
        Choose an experiment
        <select
          aria-label="Choose an experiment"
          value={active}
          onChange={(event) => navigate('playground/?module=' + event.target.value)}
        >
          {modules.map(([id, , title]) => (
            <option key={id} value={id}>
              {title}
            </option>
          ))}
        </select>
      </label>
      <p className="mobile-activity-context">{playgroundGuides[active].explanation}</p>
      <div className="experiment-toolbar">
        <div>
          <span className="eyebrow">EXPERIMENT {modules.find((m) => m[0] === active)![1]}</span>
          <h2>{modules.find((m) => m[0] === active)![2]}</h2>
        </div>
        <details className="seed-settings">
          <summary>Repeatable settings</summary>
          <div className="seed-controls">
            <label className="seed-field">
              Random seed
              <input
                type="number"
                min="0"
                max="2147483647"
                value={seed}
                aria-describedby="random-seed-help"
                onChange={(e) =>
                  setSeed(
                    Math.max(0, Math.min(2147483647, Math.trunc(Number(e.target.value) || 0))),
                  )
                }
              />
            </label>
            <p className="help" id="random-seed-help">
              A seed makes random examples repeatable. Changing it restarts this activity with
              default controls.
            </p>
          </div>
        </details>
      </div>
      <div key={active + seed}>
        {active === 'odometry' ? (
          <Odometry seed={seed} />
        ) : active === 'occupancy' ? (
          <Occupancy seed={seed} />
        ) : active === 'features' ? (
          <Features seed={seed} />
        ) : active === 'graph' ? (
          <Graph seed={seed} />
        ) : (
          <Multi seed={seed} />
        )}
      </div>
      <ExperimentGuide key={active} module={active} />
      <section className="activity-handoff">
        <div>
          <span className="eyebrow">CONNECT THE IDEAS</span>
          <p>{handoff[active]}</p>
        </div>
        <Link
          className="button secondary"
          to={nextModule ? 'playground/?module=' + nextModule[0] : 'simulations/'}
        >
          {nextModule ? 'Next: ' + nextModule[2] : 'Open Simulation Lab'}
          <Icon name="arrow" size={15} />
        </Link>
      </section>
    </>
  );
}
