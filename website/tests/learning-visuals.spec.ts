import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('all twelve lessons have working visual walkthroughs and related activities', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('learn/');
  await expect(page.locator('.lesson-preview .concept-diagram')).toHaveCount(12);
  const links = await page
    .locator('a.visual-lesson')
    .evaluateAll((elements) => elements.map((element) => (element as HTMLAnchorElement).href));
  expect(links).toHaveLength(12);
  await page.screenshot({
    path: 'test-results/learn-visuals-desktop.png',
    fullPage: false,
    animations: 'disabled',
  });
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  for (const link of links) {
    await page.goto(link);
    const visual = page.getByRole('region', { name: 'Visual concept walkthrough' });
    await expect(visual.getByRole('img')).toBeVisible();
    const firstCaption = await visual.locator('.visual-caption').innerText();
    await visual.getByRole('button', { name: 'Next visual step', exact: true }).click();
    await expect(visual.locator('.visual-caption')).not.toHaveText(firstCaption);
    await visual.getByRole('button', { name: 'Next visual step', exact: true }).click();
    await expect(
      visual.getByRole('button', { name: 'Next visual step', exact: true }),
    ).toBeDisabled();
    await expect(visual.getByRole('link', { name: 'Try this idea' })).toHaveAttribute(
      'href',
      /SLAMLab\/(playground|simulations|benchmarks|studio)/,
    );
  }
  await page.goto('documentation/frames/');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Next visual step', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: 'test-results/lesson-visual-mobile.png',
    fullPage: false,
    animations: 'disabled',
  });
  expect(errors).toEqual([]);
});

test('lessons work directly, connect to the next idea, and preserve detailed-note links', async ({
  page,
}) => {
  await page.goto('documentation/graphs/');
  await expect(
    page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Learn', exact: true }),
  ).toHaveClass(/active/);
  await expect(page.locator('.slam-context')).toContainText(
    'find your position while building its map',
  );
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'How does returning to a familiar place fix a map?',
  );
  await expect(page.locator('.learning-notes')).not.toHaveAttribute('open', '');
  await expect(page.getByRole('region', { name: 'Connect to the next lesson' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Next visual step', exact: true }).click();
  await page.getByRole('button', { name: 'Next visual step', exact: true }).click();
  await page.screenshot({
    path: 'test-results/lesson-connected-desktop.png',
    animations: 'disabled',
  });
  await page.getByRole('region', { name: 'Connect to the next lesson' }).getByRole('link').click();
  await expect(page).toHaveURL(/documentation\/multi-robot\/$/);
  await expect(
    page.getByRole('button', { name: 'Previous visual step', exact: true }),
  ).toBeDisabled();
  await page.getByRole('combobox', { name: 'Choose a lesson' }).selectOption('fundamentals');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'How can a robot explore an unfamiliar room?',
  );
  await page.getByRole('button', { name: 'Next visual step', exact: true }).click();
  await page
    .locator('.lesson-player')
    .screenshot({ path: 'test-results/mission-lesson-desktop.png', animations: 'disabled' });
  await page.goto('documentation/frames/#integrating-motion');
  await expect(page.locator('.learning-notes')).toHaveAttribute('open', '');
  await expect(page.locator('#integrating-motion')).toBeVisible();
  await expect(page.locator('#integrating-motion')).toBeInViewport();
  await page.reload();
  await expect(page.locator('#integrating-motion')).toBeVisible();
  await page.goto('documentation/frames/#coordinate-frames-and-robot-motion');
  await page.reload();
  await expect(page.locator('#coordinate-frames-and-robot-motion')).toBeVisible();
  await expect(page.locator('.learning-notes')).not.toHaveAttribute('open', '');
});

test('activity handoffs, browser history and refresh retain the selected module', async ({
  page,
}) => {
  await page.goto('playground/?module=features');
  await page.locator('.activity-handoff').getByRole('link').click();
  await expect(page).toHaveURL(/module=graph$/);
  await expect(
    page.getByRole('heading', { name: 'How can revisiting a place help correct a path?' }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: /Pose graph/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await page.goBack();
  await expect(
    page.getByRole('heading', { name: 'How does a robot recognise the same detail twice?' }),
  ).toBeVisible();
  await page.goForward();
  await expect(
    page.getByRole('heading', { name: 'How can revisiting a place help correct a path?' }),
  ).toBeVisible();
});

test('feature matching explains real descriptor decisions with accessible scene controls', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('playground/?module=features');
  await page.getByRole('button', { name: 'Try a clean match', exact: true }).click();
  await page.getByRole('combobox', { name: 'Inspect a feature', exact: true }).selectOption('1');
  await expect(page.locator('.match-decision')).toContainText('Accepted');
  await page.getByText('Compare the three nearest candidates', { exact: true }).click();
  await expect(page.locator('.candidate-table tbody tr').first()).toContainText('0.000');
  await page.getByRole('combobox', { name: 'Inspect a feature', exact: true }).selectOption('0');
  await expect(page.locator('.match-decision')).toContainText('Rejected');
  const marker = page.getByRole('button', {
    name: 'Inspect A2: Left window, upper-right corner',
    exact: true,
  });
  await marker.focus();
  await marker.press('Enter');
  await expect(page.getByRole('combobox', { name: 'Inspect a feature', exact: true })).toHaveValue(
    '1',
  );
  await expect(marker).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Try confusing details', exact: true }).click();
  const wrong = page
    .locator('.stat')
    .filter({ has: page.getByText('Wrong matches', { exact: true }) })
    .locator('strong');
  expect(Number(await wrong.innerText())).toBeGreaterThan(0);
  await page.getByRole('checkbox', { name: 'Show all accepted pairs', exact: true }).check();
  await page.getByRole('button', { name: '1 · Spot details', exact: true }).click();
  await expect(page.locator('.matching-caption')).toContainText('Corners');
  await page.getByRole('button', { name: '2 · Inspect a pair', exact: true }).click();
  await expect(page.locator('.matching-caption')).toContainText('nearest descriptor');
  await page.getByRole('button', { name: '3 · Review matches', exact: true }).click();
  await page.getByText('See the six descriptor values', { exact: true }).click();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  await page
    .locator('.feature-experiment')
    .evaluate((element) => element.scrollIntoView({ block: 'start' }));
  await page.evaluate(() => window.scrollBy(0, -85));
  await page.screenshot({ path: 'test-results/features-desktop.png', animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.matching-scene')).toHaveAttribute('viewBox', '0 0 360 575');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page
    .locator('.feature-experiment')
    .evaluate((element) => element.scrollIntoView({ block: 'start' }));
  await page.evaluate(() => window.scrollBy(0, -85));
  await page.screenshot({ path: 'test-results/features-mobile.png', animations: 'disabled' });
  await page.getByRole('button', { name: 'Switch to dark theme', exact: true }).click();
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  expect(errors).toEqual([]);
});
