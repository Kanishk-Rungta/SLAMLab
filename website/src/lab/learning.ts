export type LearningStep = [label: string, explanation: string, notice: string];
export type LearningConcept = {
  question: string;
  title: string;
  context: string;
  target: string;
  takeaway: string;
  bridge: string;
  terms: [string, string][];
  steps: LearningStep[];
};
export const lessonOrder = [
  'fundamentals',
  'frames',
  'sensors',
  'first-experiment',
  'association',
  'ekf',
  'mapping',
  'visual',
  'graphs',
  'multi-robot',
  'metrics',
  'experiments',
];
export const lessonConcepts: Record<string, LearningConcept> = {
  fundamentals: {
    question: 'How can a robot explore an unfamiliar room?',
    title: 'Find your place. Build the map.',
    context:
      'SLAM means figuring out where you are while building a map. The robot uses each to improve the other.',
    target: 'playground/',
    takeaway: 'A robot builds its map and estimates its position together.',
    bridge: 'To describe a place, we first need directions everyone can agree on.',
    terms: [
      ['SLAM', 'Simultaneous localization and mapping: estimating position while building a map.'],
      ['Landmark', 'A recognisable detail, such as a corner, that the robot can observe again.'],
    ],
    steps: [
      [
        'Look',
        'The robot sees a corner. That observation starts its map.',
        'Orange links show what the robot observes.',
      ],
      [
        'Move',
        'It estimates a new position. Small movement errors can shift the map too.',
        'The estimate drifts away from the actual position.',
      ],
      [
        'Recognise',
        'Seeing the same corner again helps correct the position and the map.',
        'A familiar detail connects the new view to the old map.',
      ],
    ],
  },
  frames: {
    question: 'Whose left and right?',
    title: 'One corner. Two sets of directions.',
    context:
      'A robot measures from its own position. Its map describes the room. Coordinate frames connect those two viewpoints.',
    target: 'playground/?module=odometry',
    takeaway: 'Turn and shift a measurement to express it in another frame.',
    bridge: 'Even with the directions sorted out, measurements are never perfect.',
    terms: [
      ['Frame', 'An origin and a set of directions used to describe positions.'],
      ['Pose', 'A position and the direction the robot faces.'],
    ],
    steps: [
      [
        'The room',
        'The room has a fixed starting point and directions.',
        'Grey axes stay in place.',
      ],
      [
        'The robot',
        'The robot carries its own starting point and directions.',
        'The coloured axes turn with the robot.',
      ],
      [
        'The same corner',
        'Both frames describe the same corner from different viewpoints.',
        'Two arrows lead to one point.',
      ],
    ],
  },
  sensors: {
    question: 'Can a robot trust every measurement?',
    title: 'An estimate is a best guess.',
    context:
      'Sensors give clues, not perfect answers. A robot needs to keep track of how uncertain its position might be.',
    target: 'playground/?module=odometry',
    takeaway: 'Uncertain movement spreads the possibilities; useful observations can narrow them.',
    bridge: 'Let’s see how movement and observations fit into a complete experiment.',
    terms: [
      ['Noise', 'Random variation in a measurement.'],
      ['Uncertainty', 'How much room there is for an estimate to be wrong.'],
    ],
    steps: [
      [
        'A first guess',
        'Several nearby positions could explain the measurement.',
        'The shaded area represents possibilities.',
      ],
      ['Move', 'Imperfect movement estimates widen those possibilities.', 'The shaded area grows.'],
      [
        'Look again',
        'A useful observation rules out some possibilities.',
        'The smaller outline shows a more constrained guess.',
      ],
    ],
  },
  'first-experiment': {
    question: 'What actually happens during a SLAM run?',
    title: 'Measure → estimate → inspect.',
    context:
      'In Landmark Lab, a simulated robot uses wheel motion and visible markers to estimate its position and map.',
    target: 'simulations/',
    takeaway: 'A useful experiment saves both the estimate and the evidence needed to check it.',
    bridge: 'Before using a visual observation, the robot must work out which detail it is seeing.',
    terms: [
      ['Webots', 'The robot simulator that runs on your computer.'],
      ['Reference', 'Separately recorded known positions used to check the estimate.'],
    ],
    steps: [
      [
        'Measure',
        'Record wheel movement and observations of nearby markers.',
        'These are the estimator’s inputs.',
      ],
      [
        'Estimate',
        'Use those inputs to update position and landmark locations.',
        'The estimator builds its own answer.',
      ],
      [
        'Inspect',
        'Open the saved path and map, then compare with the reference.',
        'Studio replays the evidence; Webots runs locally.',
      ],
    ],
  },
  association: {
    question: 'Is that the same corner I saw before?',
    title: 'Looking similar is only a clue.',
    context:
      'Robots compare distinctive image details to recognise places. Two similar windows can still belong to different parts of a room.',
    target: 'playground/?module=features',
    takeaway: 'A match is a hypothesis. Similar appearance does not prove a shared identity.',
    bridge: 'Once we have an observation we can use, how should it change the position estimate?',
    terms: [
      ['Feature', 'A distinctive image detail, such as a corner.'],
      ['Descriptor', 'Numbers describing what a feature looks like.'],
    ],
    steps: [
      [
        'Spot a detail',
        'Choose a recognisable corner in the first view.',
        'The marked corner is our feature.',
      ],
      [
        'Find a candidate',
        'Look for a similar description in the second view.',
        'A line shows a proposed pair.',
      ],
      [
        'Check the idea',
        'A repeated pattern can fool the matcher.',
        'The orange line joins different physical details.',
      ],
    ],
  },
  ekf: {
    question: 'What if movement and a camera disagree?',
    title: 'Predict. Observe. Adjust.',
    context:
      'An Extended Kalman Filter, or EKF, combines uncertain movement and landmark observations into a joint position-and-map estimate.',
    target: 'simulations/',
    takeaway: 'Combine observations with the prediction instead of treating either as perfect.',
    bridge: 'With a position estimate in place, we can record which parts of the room look open.',
    terms: [
      ['Prediction', 'Where movement measurements suggest the robot went.'],
      ['Update', 'Adjusting the estimate using new observation evidence.'],
    ],
    steps: [
      [
        'Predict',
        'Movement suggests where the robot should be now.',
        'The arrow starts from the previous pose.',
      ],
      [
        'Observe',
        'A landmark supplies another clue about the position.',
        'Orange shows the new observation.',
      ],
      [
        'Adjust',
        'Use both clues to revise the position and map.',
        'The revised estimate has fewer plausible positions.',
      ],
    ],
  },
  mapping: {
    question: 'Does an empty-looking square mean safe space?',
    title: 'Unseen is not the same as clear.',
    context:
      'An occupancy map divides the room into squares. Each holds evidence of an obstacle, open space, or no observation yet.',
    target: 'playground/?module=occupancy',
    takeaway: 'Unknown space needs observation before it can be treated as free.',
    bridge: 'Cameras can also help estimate the distance to the things we map.',
    terms: [
      ['Cell', 'One square in the map.'],
      ['Resolution', 'The real-world side length of a square. Smaller cells show finer detail.'],
    ],
    steps: [
      ['Unseen', 'Start with squares the robot knows nothing about.', 'Grey means unknown.'],
      [
        'One observation',
        'The beam passes through clear space before reaching a wall.',
        'Green is clear; the dark square is the hit.',
      ],
      [
        'More observations',
        'Build up evidence across more of the room.',
        'Space behind the walls is still unknown.',
      ],
    ],
  },
  visual: {
    question: 'How can two cameras tell how far away something is?',
    title: 'Two views add depth.',
    context:
      'A camera sees a direction to a detail. A second view of the same detail helps locate it in space.',
    target: 'playground/?module=features',
    takeaway: 'Depth needs matching details and known camera geometry.',
    bridge:
      'Even good measurements drift. Revisiting a familiar place can help correct the whole path.',
    terms: [
      ['Depth', 'How far a point lies from a camera.'],
      ['Stereo', 'Using two cameras with a known relationship.'],
    ],
    steps: [
      [
        'One view',
        'The detail could lie at different depths along this direction.',
        'One viewing ray leaves depth ambiguous.',
      ],
      [
        'A second view',
        'A matching detail supplies another viewing direction.',
        'The two rays meet at a shared point.',
      ],
      [
        'Known spacing',
        'Knowing the cameras’ spacing turns viewing directions into distance.',
        'The distance between cameras is known.',
      ],
    ],
  },
  graphs: {
    question: 'How does returning to a familiar place fix a map?',
    title: 'A revisit connects the path.',
    context:
      'A robot remembers positions linked by movement measurements. Recognising an earlier place adds a connection across that history.',
    target: 'playground/?module=graph',
    takeaway: 'A verified revisit can spread a correction across earlier estimates.',
    bridge: 'Now imagine two robots recognising some of the same places.',
    terms: [
      ['Pose graph', 'Remembered positions and headings connected by measurements.'],
      ['Loop closure', 'A verified connection to a place visited earlier.'],
    ],
    steps: [
      [
        'Keep a history',
        'Each dot remembers a position and direction. Lines link movement measurements.',
        'Small errors accumulate along the chain.',
      ],
      [
        'Recognise a place',
        'A revisit adds a constraint between distant parts of the history.',
        'Orange connects the end back toward the start.',
      ],
      [
        'Adjust together',
        'Fit the poses to the measurements while keeping the start fixed.',
        'The dashed path shows the earlier estimate.',
      ],
    ],
  },
  'multi-robot': {
    question: 'Can two robots combine their maps?',
    title: 'Find shared points. Connect the maps.',
    context:
      'Two robots can map the same room from different starting points. Details they both recognise help connect their maps.',
    target: 'playground/?module=multi',
    takeaway: 'Rotate and shift local maps using reliable observations of the same places.',
    bridge: 'A combined map may look convincing. We still need to measure whether it is accurate.',
    terms: [
      ['Local map', 'A map described from one robot’s own frame.'],
      ['Alignment', 'Turning and shifting maps into common coordinates.'],
    ],
    steps: [
      [
        'Separate maps',
        'Each robot begins with its own origin and directions.',
        'Circles and squares belong to different robots.',
      ],
      [
        'Shared places',
        'Pair observations of the same landmarks.',
        'Dashed links identify shared points.',
      ],
      [
        'Align',
        'Turn and shift one map until those pairs agree.',
        'Each square now surrounds its matching circle.',
      ],
    ],
  },
  metrics: {
    question: 'A map looks good. Is it actually right?',
    title: 'Check the estimate against evidence.',
    context:
      'In a controlled test, separately recorded positions provide a reference. Match time and coordinates before comparing paths.',
    target: 'benchmarks/',
    takeaway: 'Check position error, movement error and coverage together.',
    bridge: 'For those comparisons to be fair, we must keep track of the conditions of each run.',
    terms: [
      ['ATE', 'Absolute trajectory error: differences in position along the path.'],
      ['RPE', 'Relative pose error: differences in motion over selected intervals.'],
    ],
    steps: [
      [
        'Pair the samples',
        'Compare estimated and reference positions at corresponding times.',
        'Grey is the reference; teal is the estimate.',
      ],
      [
        'Position error',
        'Measure the gaps between the paired positions.',
        'Orange gaps contribute to ATE.',
      ],
      [
        'Movement error',
        'Compare how each path moves over the same interval.',
        'The arrows illustrate the motion compared by RPE.',
      ],
    ],
  },
  experiments: {
    question: 'Was the improvement real, or did the test change?',
    title: 'Keep the comparison fair.',
    context:
      'A result depends on its inputs and settings. Saving them makes changes easier to interpret and experiments easier to reproduce.',
    target: 'studio/',
    takeaway: 'Save the conditions, change one factor, and keep the evidence.',
    bridge: 'You have the big picture. Try an experiment, then inspect its saved evidence.',
    terms: [
      ['Seed', 'A value that makes generated random examples repeatable.'],
      ['Configuration', 'The settings used for a run.'],
    ],
    steps: [
      [
        'Save the setup',
        'Record inputs, settings and software versions.',
        'Both runs start from declared conditions.',
      ],
      [
        'Repeat',
        'The same inputs and settings repeat this controlled teaching example.',
        'Both example paths agree.',
      ],
      [
        'Change one factor',
        'Record the change before interpreting the difference.',
        'Here the second seed changes.',
      ],
    ],
  },
};
