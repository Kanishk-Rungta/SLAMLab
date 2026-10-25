import { useEffect, useId, useMemo, useState } from 'react';
import { descriptorDistance, featureScene, features, type Point } from '../lab/models';
import { Icon, Legend, Range, Stat, Toggle } from './ui';

function Room({
  x,
  y,
  shifted = false,
  clip,
}: {
  x: number;
  y: number;
  shifted?: boolean;
  clip: string;
}) {
  return (
    <g clipPath={`url(#${clip})`}>
      <rect x={x} y={y} width="320" height="220" rx="8" fill="var(--canvas)" stroke="var(--line)" />
      <g
        transform={`translate(${x + (shifted ? -14.4 : 0)} ${y + (shifted ? 3.3 : 0)}) scale(320 220)`}
        fill="var(--surface)"
        stroke="var(--slate)"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      >
        <path d="M0 .94H1M.02 .1H.98" fill="none" vectorEffect="non-scaling-stroke" />
        {[0.12, 0.66].map((left) => (
          <g key={left}>
            <rect
              x={left}
              y=".18"
              width=".22"
              height=".30"
              fill="var(--soft)"
              vectorEffect="non-scaling-stroke"
            />
            <path
              d={`M${left + 0.11} .18V.48M${left} .33H${left + 0.22}`}
              vectorEffect="non-scaling-stroke"
            />
          </g>
        ))}
        <rect
          x=".42"
          y=".50"
          width=".17"
          height=".44"
          fill="var(--soft)"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx=".56" cy=".73" r=".012" fill="var(--slate)" stroke="none" />
        <rect x=".12" y=".68" width=".19" height=".16" vectorEffect="non-scaling-stroke" />
        <path
          d="M.14 .72H.29M.14 .76H.25M.14 .80H.28M.72 .75H.89V.84H.72Z"
          vectorEffect="non-scaling-stroke"
        />
      </g>
    </g>
  );
}

