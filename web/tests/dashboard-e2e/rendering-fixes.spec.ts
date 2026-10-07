import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { readDashboardFixture } from './fixtures';

test.describe.configure({ mode: 'parallel' });

const load = (relative: string) => JSON.parse(readFileSync(path.resolve(process.cwd(), '..', relative), 'utf8'));
const apple = load('examples/dashboard/snapshots/apple-financial.public.json');
const walmartSchema = readDashboardFixture('walmart/schema.json');
const walmart = {
  dashboard_id: walmartSchema.dashboard.id,
  published_revision: 1,
  schema: walmartSchema,
  snapshot: readDashboardFixture('walmart/snapshot.json'),
};

// Read the chart library's real rendered G scene graph (the renderer uses canvas,
// not SVG). No synthetic DOM labels and no production-only testing hook.
const readPlot = (canvas: HTMLCanvasElement) => {
  const holder = canvas.parentElement as any;
  let fiber = holder[Object.keys(holder).find(key => key.startsWith('__reactFiber'))!];
  for (let depth = 0; fiber && depth < 24; depth++, fiber = fiber.return) {
    for (let hook = fiber.memoizedState, count = 0; hook && count < 32; count++, hook = hook.next) {
      const plot = hook.memoizedState?.current;
      if (!plot?.chart?.getContext) continue;
      const context = plot.chart.getContext();
      const root = context.canvas.document.documentElement;
      const rect = canvas.getBoundingClientRect();
      return {
        width: rect.width,
        height: rect.height,
        background: getComputedStyle(canvas.closest('[data-dashboard-widget-id]')!).backgroundColor,
        quantitativeMarks: context.views.flatMap((view: any) =>
          [...view.markState].flatMap(([mark, state]: any) =>
            ['line', 'point'].includes(mark.type)
              ? state.data.map((datum: any) => ({
                  type: mark.type,
                  value: datum.data?.value,
                  geometryY: datum.y,
                  axisY: view.scale.y.map(datum.data?.value),
                }))
              : [],
          ),
        ),
        runningMarkAnimations: [...root.querySelectorAll('.element'), ...root.querySelectorAll('.label')]
          .flatMap((node: any) => node.getAnimations?.() || [])
          .filter((animation: any) => ['running', 'pending'].includes(animation.playState)).length,
        dataLabels: root.querySelectorAll('.label').map((node: any) => {
          const text = node.children.find((item: any) => item.nodeName === 'text');
          const box = (text || node).getBounds();
          return {
            text: String(node.style.text ?? ''),
            visible: node.isVisible(),
            fill: text?.style.fill || node.style.fill,
            min: [...box.min],
            max: [...box.max],
          };
        }),
        bars: root
          .querySelectorAll('.element')
          .filter((node: any) => (node.attr('markType') || node.markType) === 'interval')
          .map((node: any) => {
            const box = node.getBounds();
            return { min: [...box.min], max: [...box.max] };
          }),
        labels: root.querySelectorAll('text').map((node: any) => {
          const bounds = node.getBounds();
          return {
            text: String(node.style.text ?? ''),
            className: String(node.className),
            visible: node.isVisible(),
            fill: node.style.fill,
            overflow: node.style.textOverflow,
            wrapWidth: node.style.wordWrapWidth,
            min: [...bounds.min],
            max: [...bounds.max],
          };
        }),
      };
    }
  }
  throw new Error('Cannot inspect the actual rendered chart instance');
};

