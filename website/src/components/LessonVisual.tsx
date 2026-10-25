import { useId, useState, type ReactNode } from 'react';
import { Icon, Link } from './ui';

type Concept = { title: string; target: string; steps: [string, string][] };
export const lessonConcepts: Record<string, Concept> = {
  fundamentals: {
    title: 'A robot needs a position and a map.',
    target: 'playground/',
    steps: [
      [
        'Start with a question',
        'The robot starts with incomplete knowledge: where am I, and what is around me?',
      ],
      [
        'Observe the surroundings',
        'Measurements connect the robot to visible landmarks. A landmark is a recognisable point in the environment.',
      ],
      [
        'Estimate both together',
        'SLAM uses movement and observations to update the robot’s estimated position and its map together.',
      ],
    ],
  },
  frames: {
    title: 'The same point can have different coordinates.',
    target: 'playground/?module=odometry',
    steps: [
      [
        'Room coordinates',
        'A world frame gives the room a fixed origin and directions called X and Y.',
      ],
      [
        'Robot coordinates',
        'The robot has its own origin and facing direction. Its axes move and turn with it.',
      ],
      [
        'Connect the frames',
        'A rotation and a shift relate a point measured from the robot to that same point in the room.',
      ],
    ],
  },
  sensors: {
    title: 'An estimate comes with uncertainty.',
    target: 'playground/?module=odometry',
    steps: [
      [
        'Take a measurement',
        'A measurement gives a clue about position. It usually does not identify one perfectly certain location.',
      ],
      [
        'Move without a correction',
        'Uncertain movement can widen the region of plausible positions. A small heading error also affects later movement.',
      ],
      [
        'Use another observation',
        'An informative observation can narrow the possibilities. The ellipse here illustrates uncertainty; it is not a measured confidence region.',
      ],
    ],
  },
  'first-experiment': {
    title: 'Follow a measurement through the experiment.',
    target: 'simulations/',
    steps: [
      [
        'Record sensors',
        'Webots supplies wheel measurements and relative marker observations. A separate recorder saves reference data for evaluation.',
      ],
      [
        'Estimate pose and map',
        'The EKF predicts movement, then uses observations to update the joint robot-and-landmark estimate.',
      ],
      [
        'Inspect the evidence',
        'Saved trajectories and maps go to evaluation and Studio. The browser prepares commands; Webots runs locally.',
      ],
    ],
  },
  association: {
    title: 'Similar-looking details can create wrong pairs.',
    target: 'playground/?module=features',
    steps: [
      [
        'Find distinctive details',
        'Corners and patterns can become features. The same physical detail may appear in two different observations.',
      ],
      [
        'Propose a pair',
        'Comparing numerical descriptions suggests which details might correspond. Similar appearance alone is not proof.',
      ],
      [
        'Check the hypothesis',
        'A proposed pair can be wrong when another detail looks similar. Real systems also use geometric checks.',
      ],
    ],
  },
  ekf: {
    title: 'Predict, observe, then update.',
    target: 'simulations/',
    steps: [
      ['Predict', 'Movement measurements predict a new robot pose and propagate uncertainty.'],
      ['Observe', 'A relative landmark measurement adds information about the robot and the map.'],
      [
        'Update',
        'The EKF uses the disagreement between prediction and observation to adjust the joint estimate. This diagram illustrates the sequence, not a numerical EKF result.',
      ],
    ],
  },
  mapping: {
    title: 'Unknown space is different from free space.',
    target: 'playground/?module=occupancy',
    steps: [
      [
        'Begin with unknown cells',
        'A grid divides space into squares. Unobserved squares do not yet provide evidence of a clear route.',
      ],
      [
        'Add an observation',
        'A range observation supplies evidence of free space before a hit and occupied space at the hit.',
      ],
      [
        'Accumulate evidence',
        'More observations reveal more of the room. Map coverage and map accuracy are separate questions.',
      ],
    ],
  },
  visual: {
    title: 'Two views constrain where a point can be.',
    target: 'playground/?module=features',
    steps: [
      [
        'Look from one camera',
        'A point in one image identifies a viewing direction. Its depth along that direction is still ambiguous.',
      ],
      [
        'Match a second view',
        'The same point seen from another known camera position adds a second viewing direction.',
      ],
      [
        'Use calibrated geometry',
        'Matching the same detail and knowing the camera geometry lets stereo infer depth. Incorrect matches or calibration can give incorrect depth.',
      ],
    ],
  },
  graphs: {
    title: 'A revisit connects distant parts of a path.',
    target: 'playground/?module=graph',
    steps: [
      [
        'Remember a chain of poses',
        'Each dot is a saved position and heading. Edges represent relative measurements between poses.',
      ],
      [
        'Recognise a familiar place',
        'A verified revisit adds a loop constraint between poses recorded at different times.',
      ],
      [
        'Distribute the correction',
        'Optimization adjusts the poses to fit the constraints while fixing a reference pose. This sketch shows the idea; the Playground runs the solver.',
      ],
    ],
  },
  'multi-robot': {
    title: 'Shared landmarks can connect two local maps.',
    target: 'playground/?module=multi',
    steps: [
      [
        'Start in separate frames',
        'Each robot can map the same room from its own origin and orientation. Their coordinates need not agree.',
      ],
      [
        'Identify shared points',
        'Correspondences say which observations refer to the same landmarks. Finding reliable pairs is part of the real problem.',
      ],
      [
        'Rotate and shift a map',
        'Rigid alignment brings shared observations into common coordinates. Aligning maps is one part of a collaborative SLAM system.',
      ],
    ],
  },
  metrics: {
    title: 'Compare estimates with an independent reference.',
    target: 'benchmarks/',
    steps: [
      [
        'Associate timestamps',
        'A meaningful comparison first pairs estimates and reference poses under a declared timing and frame policy.',
      ],
      [
        'Inspect position gaps',
        'ATE summarises absolute position differences. RMSE gives larger gaps more influence by squaring them before averaging.',
      ],
      [
        'Inspect changes in motion',
        'RPE compares relative motion over intervals. A small error on one metric does not establish complete coverage or reliable mapping.',
      ],
    ],
  },
  experiments: {
    title: 'A fair comparison starts with controlled inputs.',
    target: 'studio/',
    steps: [
      [
        'Save the conditions',
        'Record sensor inputs, configuration, versions and the seed that controls generated randomness.',
      ],
      [
        'Repeat the same conditions',
        'Deterministic teaching models repeat the same example with the same seed and settings. Real executions also require a stated repeatability protocol.',
      ],
      [
        'Change one factor',
        'Changing one declared setting makes the comparison easier to interpret. Preserve the evidence and record the limitation of the result.',
      ],
    ],
  },
};

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
  if (id === 'fundamentals')
    drawing = (
      <>
        <rect
          x="225"
          y="30"
          width="155"
          height="155"
          rx="6"
          fill="var(--soft)"
          stroke="var(--line)"
        />
        {robot(85, 130)}
        <text x="48" y="177">
          Robot pose
        </text>
        {[
          [260, 60],
          [340, 145],
          [275, 155],
        ].map(([x, y], index) => (
          <g key={index}>
            {step > 0 && line(`M100 125L${x} ${y}`, 'var(--orange)', true)}
            <Dot x={x} y={y} color={step > 1 ? 'var(--teal)' : 'var(--slate)'} />
          </g>
        ))}
        <text x="250" y="207">
          {step === 0 ? 'Surroundings' : 'Landmark map'}
        </text>
        {step === 0 && (
          <text x="292" y="112" className="diagram-big">
            ?
          </text>
        )}
      </>
    );
  else if (id === 'frames')
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
              Previous pose
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
            ? 'A range of possible poses'
            : step === 1
              ? 'Prediction uncertainty'
              : 'Information narrows the possibilities'}
        </text>
      </>
    );
  else if (id === 'first-experiment')
    drawing = (
      <>
        {['Sensors', 'Estimator', 'Map + replay'].map((name, index) => (
          <g key={name}>
            <rect
              x={20 + index * 135}
              y="75"
              width="112"
              height="66"
              rx="9"
              fill={step === index ? 'var(--soft)' : 'var(--surface)'}
              stroke={step === index ? 'var(--teal)' : 'var(--line)'}
              strokeWidth="2"
            />
            <text x={30 + index * 135} y="113">
              {name}
            </text>
            {index < 2 && line(`M${133 + index * 135} 108h20`, 'var(--teal)', false, true)}
          </g>
        ))}
        <text x="27" y="183">
          Measured input → estimate → inspectable evidence
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
        <Dot x={225} y={40} label="Same landmark" />
        {line('M95 170L225 40', 'var(--teal)')}
        {step === 0 && line('M225 40L255 10', 'var(--teal)', true)}
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
          </>
        )}
      </>
    );
  else if (id === 'graphs') {
    const points =
      step === 2
        ? [
            [65, 130],
            [95, 65],
            [200, 38],
            [315, 76],
            [345, 150],
            [230, 180],
            [90, 165],
          ]
        : [
            [65, 130],
            [110, 65],
            [210, 50],
            [330, 90],
            [365, 163],
            [275, 183],
            [180, 178],
          ];
    drawing = (
      <>
        {line('M' + points.map((point) => point.join(' ')).join('L'))}
        {points.map(([x, y], index) => (
          <Dot key={index} x={x} y={y} color={index === 0 ? 'var(--orange)' : 'var(--teal)'} />
        ))}
        {step > 0 && line(`M${points.at(-1)!.join(' ')}L65 130`, 'var(--orange)', true)}
        <text x="91" y="214">
          {step === 0
            ? 'A chain of relative measurements'
            : step === 1
              ? 'A revisit adds a loop constraint'
              : 'An anchored, adjusted path'}
        </text>
      </>
    );
  } else if (id === 'multi-robot')
    drawing = (
      <>
        {[
          [90, 60],
          [150, 130],
          [75, 170],
        ].map(([x, y], index) => {
          const bx = step === 2 ? x : 270 + (x - 100) * Math.cos(0.5) - (y - 110) * Math.sin(0.5),
            by = step === 2 ? y : 110 + (x - 100) * Math.sin(0.5) + (y - 110) * Math.cos(0.5);
          return (
            <g key={index}>
              {step === 1 && line(`M${x} ${y}L${bx} ${by}`, 'var(--slate)', true)}
              <Dot x={x} y={y} />
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
        <text x="38" y="210">
          {step === 2 ? 'Shared points in common coordinates' : 'Map A'}
        </text>
        {step < 2 && (
          <text x="288" y="210">
            Map B
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

export function LessonVisual({ id }: { id: string }) {
  const [step, setStep] = useState(0);
  const concept = lessonConcepts[id];
  if (!concept) return null;
  return (
    <section className="lesson-visual" aria-label="Visual concept walkthrough">
      <div className="lesson-visual-heading">
        <p className="eyebrow">SEE THE IDEA</p>
        <h2>{concept.title}</h2>
      </div>
      <div className="lesson-visual-body">
        <ConceptDiagram id={id} step={step} />
        <div>
          <div className="visual-step-buttons" role="group" aria-label="Visual walkthrough steps">
            {concept.steps.map(([name], index) => (
              <button key={name} aria-pressed={step === index} onClick={() => setStep(index)}>
                {index + 1} · {name}
              </button>
            ))}
          </div>
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
            <span>Step {step + 1} of 3</span>
            <button
              className="icon-button"
              aria-label="Next visual step"
              disabled={step === 2}
              onClick={() => setStep(step + 1)}
            >
              <Icon name="arrow" size={16} />
            </button>
          </div>
        </div>
      </div>
      <div className="lesson-visual-footer">
        <span>Conceptual schematic · not an experiment measurement.</span>
        <Link to={concept.target} className="text-link">
          Explore the related activity <Icon name="arrow" size={14} />
        </Link>
      </div>
    </section>
  );
}
