import { useId, useState, type ReactNode } from 'react';
import { Icon, Link, Legend } from './ui';
import { MissionDiagram } from './MissionDiagram';
import { optimizeGraph, poseGraph } from '../lab/models';

import { lessonConcepts } from '../lab/learning';
export { lessonConcepts } from '../lab/learning';

let graphDemo:
  { graph: ReturnType<typeof poseGraph>; solution: ReturnType<typeof optimizeGraph> } | undefined;
function getGraphDemo() {
  if (!graphDemo) {
    const graph = poseGraph(42);
    graphDemo = { graph, solution: optimizeGraph(graph.initial, graph.edges) };
  }
  return graphDemo;
}

function Dot({
  x,
  y,
  color = 'var(--teal)',
  label,
}: {
  x: number;
  y: number;
  color?: string;
  label?: string;
}) {
  return (
    <g>
      <circle cx={x} cy={y} r="7" fill={color} />
      {label && (
        <text x={x + 12} y={y + 5}>
          {label}
        </text>
      )}
    </g>
  );
}

export function ConceptDiagram({
  id,
  step = 2,
  compact = false,
}: {
  id: string;
  step?: number;
  compact?: boolean;
}) {
  const arrow = useId().replaceAll(':', '');
  const concept = lessonConcepts[id];
  if (!concept) return null;
  if (id === 'fundamentals')
    return (
      <MissionDiagram
        step={step}
        compact={compact}
        label={`${concept.title} ${concept.steps[step][1]}`}
      />
    );
  const line = (d: string, color = 'var(--teal)', dashed = false, directed = false) => (
    <path
      d={d}
      stroke={color}
      strokeWidth="3"
      fill="none"
      strokeDasharray={dashed ? '7 5' : undefined}
      markerEnd={directed ? `url(#${arrow})` : undefined}
    />
  );
  const robot = (x: number, y: number, heading = 0) => (
    <g transform={`rotate(${heading} ${x} ${y})`}>
      <circle cx={x} cy={y} r="18" fill="var(--soft)" stroke="var(--teal)" strokeWidth="2" />
      <path d={`M${x + 13} ${y}l-21 -10 5 10 -5 10Z`} fill="var(--teal)" />
    </g>
  );
  let drawing: ReactNode;
  if (id === 'frames')
    drawing = (
      <>
        {line('M55 180H360', 'var(--slate)', false, true)}
        {line('M55 180V25', 'var(--slate)', false, true)}
        <text x="365" y="185">
          X
        </text>
        <text x="38" y="28">
          Y
        </text>
        <text x="30" y="207">
          Room origin
        </text>
        {robot(205, 135, -30)}
        {step > 0 && (
          <g transform="translate(205 135) rotate(-30)">
            {line('M0 0H105', 'var(--teal)', false, true)}
            {line('M0 0V-80', 'var(--orange)', false, true)}
            <text x="105" y="20">
              x
            </text>
            <text x="8" y="-76">
              y
            </text>
          </g>
        )}
        {step > 1 && (
          <>
            <Dot x={330} y={48} label="Same point" />
            {line('M55 180L330 48', 'var(--slate)', true)}
            {line('M205 135L330 48', 'var(--orange)', true)}
          </>
        )}
      </>
    );
  else if (id === 'sensors' || id === 'ekf')
    drawing = (
      <>
        {id === 'ekf' && (
          <>
            {robot(65, 135)}
            {line('M90 135H175', 'var(--slate)', true, true)}
            <text x="43" y="186">
              Before moving
            </text>
          </>
        )}
        <ellipse
          cx="235"
          cy="115"
          rx={id === 'sensors' && step === 0 ? 42 : 100}
          ry={id === 'sensors' && step === 0 ? 30 : 61}
          fill="var(--soft)"
          stroke="var(--slate)"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
        {[
          [0, -18],
          [-24, 5],
          [22, 8],
          [7, 24],
          [-11, -3],
        ].map(([x, y], index) => (
          <circle
            key={index}
            cx={(step === 2 ? 213 : 235) + x * (step === 1 ? 2.6 : step === 2 ? 0.7 : 1)}
            cy={(step === 2 ? 107 : 115) + y * (step === 1 ? 1.6 : step === 2 ? 0.7 : 1)}
            r="3"
            fill={step === 2 ? 'var(--teal)' : 'var(--slate)'}
            opacity=".45"
          />
        ))}
        {robot(step === 2 ? 213 : 235, step === 2 ? 107 : 115)}
        {(id === 'ekf' ? step > 0 : step === 2) && (
          <>
            <Dot x={355} y={38} color="var(--orange)" />
            {line('M240 110L355 38', 'var(--orange)', true)}
            <text x="290" y="24">
              Observation
            </text>
          </>
        )}
        {step === 2 && (
          <ellipse
            cx="213"
            cy="107"
            rx="36"
            ry="24"
            fill="none"
            stroke="var(--teal)"
            strokeWidth="3"
          />
        )}
        <text x="154" y="202">
          {step === 0
            ? 'Several positions could fit'
            : step === 1
              ? 'Movement adds uncertainty'
              : 'Information narrows the possibilities'}
        </text>
      </>
    );
  else if (id === 'first-experiment')
    drawing = (
      <>
        {['Measure', 'Estimate', 'Inspect'].map((name, index) => (
          <g key={name}>
            <rect
              x={20 + index * 135}
              y="45"
              width="112"
              height="130"
              rx="9"
              fill={step === index ? 'var(--soft)' : 'var(--surface)'}
              stroke={step === index ? 'var(--teal)' : 'var(--line)'}
              strokeWidth="2"
            />
            <text x={30 + index * 135} y="162">
              {name}
            </text>
            {index < 2 && line(`M${133 + index * 135} 108h20`, 'var(--teal)', false, true)}
          </g>
        ))}
        <g opacity={step === 0 ? 1 : 0.45}>
          {robot(67, 112)}
          <path d="M46 96v28M88 96v28" stroke="var(--slate)" strokeWidth="5" />
          <path d="M82 99L107 67" stroke="var(--orange)" strokeWidth="2" strokeDasharray="4 3" />
          <Dot x={107} y={67} color="var(--orange)" />
        </g>
        <g opacity={step === 1 ? 1 : 0.45}>
          <path d="M173 127l16 -30 24 14 20 -37" fill="none" stroke="var(--teal)" strokeWidth="3" />
          <ellipse
            cx="213"
            cy="111"
            rx="21"
            ry="17"
            fill="var(--soft)"
            stroke="var(--teal)"
            strokeDasharray="3 3"
          />
          <circle cx="213" cy="111" r="5" fill="var(--teal)" />
        </g>
        <g opacity={step === 2 ? 1 : 0.45}>
          <rect
            x="300"
            y="65"
            width="80"
            height="62"
            rx="4"
            fill="var(--canvas)"
            stroke="var(--slate)"
          />
          <path d="M307 118l16 -25 18 7 28 -25" fill="none" stroke="var(--teal)" strokeWidth="3" />
          <path d="M327 134h27" stroke="var(--slate)" strokeWidth="3" />
        </g>
        <text x="40" y="208">
          Wheel + marker data → position + map → evidence
        </text>
      </>
    );
  else if (id === 'association')
    drawing = (
      <>
        {[25, 245].map((x) => (
          <g key={x}>
            <rect
              x={x}
              y="35"
              width="150"
              height="145"
              rx="8"
              fill="var(--soft)"
              stroke="var(--line)"
            />
            <path
              d={`M${x + 25} 65h45v50h-45ZM${x + 90} 65h40v50h-40Z`}
              fill="none"
              stroke="var(--slate)"
              strokeWidth="2"
            />
          </g>
        ))}
        <Dot x={50} y={65} />
        <Dot x={270} y={65} />
        <Dot x={335} y={65} color="var(--orange)" />
        {step > 0 &&
          line(
            `M50 65L${step === 1 ? 270 : 335} 65`,
            step === 1 ? 'var(--teal)' : 'var(--orange)',
            step === 2,
          )}
        <text x="57" y="206">
          Earlier view
        </text>
        <text x="269" y="206">
          Later view
        </text>
        {step === 2 && (
          <text x="114" y="156">
            Similar pattern ≠ same detail
          </text>
        )}
      </>
    );
  else if (id === 'mapping')
    drawing = (
      <>
        {Array.from({ length: 98 }, (_, index) => {
          const x = index % 14,
            y = Math.floor(index / 14),
            visible = step === 2 ? x <= 10 && y >= 2 : step === 1 && x === 3 && y >= 2 && y <= 5;
          return (
            <rect
              key={index}
              x={35 + x * 25}
              y={17 + y * 25}
              width="23"
              height="23"
              fill={
                !visible
                  ? 'var(--unknown)'
                  : y === 2 || x === 10
                    ? 'var(--occupied)'
                    : 'var(--free)'
              }
            />
          );
        })}
        {step === 1 && line('M123 147V78', 'var(--orange)', true)}
        {step > 0 && robot(125, 147)}
        {[
          { color: 'var(--unknown)', x: 25 },
          { color: 'var(--free)', x: 156 },
          { color: 'var(--occupied)', x: 272 },
        ].map(({ color, x }) => (
          <rect key={color} x={x} y="202" width="13" height="13" fill={color} />
        ))}
        <text x="45" y="213">
          Unknown
        </text>
        <text x="176" y="213">
          Free
        </text>
        <text x="292" y="213">
          Occupied
        </text>
      </>
    );
  else if (id === 'visual')
    drawing = (
      <>
        {line('M95 170L255 10', 'var(--teal)', step === 0)}
        {step === 0 ? (
          <>
            {[
              [140, 125],
              [185, 80],
              [230, 35],
            ].map(([x, y]) => (
              <circle
                key={x}
                cx={x}
                cy={y}
                r="7"
                fill="var(--canvas)"
                stroke="var(--teal)"
                strokeWidth="2"
              />
            ))}
            <text x="245" y="55">
              Near or far?
            </text>
          </>
        ) : (
          <Dot x={225} y={40} label="Shared detail" />
        )}
        <rect x="73" y="170" width="44" height="25" rx="5" fill="var(--teal)" />
        <text x="43" y="216">
          Camera A
        </text>
        {step > 0 && (
          <>
            {line('M315 170L225 40', 'var(--orange)')}
            <rect x="293" y="170" width="44" height="25" rx="5" fill="var(--orange)" />
            <text x="280" y="216">
              Camera B
            </text>
          </>
        )}
        {step === 2 && (
          <>
            {line('M120 183H290', 'var(--slate)', true)}
            <text x="155" y="177">
              Known spacing
            </text>
            {line('M225 55V163', 'var(--slate)', true, true)}
            <text x="238" y="121">
              Depth
            </text>
          </>
        )}
      </>
    );
  else if (id === 'graphs') {
    const { graph, solution } = getGraphDemo();
    const project = (p: number[]) => [210 + p[0] * 44, 185 - p[1] * 32];
    const initial = graph.initial.map(project),
      adjusted = solution.poses.map(project);
    const points = step === 2 ? adjusted : initial;
    drawing = (
      <>
        {step === 2 &&
          line('M' + initial.map((point) => point.join(' ')).join('L'), 'var(--slate)', true)}
        {line('M' + points.map((point) => point.join(' ')).join('L'))}
        {step === 2 &&
          initial.map(
            (point, index) =>
              index > 0 &&
              index % 3 === 0 && (
                <g key={index}>
                  {line(
                    'M' + point.join(' ') + 'L' + adjusted[index].join(' '),
                    'var(--slate)',
                    true,
                  )}
                </g>
              ),
          )}
        {points.map(([x, y], index) => (
          <Dot key={index} x={x} y={y} color={index === 0 ? 'var(--orange)' : 'var(--teal)'} />
        ))}
        {step > 0 &&
          line('M' + points.at(-1)!.join(' ') + 'L' + points[0].join(' '), 'var(--orange)', true)}
        <text x="222" y="208">
          Start fixed
        </text>
      </>
    );
  } else if (id === 'multi-robot')
    drawing = (
      <>
        {(step === 2 ? [100] : [25, 235]).map((x) => (
          <rect
            key={x}
            x={x}
            y="30"
            width={step === 2 ? 210 : 170}
            height="158"
            rx="12"
            fill="var(--soft)"
            stroke="var(--line)"
            strokeDasharray="4 4"
          />
        ))}
        {[
          [90, 60],
          [150, 130],
          [75, 170],
        ].map(([x, y], index) => {
          const ax = step === 2 ? x + 110 : x;
          const bx = step === 2 ? ax : 270 + (x - 100) * Math.cos(0.5) - (y - 110) * Math.sin(0.5),
            by = step === 2 ? y : 110 + (x - 100) * Math.sin(0.5) + (y - 110) * Math.cos(0.5);
          return (
            <g key={index}>
              {step === 1 && line(`M${x} ${y}L${bx} ${by}`, 'var(--slate)', true)}
              <Dot x={ax} y={y} />
              <rect
                x={bx - 9}
                y={by - 9}
                width="18"
                height="18"
                fill="none"
                stroke="var(--orange)"
                strokeWidth="3"
              />
            </g>
          );
        })}
        <text x={step === 2 ? 118 : 38} y="210">
          {step === 2 ? 'One shared set of directions' : 'Robot A’s local map'}
        </text>
        {step < 2 && (
          <text x="245" y="210">
            Robot B’s local map
          </text>
        )}
      </>
    );
  else if (id === 'metrics') {
    const reference = [
        [45, 145],
        [120, 95],
        [200, 80],
        [285, 50],
        [365, 85],
      ],
      estimate = [
        [45, 160],
        [120, 120],
        [200, 108],
        [285, 88],
        [365, 132],
      ];
    drawing = (
      <>
        {line('M' + reference.map((p) => p.join(' ')).join('L'), 'var(--slate)', true)}
        {line('M' + estimate.map((p) => p.join(' ')).join('L'))}
        {step === 1 &&
          reference.map(([x, y], index) => (
            <g key={index}>
              {line(`M${x} ${y}L${estimate[index].join(' ')}`, 'var(--orange)', true)}
            </g>
          ))}
        {step === 2 && (
          <>
            {line('M120 95L200 80', 'var(--orange)', false, true)}
            {line('M120 120L200 108', 'var(--purple)', false, true)}
            <text x="225" y="156">
              Same time interval
            </text>
          </>
        )}
        <text x="35" y="200">
          {step === 0
            ? 'Reference and estimated trajectories'
            : step === 1
              ? 'Position gaps → ATE'
              : 'Compare motion intervals → RPE'}
        </text>
      </>
    );
  } else
    drawing = (
      <>
        <rect
          x="130"
          y="15"
          width="160"
          height="45"
          rx="8"
          fill="var(--soft)"
          stroke="var(--line)"
        />
        <text x="151" y="43">
          Saved configuration
        </text>
        {line('M165 65L100 95', 'var(--slate)', false, true)}
        {line('M255 65L320 95', 'var(--slate)', false, true)}
        {[30, 245].map((x, index) => (
          <g key={x}>
            <rect
              x={x}
              y="100"
              width="145"
              height="90"
              rx="8"
              fill="var(--canvas)"
              stroke="var(--line)"
            />
            {step > 0 && line(`M${x + 15} 165l30 -20 30 10 40 ${step === 2 && index ? -40 : -15}`)}
            <text x={x + 20} y="215">
              Seed {step === 2 && index ? '7' : '42'}
            </text>
          </g>
        ))}
      </>
    );
  return (
    <svg
      className={'concept-diagram' + (compact ? ' compact' : '')}
      viewBox="0 0 420 230"
      role="img"
      aria-hidden={compact || undefined}
      aria-label={`${concept.title} ${concept.steps[step][1]}`}
    >
      <title>{concept.title}</title>
      <defs>
        <marker
          id={arrow}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0L10 5 0 10Z" fill="var(--teal)" />
        </marker>
      </defs>
      <rect width="420" height="230" rx="10" fill="var(--canvas)" />
      {drawing}
    </svg>
  );
}

