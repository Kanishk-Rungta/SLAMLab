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
import { plotBounds } from '../lab/plotBounds';
import { ConceptDiagram, LessonVisual } from '../components/LessonVisual';
import { lessonConcepts } from '../lab/learning';
import { LearningExperience } from '../components/LearningExperience';
import { CodeBlock, HtmlContent, LoadNotice } from '../components/ContentTools';
import { SiteJourney } from '../components/SiteJourney';
import { ResearchResources } from '../components/ResearchResources';
import { MetricComparison } from '../components/MetricComparison';
import { algorithmStories, availability } from '../lab/algorithmStories';
import { documentGroups } from '../lab/documentGroups';

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
        bounds={plotBounds(motion.flatMap((frame) => [frame.truth, frame.estimate]))}
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
            A robot needs to find its position while building a map. That is SLAM. See the idea,
            change a small experiment, then explore a complete recorded run.
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
      <SiteJourney />
      <section className="panel home-project">
        <div>
          <p className="eyebrow">THE PROJECT BEHIND SLAMLAB</p>
          <h2>From learning ideas to collaborative mapping.</h2>
          <p>
            Team 98 is investigating an edge-based multi-robot system for collaborative SLAM and
            autonomous task coordination.
          </p>
        </div>
        <Link to="project/" className="button secondary">
          Project, team and current progress <Icon name="arrow" size={16} />
        </Link>
      </section>
    </>
  );
}

