import { useMemo, useState } from 'react';
import content from '../generated/content.json';
import {
  BASE,
  Icon,
  Legend,
  Link,
  PageHeader,
  PathLine,
  Playback,
  Plot,
  REPO,
  Robot,
  Stat,
  usePlayback,
  useReplay,
} from '../components/ui';
import { odometry } from '../lab/models';

function HeroPlot() {
  const motion = useMemo(() => odometry(42, 0.045, 0.045, 0.65), []),
    player = usePlayback(motion.length, 90);
  const current = motion[player.frame];
  return (
    <div className="hero-plot panel">
      <div className="panel-heading">
        <span>
          <i className="live-dot" />
          LIVE EXPERIMENT
        </span>
        <span className="subtle">01 / Motion & uncertainty</span>
      </div>
      <Plot
        label="Interactive odometry experiment showing noise accumulating along a trajectory"
        bounds={[-4, -3, 4, 5]}
      >
        <PathLine
          points={motion.slice(0, player.frame + 1).map((f) => f.truth)}
          color="var(--slate)"
          dashed
        />
        <PathLine
          points={motion.slice(0, player.frame + 1).map((f) => f.estimate)}
          color="var(--teal)"
        />
        <Robot pose={current.estimate} />
      </Plot>
      <div className="hero-readout">
        <span>
          POSITION ERROR{' '}
          <b>
            {current.error.toFixed(3)} <small>m</small>
          </b>
        </span>
        <span>
          MODEL <b>Seed 42</b>
        </span>
      </div>
      <Legend
        items={[
          ['Reference motion', 'var(--slate)'],
          ['Noisy odometry', 'var(--teal)'],
        ]}
      />
      <Playback player={player} total={motion.length} />
    </div>
  );
}
export function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="status-dot" /> AN OPEN LAB FOR SPATIAL INTELLIGENCE
          </div>
          <h1>
            How does a robot
            <br />
            find its <em>place?</em>
          </h1>
          <p>
            Explore the ideas behind simultaneous localization and mapping. Change the noise. Close
            a loop. Build a map. Then run the experiment yourself.
          </p>
          <div className="button-row">
            <Link to="playground/" className="button">
              Enter the playground <Icon name="arrow" size={18} />
            </Link>
            <Link to="learn/" className="button secondary">
              Start learning
            </Link>
          </div>
          <div className="hero-tags">
            <span>Interactive by design</span>
            <span>Reproducible experiments</span>
            <span>Open source</span>
          </div>
        </div>
        <HeroPlot />
      </section>
      <div className="numbers-strip">
        <div>
          <b>05</b>
          <span>interactive experiments</span>
        </div>
        <div>
          <b>12</b>
          <span>guided lessons</span>
        </div>
        <div>
          <b>07</b>
          <span>algorithm profiles</span>
        </div>
        <div>
          <b>∞</b>
          <span>questions to explore</span>
        </div>
      </div>
      <section className="section">
        <div className="section-heading">
          <div className="eyebrow">A LITTLE THEORY. A LOT OF DISCOVERY.</div>
          <h2>Make the invisible visible.</h2>
          <p>Follow a measurement from a noisy sensor to a shared understanding of space.</p>
        </div>
        <div className="card-grid three">
          {[
            [
              'lab',
              'Build an intuition',
              'Turn abstract equations into experiments you can see, pause, and change.',
              'playground/',
              'Try an experiment',
            ],
            [
              'simulation',
              'Run a real pipeline',
              'Launch a differential-drive robot in Webots and estimate its pose and landmark map.',
              'simulations/',
              'Open Simulation Lab',
            ],
            [
              'studio',
              'Read the evidence',
              'Replay measured trajectories, inspect map checkpoints, and understand ATE and RPE.',
              'studio/',
              'Open the Studio',
            ],
          ].map(([icon, title, text, to, cta]) => (
            <Link to={to} className="feature-card" key={title}>
              <span className="card-icon">
                <Icon name={icon} size={24} />
              </span>
              <h3>{title}</h3>
              <p>{text}</p>
              <span className="text-link">
                {cta} <Icon name="arrow" size={16} />
              </span>
            </Link>
          ))}
        </div>
      </section>
      <section className="journey panel">
        <div>
          <div className="eyebrow">YOUR NEXT COORDINATE</div>
          <h2>Curiosity is the only prerequisite.</h2>
          <p>
            Start with motion and uncertainty. Work toward visual SLAM, pose graphs, and
            collaborative robots at your own pace.
          </p>
          <Link to="learn/" className="button secondary">
            Find your learning path <Icon name="arrow" size={16} />
          </Link>
        </div>
        <div className="journey-steps">
          <span>
            01 <b>Understand motion</b>
          </span>
          <span>
            02 <b>Connect observations</b>
          </span>
          <span>
            03 <b>Optimize the map</b>
          </span>
        </div>
      </section>
    </>
  );
}

