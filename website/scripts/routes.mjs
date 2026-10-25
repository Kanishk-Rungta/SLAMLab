import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const content = JSON.parse(
  await fs.readFile(path.join(root, 'src/generated/content.json'), 'utf8'),
);
const index = await fs.readFile(path.join(root, 'dist/index.html'), 'utf8');
const routes = [
  '',
  'learn',
  'playground',
  'algorithms',
  'simulations',
  'studio',
  'benchmarks',
  'documentation',
  'about',
  ...content.documents.map((d) => 'documentation/' + d.id),
  ...content.catalog.map((a) => 'algorithms/' + a.id),
];
for (const route of routes) {
  const target = path.join(root, 'dist', route, 'index.html');
  await fs.mkdir(path.dirname(target), { recursive: true });
  const title =
    content.documents.find((d) => route === 'documentation/' + d.id)?.title ||
    content.catalog.find((a) => route === 'algorithms/' + a.id)?.name ||
    'Learn. Simulate. Visualize. Benchmark.';
  await fs.writeFile(
    target,
    index.replace(/<title>.*?<\/title>/, `<title>SLAMLab — ${title}</title>`),
  );
}
await fs.copyFile(path.join(root, 'dist/index.html'), path.join(root, 'dist/404.html'));
await fs.writeFile(path.join(root, 'dist/.nojekyll'), '');
await fs.writeFile(
  path.join(root, 'dist/sitemap.xml'),
  '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
    routes
      .map(
        (r) => `<url><loc>https://kanishk-rungta.github.io/SLAMLab/${r}${r ? '/' : ''}</loc></url>`,
      )
      .join('') +
    '</urlset>',
);
console.log(`Emitted ${routes.length} refresh-safe project routes.`);
