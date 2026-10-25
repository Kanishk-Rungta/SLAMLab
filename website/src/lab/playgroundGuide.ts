export type ModuleId = 'odometry' | 'occupancy' | 'features' | 'graph' | 'multi';

type Guide = {
  title: string;
  explanation: string;
  example: string;
  readout: string;
  steps: string[];
  terms: [string, string][];
  scope: string;
};

export const playgroundGuides: Record<ModuleId, Guide> = {
  odometry: {
    title: 'Why does a robot lose track of where it is?',
    explanation:
      'Odometry estimates movement by adding up small steps, such as wheel rotations. Drift is the growing disagreement between that estimate and the actual position when small measurement errors accumulate.',
    example:
      'Imagine walking across a room by counting steps with your eyes closed. If you misjudge a step or turn slightly, your idea of where you are can move away from your real position.',
    readout:
      'The dashed grey path is the reference motion: where this simulated robot actually goes. The teal path is its estimate. The robot symbol shows position and facing direction. Position error is the straight-line gap between the two positions at the selected moment; distance travelled is the length of the reference path so far.',
    steps: [
      'Set Translation noise and Rotation noise to zero, then press Play. The paths should agree.',
      'Increase Rotation noise and replay. Small mistakes in facing direction can affect every later step.',
      'Pause or drag the playback slider to compare the paths at a particular moment. One noisy run need not get worse at every step.',
    ],
    terms: [
      [
        'Translation',
        'Movement from one position to another. Translation noise adds random errors to each estimated forward step.',
      ],
      [
        'Rotation / heading',
        'Turning, and the direction the robot faces. Rotation noise adds random errors to estimated turns.',
      ],
      [
        'Trajectory',
        'The path traced by a robot over time. Visible-layer switches hide or show the reference and estimated paths.',
      ],
      [
        'Noise units',
        'm means metres, s means seconds, and rad means radians (about 57 degrees each). m/√s and rad/√s set how random step errors scale with elapsed time; they are not fixed position offsets.',
      ],
      [
        '2D unicycle',
        'A simple motion model that moves forward and turns on a flat plane. It does not model individual wheels or physical contact.',
      ],
    ],
    scope:
      'This model adds motion errors without correcting them from a camera or map. It illustrates why a SLAM system needs observations beyond wheel motion.',
  },
  occupancy: {
    title: 'How can a robot turn observations into a map?',
    explanation:
      'An occupancy map divides a room into small squares called cells. Each cell stores evidence about whether that part of the room contains an obstacle, appears open or has not been observed.',
    example:
      'Think of colouring graph paper while exploring a dark room: mark where you see a wall, mark the clear space before it, and leave places you have not seen undecided.',
    readout:
      'Use the legend to distinguish occupied, free and unknown cells. Orange beams show simulated distance measurements. Repeated observations strengthen the evidence. Observed cells counts cells whose stored evidence differs from the initial unknown value; it is not a map-accuracy score.',
    steps: [
      'Press Play or move the playback slider toward the end to watch observations build up.',
      'Reduce Sensor range to see how a shorter view changes which cells are observed.',
      'Compare small and large Cell resolution values, then increase Range noise to see how uncertain distances affect the map.',
    ],
    terms: [
      [
        'Occupied / free / unknown',
        'Evidence of an obstacle, evidence of open space, or no net evidence yet. Unknown space must not be assumed safe.',
      ],
      [
        'Sensor range and range noise',
        'Range is how far a simulated beam can reach. Range noise adds random error to the reported distance, in metres.',
      ],
      [
        'Cell resolution',
        'The side length of a grid square in metres. A smaller number gives finer cells and requires more cells to cover the same room.',
      ],
      [
        'Inverse sensor model / log odds',
        'Rules for turning a distance observation into evidence about cells. Log odds is the numerical form used to add that evidence over time.',
      ],
      [
        'Map JSON',
        'Downloads the current grid as a structured text file for inspection or local import in Studio. The layer switches only change what is drawn.',
      ],
    ],
    scope:
      'The robot position is supplied here so you can study mapping on its own. The beams are a teaching model, not a claim that the research robot uses LiDAR.',
  },
  features: {
    title: 'How does a robot recognise the same detail twice?',
    explanation:
      'A feature is a distinctive detail, such as a corner in a camera image. Feature matching tries to pair a detail in one view with the same detail in another. Those pairs help a robot reason about movement and familiar places.',
    example:
      'When comparing two photos of a room, you might recognise the same window corner in each. A robot compares numerical descriptions of details to make similar guesses.',
    readout:
      'The two boxes represent different views. Lines join proposed pairs: teal lines are correct matches and orange lines are mistakes. Unconnected points have no accepted match. Correct and wrong match counts are checked against identities known to this teaching model.',
    steps: [
      'Increase Observation noise to make the numerical descriptions less reliable.',
      'Raise Distance threshold to accept more possible pairs, then lower it to reject less similar pairs. Compare both match counts.',
      'Switch Mutual nearest neighbors off and on to see what changes when both features must choose each other.',
    ],
    terms: [
      [
        'Frame A / Frame B',
        'Two sets of observations, like two camera views. These points are generated examples rather than features extracted from photographs.',
      ],
      [
        'Descriptor',
        'A list of numbers describing a feature. Similar descriptors may belong to the same detail, but similar-looking details can cause mistakes.',
      ],
      [
        'Distance threshold',
        'The largest allowed difference between descriptors. This is a similarity score, not physical distance in metres.',
      ],
      [
        'Mutual nearest neighbors',
        'A pair is kept only if each feature selects the other as its closest descriptor match. This extra check cannot guarantee correctness.',
      ],
      [
        'Correspondence / outlier',
        'A correspondence is a proposed pairing. An outlier is a misleading observation or wrong pairing that does not fit the intended scene relationship.',
      ],
    ],
    scope:
      'This experiment compares generated descriptors. A real vision system also checks whether proposed matches make geometric sense.',
  },
  graph: {
    title: 'How can revisiting a place help correct a path?',
    explanation:
      'A pose means a position and a facing direction. A pose graph connects remembered poses with measurements of movement. A loop closure adds a connection when the robot recognises a previously visited place.',
    example:
      'Imagine drawing a walk around a building. Your sketch ends away from the doorway where you started. Recognising that doorway gives you another clue for adjusting the sketch.',
    readout:
      'Dots are remembered poses and lines are movement constraints. The dashed grey path is the initial estimate. After Optimize graph, the teal graph shows the adjusted poses. The orange loop edge connects the last and first poses; the orange anchor keeps the first pose fixed.',
    steps: [
      'Leave Include loop closure on and click Optimize graph. Compare the adjusted path with the dashed starting path.',
      'Switch the loop closure off and optimize again. With no revisit constraint, the original chain already fits its own relative measurements.',
      'Change Measurement noise to generate different uncertain constraints. Reset graph returns to the unoptimized estimate.',
    ],
    terms: [
      [
        'Node / edge / constraint',
        'A node is a saved pose. An edge connects two poses; its measurement constrains how those poses should relate.',
      ],
      [
        'SE(2) / anchor',
        'SE(2) describes position and rotation on a flat plane. Fixing one pose, the anchor, stops the entire graph from freely shifting or rotating.',
      ],
      [
        'Optimization',
        'Adjusting pose estimates to reduce disagreement with the selected measurements. Gauss–Newton makes repeated small adjustments; line search chooses a step that reduces the disagreement.',
      ],
      [
        'Weighted objective',
        'A combined score of disagreement with the measurements. Smaller means a closer fit to those constraints, not proof of a more accurate real-world map.',
      ],
      [
        'Iteration / measurement noise',
        'An iteration is one accepted adjustment. The noise slider changes random errors in movement measurements. This model also adds a fixed turning bias: the same small extra turn in each movement measurement.',
      ],
    ],
    scope:
      'The revisit connection is supplied by this model. A real SLAM system must first detect and verify that it has returned to the same place.',
  },
  multi: {
    title: 'How can two robots put their maps together?',
    explanation:
      'Each robot can describe the same room using its own starting point and direction. Map alignment finds how to rotate and shift one map so that observations of the same places line up.',
    example:
      'Two people sketch the same room from opposite doors. Matching landmarks, such as the same two corners, helps them turn and slide the sketches into a common orientation.',
    readout:
      'Teal circles belong to map A and orange squares to map B. Dashed lines connect shared landmark pairs. After alignment, paired points should be closer, although noise can leave a gap. Recovered rotation and translation report the turn and shift applied to map B.',
    steps: [
      'Choose at least two Shared landmarks, leave Communication enabled and click Align shared landmarks.',
      'Increase Observation noise and align again. Compare the remaining gaps with a low-noise example.',
      'Turn communication off or choose fewer than two landmarks. Alignment is disabled because this fit needs at least two distinct shared pairs.',
    ],
    terms: [
      [
        'Local frame / origin',
        'A robot’s own coordinate system: where it calls zero and which directions it calls X and Y.',
      ],
      [
        'Landmark / correspondence',
        'A recognisable place or point, and a pairing saying that both robots observed the same one. Pair identities are given in this example.',
      ],
      [
        'Rigid transform',
        'A rotation and a shift that preserve a map’s size and shape. It does not stretch or rescale the map.',
      ],
      [
        'Least-squares fit',
        'A calculation that chooses the rotation and shift to reduce the sum of squared gaps between shared pairs.',
      ],
      [
        'Communication / playback',
        'The communication switch makes the shared pairs available to the fit. Playback animates the robot symbols; it does not collect new landmarks. Reset alignment removes the fit and resets playback.',
      ],
    ],
    scope:
      'This is a map-alignment lesson with known pairs, not a full cooperative exploration or cleaning system. Communication timing and bandwidth are not simulated.',
  },
};