const legendFor = (id: string): [string, string][] => {
  if (id === 'fundamentals')
    return [
      ['Actual in this sketch', 'var(--slate)'],
      ['Robot estimate', 'var(--teal)'],
      ['Observation', 'var(--orange)'],
    ];
  if (id === 'frames')
    return [
      ['Room directions', 'var(--slate)'],
      ['Robot forward', 'var(--teal)'],
      ['Robot left', 'var(--orange)'],
    ];
  if (id === 'mapping')
    return [
      ['Unknown', 'var(--unknown)'],
      ['Free', 'var(--free)'],
      ['Obstacle', 'var(--occupied)'],
    ];
  if (id === 'multi-robot')
    return [
      ['Robot A', 'var(--teal)'],
      ['Robot B', 'var(--orange)'],
    ];
  if (id === 'graphs')
    return [
      ['Earlier estimate', 'var(--slate)'],
      ['Adjusted path', 'var(--teal)'],
      ['Start / revisit', 'var(--orange)'],
    ];
  if (id === 'metrics')
    return [
      ['Reference', 'var(--slate)'],
      ['Estimate', 'var(--teal)'],
      ['Difference', 'var(--orange)'],
    ];
  if (id === 'sensors' || id === 'ekf')
    return [
      ['Earlier possibilities', 'var(--slate)'],
      ['Revised estimate', 'var(--teal)'],
      ['Observation', 'var(--orange)'],
    ];
  return [];
};

