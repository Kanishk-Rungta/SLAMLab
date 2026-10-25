import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';

test('playground activities produce the outcomes described in their instructions', async ({
  page,
}, info) => {
  const stat = (name: string) =>
    page
      .locator('.stat')
      .filter({ has: page.getByText(name, { exact: true }) })
      .locator('strong');
  await page.goto('playground/');
  await page.getByRole('slider', { name: 'Translation noise' }).fill('0');
  await page.getByRole('slider', { name: 'Rotation noise' }).fill('0');
  await page.getByRole('slider', { name: 'Playback position' }).fill('280');
  await expect(stat('Position error')).toContainText('0.000');
  await page.getByRole('slider', { name: 'Rotation noise' }).fill('0.15');
  expect(parseFloat(await stat('Position error').innerText())).toBeGreaterThan(0);
  await page.getByRole('button', { name: 'Reset playback', exact: true }).click();
  await expect(page.getByRole('slider', { name: 'Playback position' })).toHaveValue('0');

  await page.getByRole('button', { name: /Occupancy mapping/ }).click();
  await page.getByRole('slider', { name: 'Cell resolution' }).fill('0.1');
  await page.getByRole('slider', { name: 'Playback position' }).fill('79');
  const unknown = await page
    .locator('.plot rect[fill="var(--unknown)"]')
    .first()
    .evaluate((element) => getComputedStyle(element).fill);
  const occupied = await page
    .locator('.plot rect[fill="var(--occupied)"]')
    .first()
    .evaluate((element) => getComputedStyle(element).fill);
  expect(unknown).not.toBe('rgb(0, 0, 0)');
  expect(unknown).not.toBe(occupied);
  const mapDownload = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Map JSON' }).click();
  const mapPath = info.outputPath('map.json');
  await (await mapDownload).saveAs(mapPath);
  const map = JSON.parse(await fs.readFile(mapPath, 'utf8'));
  expect(map.width).toBe(80);
  expect(map.cells).toHaveLength(6400);
  expect(map.cells.every((cell: number) => [-1, 0, 1].includes(cell))).toBe(true);

  await page.getByRole('button', { name: /Feature matching/ }).click();
  await page.getByRole('slider', { name: 'Observation noise' }).fill('0');
  await page.getByRole('slider', { name: 'Distance threshold' }).fill('0.05');
  await expect(stat('Correct matches')).toHaveText('15');
  await expect(stat('Wrong matches')).toHaveText('0');

  await page.getByRole('button', { name: /Pose graph/ }).click();
  const initial = parseFloat(await stat('Weighted objective').innerText());
  await page.getByRole('button', { name: 'Optimize graph' }).click();
  expect(parseFloat(await stat('Weighted objective').innerText())).toBeLessThan(initial);
  await page.getByRole('checkbox', { name: 'Include loop closure' }).uncheck();
  await expect(stat('Weighted objective')).toHaveText('0.0000');

  await page.getByRole('button', { name: /Multi-robot alignment/ }).click();
  await page.getByRole('slider', { name: 'Shared landmarks' }).fill('1');
  await expect(page.getByRole('button', { name: 'Align shared landmarks' })).toBeDisabled();
  await page.getByRole('slider', { name: 'Shared landmarks' }).fill('2');
  await page.getByRole('slider', { name: 'Observation noise' }).fill('0');
  await page.getByRole('button', { name: 'Align shared landmarks' }).click();
  await expect(page.getByText(/^Recovered rotation /)).toContainText(
    '40.1°; translation 1.40, -1.10 m',
  );

  await page.goto('studio/');
  await page.getByLabel('Open local occupancy map').setInputFiles(mapPath);
  await expect(page.getByRole('status')).toContainText('Loaded map locally');
  await expect(page.getByRole('checkbox', { name: 'Occupancy map layer' })).toBeChecked();
});

