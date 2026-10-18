import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const sources = ['Walmart_Sales', 'sqlite_energy', 'sqlite_itsm', 'sqlite_maintenance', 'sqlite_students'];
const snapshot = JSON.parse(
  readFileSync(path.resolve(process.cwd(), '../examples/dashboard/snapshots/walmart-sales.public.json'), 'utf8'),
);
const success = (data: unknown) => ({ success: true, data, err_code: null, err_msg: null });

async function fixture(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('__db_gpt_theme_key', 'light');
  });
  const imageErrors: string[] = [];
  page.on('response', response => {
    if (response.url().includes('/dashboard-templates/') && response.status() >= 400) imageErrors.push(response.url());
  });
  page.on('requestfailed', request => {
    if (request.url().includes('/dashboard-templates/')) imageErrors.push(request.url());
  });
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (pathname === '/api/v2/serve/datasources')
      data = sources.map((db_name, id) => ({ id, db_name, type: 'sqlite', params: { name: db_name } }));
    else if (pathname === '/api/v1/dashboards/page') data = { items: [], total: 0, limit: 24, offset: 0 };
    else if (pathname.endsWith('/source'))
      data = { builtin_available: true, grain: 'store_week', tables: [], roles: [] };
    else if (pathname.endsWith('/features'))
      data = { template_id: 'retail-overview', title: '零售经营总览', prompt: '从所选数据源生成零售看板', widgets: [] };
    else if (pathname.endsWith('/adapt'))
      data = {
        schema: snapshot.schema,
        snapshot: snapshot.snapshot,
        validation: { records: 10, widgets: snapshot.schema.widgets.length },
      };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(success(data)) });
  });
  return { imageErrors, errors };
}

test('template gallery loads distinct preview images and opens a query preview', async ({ page }, testInfo) => {
  const { imageErrors, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template]')).toHaveCount(32);
  const previews = page.locator('[data-catalog-template] img');
  await expect(previews).toHaveCount(32);
  await expect(page.locator('svg[data-template-layout]')).toHaveCount(0);
  for (const preview of await previews.all()) {
    await preview.scrollIntoViewIfNeeded();
    await expect.poll(() => preview.evaluate(img => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  }
  const imageSources = await previews.evaluateAll(images => images.map(img => img.getAttribute('src')));
  expect(new Set(imageSources).size).toBe(32);
  await expect(page.locator('[data-design-template]')).toHaveCount(7);
  await expect(page.getByText('风格技能 · 连接数据后生成', { exact: true })).toHaveCount(7);
  for (const name of ['learnhub', 'brutal', 'pawspa', 'serenityspa', 'datapulse', 'nexusai']) {
    const design = page.locator(`[data-design-template="${name}-viz-design"]`);
    await expect(design.getByRole('button', { name: /^使用模板 / })).toHaveCount(1);
  }
  await page.getByRole('button', { name: '风格技能', exact: true }).first().click();
  await expect(page.locator('[data-design-template]')).toHaveCount(7);
  await expect(page.locator('[data-catalog-template]')).toHaveCount(0);
  await page.getByRole('button', { name: '全部模板', exact: true }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(32);
  await page
    .locator('[data-design-template]')
    .first()
    .evaluate(el => {
      for (let parent = el.parentElement; parent; parent = parent.parentElement) parent.scrollTop = 0;
    });
  await page.screenshot({ path: testInfo.outputPath('retained-template-gallery.png') });
  const cover = page.locator('[data-catalog-template="retail-overview"]');
  await expect(cover.getByRole('img', { name: '零售经营总览实际生成预览' })).toBeVisible();
  await cover.screenshot({ path: testInfo.outputPath('preview-cover.png') });
  await cover.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('使用哪个数据源生成看板')).toBeVisible();
  await dialog.getByRole('button', { name: 'AI 适配并预览', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '创建看板', exact: true })).toBeVisible();
  await expect(dialog.locator('[data-dashboard-widget-id]')).not.toHaveCount(0);
  await expect(dialog.locator('canvas').first()).toBeVisible();
  await expect
    .poll(() =>
      dialog
        .locator('canvas')
        .first()
        .evaluate(canvas => {
          const bitmap = canvas as HTMLCanvasElement;
          const context = bitmap.getContext('2d');
          if (!context) return 0;
          const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
          let colored = 0;
          for (let i = 0; i < pixels.length; i += 4)
            if (
              pixels[i + 3] > 100 &&
              Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) - Math.min(pixels[i], pixels[i + 1], pixels[i + 2]) > 40
            )
              colored++;
          return colored;
        }),
    )
    .toBeGreaterThan(100);
  expect(imageErrors).toEqual([]);
  expect(errors).toEqual([]);
  let previousFrame = '';
  let stableFrames = 0;
  await expect
    .poll(
      async () => {
        const frame = await dialog
          .locator('canvas')
          .first()
          .evaluate(canvas => (canvas as HTMLCanvasElement).toDataURL());
        stableFrames = frame === previousFrame ? stableFrames + 1 : 0;
        previousFrame = frame;
        return stableFrames;
      },
      { intervals: [100, 150, 250], timeout: 10000 },
    )
    .toBeGreaterThanOrEqual(3);
  await page.screenshot({ path: testInfo.outputPath('query-preview.png') });
  await dialog
    .locator('canvas')
    .first()
    .screenshot({ path: testInfo.outputPath('chart-canvas.png') });
});

test('favorites retain restored styles and still open data templates', async ({ page }) => {
  const { errors } = await fixture(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      'dbgpt.template.favorites.v1',
      JSON.stringify(['design:learnhub-viz-design', 'design:brutal-viz-design', 'retail-overview']),
    );
  });
  await page.goto('/dashboards/?tab=templates');
  await page.getByRole('button', { name: /收藏夹\s*3/ }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(1);
  await expect(page.locator('[data-design-template]')).toHaveCount(2);
  await page.getByRole('button', { name: '预览模板 学习成长', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('img', { name: /学习成长风格示意/ })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
  await expect(page.getByRole('dialog').getByText('使用哪个数据源生成看板')).toBeVisible();
  expect(errors).toEqual([]);
});

test('template preview covers remain visible on a narrow screen', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { imageErrors, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  const previews = page.locator('[data-catalog-template] img');
  await expect(previews).toHaveCount(32);
  await previews.first().scrollIntoViewIfNeeded();
  await expect.poll(() => previews.first().evaluate(img => (img as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const box = await previews.first().boundingBox();
  expect(box?.width).toBeGreaterThan(100);
  expect(box?.width).toBeLessThanOrEqual(390);
  expect(imageErrors).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('mobile-gallery.png') });
});