export function Learn() {
  return (
    <>
      <PageHeader
        eyebrow="LEARN BY SEEING"
        title="How does a robot find its way?"
        description="SLAM helps a robot find its position while building a map of an unfamiliar room. Follow the idea, one change at a time."
      />
      <LessonVisual id="fundamentals" />
      <div className="course-intro-actions">
        <Link to="documentation/fundamentals/" className="button">
          Start the journey <Icon name="arrow" size={16} />
        </Link>
        <a href="#learning-questions" className="text-link">
          Or choose a question below
        </a>
        <span>Every lesson works on its own.</span>
      </div>
      <div id="learning-questions" />
      {['Beginner', 'Intermediate', 'Advanced'].map((level, i) => (
        <section className="section" key={level}>
          <div className="level-heading">
            <span className="level-number">0{i + 1}</span>
            <div>
              <span className="eyebrow">{level}</span>
              <h2>{['Start with the robot', 'Build an understanding', 'Connect and check'][i]}</h2>
              <p>
                {
                  [
                    'Where am I? What can I trust?',
                    'Recognise details. Estimate movement. Map the room.',
                    'Revisit places. Share maps. Check the evidence.',
                  ][i]
                }
              </p>
            </div>
          </div>
          <div className="card-grid two">
            {content.documents
              .filter((d) => d.level === level)
              .map((d, j) => (
                <Link
                  to={'documentation/' + d.id + '/'}
                  className="lesson-card visual-lesson"
                  key={d.id}
                >
                  <div className="lesson-preview">
                    <ConceptDiagram id={d.id} step={d.id === 'multi-robot' ? 1 : 2} compact />
                  </div>
                  <div className="lesson-card-copy">
                    <span className="lesson-number">{String(i * 4 + j + 1).padStart(2, '0')}</span>
                    <div>
                      <span className="lesson-topic">{d.title}</span>
                      <h3>{lessonConcepts[d.id].question}</h3>
                      <p>{lessonConcepts[d.id].title}</p>
                      <span className="text-link">
                        See the idea <Icon name="arrow" size={15} />
                      </span>
                    </div>
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
        <section className="panel algorithm-story">
          <span className="chip availability">{availability(chosen.operation)}</span>
          <h2>The idea in plain words</h2>
          <p>{algorithmStories[chosen.id].idea}</p>
          <div className="flow-three" aria-label="Algorithm input, process and output">
            {[
              algorithmStories[chosen.id].input,
              algorithmStories[chosen.id].process,
              algorithmStories[chosen.id].output,
            ].map((text, index) => (
              <div key={text}>
                <span className="eyebrow">{['INPUT', 'PROCESS', 'OUTPUT'][index]}</span>
                <strong>{text}</strong>
                {index < 2 && <Icon name="arrow" size={18} />}
              </div>
            ))}
          </div>
          {chosen.operation !== 'run' && (
            <p className="help">
              This describes the original research system. Native build and execution have not been
              validated in SLAMLab.
            </p>
          )}
        </section>
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
              <span className="chip">{availability(a.operation)}</span>
              <Icon name="arrow" size={18} />
            </div>
            <h2>{a.name}</h2>
            <p>{algorithmStories[a.id].idea}</p>
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
        description="Watch how a simulated robot builds a landmark map, or run the experiment on your computer with Python and Webots."
      />
      <div className="simulation-entry">
        <section className="panel">
          <p className="eyebrow">START IN YOUR BROWSER</p>
          <h2>Explore a saved experiment</h2>
          <p>Replay a measured robot path and its growing map. No installation needed.</p>
          <Link to="studio/" className="button">
            Explore a recording <Icon name="play" size={16} />
          </Link>
        </section>
        <section className="panel">
          <p className="eyebrow">RUN ON YOUR COMPUTER</p>
          <h2>Create your own recording</h2>
          <p>Choose the settings below, copy the commands, and run Webots locally.</p>
          <a className="button secondary" href="#local-run">
            Prepare a local experiment <Icon name="arrow" size={16} />
          </a>
        </section>
      </div>
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
        <aside id="local-run" className="panel controls">
          <h2>Prepare a local run command</h2>
          <p>
            This page prepares commands. Run them from the repository root on your computer with
            Python and Webots installed.
          </p>
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
          <CodeBlock
            label="Local Webots commands"
            code={`python -B tools/slam.py setup ekf-slam\npython -B tools/slam.py run ekf-slam --robots ${robots} --seconds ${duration} --output outputs/my-landmark-run`}
          />
          <p className="help">
            Use a new output directory for each run. The single-line commands work in PowerShell and
            POSIX shells.
          </p>
          <Link to="documentation/installation/" className="button">
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
    { data, error, loading, retry } = useReplay(sample),
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
      <LoadNotice loading={loading} error={error} retry={retry} />
      {m && r && (
        <>
          <MetricComparison metrics={m} />
          <div className="metric-grid">
            <Stat
              label="Position ATE · RMSE"
              value={m.ate_m.rmse.toFixed(4)}
              unit="m"
              detail="Overall position error against the reference. Lower is closer."
            />
            <Stat
              label="Odometry baseline · ATE"
              value={m.odometry_baseline_ate_m?.rmse.toFixed(4) || '—'}
              unit="m"
              detail="Position error using wheel movement alone."
            />
            <Stat
              label="Landmark map · RMSE"
              value={m.landmark_map?.rmse_m.toFixed(4) || '—'}
              unit="m"
              detail="Error in the mapped landmark positions."
            />
            <Stat
              label="Matched poses"
              value={m.association?.matched || r.estimate.length}
              detail="Position samples paired with the reference for evaluation."
            />
          </div>
          <details className="panel metric-explainer">
            <summary>Understand ATE, RPE, RMSE and coverage</summary>
            <dl>
              <div>
                <dt>ATE · position error</dt>
                <dd>
                  How far estimated positions lie from the reference after matching times and
                  applying the declared frame policy.
                </dd>
              </div>
              <div>
                <dt>RPE · movement error</dt>
                <dd>
                  How much the estimated movement differs from reference movement over the same
                  interval, including turning.
                </dd>
              </div>
              <div>
                <dt>RMSE · error summary</dt>
                <dd>
                  Root mean square error combines many errors into one value, giving larger errors
                  more weight.
                </dd>
              </div>
              <div>
                <dt>Reference coverage</dt>
                <dd>
                  The share of reference positions that could be paired with estimates. Check it
                  alongside error.
                </dd>
              </div>
            </dl>
          </details>
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
      {data && <ResearchResources sample={sample} />}
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
  if (doc && lessonConcepts[doc.id]) return <LearningExperience key={doc.id} doc={doc} />;
  if (doc) {
    const group = documentGroups.find((group) => group.ids.includes(doc.id))!;
    const nextId = group.ids[group.ids.indexOf(doc.id) + 1];
    const next = content.documents.find((d) => d.id === nextId);
    return (
      <>
        <div className="doc-layout">
          <aside className="doc-nav">
            <Link to="documentation/" className="text-link">
              All documentation
            </Link>
            <p className="eyebrow">{group.title}</p>
            {content.documents
              .filter((d) => group.ids.includes(d.id))
              .map((d) => (
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
            <HtmlContent html={doc.html} />
            {next && (
              <Link to={'documentation/' + next.id + '/'} className="next-lesson">
                <span>CONTINUE EXPLORING</span>
                <b>
                  {next.title} <Icon name="arrow" size={14} />
                </b>
              </Link>
            )}
          </article>
        </div>
        {doc.id === 'references' && <ResearchResources />}
      </>
    );
  }
  const docs = content.documents.filter((d) =>
    (d.title + ' ' + d.description).toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        eyebrow="DOCUMENTATION"
        title="Find the guide for your next step."
        description="Understand an idea, set up your computer, run an experiment, or interpret its results."
      />
      <label className="search-field panel">
        <Icon name="search" />
        <input
          aria-label="Search documentation"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find a lesson or guide..."
        />
      </label>
      <nav className="document-categories" aria-label="Documentation categories">
        {documentGroups.map((group, index) => (
          <a key={group.title} href={'#document-group-' + index}>
            {group.title}
          </a>
        ))}
      </nav>
      {documentGroups.map((group, index) => {
        const entries = group.ids.flatMap((id) => docs.filter((d) => d.id === id));
        return (
          entries.length > 0 && (
            <section
              className="section document-group"
              id={'document-group-' + index}
              key={group.title}
            >
              <h2>{group.title}</h2>
              <p>{group.description}</p>
              <div className="card-grid two">
                {entries.map((d) => (
                  <Link
                    className="document-card panel"
                    key={d.id}
                    to={'documentation/' + d.id + '/'}
                  >
                    <span className="eyebrow">{d.level}</span>
                    <h3>{d.title}</h3>
                    <p>{d.description}</p>
                    <Icon name="arrow" size={18} />
                  </Link>
                ))}
              </div>
            </section>
          )
        );
      })}
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
        description="The people, origins and open-source principles behind the platform."
      />
      <section className="panel prose about-copy">
        <h2>Why SLAMLab exists</h2>
        <p>
          SLAMLab connects visual lessons, small browser experiments and inspectable robot
          recordings. Its purpose is to make mapping ideas easier to understand and experiments
          easier to reproduce.
        </p>
        <p>
          It grew from Team 98's final-year research project. The{' '}
          <Link to="project/">project overview</Link> holds the research problem, objectives,
          methodology and current progress.
        </p>
        <h2>People and origins</h2>
        <p>
          <strong>Project guide:</strong> Dr. Vidhya Balasubramanian.
        </p>
        <p>
          The team comprises Konduru Hemesh, Manu Santosh, Rithvik Mukka, Kanishk Rungta and
          Praneeth Gorugantu. SLAMLab is developed and maintained collaboratively by the entire
          project team.
        </p>
        <p>
          The original{' '}
          <a href="https://github.com/Kanishk-Rungta/Final-Year-Project">Final-Year-Project</a>{' '}
          remains a historical source. Original algorithm authors and imported team work retain
          their attribution.
        </p>
        <h2>Built in the open</h2>
        <p>
          Project-authored software is MIT licensed. Imported systems retain their own licenses.
          Cite the research systems you use alongside SLAMLab's platform tooling.
        </p>
        <div className="button-row">
          <a href={REPO} className="button">
            Explore the repository <Icon name="external" size={16} />
          </a>
          <Link to="documentation/contributing/" className="button secondary">
            Contribute a lesson or experiment
          </Link>
        </div>
      </section>
      <ResearchResources />
    </>
  );
}
