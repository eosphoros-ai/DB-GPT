import { expect, test, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { MODELS_CHANGED_EVENT } from '../../utils/events';

const sources = ['Walmart_Sales', 'sqlite_energy', 'sqlite_itsm', 'sqlite_maintenance', 'sqlite_students'];
const snapshot = JSON.parse(
  readFileSync(path.resolve(process.cwd(), '../examples/dashboard/snapshots/walmart-sales.public.json'), 'utf8'),
);
const success = (data: unknown) => ({ success: true, data, err_code: null, err_msg: null });

async function fixture(page: Page, model?: string | null) {
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
    else if (pathname === '/api/v1/model/types') data = ['available-model'];
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
        adaptation: model === undefined ? undefined : { model, changes: [] },
      };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(success(data)) });
  });
  return { removedImages, errors };
}

for (const model of [null, 'test-model', undefined]) {
  test(`template creation preserves ${model === null ? 'preset' : model ? 'AI' : 'legacy AI'} preview routing`, async ({
    page,
  }) => {
    await fixture(page, model);
    await page.route('**/api/v1/dashboard-catalog/retail-overview/generate', route =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ success: false, err_msg: 'Creation request captured before persistence.' }),
      }),
    );
    await page.goto('/dashboards/?tab=templates');
    await page.getByRole('button', { name: '使用模板 零售经营总览', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'AI 适配并预览', exact: true }).click();
    const request = page.waitForRequest('**/api/v1/dashboard-catalog/retail-overview/generate');
    await dialog.getByRole('button', { name: '创建看板', exact: true }).click();
    const body = (await request).postDataJSON();
    expect(body.data_source_id).toBe('Walmart_Sales');
    if (model === null) expect(body).not.toHaveProperty('schema');
    else expect(body.schema).toEqual(snapshot.schema);
  });
}

test('template gallery renders fixed previews and opens a query preview without old PNG assets', async ({
  page,
}, testInfo) => {
  const { removedImages, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template]')).toHaveCount(32);
  await expect(page.locator('img[data-template-preview]')).toHaveCount(32);
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
  await page.screenshot({ path: testInfo.outputPath('retained-template-gallery.png') });
  const cover = page.locator('[data-catalog-template="retail-overview"]');
  await expect(cover.getByRole('img', { name: /模板示例预览/ })).toBeVisible();
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

test('template covers remain visible on a narrow screen', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { removedImages, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('img[data-template-preview]')).toHaveCount(32);
  await page.locator('img[data-template-preview]').first().scrollIntoViewIfNeeded();
  const box = await page.locator('img[data-template-preview]').first().boundingBox();
  expect(box?.width).toBeGreaterThan(100);
  expect(box?.width).toBeLessThanOrEqual(390);
  expect(removedImages).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('mobile-gallery.png') });
});

