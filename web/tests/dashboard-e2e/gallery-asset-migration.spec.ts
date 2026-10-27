import { expect, test, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { MODELS_CHANGED_EVENT } from '../../utils/events';

const success = (data: unknown) => ({ success: true, data, err_code: null, err_msg: null });

async function fixture(page: Page) {
  const errors: string[] = [];
  const removedImages: string[] = [];
  const legacyRequests: string[] = [];
  const chatRequests: Record<string, any>[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('__db_gpt_theme_key', 'light');
  });
  page.on('request', request => {
    const pathname = new URL(request.url()).pathname;
    if (/\/dashboard-(?:templates|previews)\/.+\.png/.test(pathname)) removedImages.push(pathname);
    if (pathname.startsWith('/api/v1/dashboard-catalog/')) legacyRequests.push(pathname);
  });
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === '/api/v1/chat/react-agent') {
      chatRequests.push(route.request().postDataJSON());
      await route.fulfill({ contentType: 'text/event-stream', body: 'data: [DONE]\n\n' });
      return;
    }
    let data: unknown = [];
    if (pathname === '/api/v2/serve/datasources')
      data = [{ id: 1, db_name: 'Walmart_Sales', type: 'sqlite', params: { name: 'Walmart_Sales' } }];
    else if (pathname === '/api/v1/model/types') data = ['available-model'];
    else if (pathname === '/api/v1/dashboards/page') data = { items: [], total: 0, limit: 24, offset: 0 };
    await route.fulfill({ json: success(data) });
  });
  return { removedImages, legacyRequests, chatRequests, errors };
}

async function chooseData(page: Page) {
  await page
    .getByRole('button')
    .filter({ has: page.locator('.anticon-database') })
    .last()
    .click();
  await page.locator('.manus-database-menu:visible').getByText('Walmart_Sales', { exact: true }).click();
}

async function expectTemplateDraft(page: Page) {
  await expect(page).toHaveURL(/\/?\?creation_mode=dashboard&template=retail-overview$/, { timeout: 60_000 });
  await expect(page.locator('textarea').first()).toHaveValue(/零售经营总览/);
}

