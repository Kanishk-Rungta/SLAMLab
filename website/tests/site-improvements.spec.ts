import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('recording errors clear old results and retry loads the selected experiment', async ({
  page,
}) => {
  for (const route of ['studio/', 'benchmarks/']) {
    await page.goto(route);
    await expect(page.getByText('Position ATE · RMSE', { exact: true })).toBeVisible();
    await page.route('**/generated/landmark-two-robots.json', (request) => request.abort());
    await page
      .getByRole('combobox', {
        name: route === 'studio/' ? 'Example recording' : 'Experiment',
        exact: true,
      })
      .selectOption('landmark-two-robots');
    await expect(page.getByRole('alert')).toContainText('Could not load the selected recording');
    await expect(page.getByText('Position ATE · RMSE', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('status')).toHaveCount(0);
    await page.unroute('**/generated/landmark-two-robots.json');
    await page.getByRole('button', { name: 'Retry recording' }).click();
    await expect(page.getByText('Position ATE · RMSE', { exact: true })).toBeVisible();
    await expect(
      page
        .getByRole('combobox', {
          name: route === 'studio/' ? 'Metric robot' : 'Robot',
          exact: true,
        })
        .locator('option'),
    ).toHaveCount(2);
  }
  await page.route('**/generated/landmark-reference.json', (request) => request.abort());
  await page.goto('studio/');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('status')).toHaveCount(0);
});

test('maps have an independent preview and published replays open at a useful final state', async ({
  page,
}) => {
  await page.goto('studio/');
  await expect(page.locator('[data-robot-id="robot-1"] circle[opacity=".9"]')).toHaveCount(12);
  await page.getByRole('button', { name: 'Try a sample grid' }).click();
  await expect(page.getByRole('region', { name: 'Separate occupancy map' })).toBeVisible();
  expect(await page.locator('.standalone-map .plot rect[opacity=".6"]').count()).toBeGreaterThan(
    100,
  );
  await expect(page.locator('.studio-layout .plot rect[opacity=".6"]')).toHaveCount(0);
  await page.getByRole('checkbox', { name: 'Occupancy map layer' }).uncheck();
  await expect(page.locator('.standalone-map .plot rect[opacity=".6"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Remove grid' }).click();
  await page.getByRole('button', { name: 'Replay from start' }).click();
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
});

test('guided examples calculate results and freeze saved visuals across all five playgrounds', async ({
  page,
}) => {
  const cases = [
    ['odometry', 'No movement errors', 'Add turning errors'],
    ['occupancy', 'Look farther', 'Shorten the view'],
    ['features', 'Try a clean match', 'Try confusing details'],
    ['graph', 'Correct with a revisit', 'Without a revisit'],
    ['multi', 'Align clear observations', 'Align noisy observations'],
  ];
  for (const [module, before, after] of cases) {
    await page.goto('playground/?module=' + module);
    await page.getByRole('button', { name: before, exact: true }).click();
    await page.getByRole('button', { name: 'Save current example for comparison' }).click();
    const panel = page.getByRole('region', { name: 'Saved experiment comparison' });
    const frozen = panel.locator('figure').first();
    const caption = await frozen.locator('figcaption').textContent();
    const result = await frozen.locator('figcaption p').innerText();
    const savedContent = module === 'features' ? frozen.locator('svg') : frozen.locator('svg > g');
    const geometry = await savedContent.innerHTML();
    await page.getByRole('button', { name: after, exact: true }).click();
    await expect(frozen.locator('figcaption')).toHaveText(caption);
    expect(await savedContent.innerHTML()).toBe(geometry);
    await expect(panel.locator('figure').nth(1).locator('figcaption p')).not.toHaveText(result);
    if (module === 'odometry') {
      await expect(panel.locator('figure').first().locator('svg')).toHaveAttribute(
        'viewBox',
        (await panel.locator('figure').nth(1).locator('svg').getAttribute('viewBox'))!,
      );
      await expect(frozen).toContainText('0.000 m');
      await expect(panel.locator('figure').nth(1)).not.toContainText('0.000 m from');
      await panel.screenshot({
        path: 'test-results/saved-playground-comparison.png',
        animations: 'disabled',
      });
    }
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([]);
  }
});