export function LessonVisual({
  id,
  currentStep,
  onStepChange,
}: {
  id: string;
  currentStep?: number;
  onStepChange?: (step: number) => void;
}) {
  const [localStep, setLocalStep] = useState(0);
  const step = currentStep ?? localStep;
  const setStep = onStepChange ?? setLocalStep;
  const concept = lessonConcepts[id];
  if (!concept) return null;
  return (
    <section className="lesson-visual lesson-player" aria-label="Visual concept walkthrough">
      <div className="lesson-visual-heading">
        <p className="eyebrow">THE IDEA, ONE STEP AT A TIME</p>
        <h2>{concept.title}</h2>
      </div>
      <div className="visual-step-buttons" role="group" aria-label="Visual walkthrough steps">
        {concept.steps.map(([name], index) => (
          <button key={name} aria-pressed={step === index} onClick={() => setStep(index)}>
            <span className="step-index">{index + 1}</span>
            <span>{name}</span>
          </button>
        ))}
      </div>
      <div className="lesson-visual-body">
        <figure className="learning-scene">
          <ConceptDiagram id={id} step={step} />
          <Legend items={legendFor(id)} />
          <figcaption className="visual-notice">
            <span>NOTICE</span>
            {concept.steps[step][2]}
          </figcaption>
        </figure>
        <div className="player-story">
          <span className="eyebrow">STEP {step + 1} / 3</span>
          <h3>{concept.steps[step][0]}</h3>
          <p className="visual-caption" aria-live="polite">
            {concept.steps[step][1]}
          </p>
          <div className="visual-navigation">
            <button
              className="icon-button"
              aria-label="Previous visual step"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              <Icon name="arrow" size={16} />
            </button>
            <span>{step === 2 ? 'The idea is connected.' : 'Keep following the same scene.'}</span>
            <button
              className="button small"
              aria-label="Next visual step"
              disabled={step === 2}
              onClick={() => setStep(step + 1)}
            >
              Next <Icon name="arrow" size={15} />
            </button>
          </div>
        </div>
      </div>
      <div className="lesson-visual-footer">
        <span>Teaching graphic · not a measured run.</span>
        <Link to={concept.target} className="text-link">
          Try this idea <Icon name="arrow" size={14} />
        </Link>
      </div>
    </section>
  );
}
