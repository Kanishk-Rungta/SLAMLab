export const algorithmStories: Record<
  string,
  { input: string; process: string; output: string; idea: string }
> = {
  'ekf-slam': {
    input: 'Wheel motion + visible markers',
    process: 'Predict, then correct with observations',
    output: 'Robot path + landmark map',
    idea: 'Combine movement with observations of known marker identities to estimate position and map together.',
  },
  'door-slam': {
    input: 'Stereo views from several robots',
    process: 'Check shared places; correct paths together',
    output: 'More consistent robot paths',
    idea: 'Robots exchange selected place matches and reject misleading connections before adjusting their paths.',
  },
  'kimera-multi': {
    input: 'Camera pairs + motion sensors',
    process: 'Recognise shared places; connect local maps',
    output: 'Paths + a 3D surface map',
    idea: 'Combine local 3D reconstructions across robots. Object labels require additional semantic inputs.',
  },
  d2slam: {
    input: 'Stereo cameras + motion sensors',
    process: 'Track locally; share clues across robots',
    output: 'Local and globally corrected paths',
    idea: 'Each robot tracks its own movement while shared observations help correct the group’s estimates.',
  },
  'swarm-slam': {
    input: 'Local motion + sensor observations',
    process: 'Prioritise useful shared-place checks',
    output: 'Connected robot paths',
    idea: 'Choose which observations to exchange so robots can connect maps while limiting communication.',
  },
  'orb-slam2': {
    input: 'One camera, stereo, or depth images',
    process: 'Track corners; recognise earlier places',
    output: 'Camera path + sparse 3D points',
    idea: 'Follow recognisable image details through successive views, then use revisits to correct the map.',
  },
  rtabmap: {
    input: 'Images, depth, or laser data',
    process: 'Recognise places; manage map memory',
    output: 'Paths and configurable map formats',
    idea: 'Recognise familiar places while managing how much mapping history stays active in memory.',
  },
};
export function availability(operation: string) {
  return operation === 'run'
    ? 'Runnable locally'
    : operation === 'external'
      ? 'Native validation pending'
      : 'Reference guide';
}