export function Learn() {
  return (
    <>
      <PageHeader
        eyebrow="LEARNING PATHS"
        title="From first principles to shared maps."
        description="Twelve connected lessons. Read the idea, work through the math, then make it move in the playground."
      />
      {['Beginner', 'Intermediate', 'Advanced'].map((level, i) => (
        <section className="section" key={level}>
          <div className="level-heading">
            <span className="level-number">0{i + 1}</span>
            <div>
              <h2>{level}</h2>
              <p>
                {
                  [
                    'Build a geometric and probabilistic intuition.',
                    'Connect measurements to maps and estimation.',
                    'Optimize, collaborate, and evaluate responsibly.',
                  ][i]
                }
              </p>
            </div>
          </div>
          <div className="card-grid two">
            {content.documents
              .filter((d) => d.level === level)
              .map((d, j) => (
                <Link to={'documentation/' + d.id + '/'} className="lesson-card" key={d.id}>
                  <span className="lesson-number">{String(i * 4 + j + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{d.title}</h3>
                    <p>{d.description}</p>
                    <span className="text-link">
                      Read lesson <Icon name="arrow" size={15} />
                    </span>
                  </div>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </>
  );
}

export function Algorithms({ id }: { id?: string }) {
  const [sensor, setSensor] = useState('All'),
    [query, setQuery] = useState('');
  const chosen = content.catalog.find((a) => a.id === id);
  if (id && !chosen)
    return (
      <>
        <h1>Algorithm not found</h1>
        <Link to="algorithms/">All algorithms</Link>
      </>
    );
  if (chosen)
    return (
      <>
        <Link to="algorithms/" className="text-link">
          ← All algorithms
        </Link>
        <PageHeader
          eyebrow={chosen.category.toUpperCase()}
          title={chosen.name}
          description={chosen.approach}
        />
        <div className="detail-grid">
          <section className="panel prose">
            <h2>How it works</h2>
            <h3>Front end</h3>
            <p>{chosen.frontEnd}</p>
            <h3>Back end</h3>
            <p>{chosen.backEnd}</p>
            <h3>Outputs</h3>
            <p>{chosen.outputs}</p>
            <h3>Research & attribution</h3>
            <p>{chosen.publication}</p>
            <p>{chosen.authors}</p>
            <div className="button-row">
              <a href={chosen.paper} className="button secondary">
                Read reference <Icon name="external" size={15} />
              </a>
              <a href={chosen.source} className="text-link">
                Upstream source <Icon name="external" size={15} />
              </a>
            </div>
          </section>
          <aside className="panel controls">
            <h2>System profile</h2>
            <dl>
              <dt>Sensors</dt>
              <dd>{chosen.sensors.join(', ')}</dd>
              <dt>Architecture</dt>
              <dd>{chosen.architecture}</dd>
              <dt>Environment</dt>
              <dd>{chosen.ros}</dd>
              <dt>Scale</dt>
              <dd>{chosen.scale}</dd>
            </dl>
            <a href={REPO + '/blob/main/' + chosen.guide} className="button secondary">
              Integration guide <Icon name="arrow" size={15} />
            </a>
            {chosen.id === 'ekf-slam' ? (
              <Link to="simulations/" className="button">
                Run the experiment
              </Link>
            ) : (
              <p className="help">
                Native build and execution requirements are tracked in the{' '}
                <a href={REPO + '/milestone/1'}>research integration milestone</a>. This profile
                describes the published system.
              </p>
            )}
          </aside>
        </div>
      </>
    );
  const visible = content.catalog.filter(
    (a) =>
      (sensor === 'All' || a.sensors.includes(sensor)) &&
      (a.name + ' ' + a.approach + ' ' + a.architecture)
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="ALGORITHM EXPLORER"
        title="Different sensors. Different strategies."
        description="Compare the ideas, sensor contracts, and architectures behind seven SLAM systems. Follow each profile to the original research and implementation."
      />
      <div className="filter-bar panel">
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Search algorithms"
            placeholder="Search algorithms or approaches…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label className="select-label">
          Sensor
          <select value={sensor} onChange={(e) => setSensor(e.target.value)}>
            {['All', ...new Set(content.catalog.flatMap((a) => a.sensors))].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <span className="subtle">{visible.length} systems</span>
      </div>
      <div className="card-grid two">
        {visible.map((a) => (
          <Link to={'algorithms/' + a.id + '/'} className="algorithm-card panel" key={a.id}>
            <div className="card-top">
              <span className="chip">{a.category}</span>
              <Icon name="arrow" size={18} />
            </div>
            <h2>{a.name}</h2>
            <p>{a.approach}</p>
            <div className="tags">
              {a.sensors.map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <div className="algorithm-meta">
              <span>{a.architecture}</span>
              <span>{a.ros}</span>
            </div>
          </Link>
        ))}
      </div>
      {!visible.length && <p role="status">No systems match. Try another sensor or search term.</p>}
    </>
  );
}

export function Simulations() {
  const [robots, setRobots] = useState(1),
    [duration, setDuration] = useState(30);
  return (
    <>
      <PageHeader
        eyebrow="SIMULATION LAB"
        title="An idea becomes an experiment."
        description="Run a complete landmark EKF-SLAM pipeline in Webots R2025a. Wheel encoders predict motion; relative range and bearing observations correct the robot and map together."
      />
      <div className="detail-grid">
        <section className="panel scenario">
          <img
            className="result-image"
            src={BASE + 'generated/landmark-slam.png'}
            alt="Measured Webots landmark map with the EKF trajectory, odometry and reference geometry"
          />
          <div className="scenario-copy">
            <span className="chip">RUNNABLE · PYTHON + WEBOTS</span>
            <h2>Landmark Lab</h2>
            <p>
              A differential-drive robot explores twelve markers. A separate supervisor records
              reference poses for evaluation. Marker identities come from simulated camera
              recognition; the estimator receives relative observations.
            </p>
            <div className="tags">
              <span>Metric SE(2)</span>
              <span>Seed 42</span>
              <span>Wheel encoders</span>
              <span>Range / bearing</span>
            </div>
            <Link to="studio/" className="text-link">
              Inspect the recorded experiment <Icon name="arrow" size={16} />
            </Link>
          </div>
        </section>
        <aside className="panel controls">
          <h2>Configure your run</h2>
          <label className="select-label">
            Robot sessions
            <select value={robots} onChange={(e) => setRobots(Number(e.target.value))}>
              <option value={1}>One robot</option>
              <option value={2}>Two independent robots</option>
            </select>
          </label>
          <label className="select-label">
            Duration
            <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
              {[15, 30, 60].map((n) => (
                <option key={n} value={n}>
                  {n} seconds
                </option>
              ))}
            </select>
          </label>
          <p className="help">
            Two robots estimate separate maps. Collaborative frame alignment is explored in the
            playground.
          </p>
          <pre>
            <code>{`python -B tools/slam.py setup ekf-slam\npython -B tools/slam.py run ekf-slam \\\n  --robots ${robots} --seconds ${duration} \\\n  --output outputs/my-landmark-run`}</code>
          </pre>
          <Link to="documentation/first-experiment/" className="button">
            Follow the setup guide <Icon name="arrow" size={16} />
          </Link>
        </aside>
      </div>
      <section className="section">
        <h2>From sensors to evidence</h2>
        <div className="pipeline">
          {[
            'Encoders + markers',
            'EKF joint estimation',
            'Trajectory + landmark map',
            'ATE / RPE + replay',
          ].map((s, i) => (
            <div key={s}>
              <span>0{i + 1}</span>
              <b>{s}</b>
            </div>
          ))}
        </div>
        <p>
          Each run preserves its configuration, relative sensor stream, estimated states, reference
          poses, map covariance, evaluation JSON, plots, and a browser replay. Sensor-only replay
          can reproduce the estimator without reference data.
        </p>
        <div className="button-row">
          <Link to="documentation/landmark-lab/" className="button secondary">
            Sensor contract & outputs
          </Link>
          <Link to="playground/?module=multi" className="text-link">
            Explore multi-robot alignment <Icon name="arrow" size={16} />
          </Link>
        </div>
      </section>
    </>
  );
}

export function Benchmarks() {
  const [sample, setSample] = useState('landmark-reference'),
    { data, error } = useReplay(sample),
    [robot, setRobot] = useState(0);
  const r = data?.robots[robot] || data?.robots[0],
    m = r?.metrics;
  return (
    <>
      <PageHeader
        eyebrow="MEASURED RESULTS"
        title="A result you can trace back."
        description="Inspect metrics from recorded Webots runs. These results describe Landmark Lab with a known initial pose and marker identities; they are not a ranking of the research systems."
      />
      <div className="filter-bar panel">
        <label className="select-label">
          Experiment
          <select
            value={sample}
            onChange={(e) => {
              setSample(e.target.value);
              setRobot(0);
            }}
          >
            <option value="landmark-reference">One robot · seed 42 · 30 seconds</option>
            <option value="landmark-two-robots">
              Two independent robots · seed 42 · 30 seconds
            </option>
          </select>
        </label>
        <label className="select-label">
          Robot
          <select value={robot} onChange={(e) => setRobot(Number(e.target.value))}>
            {data?.robots.map((r, i) => (
              <option value={i} key={r.id}>
                {r.id}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      {m && r && (
        <>
          <div className="metric-grid">
            <Stat label="Position ATE · RMSE" value={m.ate_m.rmse.toFixed(4)} unit="m" />
            <Stat
              label="Odometry baseline · ATE"
              value={m.odometry_baseline_ate_m?.rmse.toFixed(4) || '—'}
              unit="m"
            />
            <Stat
              label="Landmark map · RMSE"
              value={m.landmark_map?.rmse_m.toFixed(4) || '—'}
              unit="m"
            />
            <Stat label="Matched poses" value={m.association?.matched || r.estimate.length} />
          </div>
          <section className="panel prose">
            <h2>Read the experiment</h2>
            <dl className="facts">
              <dt>Translation RPE RMSE</dt>
              <dd>{m.rpe?.translation_m.rmse.toFixed(5)} m</dd>
              <dt>Rotation RPE RMSE</dt>
              <dd>{m.rpe?.rotation_deg.rmse.toFixed(4)}°</dd>
              <dt>Reference coverage</dt>
              <dd>{((m.association?.reference_fraction || 0) * 100).toFixed(1)}%</dd>
              <dt>Landmarks</dt>
              <dd>{r.landmarks.length}</dd>
              <dt>Estimator</dt>
              <dd>Landmark EKF-SLAM · independent sessions</dd>
              <dt>Evaluation</dt>
              <dd>Python toolkit · timestamp association · shared world frame, no alignment</dd>
            </dl>
            <div className="button-row">
              <Link
                to={'studio/' + (sample.endsWith('two-robots') ? '?sample=two' : '')}
                className="button"
              >
                Replay this result <Icon name="arrow" size={16} />
              </Link>
              <a
                href={BASE + 'generated/' + sample + '.json'}
                download
                className="button secondary"
              >
                Download data
              </a>
            </div>
          </section>
        </>
      )}
      <section className="section prose">
        <h2>Understand the comparison</h2>
        <p>
          The odometry baseline and EKF use the same wheel measurements. EKF corrections use
          relative camera marker observations. Reference poses and marker positions are available to
          the evaluator, separately from estimation. Map RMSE compares matching marker identities in
          the declared world frame.
        </p>
        <p>
          Benchmark numbers are copied from the Python evaluator. Browser animations use compact
          display data. Inspect configuration and reproduction commands in the{' '}
          <a href={REPO + '/tree/main/examples/results'}>published result manifests</a>.
        </p>
        <Link to="documentation/metrics/" className="text-link">
          How ATE, RPE, alignment and coverage work <Icon name="arrow" size={16} />
        </Link>
      </section>
    </>
  );
}

export function Documentation({ id }: { id?: string }) {
  const [query, setQuery] = useState('');
  const doc = content.documents.find((d) => d.id === id);
  if (id && !doc)
    return (
      <>
        <h1>Document not found</h1>
        <Link to="documentation/">Documentation index</Link>
      </>
    );
  if (doc) {
    const index = content.documents.indexOf(doc),
      next = content.documents[index + 1];
    return (
      <div className="doc-layout">
        <aside className="doc-nav">
          <Link to="documentation/" className="text-link">
            ← Documentation
          </Link>
          {content.documents.map((d) => (
            <Link
              key={d.id}
              to={'documentation/' + d.id + '/'}
              className={d.id === id ? 'selected' : ''}
            >
              {d.title}
            </Link>
          ))}
        </aside>
        <article className="prose document">
          <div className="doc-meta">
            <span className="eyebrow">{doc.level}</span>
            <a href={REPO + '/blob/main/' + doc.source}>
              Edit on GitHub <Icon name="external" size={13} />
            </a>
          </div>
          <div dangerouslySetInnerHTML={{ __html: doc.html }} />
          {next && (
            <Link to={'documentation/' + next.id + '/'} className="next-lesson">
              <span>CONTINUE EXPLORING</span>
              <b>{next.title} →</b>
            </Link>
          )}
        </article>
      </div>
    );
  }
  const docs = content.documents.filter((d) =>
    (d.title + ' ' + d.description).toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="DOCUMENTATION"
        title="Keep a good field notebook."
        description="Installation, mathematical foundations, reproducible experiments, and practical guides. The website and repository share the same documentation."
      />
      <label className="search-field panel">
        <Icon name="search" />
        <input
          aria-label="Search documentation"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find a lesson or guide…"
        />
      </label>
      <div className="card-grid two section">
        {docs.map((d) => (
          <Link className="document-card panel" key={d.id} to={'documentation/' + d.id + '/'}>
            <span className="eyebrow">{d.level}</span>
            <h2>{d.title}</h2>
            <p>{d.description}</p>
            <Icon name="arrow" size={18} />
          </Link>
        ))}
      </div>
      {!docs.length && <p role="status">No guides match your search.</p>}
    </>
  );
}

export function About() {
  return (
    <>
      <PageHeader
        eyebrow="ABOUT SLAMLAB"
        title="A shared space for understanding space."
        description="An open-source learning and experimentation platform for simultaneous localization and mapping."
      />
      <section className="panel prose about-copy">
        <h2>Learn it. Run it. Question it.</h2>
        <p>
          SLAMLab connects interactive explanations with inspectable implementations and measured
          experiments. It grew from{' '}
          <em>
            Autonomous Swarm Robotic System for Intelligent Mapping and Cleaning of Large
            Environments
          </em>
          , consolidating reusable educational, simulation, SLAM integration, and evaluation
          resources from that project. It continues as a place to learn, reproduce, and extend
          multi-robot mapping ideas.
        </p>
        <p>
          The original{' '}
          <a href="https://github.com/Kanishk-Rungta/Final-Year-Project">Final-Year-Project</a>{' '}
          remains its own historical source. SLAMLab adds new tooling, a runnable landmark pipeline,
          a curriculum, and browser experiments while preserving upstream attribution and licenses.
        </p>
        <h2>People & attribution</h2>
        <p>
          Platform maintainer: <a href="https://github.com/Kanishk-Rungta">Kanishk Rungta</a>, as
          credited in the repository software citation. Original research authors are credited in
          each algorithm profile; imported team work retains its source notices.
        </p>
        <h2>Built in the open</h2>
        <p>
          Project-authored software is MIT licensed. Imported systems retain their respective
          licenses. Cite the original papers for the algorithms you use, alongside SLAMLab for
          platform tooling.
        </p>
        <div className="button-row">
          <a href={REPO} className="button">
            Explore the repository <Icon name="external" size={16} />
          </a>
          <Link to="documentation/contributing/" className="button secondary">
            Contribute a lesson or experiment
          </Link>
        </div>
        <h2>Where we go next</h2>
        <p>
          Native research integrations are developed through{' '}
          <a href={REPO + '/milestone/1'}>tracked build and execution tasks</a>. Contributions can
          add calibrated sensor adapters, validated native runs, new scenarios, accessible lessons,
          or more ways to inspect results.
        </p>
        <Link to="documentation/references/" className="text-link">
          Research references & attribution <Icon name="arrow" size={16} />
        </Link>
      </section>
    </>
  );
}
