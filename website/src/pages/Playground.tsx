import { useMemo, useState } from 'react';
import katex from 'katex';
import { features, odometry, occupancy, optimizeGraph, graphCost, poseGraph, multiRobot, alignPoints, type Point } from '../lab/models';
import { download } from '../lab/data';
import { Icon, Legend, Link, PageHeader, PathLine, Playback, Plot, Range, Robot, Stat, Toggle, usePlayback } from '../components/ui';

const modules = [
  ['odometry', '01', 'Odometry drift', 'Motion & uncertainty'],
  ['occupancy', '02', 'Occupancy mapping', 'A probabilistic map'],
  ['features', '03', 'Feature matching', 'Finding correspondences'],
  ['graph', '04', 'Pose graph', 'Closing the loop'],
  ['multi', '05', 'Multi-robot alignment', 'From local to shared'],
];

function Equation({ tex, label }: { tex: string; label: string }) {
  return <div className="equation" role="math" aria-label={label} dangerouslySetInnerHTML={{ __html: katex.renderToString(tex, { throwOnError: false, displayMode: true, output: 'html' }) }}/>;
}

function Lesson({ title, children, formula, label, link }: { title: string; children: React.ReactNode; formula: string; label: string; link: string }) {
  return <section className="lesson-note"><div><p className="eyebrow">WHAT TO NOTICE</p><h2>{title}</h2>{children}<Link to={'documentation/' + link + '/'} className="text-link">Read the lesson <Icon name="arrow" size={16}/></Link></div>
    <Equation tex={formula} label={label}/></section>;
}

function Odometry({ seed }: { seed: number }) {
  const [trans, setTrans] = useState(.04), [rotation, setRotation] = useState(.035), [speed, setSpeed] = useState(.45);
  const [truthVisible, setTruthVisible] = useState(true), [estimateVisible, setEstimateVisible] = useState(true);
  const frames = useMemo(() => odometry(seed, trans, rotation, speed), [seed, trans, rotation, speed]);
  const player = usePlayback(frames.length), current = frames[player.frame];
  return <><div className="experiment-layout"><section className="panel visual-panel"><div className="panel-heading"><span><i className="live-dot"/>Motion model</span><span className="subtle">Seed {seed} · 2D unicycle</span></div>
    <Plot label="Ground-truth and noisy odometry trajectories" bounds={[-4, -3, 4, 5]}>
      {truthVisible && <PathLine points={frames.slice(0, player.frame + 1).map(f => f.truth)} color="var(--slate)" dashed/>}
      {estimateVisible && <><PathLine points={frames.slice(0, player.frame + 1).map(f => f.estimate)}/><Robot pose={current.estimate}/></>}
      {truthVisible && <Robot pose={current.truth} color="var(--slate)" size={.1}/>}</Plot>
    <Legend items={[["Reference motion", 'var(--slate)'], ['Wheel odometry', 'var(--teal)']]}/>
    <Playback player={player} total={frames.length} label={current.t.toFixed(1) + ' s'}/></section>
    <aside className="panel controls"><h2>Experiment controls</h2><p>Change the noise model, then replay the same motion.</p>
      <Range label="Robot speed" value={speed} min={.15} max={.65} unit="m/s" onChange={setSpeed}/>
      <Range label="Translation noise" value={trans} min={0} max={.15} step={.005} unit="m/√s" onChange={setTrans}/>
      <Range label="Rotation noise" value={rotation} min={0} max={.15} step={.005} unit="rad/√s" onChange={setRotation}/>
      <fieldset><legend>Visible layers</legend><Toggle label="Reference trajectory" checked={truthVisible} onChange={setTruthVisible}/><Toggle label="Estimated trajectory" checked={estimateVisible} onChange={setEstimateVisible}/></fieldset>
      <div className="small-stats"><Stat label="Position error" value={current.error.toFixed(3)} unit="m"/><Stat label="Distance travelled" value={current.length.toFixed(2)} unit="m"/></div></aside></div>
    <Lesson title="Small errors travel with you." formula={String.raw`x_{t+1}=x_t+d\cos(\theta_t+\Delta\theta/2)`} label="Midpoint planar motion update" link="frames">
      <p>A heading error changes the direction of every later step. Set both noise terms to zero to make the paths agree, then increase rotation noise and watch the position error grow.</p>
      <p>Noise is sampled with √Δt scaling. This is a seeded educational motion model, so resets replay the same random sequence.</p></Lesson></>;
}