test('every template has a different compact cover that loads in the gallery', async ({ page }) => {
  await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  const covers = page.locator('img[data-template-preview]');
  await expect(covers).toHaveCount(32);
  const digests = new Set<string>();
  let totalBytes = 0;
  for (const cover of await covers.all()) {
    await cover.scrollIntoViewIfNeeded();
    await expect.poll(() => cover.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBe(800);
    const id = await cover.getAttribute('data-template-preview');
    const bytes = readFileSync(path.resolve(process.cwd(), `public/dashboard-templates/covers/${id}.webp`));
    digests.add(createHash('sha256').update(bytes).digest('hex'));
    totalBytes += bytes.length;
  }
  expect(digests.size).toBe(32);
  expect(totalBytes).toBeLessThan(1024 * 1024);
});

test('template adaptation does not send a model removed from the current server', async ({ page }) => {
  await fixture(page);
  await page.addInitScript(() => localStorage.setItem('dbgpt-selected-model', 'removed-model'));
  const models = page.waitForResponse('**/api/v1/model/types');
  await page.goto('/dashboards/?tab=templates');
  await models;
  await page.getByRole('button', { name: '使用模板 零售经营总览', exact: true }).click();
  const request = page.waitForRequest('**/api/v1/dashboard-catalog/retail-overview/adapt');
  await page.getByRole('dialog').getByRole('button', { name: 'AI 适配并预览', exact: true }).click();
  expect((await request).postDataJSON().model).toBe('available-model');
  await expect(page.getByRole('dialog').getByRole('button', { name: '创建看板', exact: true })).toBeVisible();
});

for (const refreshing of [false, true]) {
  test(`template AI preview waits for ${refreshing ? 'refreshed' : 'initial'} model discovery`, async ({
    page,
  }, testInfo) => {
    await fixture(page);
    await page.addInitScript(() => localStorage.setItem('dbgpt-selected-model', 'removed-model'));
    let releaseModels!: () => void;
    const modelsReady = new Promise<void>(resolve => {
      releaseModels = resolve;
    });
    let modelRequests = 0;
    const adaptationRequests: string[] = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.endsWith('/adapt')) adaptationRequests.push(request.url());
    });
    await page.route('**/api/v1/model/types', async route => {
      modelRequests++;
      if (refreshing && modelRequests === 1) {
        await route.fulfill({ json: success(['old-model']) });
        return;
      }
      await modelsReady;
      await route.fulfill({ json: success(['available-model']) });
    });
    try {
      await page.goto('/dashboards/?tab=templates');
      await page.getByRole('button', { name: '使用模板 零售经营总览', exact: true }).click();
      const dialog = page.getByRole('dialog');
      const previewButton = dialog.getByRole('button', { name: 'AI 适配并预览', exact: true });
      await expect(dialog.getByTestId('template-ai-assistant')).toBeVisible();
      if (refreshing) {
        await expect(previewButton).toBeEnabled();
        await page.evaluate(event => window.dispatchEvent(new Event(event)), MODELS_CHANGED_EVENT);
      }
      await expect.poll(() => modelRequests).toBe(refreshing ? 2 : 1);
      await expect(previewButton).toBeDisabled();
      await expect(dialog.getByText('正在加载可用模型…', { exact: true })).toBeVisible();
      await dialog.getByRole('radio', { name: /使用预设匹配/ }).check();
      await expect(dialog.getByRole('button', { name: '验证并预览', exact: true })).toBeEnabled();
      await dialog.getByRole('radio', { name: /AI 智能适配/ }).check();
      await expect(previewButton).toBeDisabled();
      expect(adaptationRequests).toEqual([]);
      await dialog.screenshot({ path: testInfo.outputPath('waiting-for-models.png') });
      releaseModels();
      await expect(previewButton).toBeEnabled();
      const request = page.waitForRequest('**/api/v1/dashboard-catalog/retail-overview/adapt');
      await previewButton.click();
      expect((await request).postDataJSON().model).toBe('available-model');
      await expect(dialog.getByRole('button', { name: '创建看板', exact: true })).toBeVisible();
    } finally {
      releaseModels();
    }
  });
}

for (const unavailable of ['empty', 'failed']) {
  test(`template AI preview stays disabled when model discovery is ${unavailable}`, async ({ page }, testInfo) => {
    await fixture(page);
    await page.route('**/api/v1/model/types', route =>
      route.fulfill({
        json: unavailable === 'empty' ? success([]) : { success: false, err_msg: 'Model discovery unavailable.' },
      }),
    );
    await page.goto('/dashboards/?tab=templates');
    await page.getByRole('button', { name: '使用模板 零售经营总览', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('button', { name: 'AI 适配并预览', exact: true })).toBeDisabled();
    await expect(dialog.getByText('暂无可用模型，请检查模型服务后重试。', { exact: true })).toBeVisible();
    await dialog.screenshot({ path: testInfo.outputPath('no-available-models.png') });
    await dialog.getByRole('radio', { name: /使用预设匹配/ }).check();
    await expect(dialog.getByRole('button', { name: '验证并预览', exact: true })).toBeEnabled();
  });
}