const contrast = (foreground: string, background: string) => {
  const luminance = (color: string) => {
    const parts = color.startsWith('#')
      ? [1, 3, 5].map(index => parseInt(color.slice(index, index + 2), 16))
      : color
          .match(/[\d.]+/g)!
          .slice(0, 3)
          .map(Number);
    const rgb = parts
      .map(value => value / 255)
      .map(value => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
};
const overlap = (a: any, b: any) =>
  a.min[0] < b.max[0] - 0.5 && a.max[0] > b.min[0] + 0.5 && a.min[1] < b.max[1] - 0.5 && a.max[1] > b.min[1] + 0.5;

for (const offset of [0, -200_000, -500_000]) {
  test(`line positions agree with the displayed numeric axis, offset ${offset}`, async ({ page }) => {
    const published = structuredClone(apple);
    const widget = published.schema.widgets.find((item: any) => item.type === 'line');
    const result = published.snapshot.widgets[widget.id];
    const valueColumn = result.columns.indexOf(widget.encoding.y);
    result.rows.forEach((row: number[]) => (row[valueColumn] += offset));
    await page.route('**/api/**', route => route.fulfill({ json: { success: true, data: published } }));
    await page.goto('/dashboard-share/axis-scale-regression/', { waitUntil: 'domcontentloaded' });
    const canvas = page.locator(`[data-dashboard-widget-id="${widget.id}"] canvas`);
    await expect(canvas).toBeVisible();
    await expect.poll(async () => (await canvas.evaluate(readPlot)).runningMarkAnimations).toBe(0);
    const plotted = (await canvas.evaluate(readPlot)).quantitativeMarks;
    expect(plotted.filter((mark: any) => mark.type === 'point')).toHaveLength(result.rows.length);
    for (const mark of plotted) {
      expect(Number.isFinite(mark.value)).toBe(true);
      expect(mark.geometryY, `value ${mark.value} must align with the displayed axis`).toBeCloseTo(mark.axisY, 6);
    }
  });
}

for (const width of [1440, 1024]) {
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm']) {
    for (const mode of ['light', 'dark']) {
      for (const [source, original] of [
        ['apple', apple],
        ['walmart', walmart],
      ] as const) {
        test(`rendered axes ${source} ${preset} ${mode} ${width}`, async ({ page }, testInfo) => {
          const published = structuredClone(original);
          published.schema.dashboard.theme = { preset, mode, overrides: {} };
          const errors: string[] = [];
          page.on('pageerror', error => errors.push(error.message));
          await page.setViewportSize({ width, height: 1000 });
          await page.route('**/api/**', route =>
            route.fulfill({
              json: {
                success: true,
                data: route.request().url().includes('/public/dashboards/') ? published : null,
              },
            }),
          );
          await page.goto('/dashboard-share/rendering-qa/', { waitUntil: 'domcontentloaded' });
          const renderer = page.locator('[data-dashboard-theme]').last();
          await expect(renderer).toHaveAttribute('data-dashboard-theme', preset);
          await expect(renderer).toHaveAttribute('data-dashboard-mode', mode);
          const records = [];
          for (const widget of published.schema.widgets) {
            const type = widget.presentation?.visualization || widget.type;
            if (['kpi', 'table', 'heatmap', 'gauge'].includes(type)) continue;
            const card = page.locator(`[data-dashboard-widget-id="${widget.id}"]`);
            const canvas = card.locator('canvas');
            await expect(canvas).toBeAttached();
            await expect.poll(async () => (await canvas.evaluate(readPlot)).height).toBeGreaterThan(100);
            const data = published.snapshot.widgets[widget.id];
            const color =
              widget.encoding.series ||
              widget.encoding.color ||
              (['pie', 'donut'].includes(type) ? widget.encoding.category || widget.encoding.x : null);
            const series = color
              ? [...new Set(data.rows.map((row: unknown[]) => String(row[data.columns.indexOf(color)])))]
              : [widget.encoding.y];
            if (widget.presentation?.show_legend !== false && widget.style.showLegend !== false) {
              await expect
                .poll(
                  async () =>
                    (await canvas.evaluate(readPlot)).labels.filter(
                      (label: any) => /legend.*item.*label/.test(label.className) && label.visible && label.text.trim(),
                    ).length,
                )
                .toBe(series.length);
              const withLegend = await canvas.evaluate(readPlot);
              const names = withLegend.labels.filter(
                (label: any) => /legend.*item.*label/.test(label.className) && label.visible,
              );
              for (const label of names) {
                expect(contrast(label.fill, withLegend.background)).toBeGreaterThanOrEqual(4.5);
                expect(label.max[0]).toBeLessThanOrEqual(withLegend.width + 1);
                expect(label.max[1]).toBeLessThanOrEqual(withLegend.height + 1);
                expect(
                  withLegend.labels
                    .filter((axis: any) => /axis-label/.test(axis.className))
                    .some((axis: any) => overlap(label, axis)),
                ).toBe(false);
              }
            }
            if (['pie', 'donut'].includes(type)) continue;
            const dimensionIndex = data.columns.indexOf(widget.encoding.x);
            const categories = [...new Set(data.rows.map((row: unknown[]) => String(row[dimensionIndex])))];
            await expect
              .poll(async () => {
                const plot = await canvas.evaluate(readPlot);
                return plot.labels.filter(
                  (label: any) =>
                    label.className.includes('axis-label-item') &&
                    categories.includes(label.text) &&
                    label.visible &&
                    label.min[0] >= -1 &&
                    label.min[1] >= -1 &&
                    label.max[0] <= plot.width + 1 &&
                    label.max[1] <= plot.height + 1,
                ).length;
              })
              .toBe(categories.length);
            let plot = await canvas.evaluate(readPlot);
            const body = await card.locator('[data-dashboard-widget-body]').boundingBox();
            expect(plot.height).toBeLessThanOrEqual(body!.height);
            const measureTicks = plot.labels.filter(
              (label: any) =>
                label.className.includes('axis-label-item') && !categories.includes(label.text) && label.visible,
            );
            expect(measureTicks.length).toBeGreaterThan(0);
            if (['bar', 'column', 'stacked_column'].includes(type)) {
              // Label existence does not mean the bar resize animation has finished.
              // Inspect real animation state and unchanged geometry before asserting
              // the same collision/contrast/bounds requirements on the settled chart.
              let previousGeometry = '';
              let stableFrames = 0;
              await expect
                .poll(
                  async () => {
                    const scene = await canvas.evaluate(readPlot);
                    const visible = scene.dataLabels.filter((label: any) => label.visible && label.text);
                    const geometry = JSON.stringify({ bars: scene.bars, labels: visible });
                    stableFrames =
                      visible.length &&
                      scene.bars.length &&
                      !scene.runningMarkAnimations &&
                      geometry === previousGeometry
                        ? stableFrames + 1
                        : 0;
                    previousGeometry = geometry;
                    return stableFrames;
                  },
                  { intervals: [100], timeout: 15000 },
                )
                .toBeGreaterThanOrEqual(4);
              const settled = await canvas.evaluate(readPlot);
              plot = settled;
              const labels = settled.dataLabels.filter((label: any) => label.visible && label.text);
              expect(labels.length).toBeGreaterThan(0);
              expect(settled.bars.length).toBeGreaterThan(0);
              for (const [index, label] of labels.entries()) {
                expect(contrast(label.fill, settled.background)).toBeGreaterThanOrEqual(4.5);
                expect(label.min[0]).toBeGreaterThanOrEqual(-0.5);
                expect(label.min[1]).toBeGreaterThanOrEqual(-0.5);
                expect(label.max[0]).toBeLessThanOrEqual(settled.width + 0.5);
                expect(label.max[1]).toBeLessThanOrEqual(settled.height + 0.5);
                expect(settled.bars.some((bar: any) => overlap(label, bar))).toBe(false);
                expect(labels.slice(index + 1).some((other: any) => overlap(label, other))).toBe(false);
                expect(label.text).not.toContain('…');
              }
            }
            records.push({ widget: widget.id, categories, plot });
          }
          expect(errors).toEqual([]);
          const matrixImage = testInfo.outputPath('public-matrix.png');
          await page.screenshot({ path: matrixImage, fullPage: true, animations: 'disabled' });
          await testInfo.attach('public-matrix', { path: matrixImage, contentType: 'image/png' });
          await testInfo.attach('actual-rendered-axis-nodes', {
            body: JSON.stringify({ source, preset, mode, width, records }),
            contentType: 'application/json',
          });
        });
      }
    }
  }
}

test('long series names ellipsize and reveal the full escaped name on hover', async ({ page }) => {
  const published = structuredClone(apple);
  const longName = '收入系列非常长的完整名称-<img src=x>-2022至2024财年-'.repeat(3);
  const result = published.snapshot.widgets['profit-trend'];
  const seriesIndex = result.columns.indexOf('metric');
  const first = result.rows[0][seriesIndex];
  for (const row of result.rows) if (row[seriesIndex] === first) row[seriesIndex] = longName;
  await page.setViewportSize({ width: 1024, height: 1000 });
  await page.route('**/api/**', route =>
    route.fulfill({
      json: { success: true, data: route.request().url().includes('/public/dashboards/') ? published : null },
    }),
  );
  await page.goto('/dashboard-share/rendering-legend-qa/');
  const canvas = page.locator('[data-dashboard-widget-id="profit-trend"] canvas');
  await expect(canvas).toBeAttached();
  await expect
    .poll(
      async () =>
        (await canvas.evaluate(readPlot)).labels.filter(
          (label: any) => /legend.*item.*label/.test(label.className) && label.text === longName,
        ).length,
    )
    .toBe(1);
  const label = (await canvas.evaluate(readPlot)).labels.find(
    (item: any) => /legend.*item.*label/.test(item.className) && item.text === longName,
  )!;
  expect(label.overflow).toBe('...');
  expect(label.max[0] - label.min[0]).toBeLessThan(180);
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + (label.min[0] + label.max[0]) / 2, box.y + (label.min[1] + label.max[1]) / 2);
  const poptip = page.locator('[data-dashboard-legend-full-name]');
  await expect(poptip).toBeVisible();
  await expect(poptip).toHaveText(longName);
  await expect(poptip.locator('img')).toHaveCount(0);
});