function Occupancy({ seed }: { seed: number }) {
  const [range, setRange] = useState(4), [noise, setNoise] = useState(.03), [resolution, setResolution] = useState(.2), [visible, setVisible] = useState(true), [raysVisible, setRaysVisible] = useState(true);
  const frames = useMemo(() => occupancy(seed, range, noise, resolution), [seed, range, noise, resolution]);
  const player = usePlayback(frames.length), frame = frames[player.frame];
  const known = frame.grid.filter(v => v !== 0).length;
  const exportMap = () => download('educational-occupancy-map.json', { schema_version: 1, kind: 'educational_model', width: frame.width, height: frame.width, resolution: frame.resolution, origin: [-4, -4], frame: 'World XY; rows along +Y', cells: frame.grid.map(v => v === 0 ? -1 : v > .5 ? 1 : 0) });
  return <><div className="experiment-layout"><section className="panel visual-panel"><div className="panel-heading"><span><i className="live-dot"/>Inverse sensor model</span><button className="text-link" onClick={exportMap}><Icon name="download" size={15}/> Map JSON</button></div>
    <Plot label="Incremental log-odds occupancy grid with simulated range beams">
      {visible && frame.grid.map((v, i) => <rect key={i} x={-4 + i % frame.width * frame.resolution} y={-4 + Math.floor(i / frame.width) * frame.resolution}
        width={frame.resolution * .98} height={frame.resolution * .98} fill={v === 0 ? 'var(--unknown)' : v > .5 ? 'var(--occupied)' : 'var(--free)'} opacity={v === 0 ? .45 : Math.min(.95, .4 + Math.abs(v) * .12)}/>)}
      {raysVisible && frame.rays.map((p, i) => <line key={i} x1={frame.pose[0]} y1={frame.pose[1]} x2={p[0]} y2={p[1]} stroke="var(--orange)" strokeWidth=".012" opacity=".55"/>)}
      <Robot pose={frame.pose}/></Plot>
    <Legend items={[["Occupied", 'var(--occupied)'], ['Free', 'var(--free)'], ['Unknown', 'var(--unknown)'], ['Range beams', 'var(--orange)']]}/>
    <Playback player={player} total={frames.length}/></section>
    <aside className="panel controls"><h2>Sensor & map</h2><p>Every range beam contributes free-space and hit evidence.</p>
      <Range label="Sensor range" value={range} min={1} max={6} step={.25} unit="m" onChange={setRange}/>
      <Range label="Range noise" value={noise} min={0} max={.2} step={.01} unit="m" onChange={setNoise}/>
      <Range label="Cell resolution" value={resolution} min={.1} max={.5} step={.05} unit="m" onChange={setResolution}/>
      <Toggle label="Occupancy map" checked={visible} onChange={setVisible}/><Toggle label="Sensor beams" checked={raysVisible} onChange={setRaysVisible}/>
      <Stat label="Observed cells" value={known} detail={`${frame.width} × ${frame.width} grid · unknown is not free`}/></aside></div>
    <Lesson title="A map is accumulated evidence." formula={String.raw`l_t=l_{t-1}+\log\frac{p(m\mid z_t,x_t)}{1-p(m\mid z_t,x_t)}`} label="Log odds occupancy update" link="mapping">
      <p>Beams reduce occupancy belief along their path and increase it at measured hits. Smaller cells reveal detail but require more memory and updates.</p><p>The robot pose is supplied in this mapping lesson. Estimating pose and map together is the next step in a SLAM system.</p></Lesson></>;
}

