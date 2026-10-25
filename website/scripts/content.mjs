import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Marked } from 'marked';
import katex from 'katex';

const website = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.dirname(website);
const base = '/SLAMLab/';
const repo = 'https://github.com/Kanishk-Rungta/SLAMLab/blob/main/';
const sources = [
  ['fundamentals', 'SLAM fundamentals', 'Beginner', 'docs/fundamentals/README.md', 'A mental model of localization, mapping and uncertainty.'],
  ['frames', 'Coordinate frames & motion', 'Beginner', 'docs/learning/frames.md', 'Turn local measurements into a consistent geometric picture.'],
  ['sensors', 'Sensors & uncertainty', 'Beginner', 'docs/learning/sensors.md', 'Understand noise, drift and what each sensor tells you.'],
  ['first-experiment', 'Your first SLAM experiment', 'Beginner', 'docs/learning/first-slam.md', 'Run Webots, inspect a landmark map and replay your result.'],
  ['association', 'Features & data association', 'Intermediate', 'docs/learning/association.md', 'Connect observations without mistaking one place for another.'],
  ['ekf', 'Inside EKF-SLAM', 'Intermediate', 'docs/learning/ekf.md', 'Predict, initialize landmarks and correct the joint state.'],
  ['mapping', 'Occupancy grids & particles', 'Intermediate', 'docs/learning/mapping.md', 'Represent space and reason about alternate pose hypotheses.'],
  ['visual', 'Visual, stereo & RGB-D SLAM', 'Intermediate', 'docs/learning/visual.md', 'From image features to metric geometry and camera motion.'],
  ['graphs', 'Pose graphs & optimization', 'Advanced', 'docs/learning/graphs.md', 'Read factors, loop constraints and bundle adjustment.'],
  ['multi-robot', 'Multi-robot mapping', 'Advanced', 'docs/learning/multi-robot.md', 'Align maps and account for communication constraints.'],
  ['metrics', 'SLAM evaluation', 'Advanced', 'docs/benchmarking/metrics.md', 'Associate poses and interpret ATE, RPE and coverage.'],
  ['experiments', 'Reproducible experiments', 'Advanced', 'docs/learning/experiments.md', 'Keep sensor inputs, computation and provenance comparable.'],
  ['installation', 'Installation', 'Documentation', 'docs/getting-started/installation.md', 'Python environments, Webots and native stacks.'],
  ['landmark-lab', 'Landmark Lab guide', 'Documentation', 'examples/landmark-slam/README.md', 'Configuration, sensor contract and experiment outputs.'],
  ['reading-results', 'Reading maps & trajectories', 'Documentation', 'docs/tutorials/reading-results.md', 'Frames, occupancy cells and point-cloud conventions.'],
  ['troubleshooting', 'Troubleshooting', 'Documentation', 'docs/troubleshooting/README.md', 'Resolve common environment and data-format issues.'],
  ['contributing', 'Contributing', 'Documentation', 'CONTRIBUTING.md', 'Add an experiment, research integration or lesson.'],
  ['references', 'Research references', 'Documentation', 'docs/references/README.md', 'Original papers, upstream sources and citations.'],
];
const bySource = new Map(sources.map(([id, , , source]) => [path.resolve(root, source), id]));
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const documents = [];
for (const [id, title, level, source, description] of sources) {
  const absolute = path.resolve(root, source);
  const used = new Map();
  const md = new Marked({ renderer: {
    html: ({ text }) => escape(text),
    heading({ text, tokens, depth }) {
      const slug = text.toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu, '').replaceAll(' ', '-');
      const count = used.get(slug) || 0; used.set(slug, count + 1);
      return `<h${depth} id="${slug}${count ? '-' + count : ''}">${this.parser.parseInline(tokens)}</h${depth}>`;
    },
  } });
  md.use({ extensions: [
    { name: 'mathBlock', level: 'block', start: text => text.indexOf('$$'), tokenizer(text) {
      const m = /^\$\$\s*\n?([\s\S]+?)\n?\$\$(?:\n|$)/.exec(text);
      if (m) return { type: 'mathBlock', raw: m[0], text: m[1] };
    }, renderer: token => katex.renderToString(token.text, { displayMode: true, throwOnError: true, output: 'html' }) },
    { name: 'mathInline', level: 'inline', start: text => text.indexOf('$'), tokenizer(text) {
      const m = /^\$([^$\n]+)\$/.exec(text);
      if (m) return { type: 'mathInline', raw: m[0], text: m[1] };
    }, renderer: token => katex.renderToString(token.text, { throwOnError: true, output: 'html' }) },
  ], walkTokens(token) {
    if ((token.type === 'link' || token.type === 'image') && token.href && !/^(https?:|mailto:|#)/.test(token.href)) {
      const [relative, fragment] = token.href.split('#');
      const target = path.resolve(path.dirname(absolute), decodeURIComponent(relative));
      const slug = bySource.get(target);
      token.href = slug ? `${base}documentation/${slug}/${fragment ? '#' + fragment : ''}` : repo + path.relative(root, target).split(path.sep).join('/') + (fragment ? '#' + fragment : '');
    }
  } });
  const markdown = await fs.readFile(absolute, 'utf8');
  documents.push({ id, title, level, source, description, markdown, html: await md.parse(markdown) });
}
const catalog = JSON.parse(await fs.readFile(path.join(root, 'algorithms/catalog.json'), 'utf8'));
await fs.mkdir(path.join(website, 'src/generated'), { recursive: true });
await fs.writeFile(path.join(website, 'src/generated/content.json'), JSON.stringify({ documents, catalog }));
const out = path.join(website, 'public/generated');
await fs.mkdir(out, { recursive: true });
await fs.copyFile(path.join(root, 'assets/logo.svg'), path.join(out, 'logo.svg'));
await fs.copyFile(path.join(root, 'assets/results/landmark-slam.png'), path.join(out, 'landmark-slam.png'));
for (const name of ['landmark-reference', 'landmark-two-robots']) {
  await fs.copyFile(path.join(root, 'examples/results', name, 'viewer.json'), path.join(out, name + '.json'));
}
await fs.copyFile(path.join(root, 'examples/landmark-slam/config.json'), path.join(out, 'landmark-config.json'));
console.log(`Generated ${documents.length} canonical documents, ${catalog.length} algorithm profiles and two measured replay bundles.`);
