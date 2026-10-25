import { useEffect, useId, useMemo, useState } from 'react';
import { descriptorDistance, featureScene, features, type Point } from '../lab/models';
import { Icon, Legend, Range, Stat, Toggle } from './ui';
import { useExperimentComparison } from './ExperimentComparison';

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
  const resultNote = `${result.matches.length} pairs accepted: ${correct} correct and ${result.matches.length - correct} wrong. These checks compare descriptions; they do not prove identity.`;
  const comparison = useExperimentComparison({
    settings: `Seed ${seed}; noise ${noise}; threshold ${threshold}; two-way ${mutual ? 'on' : 'off'}`,
    result: resultNote,
    graphic: (
      <svg
        className="comparison-features"
        viewBox="0 0 420 180"
        role="img"
        aria-label="Accepted feature pairs in the saved settings"
      >
        <rect x="10" y="10" width="165" height="160" fill="var(--soft)" />
        <rect x="245" y="10" width="165" height="160" fill="var(--soft)" />
        {result.matches.map((match) => (
          <line
            key={match.left}
            x1={15 + result.left[match.left].point[0] * 150}
            y1={15 + result.left[match.left].point[1] * 150}
            x2={250 + result.right[match.right].point[0] * 150}
            y2={15 + result.right[match.right].point[1] * 150}
            stroke={match.correct ? 'var(--teal)' : 'var(--orange)'}
            strokeWidth="2"
            strokeDasharray={match.correct ? undefined : '4 3'}
          />
        ))}
      </svg>
    ),
  });
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
      ? 'Rejected: distance exceeds the threshold.'
      : candidate.reason === 'mutual'
        ? 'Rejected: the two details do not choose each other.'
        : 'Accepted: matching checks passed.';
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
              ? 'Corners make useful features. Choose one in view A.'
              : stage === 1
                ? `A${selected + 1} → B${candidate.right + 1} is the nearest descriptor. Similar does not always mean the same detail.`
                : candidate.accepted
                  ? candidate.correct
                    ? 'Accepted, and the same detail. This pair is correct.'
                    : 'Accepted, but a different detail. A close description can still be wrong.'
                  : 'Rejected. The dashed grey line shows a candidate that failed a check.'}
          </p>
          <Legend
            items={[
              ['Accepted, correct', 'var(--teal)'],
              ['Accepted, wrong', 'var(--orange)'],
              ['Rejected', 'var(--muted)'],
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
          <h2>Compare details</h2>
          <p>Start clear. Add confusing details. Watch the decision change.</p>
          <div className="matching-presets">
            <button className="button secondary" onClick={() => preset(false)}>
              Try a clean match
            </button>
            <button className="button secondary" onClick={() => preset(true)}>
              Try confusing details
            </button>
          </div>
          <button className="text-link" onClick={comparison.save}>
            Save current example for comparison
          </button>
          {comparison.saved && (
            <p className="help" aria-live="polite">
              Saved. Change the current settings, then{' '}
              <a href="#experiment-comparison">view the comparison</a>.
            </p>
          )}
          <Range
            label="Observation noise"
            value={noise}
            min={0}
            max={0.9}
            step={0.025}
            onChange={setNoise}
            help="How much the descriptions and detected positions vary."
          />
          <Range
            label="Distance threshold"
            value={threshold}
            min={0.05}
            max={2}
            step={0.05}
            onChange={setThreshold}
            help="How different two descriptions may be. Lower is stricter."
          />
          <Toggle label="Require a two-way match" checked={mutual} onChange={setMutual} />
          <p className="help">Both details must choose each other.</p>

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
      <p className="result-note" aria-live="polite">
        {resultNote}
      </p>
      {comparison.panel}
      <section className="match-inspector panel" aria-labelledby="pair-inspector-title">
        <div>
          <p className="eyebrow">FOLLOW ONE DECISION</p>
          <h2 id="pair-inspector-title">
            Why A{selected + 1} → B{candidate.right + 1}?
          </h2>
          <p className="help">
            A{selected + 1}: {featureScene[selected].name}
          </p>
          <p>
            <strong>B{candidate.right + 1} is the closest description.</strong> Difference{' '}
            {candidate.distance.toFixed(3)} · limit {threshold.toFixed(3)}.
          </p>
          <p
            className="match-decision"
            data-outcome={
              candidate.accepted ? (candidate.correct ? 'correct' : 'wrong') : 'rejected'
            }
            role="status"
          >
            {decision}
          </p>
          {stage === 2 && (
            <details className="teaching-check">
              <summary>Check the known identities</summary>
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
            </details>
          )}
          <p>
            {mutual
              ? candidate.reciprocal
                ? 'Two-way check: both choose each other.'
                : 'Two-way check: this candidate prefers another detail.'
              : 'Two-way checking is off.'}
          </p>
          <p className="help">
            Generated descriptors, illustrated room. Known identities score the result; the matcher
            never sees them.
          </p>
        </div>
        <div>
          <details className="candidate-comparison">
            <summary>Compare the three nearest candidates</summary>
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
          </details>
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