function Features({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(.2), [threshold, setThreshold] = useState(.65), [mutual, setMutual] = useState(true);
  const result = useMemo(() => features(seed, noise, threshold, mutual), [seed, noise, threshold, mutual]);
  const correct = result.matches.filter(m => m.correct).length;
  const position = (point: Point, right = false): Point => [35 + point[0] * 220 + (right ? 320 : 0), 35 + point[1] * 260];
  return <><div className="experiment-layout"><section className="panel visual-panel"><div className="panel-heading"><span>Descriptor correspondence</span><span className="subtle">Synthetic feature pair</span></div>
    <div className="feature-visual"><svg viewBox="0 0 640 340" role="img" aria-label="Two feature sets with computed correct and incorrect descriptor matches">
      <rect x="15" y="15" width="280" height="310" rx="12" fill="var(--canvas)" stroke="var(--border)"/><rect x="335" y="15" width="280" height="310" rx="12" fill="var(--canvas)" stroke="var(--border)"/>
      {result.matches.map((m, i) => { const a = position(result.left[m.left].point), b = position(result.right[m.right].point, true); return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={m.correct ? 'var(--teal)' : 'var(--orange)'} opacity=".55" strokeWidth="1.4"/>; })}
      {result.left.map((f, i) => { const p = position(f.point); return <circle key={i} cx={p[0]} cy={p[1]} r="4" fill="var(--teal)"/>; })}
      {result.right.map((f, i) => { const p = position(f.point, true); return <rect key={i} x={p[0] - 3} y={p[1] - 3} width="6" height="6" fill={f.identity < 0 ? 'var(--orange)' : 'var(--teal)'}/>; })}
    </svg></div><Legend items={[["Correct correspondence", 'var(--teal)'], ['Outlier / wrong match', 'var(--orange)']]}/>
    <div className="feature-captions"><span>Frame A · reference features</span><span>Frame B · noisy observations</span></div></section>
    <aside className="panel controls"><h2>Association controls</h2><p>Descriptors drive matching. Hidden identities are used only to score the display.</p>
      <Range label="Observation noise" value={noise} min={0} max={.9} step={.025} onChange={setNoise}/>
      <Range label="Distance threshold" value={threshold} min={.05} max={2} step={.05} onChange={setThreshold}/>
      <Toggle label="Mutual nearest neighbors" checked={mutual} onChange={setMutual}/>
      <button className="button secondary" onClick={() => { setNoise(.2); setThreshold(.65); setMutual(true); }}><Icon name="reset" size={16}/> Reset matching</button>
      <div className="small-stats"><Stat label="Correct matches" value={correct}/><Stat label="Wrong matches" value={result.matches.length - correct}/></div></aside></div>
    <Lesson title="A match is a hypothesis." formula={String.raw`d(a,b)=\sqrt{\sum_i(a_i-b_i)^2}`} label="Euclidean descriptor distance" link="association">
      <p>Loose thresholds accept more candidates, including outliers. Tight thresholds can reject useful observations. Mutual matching helps, but geometry is still needed to verify a real scene correspondence.</p></Lesson></>;
}

function Graph({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(.045), [loop, setLoop] = useState(true);
  const graph = useMemo(() => poseGraph(seed, noise), [seed, noise]);
  const [solution, setSolution] = useState<ReturnType<typeof optimizeGraph> | null>(null);
  const edges = graph.edges.filter(e => !e.loop || loop);
  const display = solution?.poses || graph.initial;
  return <><div className="experiment-layout"><section className="panel visual-panel"><div className="panel-heading"><span>SE(2) pose graph</span><span className="subtle">18 nodes · pose 0 anchored</span></div>
    <Plot label="Drifted pose graph, loop constraint and optimized trajectory" bounds={[-3, -1, 4, 6]}>
      <PathLine points={graph.initial} color="var(--slate)" dashed/>
      {edges.map((e, i) => <line key={i} x1={display[e.i][0]} y1={display[e.i][1]} x2={display[e.j][0]} y2={display[e.j][1]} stroke={e.loop ? 'var(--orange)' : 'var(--teal)'} strokeWidth={e.loop ? .055 : .035} strokeDasharray={e.loop ? '.12 .08' : undefined}/>)}
      {display.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r={i === 0 ? .095 : .065} fill={i === 0 ? 'var(--orange)' : 'var(--teal)'}/>)}
    </Plot><Legend items={[["Initial odometry", 'var(--slate)'], ['Optimized graph', 'var(--teal)'], ['Loop edge / anchor', 'var(--orange)']]}/></section>
    <aside className="panel controls"><h2>Graph constraints</h2><p>Optimize relative measurements with Gauss–Newton updates and a line search.</p>
      <Range label="Measurement noise" value={noise} min={0} max={.12} step={.005} onChange={v => { setNoise(v); setSolution(null); }}/>
      <Toggle label="Include loop closure" checked={loop} onChange={v => { setLoop(v); setSolution(null); }}/>
      <button className="button primary" onClick={() => setSolution(optimizeGraph(graph.initial, edges))}><Icon name="algorithms" size={17}/> Optimize graph</button>
      <button className="button secondary" onClick={() => setSolution(null)}><Icon name="reset" size={16}/> Reset graph</button>
      <Stat label="Weighted objective" value={solution ? solution.costs.at(-1)!.toFixed(4) : graphCost(graph.initial, edges).toFixed(4)}
        detail={solution ? `Initial ${solution.costs[0].toFixed(4)} · ${solution.costs.length - 1} accepted iterations` : 'The solver uses edges, not a truth trajectory.'}/></aside></div>
    <Lesson title="One revisit connects the whole path." formula={String.raw`\min_{T}\sum_{(i,j)}e_{ij}^{T}\Omega_{ij}e_{ij}`} label="Weighted pose graph objective" link="graphs">
      <p>A loop edge links poses that local odometry treats as distant in time. Optimization distributes its correction across the graph while preserving the first pose as a gauge anchor.</p><p>Adding noisy constraints can also harm a graph. The displayed objective measures consistency with these observations, not accuracy against a hidden reference.</p></Lesson></>;
}

function Multi({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(.05), [shared, setShared] = useState(5), [connected, setConnected] = useState(true);
  const maps = useMemo(() => multiRobot(seed, noise), [seed, noise]);
  const [aligned, setAligned] = useState(false), player = usePlayback(120);
  const alignment = aligned && connected && shared >= 2 ? alignPoints(maps.b.slice(0, shared), maps.a.slice(0, shared)) : null;
  const b = maps.b.map(p => alignment ? alignment.transform(p) : p);
  const phase = player.frame / 120 * Math.PI * 2;
  const localB: Point = [Math.cos(phase + 1), Math.sin(phase + 1)];
  const robotB = alignment ? alignment.transform(localB) : localB;
  return <><div className="experiment-layout"><section className="panel visual-panel"><div className="panel-heading"><span>Two local map frames</span><span className="subtle">Known shared landmark identities</span></div>
    <Plot label="Two independently moving robots and local maps aligned from shared landmarks" bounds={[-5, -4, 4, 4]}>
      {maps.a.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r=".085" fill="var(--teal)"/>)}
      {b.map((p, i) => <rect key={i} x={p[0] - .07} y={p[1] - .07} width=".14" height=".14" fill="var(--orange)"/>)}
      {connected && b.slice(0, shared).map((p, i) => <line key={i} x1={maps.a[i][0]} y1={maps.a[i][1]} x2={p[0]} y2={p[1]} stroke="var(--slate)" strokeWidth=".018" strokeDasharray=".08 .08"/>)}
      <Robot pose={[Math.cos(phase), Math.sin(phase), phase + Math.PI / 2]}/>
      <Robot pose={[robotB[0], robotB[1], phase + 1 + Math.PI / 2 + (alignment?.angle || 0)]} color="var(--orange)"/>
    </Plot><Legend items={[["Robot A / map A", 'var(--teal)'], ['Robot B / map B', 'var(--orange)'], ['Shared correspondence', 'var(--slate)']]}/><Playback player={player} total={120}/></section>
    <aside className="panel controls"><h2>Share & align</h2><p>Recover a rigid transform from shared observations. No common map origin is supplied to the fit.</p>
      <Range label="Shared landmarks" value={shared} min={0} max={10} step={1} onChange={v => { setShared(v); setAligned(false); }}/>
      <Range label="Observation noise" value={noise} min={0} max={.3} step={.01} unit="m" onChange={v => { setNoise(v); setAligned(false); }}/>
      <Toggle label="Communication enabled" checked={connected} onChange={v => { setConnected(v); setAligned(false); }}/>
      <button className="button primary" disabled={!connected || shared < 2} onClick={() => setAligned(true)}><Icon name="algorithms" size={17}/> Align shared landmarks</button>
      <button className="button secondary" onClick={() => { setAligned(false); player.reset(); }}>Reset alignment</button>
      <p className="help">{!connected ? 'Enable communication to share observations.' : shared < 2 ? 'Choose at least two distinct shared landmarks.' : alignment ? `Recovered rotation ${(alignment.angle * 180 / Math.PI).toFixed(1)}°; translation ${alignment.translation.map(v => v.toFixed(2)).join(', ')} m.` : 'Fit uses the chosen shared correspondences.'}</p></aside></div>
    <Lesson title="Shared observations connect local frames." formula={String.raw`\min_{R\in SO(2),t}\sum_i\|Rp_i+t-q_i\|^2`} label="Rigid map alignment objective" link="multi-robot">
      <p>Each robot begins in a local frame. A rigid least-squares fit estimates the rotation and translation that reconcile shared landmarks. Communication controls the available correspondences.</p><p>This is an introductory alignment model. The research collection explores full distributed estimation and communication protocols.</p></Lesson></>;
}

export default function Playground() {
  const requested = new URLSearchParams(location.search).get('module');
  const [active, setActive] = useState(modules.some(m => m[0] === requested) ? requested! : 'odometry'), [seed, setSeed] = useState(42);
  return <><PageHeader eyebrow="THE INTERACTIVE PLAYGROUND" title="Learn by changing the experiment." description="A few controls. A visible consequence. Build intuition for the ideas that make SLAM work."
    action={<span className="badge">Educational models · browser-local</span>}/>
    <nav className="module-tabs" aria-label="Playground modules">{modules.map(([id, n, title, subtitle]) => <button key={id} className={active === id ? 'active' : ''} aria-pressed={active === id} onClick={() => setActive(id)}><span>{n}</span><strong>{title}</strong><small>{subtitle}</small></button>)}</nav>
    <div className="experiment-toolbar"><div><span className="eyebrow">EXPERIMENT {modules.find(m => m[0] === active)![1]}</span><h2>{modules.find(m => m[0] === active)![2]}</h2></div>
      <label className="seed-field">Random seed<input type="number" min="0" max="2147483647" value={seed} onChange={e => setSeed(Math.max(0, Math.min(2147483647, Math.trunc(Number(e.target.value) || 0))))}/></label></div>
    <div key={active + seed}>{active === 'odometry' ? <Odometry seed={seed}/> : active === 'occupancy' ? <Occupancy seed={seed}/> : active === 'features' ? <Features seed={seed}/> : active === 'graph' ? <Graph seed={seed}/> : <Multi seed={seed}/>}</div></>;
}
