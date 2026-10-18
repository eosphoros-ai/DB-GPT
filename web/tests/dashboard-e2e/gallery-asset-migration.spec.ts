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
  const removedImages: string[] = [];
  page.on('request', request => {
    if (/\/dashboard-(?:templates|previews)\/.+\.png/.test(new URL(request.url()).pathname))
      removedImages.push(request.url());
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
  return { removedImages, errors };
}

test('template gallery renders all retained layouts and opens a query preview without screenshot assets', async ({
  page,
}, testInfo) => {
  const { removedImages, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template]')).toHaveCount(32);
  await expect(page.locator('svg[data-template-layout]')).toHaveCount(32);
  await expect(page.locator('[data-design-template]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '风格技能', exact: true })).toHaveCount(0);
  await expect(page.getByText('风格技能 · 连接数据后生成', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('retained-template-gallery.png') });
  const cover = page.locator('[data-catalog-template="retail-overview"]');
  await expect(cover.getByRole('img', { name: /布局示意/ })).toBeVisible();
  await cover.screenshot({ path: testInfo.outputPath('layout-cover.png') });
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
  expect(removedImages).toEqual([]);
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

test('favorites ignore retired styles and still open retained templates', async ({ page }) => {
  const { errors } = await fixture(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      'dbgpt.template.favorites.v1',
      JSON.stringify(['design:learnhub-viz-design', 'design:brutal-viz-design', 'retail-overview']),
    );
  });
  await page.goto('/dashboards/?tab=templates');
  await page.getByRole('button', { name: /收藏夹\s*1/ }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(1);
  await expect(page.locator('[data-design-template]')).toHaveCount(0);
  await page.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
  await expect(page.getByRole('dialog').getByText('使用哪个数据源生成看板')).toBeVisible();
  expect(errors).toEqual([]);
});

test('template layout covers remain visible on a narrow screen', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { removedImages, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('svg[data-template-layout]')).toHaveCount(32);
  await page.locator('svg[data-template-layout]').first().scrollIntoViewIfNeeded();
  const box = await page.locator('svg[data-template-layout]').first().boundingBox();
  expect(box?.width).toBeGreaterThan(100);
  expect(box?.width).toBeLessThanOrEqual(390);
  expect(removedImages).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('mobile-gallery.png') });
});