for (const entry of ['card', 'preview'] as const) {
  test(`template ${entry} starts the builder only after data selection and send`, async ({ page }) => {
    const { chatRequests, legacyRequests, errors } = await fixture(page);
    await page.goto('/dashboards/?tab=templates');
    if (entry === 'preview') {
      await page.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
      await page.getByRole('dialog').getByRole('button', { name: '选择数据并创建看板', exact: true }).click();
    } else {
      await page.getByRole('button', { name: '使用模板 零售经营总览', exact: true }).click();
    }
    await expectTemplateDraft(page);
    expect(chatRequests).toEqual([]);
    const composer = page.locator('textarea').first();
    await composer.press('Enter');
    const reminder = page.getByRole('dialog', { name: '请先选择数据库' });
    await expect(reminder).toBeVisible();
    expect(chatRequests).toEqual([]);
    await reminder.getByRole('button', { name: '继续编辑' }).click();
    await chooseData(page);
    const sent = page.waitForRequest('**/api/v1/chat/react-agent');
    await composer.press('Enter');
    expect((await sent).postDataJSON().ext_info).toMatchObject({
      creation_mode: 'dashboard',
      skill_name: 'dashboard-builder',
      dashboard_template: 'catalog:retail-overview',
      database_name: 'Walmart_Sales',
    });
    expect(chatRequests).toHaveLength(1);
    expect(legacyRequests).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('template gallery displays static previews without querying data or old PNG assets', async ({
  page,
}, testInfo) => {
  const { removedImages, legacyRequests, chatRequests, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('img[data-template-preview]')).toHaveCount(6);
  await expect(page.locator('[data-design-template]')).toHaveCount(2);
  await page.getByRole('button', { name: '风格技能', exact: true }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(0);
  await page.getByRole('button', { name: '全部模板', exact: true }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(6);
  await page.screenshot({ path: testInfo.outputPath('retained-template-gallery.png') });
  await page.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const preview = dialog.getByRole('img', { name: '零售经营总览模板示例预览' });
  await expect(preview).toBeVisible();
  await expect.poll(() => preview.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await expect(dialog.getByRole('button', { name: '选择数据并创建看板' })).toBeVisible();
  await dialog.screenshot({ path: testInfo.outputPath('static-preview.png') });
  expect(removedImages).toEqual([]);
  expect(legacyRequests).toEqual([]);
  expect(chatRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test('favorites open the retained styles and data preview', async ({ page }) => {
  const { errors } = await fixture(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      'dbgpt.template.favorites.v1',
      JSON.stringify(['design:serenityspa-viz-design', 'design:brutal-viz-design', 'retail-overview']),
    ),
  );
  await page.goto('/dashboards/?tab=templates');
  await page.getByRole('button', { name: /收藏夹\s*3/ }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(1);
  await expect(page.locator('[data-design-template]')).toHaveCount(2);
  await page.getByRole('button', { name: '预览模板 美业预约管理', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('img', { name: /美业预约管理风格示意/ })).toBeVisible();
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByRole('button', { name: '预览模板 零售经营总览', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: '选择数据并创建看板' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('template covers remain visible on a narrow screen', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { removedImages, errors } = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('img[data-template-preview]')).toHaveCount(6);
  await page.locator('img[data-template-preview]').first().scrollIntoViewIfNeeded();
  const box = await page.locator('img[data-template-preview]').first().boundingBox();
  expect(box?.width).toBeGreaterThan(100);
  expect(box?.width).toBeLessThanOrEqual(390);
  expect(removedImages).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('mobile-gallery.png') });
});

test('every retained data template has a distinct compact cover', async ({ page }) => {
  await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  const covers = page.locator('img[data-template-preview]');
  await expect(covers).toHaveCount(6);
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
  expect(digests.size).toBe(6);
  expect(totalBytes).toBeLessThan(1024 * 1024);
});

test('builder replaces a model removed from the current server', async ({ page }) => {
  await fixture(page);
  await page.addInitScript(() => localStorage.setItem('dbgpt-selected-model', 'removed-model'));
  await page.goto('/?creation_mode=dashboard&template=retail-overview');
  await expectTemplateDraft(page);
  await expect(page.getByText('available-model', { exact: true }).first()).toBeVisible();
  await chooseData(page);
  const sent = page.waitForRequest('**/api/v1/chat/react-agent');
  await page.locator('textarea').first().press('Enter');
  expect((await sent).postDataJSON().model_name).toBe('available-model');
});

for (const refreshing of [false, true]) {
  test(`builder waits for ${refreshing ? 'refreshed' : 'initial'} model discovery before sending`, async ({ page }) => {
    const { chatRequests } = await fixture(page);
    let releaseModels!: () => void;
    const modelsReady = new Promise<void>(resolve => {
      releaseModels = resolve;
    });
    let modelRequests = 0;
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
      await page.goto('/?creation_mode=dashboard&template=retail-overview');
      await expectTemplateDraft(page);
      await chooseData(page);
      if (refreshing) {
        await expect(page.getByText('old-model', { exact: true }).first()).toBeVisible();
        await page.evaluate(event => window.dispatchEvent(new Event(event)), MODELS_CHANGED_EVENT);
      }
      await expect.poll(() => modelRequests).toBe(refreshing ? 2 : 1);
      const composer = page.locator('textarea').first();
      const draft = await composer.inputValue();
      await composer.press('Enter');
      await expect(page.getByText('正在加载可用模型…', { exact: true })).toBeVisible();
      await expect(composer).toHaveValue(draft);
      expect(chatRequests).toEqual([]);
      releaseModels();
      await expect(page.getByText('available-model', { exact: true }).first()).toBeVisible();
      const sent = page.waitForRequest('**/api/v1/chat/react-agent');
      await composer.press('Enter');
      expect((await sent).postDataJSON().model_name).toBe('available-model');
    } finally {
      releaseModels();
    }
  });
}

for (const unavailable of ['empty', 'failed']) {
  test(`builder retains its draft when model discovery is ${unavailable}`, async ({ page }) => {
    const { chatRequests } = await fixture(page);
    await page.route('**/api/v1/model/types', route =>
      route.fulfill({
        json: unavailable === 'empty' ? success([]) : { success: false, err_msg: 'Model discovery unavailable.' },
      }),
    );
    await page.goto('/?creation_mode=dashboard&template=retail-overview');
    await expectTemplateDraft(page);
    await chooseData(page);
    const composer = page.locator('textarea').first();
    const draft = await composer.inputValue();
    await composer.press('Enter');
    await expect(page.getByText('暂无可用模型，请检查模型服务后重试。', { exact: true })).toBeVisible();
    await expect(composer).toHaveValue(draft);
    expect(chatRequests).toEqual([]);
  });
}
