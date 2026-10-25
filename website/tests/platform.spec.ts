import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('home playback, navigation, theme, and direct refresh', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('./');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('find its');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await expect
    .poll(async () =>
      Number(await page.getByRole('slider', { name: 'Playback position' }).inputValue()),
    )
    .toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('link', { name: 'Start learning', exact: true }).click();
  await page.getByRole('link', { name: /Coordinate frames & motion/ }).click();
  await page.reload();
  await expect(page.locator('article h1')).toHaveText('Whose left and right?');
  await page.getByText('Equations & detailed notes', { exact: true }).click();
  await expect(page.locator('.katex').first()).toBeVisible();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Project', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Project objectives', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Dr. Vidhya Balasubramanian', { exact: false })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'Rithvik Mukka', exact: true })).toBeVisible();
  await expect(
    page.getByText('No demonstration videos are currently available.', { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Project overview', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('every playground runs a real model and controls work', async ({ page }) => {
  async function checkContext(title: string) {
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await page.getByText('Words used in this experiment', { exact: true }).click();
    await expect(page.locator('.guide-glossary dd').first()).toBeVisible();
    await page.getByText('Explore the equation', { exact: true }).click();
    await expect(page.locator('.equation')).toBeVisible();
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([]);
  }
  await page.goto('playground/');
  await checkContext('Why does a robot lose track of where it is?');
  await expect(page.getByRole('slider', { name: 'Translation noise' })).toHaveAccessibleDescription(
    /Random error in estimated forward movement/,
  );
  await page.getByRole('slider', { name: 'Playback position' }).fill('160');
  await page.getByRole('slider', { name: 'Translation noise' }).fill('0');
  await page.getByRole('button', { name: /Occupancy mapping/ }).click();
  await checkContext('How can a robot turn observations into a map?');
  await page.getByRole('slider', { name: 'Playback position' }).fill('79');
  await expect(page.locator('.plot rect').count()).resolves.toBeGreaterThan(100);
  await page.getByRole('button', { name: /Feature matching/ }).click();
  await checkContext('How does a robot recognise the same detail twice?');
  await expect(page.getByText('Correct matches', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /Pose graph/ }).click();
  await checkContext('How can revisiting a place help correct a path?');
  await page.getByRole('button', { name: /Optimize/ }).click();
  await expect(page.getByText(/iterations/i).first()).toBeVisible();
  await page.getByRole('button', { name: /Multi-robot alignment/ }).click();
  await checkContext('How can two robots put their maps together?');
  await page.getByRole('button', { name: 'Align shared landmarks' }).click();
  await expect(page.getByText(/^Recovered rotation /)).toBeVisible();
  await page.getByRole('checkbox', { name: 'Communication enabled' }).uncheck();
  await expect(page.getByRole('button', { name: 'Align shared landmarks' })).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: 'test-results/mobile-playground-context.png',
    fullPage: true,
    animations: 'disabled',
  });
});

test('studio uses measured results and accepts and rejects local files', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('studio/');
  await expect(page.getByText('Position ATE · RMSE')).toBeVisible();
  await page
    .getByRole('combobox', { name: 'Example recording' })
    .selectOption('landmark-two-robots');
  await expect(page.getByRole('checkbox', { name: 'robot-2', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Zoom in' }).click();
  await page.getByRole('button', { name: 'Try a sample grid' }).click();
  await expect(page.getByRole('button', { name: 'Remove grid' })).toBeVisible();
  const upload = page.getByLabel('Open local replay or trajectory');
  await upload.setInputFiles({
    name: 'bad.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('timestamp,x,y,yaw\n0,NaN,0,0\n1,1,0,0'),
  });
  await expect(page.getByRole('alert')).toContainText('finite');
  await upload.setInputFiles({
    name: 'local.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('timestamp,x,y,yaw\n0,0,0,0\n1,1,0,0'),
  });
  await expect(page.getByText('Local trajectory', { exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Loaded local trajectory');
  expect(errors).toEqual([]);
});

test('all main routes support light and dark themes with accessible controls', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  for (const theme of ['light', 'dark']) {
    await page.goto('./');
    await page.evaluate((t) => {
      localStorage.setItem('slamlab-theme', t);
    }, theme);
    for (const route of [
      '',
      'learn/',
      'algorithms/ekf-slam/',
      'simulations/',
      'studio/',
      'benchmarks/',
      'documentation/ekf/',
      'about/',
      'project/',
      'documentation/project-overview/',
    ]) {
      await page.goto(route || './');
      await expect(page.locator('h1').first()).toBeVisible();
      if (route === 'studio/' || route === 'benchmarks/')
        await expect(page.getByText('Position ATE · RMSE')).toBeVisible();
      const issues = (
        await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
      ).violations;
      expect(
        issues.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        theme + ' ' + route,
      ).toEqual([]);
      if (!route) await page.screenshot({ path: `test-results/home-${theme}.png`, fullPage: true });
    }
  }
  expect(errors).toEqual([]);
});

test('filters, benchmark data, and responsive accessibility', async ({ page }) => {
  await page.goto('algorithms/');
  await page.getByRole('textbox', { name: 'Search algorithms' }).fill('ORB');
  await expect(page.getByRole('heading', { name: 'ORB-SLAM2', exact: true })).toBeVisible();
  await expect(page.locator('.algorithm-card')).toHaveCount(1);
  await page.goto('benchmarks/');
  await expect(page.getByText('Position ATE · RMSE')).toBeVisible();
  await page.goto('./');
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Playground' })
    .click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('changing');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile-playground.png', fullPage: true });
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  await page.goto('project/');
  await expect(page.getByRole('heading', { name: 'Team details', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/mobile-project.png', fullPage: true });
});
