import { expect, test } from '@playwright/test';
import { readDashboardFixture } from './fixtures';

const original = readDashboardFixture('apple/record.json');
const publication = readDashboardFixture('apple/publication.json');

// Count actual G2 axis nodes AND their visibility in the browser viewport.
// A canvas containing all nodes can still be clipped by an oversized grid track.
const axes = (canvas: HTMLCanvasElement) => {
  const holder = canvas.parentElement as any;
  let fiber = holder[Object.keys(holder).find(key => key.startsWith('__reactFiber'))!];
  for (let depth = 0; fiber && depth < 24; depth++, fiber = fiber.return) {
    for (let hook = fiber.memoizedState, count = 0; hook && count < 32; count++, hook = hook.next) {
      const plot = hook.memoizedState?.current;
      if (!plot?.chart?.getContext) continue;
      const rect = canvas.getBoundingClientRect();
      return plot.chart
        .getContext()
        .canvas.document.documentElement.querySelectorAll('text')
        .filter((node: any) => String(node.className).includes('axis-label-item') && node.isVisible())
        .map((node: any) => {
          const box = node.getBounds();
          return {
            text: String(node.style.text),
            inViewport: rect.x + box.min[0] >= -1 && rect.x + box.max[0] <= innerWidth + 1,
          };
        });
    }
  }
  return [];
};

for (const width of [1440, 1024])
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm'])
    for (const mode of ['light', 'dark']) {
      test(`wide Apple table does not clip editor axes ${preset} ${mode} ${width}`, async ({ page }, testInfo) => {
        const record = structuredClone(original);
        record.schema.dashboard.theme = { preset, mode, overrides: {} };
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setViewportSize({ width, height: 1000 });
        await page.route('**/api/**', route => {
          const url = new URL(route.request().url());
          let data: unknown = [];
          if (url.pathname === `/api/v1/dashboards/${record.id}`) data = record;
          if (url.pathname === `/api/v1/dashboards/${record.id}/snapshot`) data = publication.snapshot;
          return route.fulfill({ json: { success: true, data, err_code: null, err_msg: null } });
        });
        await page.goto(`/dashboards/${record.id}/`);
        const renderer = page.locator('[data-dashboard-theme]').last();
        await expect(renderer).toHaveAttribute('data-dashboard-theme', preset);
        await expect(renderer).toHaveAttribute('data-dashboard-mode', mode);
        for (const label of ['折叠属性设置', '折叠组件库']) {
          const button = page.getByRole('button', { name: label, exact: true });
          if (await button.count()) await button.click();
        }
        const observations = [];
        for (const widget of record.schema.widgets) {
          const card = page.locator(`[data-dashboard-widget-id="${widget.id}"]`);
          await expect(card).toBeAttached();
          await expect
            .poll(async () => {
              const rect = await card.boundingBox();
              return rect!.x + rect!.width;
            })
            .toBeLessThanOrEqual(width + 1);
          if (!widget.encoding.x || ['pie', 'donut', 'table', 'kpi'].includes(widget.type)) continue;
          const canvas = card.locator('canvas');
          const result = publication.snapshot.widgets[widget.id];
          const column = result.columns.indexOf(widget.encoding.x);
          const categories = [...new Set(result.rows.map((row: unknown[]) => String(row[column])))];
          await expect(canvas).toBeAttached();
          await expect
            .poll(
              async () =>
                (await canvas.evaluate(axes)).filter(
                  (label: any) => categories.includes(label.text) && label.inViewport,
                ).length,
            )
            .toBe(categories.length);
          observations.push({
            widget: widget.id,
            categories,
            labels: await canvas.evaluate(axes),
            bounds: await card.boundingBox(),
          });
        }
        expect(errors).toEqual([]);
        const matrixImage = testInfo.outputPath('editor-matrix.png');
        await page.screenshot({ path: matrixImage, fullPage: true, animations: 'disabled' });
        await testInfo.attach('editor-matrix', { path: matrixImage, contentType: 'image/png' });
        await testInfo.attach('editor-viewport-axes', {
          body: JSON.stringify({ preset, mode, width, observations, errors }),
          contentType: 'application/json',
        });
      });
    }