test('Studio preserves robot identity, recorded timing, full bounds and replay metadata', async ({
  page,
}, info) => {
  await page.goto('studio/?sample=two');
  const robot2 = page.locator('[data-robot-id="robot-2"] > g path');
  await expect(robot2).toBeVisible();
  const originalColor = await robot2.getAttribute('fill');
  await page.getByRole('checkbox', { name: 'robot-1', exact: true }).uncheck();
  await expect(robot2).toHaveAttribute('fill', originalColor!);

  const replay = {
    schema_version: 1,
    id: 'timing-audit',
    algorithm: 'Local timing audit',
    versions: { python: '3.10' },
    robots: [
      {
        id: 'r',
        estimate: [
          [0, 0, 0, 0],
          [2, 10, 0, 0],
        ],
        reference: [
          [0, 100, 0, 0],
          [2, 101, 0, 0],
        ],
        odometry: [
          [0, -100, 0, 0],
          [2, -99, 0, 0],
        ],
        landmarks: [
          {
            id: 'a',
            x: 1,
            y: 1,
            covariance: [
              [0.1, 0],
              [0, 0.2],
            ],
          },
        ],
      },
      {
        id: 'late',
        estimate: [
          [1, 50, 1, 0],
          [2, 51, 1, 0],
        ],
        reference: [],
        landmarks: [],
      },
    ],
  };
  const upload = page.getByLabel('Open local replay or trajectory');
  await upload.setInputFiles({
    name: 'audit.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(replay)),
  });
  await expect(page.getByRole('status')).toContainText('Loaded replay locally');
  const box = (await page.locator('.plot > svg').getAttribute('viewBox'))!.split(' ').map(Number);
  expect(box[0]).toBeLessThan(-100);
  expect(box[0] + box[2]).toBeGreaterThan(101);
  await page.getByRole('slider', { name: 'Playback position' }).fill('75');
  await expect(page.locator('[data-robot-id="r"] > g')).toHaveAttribute(
    'transform',
    'translate(0 0) rotate(0)',
  );
  await expect(page.locator('[data-robot-id="late"]')).toHaveCount(0);
  await page.getByRole('slider', { name: 'Playback position' }).fill('225');
  await expect(page.locator('[data-robot-id="late"]')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download replay', exact: true }).click();
  const file = info.outputPath('replay.json');
  await (await download).saveAs(file);
  const restored = JSON.parse(await fs.readFile(file, 'utf8'));
  expect(restored.versions).toEqual(replay.versions);
  expect(restored.robots[0].landmarks[0].covariance).toEqual(
    replay.robots[0].landmarks[0].covariance,
  );
  await upload.setInputFiles({
    name: 'large.json',
    mimeType: 'application/json',
    buffer: Buffer.alloc(5 * 1024 * 1024 + 1, ' '),
  });
  await expect(page.getByRole('alert')).toContainText('5 MiB');
});

test('Simulation Lab prepares selected local commands and Studio opens a fresh Webots export', async ({
  page,
}) => {
  await page.goto('simulations/');
  await page.getByRole('combobox', { name: 'Robot sessions' }).selectOption('2');
  await page.getByRole('combobox', { name: 'Duration', exact: true }).selectOption('60');
  await expect(page.locator('pre code')).toContainText('--robots 2 --seconds 60');
  expect(await page.locator('pre code').innerText()).not.toContain('\\');
  await expect(page.getByText('This page prepares commands.', { exact: false })).toBeVisible();
  if (process.env.SLAMLAB_ACTIVITY_REPLAY) {
    await page.goto('studio/');
    await page
      .getByLabel('Open local replay or trajectory')
      .setInputFiles(process.env.SLAMLAB_ACTIVITY_REPLAY);
    await expect(page.getByRole('status')).toContainText('Loaded replay locally');
    await expect(page.getByRole('checkbox', { name: 'robot-2', exact: true })).toBeVisible();
    await page.getByRole('slider', { name: 'Playback position' }).fill('300');
    await expect(page.locator('[data-robot-id="robot-2"] circle[opacity=".9"]')).toHaveCount(12);
    await expect(page.getByText('Position ATE · RMSE', { exact: true })).toBeVisible();
  }
});