test('documentation groups all guides and code can be copied and scrolled with a keyboard', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('documentation/');
  await expect(page.locator('.document-group')).toHaveCount(5);
  await expect(page.locator('a.document-card')).toHaveCount(19);
  await page.getByRole('textbox', { name: 'Search documentation' }).fill('installation');
  await expect(page.locator('a.document-card')).toHaveCount(1);
  await page.locator('a.document-card').click();
  const firstCode = await page.locator('pre code').first().innerText();
  await page.getByRole('button', { name: 'Copy code', exact: true }).first().click();
  await expect
    .poll(() =>
      page.evaluate(async () => (await navigator.clipboard.readText()).replace(/\r\n/g, '\n')),
    )
    .toBe(firstCode);
  for (const route of [
    'documentation/landmark-lab/',
    'documentation/reading-results/',
    'algorithms/door-slam/',
    'algorithms/kimera-multi/',
    'algorithms/d2slam/',
    'algorithms/swarm-slam/',
    'algorithms/orb-slam2/',
    'algorithms/rtabmap/',
  ]) {
    await page.goto(route);
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
      route,
    ).toEqual([]);
    if (route.startsWith('documentation/'))
      await expect(page.locator('pre').first()).toHaveAttribute('tabindex', '0');
    else await expect(page.getByRole('heading', { name: 'The idea in plain words' })).toBeVisible();
  }
});

test('mobile layouts fit and the playground visual is reachable on the first screen', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ['simulations/', 'playground/', 'project/', 'benchmarks/', 'about/']) {
    await page.goto(route);
    await expect(page.locator('main h1')).toBeVisible();
    if (route === 'benchmarks/')
      await expect(page.getByText('Position ATE · RMSE', { exact: true })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      route,
    ).toBe(true);
    if (route === 'playground/') {
      expect((await page.locator('.visual-panel .plot').boundingBox())!.y).toBeLessThan(650);
      await page.getByRole('combobox', { name: 'Choose an experiment' }).selectOption('occupancy');
      await expect(page).toHaveURL(/module=occupancy/);
      await page.screenshot({
        path: 'test-results/playground-mobile-first-screen.png',
        animations: 'disabled',
      });
    }
    if (route === 'simulations/')
      await page.screenshot({ path: 'test-results/simulation-mobile.png', animations: 'disabled' });
  }
});

test('research resources retain attribution and match the selected recording', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('benchmarks/');
  const resources = page.getByRole('region', { name: 'Citation and reproduction' });
  await page.getByText('Position ATE · RMSE', { exact: true }).waitFor();
  await resources.getByRole('button', { name: 'Copy software citation' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    'SLAMLab project team. SLAMLab',
  );
  await page
    .getByRole('combobox', { name: 'Experiment', exact: true })
    .selectOption('landmark-two-robots');
  await expect(resources.locator('code')).toContainText('--robots 2 --seconds 30');
  await expect(resources.getByRole('link', { name: 'Download run manifest' })).toHaveAttribute(
    'href',
    /landmark-two-robots-manifest.json$/,
  );
  const manifest = await page.request.get('generated/landmark-two-robots-manifest.json');
  expect((await manifest.json()).configuration.robots).toBe(2);
  const citation = await page.request.get('generated/CITATION.cff');
  expect(await citation.text()).toContain('name: SLAMLab project team');
  const figure = await page.request.get('generated/landmark-slam.png');
  expect(figure.ok()).toBe(true);
  expect((await figure.body()).length).toBeGreaterThan(1000);
  await page.goto('about/');
  await expect(
    page.getByText(
      'SLAMLab is developed and maintained collaboratively by the entire project team.',
      {
        exact: false,
      },
    ),
  ).toBeVisible();
});