export function FeatureExperiment({ seed }: { seed: number }) {
  const [noise, setNoise] = useState(0.2),
    [threshold, setThreshold] = useState(0.65),
    [mutual, setMutual] = useState(true);
  const [selected, setSelected] = useState(1),
    [stage, setStage] = useState(2),
    [all, setAll] = useState(false);
  const [stacked, setStacked] = useState(() => window.matchMedia('(max-width: 640px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 640px)');
    const update = () => setStacked(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  const result = useMemo(
    () => features(seed, noise, threshold, mutual),
    [seed, noise, threshold, mutual],
  );
  const candidate = result.candidates[selected],
    left = result.left[selected],
    right = result.right[candidate.right];
  const counterpart = result.right.findIndex((feature) => feature.identity === left.identity);
  const correct = result.matches.filter((match) => match.correct).length;
  const alternatives = result.right
    .map((feature, index) => ({ index, distance: descriptorDistance(left, feature) }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 3);
  const originA: Point = [20, 40],
    originB: Point = stacked ? [20, 335] : [420, 40];
  const position = (point: Point, second = false): Point => {
    const origin = second ? originB : originA;
    return [origin[0] + point[0] * 320, origin[1] + point[1] * 220];
  };
  const clip = useId().replaceAll(':', '');
  const color = !candidate.accepted
    ? 'var(--muted)'
    : candidate.correct
      ? 'var(--teal)'
      : 'var(--orange)';
  const decision =
    candidate.reason === 'threshold'
      ? 'Rejected: descriptor distance is above the threshold.'
      : candidate.reason === 'mutual'
        ? 'Rejected: the two features do not choose each other.'
        : 'Accepted: this pair passes the selected matching checks.';
  const line = (a: number, b: number) => {
    const p = position(result.left[a].point),
      q = position(result.right[b].point, true);
    return `M${p.join(' ')}L${q.join(' ')}`;
  };
  function preset(ambiguous: boolean) {
    setNoise(ambiguous ? 0.65 : 0);
    setThreshold(ambiguous ? 1.4 : 0.05);
    setMutual(!ambiguous);
    setStage(2);
  }
  return (
    <>
      <div className="experiment-layout feature-experiment">
        <section className="panel visual-panel">
          <div className="panel-heading">
            <span>Same room. Two observations.</span>
            <span className="subtle">Schematic scene · generated features</span>
          </div>
          <div className="matching-stages" role="group" aria-label="Feature matching explanation">
            {['1 · Spot details', '2 · Inspect a pair', '3 · Review matches'].map(
              (title, index) => (
                <button key={title} aria-pressed={stage === index} onClick={() => setStage(index)}>
                  {title}
                </button>
              ),
            )}
          </div>
          <svg
            className="matching-scene"
            viewBox={`0 0 ${stacked ? 360 : 760} ${stacked ? 575 : 280}`}
            role="group"
            aria-label="Two schematic room views with numbered features and computed candidate connections"
          >
            <title>
              Inspect a numbered corner in view A and its nearest descriptor candidate in view B
            </title>
            <defs>
              {[originA, originB].map(([x, y], index) => (
                <clipPath id={clip + index} key={index}>
                  <rect x={x} y={y} width="320" height="220" rx="8" />
                </clipPath>
              ))}
            </defs>
            {[originA, originB].map(([x, y], index) => (
              <g key={index}>
                <text x={x} y={y - 16} className="scene-label">
                  {index === 0 ? 'VIEW A · Earlier observation' : 'VIEW B · Later observation'}
                </text>
                <Room x={x} y={y} shifted={index === 1} clip={clip + index} />
              </g>
            ))}
            {result.right
              .filter((feature) => feature.identity < 0)
              .map((feature, index) => {
                const [x, y] = position(feature.point, true);
                return (
                  <path
                    key={index}
                    d={`M${x - 7} ${y + 7}v-14h14`}
                    stroke="var(--slate)"
                    strokeWidth="2"
                    fill="none"
                  />
                );
              })}
            {stage === 2 &&
              all &&
              result.matches.map((match) => (
                <path
                  key={match.left}
                  d={line(match.left, match.right)}
                  stroke={match.correct ? 'var(--teal)' : 'var(--orange)'}
                  strokeWidth="1.5"
                  strokeDasharray={match.correct ? undefined : '5 4'}
                  fill="none"
                  opacity=".25"
                />
              ))}
            {stage > 0 && (
              <>
                <path
                  d={line(selected, candidate.right)}
                  stroke="var(--surface)"
                  strokeWidth="7"
                  fill="none"
                />
                <path
                  d={line(selected, candidate.right)}
                  stroke={stage === 1 ? 'var(--purple)' : color}
                  strokeWidth="3"
                  strokeDasharray={
                    stage === 1 || !candidate.accepted || !candidate.correct ? '7 5' : undefined
                  }
                  fill="none"
                />
              </>
            )}
            {result.right.map((feature, index) => {
              const [x, y] = position(feature.point, true),
                highlighted = index === candidate.right && stage > 0;
              return (
                <g key={index}>
                  <rect
                    x={x - (highlighted ? 7 : 3)}
                    y={y - (highlighted ? 7 : 3)}
                    width={highlighted ? 14 : 6}
                    height={highlighted ? 14 : 6}
                    fill={highlighted ? (stage === 1 ? 'var(--purple)' : color) : 'var(--slate)'}
                    stroke="var(--surface)"
                    strokeWidth="1"
                  />
                  {highlighted && (
                    <text x={x + 10} y={y - 10} className="feature-number">
                      B{index + 1}
                    </text>
                  )}
                </g>
              );
            })}
            {result.left.map((feature, index) => {
              const [x, y] = position(feature.point),
                active = index === selected;
              return (
                <g
                  key={index}
                  role="button"
                  tabIndex={0}
                  aria-pressed={active}
                  aria-label={`Inspect A${index + 1}: ${featureScene[index].name}`}
                  onClick={() => setSelected(index)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      setSelected(index);
                    }
                  }}
                >
                  <circle cx={x} cy={y} r="18" fill="transparent" />
                  <circle
                    cx={x}
                    cy={y}
                    r={active ? 8 : 4}
                    fill={active ? 'var(--teal)' : 'var(--slate)'}
                    stroke="var(--surface)"
                    strokeWidth="1.5"
                  />
                  <text x={x + 8} y={y - 9} className="feature-number" aria-hidden="true">
                    A{index + 1}
                  </text>
                </g>
              );
            })}
          </svg>
          <p className="matching-caption" aria-live="polite">
            {stage === 0
              ? 'Corners and distinctive marks are possible features. Some details are missing or appear more than once in the second observation.'
              : stage === 1
                ? `Comparing A${selected + 1} with B${candidate.right + 1}: the nearest descriptor, not necessarily the same physical detail.`
                : `${decision} ${candidate.accepted ? (candidate.correct ? 'The model’s known identities confirm this is the same detail.' : 'The model’s known identities reveal a wrong match.') : 'A rejected candidate is drawn with a dashed grey line.'}`}
          </p>
          <Legend
            items={[
              ['Correct accepted pair', 'var(--teal)'],
              ['Wrong accepted pair', 'var(--orange)'],
              ['Rejected candidate', 'var(--muted)'],
            ]}
          />
          <div className="matching-display-controls">
            <label className="select-label">
              Inspect a feature
              <select
                value={selected}
                onChange={(event) => setSelected(Number(event.target.value))}
              >
                {featureScene.map((feature, index) => (
                  <option key={index} value={index}>
                    A{index + 1} · {feature.name}
                  </option>
                ))}
              </select>
            </label>
            <Toggle label="Show all accepted pairs" checked={all} onChange={setAll} />
          </div>
        </section>
        <aside className="panel controls">
          <h2>Association controls</h2>
          <p>
            The matcher compares descriptions. It does not know which room detail a point really
            represents.
          </p>
          <Range
            label="Observation noise"
            value={noise}
            min={0}
            max={0.9}
            step={0.025}
            onChange={setNoise}
            help="Disturbs the second view’s feature positions and descriptors. It is a model setting, not metres."
          />
          <Range
            label="Distance threshold"
            value={threshold}
            min={0.05}
            max={2}
            step={0.05}
            onChange={setThreshold}
            help="Largest allowed descriptor difference. Higher values admit less similar candidates."
          />
          <Toggle label="Mutual nearest neighbors" checked={mutual} onChange={setMutual} />
          <div className="matching-presets">
            <button className="button secondary" onClick={() => preset(false)}>
              Try a clean match
            </button>
            <button className="button secondary" onClick={() => preset(true)}>
              Try confusing details
            </button>
          </div>
          <button
            className="button secondary"
            onClick={() => {
              setNoise(0.2);
              setThreshold(0.65);
              setMutual(true);
              setSelected(1);
              setStage(2);
              setAll(false);
            }}
          >
            <Icon name="reset" size={16} /> Reset matching
          </button>
          <div className="small-stats">
            <Stat
              label="Correct matches"
              value={correct}
              detail="Accepted pairs with the same known identity."
            />
            <Stat
              label="Wrong matches"
              value={result.matches.length - correct}
              detail="Accepted pairs with different known identities."
            />
          </div>
        </aside>
      </div>
      <section className="match-inspector panel" aria-labelledby="pair-inspector-title">
        <div>
          <p className="eyebrow">FOLLOW ONE DECISION</p>
          <h2 id="pair-inspector-title">
            A{selected + 1}: {featureScene[selected].name}
          </h2>
          <p>
            <strong>Nearest candidate: B{candidate.right + 1}.</strong> Descriptor distance{' '}
            {candidate.distance.toFixed(3)}; threshold {threshold.toFixed(3)}.
          </p>
          <p className="match-decision" role="status">
            {decision}
          </p>
          {stage === 2 && (
            <p>
              <strong>Teaching check:</strong>{' '}
              {counterpart < 0
                ? 'This detail has no detected counterpart in view B.'
                : `This detail’s known counterpart is B${counterpart + 1}.`}{' '}
              {right.identity < 0
                ? `B${candidate.right + 1} is a generated look-alike.`
                : !candidate.correct
                  ? `B${candidate.right + 1} belongs to a different detail: ${featureScene[right.identity].name.toLowerCase()}.`
                  : 'The nearest candidate refers to that same detail.'}
            </p>
          )}
          <p>
            {mutual
              ? candidate.reciprocal
                ? 'Mutual check: both features choose each other.'
                : 'Mutual check: this candidate prefers another feature in view A.'
              : 'Mutual check is off. One-way nearest matches are allowed.'}
          </p>
          <p className="help">
            Ground-truth identities score the example after matching. They never choose or reject a
            pair. The room is an illustration; features and descriptors are generated, not extracted
            from a photograph.
          </p>
        </div>
        <div>
          <h3>The three closest descriptions</h3>
          <table className="candidate-table">
            <thead>
              <tr>
                <th scope="col">View B</th>
                <th scope="col">Distance</th>
                <th scope="col">Rank</th>
              </tr>
            </thead>
            <tbody>
              {alternatives.map((alternative, index) => (
                <tr key={alternative.index}>
                  <th scope="row">B{alternative.index + 1}</th>
                  <td>{alternative.distance.toFixed(3)}</td>
                  <td>{index === 0 ? 'Nearest' : index + 1}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="help">
            Distances are rounded for display. Acceptance checks use the full-precision values.
          </p>
          <details className="descriptor-details">
            <summary>See the six descriptor values</summary>
            <p>
              A{selected + 1}:{' '}
              <code>{left.descriptor.map((value) => value.toFixed(2)).join(' · ')}</code>
            </p>
            <p>
              B{candidate.right + 1}:{' '}
              <code>{right.descriptor.map((value) => value.toFixed(2)).join(' · ')}</code>
            </p>
            <p className="help">
              The distance is computed from the full-precision values. Values here are rounded for
              reading.
            </p>
          </details>
        </div>
      </section>
    </>
  );
}
