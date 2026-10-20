import { expect, test, type Page } from '@playwright/test';

const success = (data: unknown) => ({ success: true, data, err_code: null, err_msg: null });

async function fixture(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('__db_gpt_theme_key', 'light');
  });
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (pathname === '/api/v1/model/types') data = ['fixture-model'];
    else if (pathname === '/api/v2/serve/datasources') {
      data = [{ id: 1, db_name: 'Walmart_Sales', type: 'sqlite', params: { name: 'Walmart_Sales' } }];
    } else if (pathname === '/api/v1/dashboards/page') data = { items: [], total: 0, limit: 12, offset: 0 };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(success(data)) });
  });
  return errors;
}

test('development home renders without an exception', async ({ page }) => {
  const errors = await fixture(page);
  const response = await page.goto('/');
  expect(response?.status()).toBe(200);
  await expect(page.locator('.anticon-global')).toBeVisible();
  await expect(page.locator('textarea').first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('home offers dashboard-builder without editor-only skills and sends the selected skill', async ({
  page,
}, testInfo) => {
  const errors = await fixture(page);
  const editorSkills = ['dashboard-chart-configuration', 'dashboard-filter-configuration', 'dashboard-collaboration'];
  const skills = ['dashboard-builder', ...editorSkills, 'csv-data-analysis', 'learnhub-viz-design'];
  await page.route('**/api/v1/skills/list', route =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(success(skills.map(name => ({ id: name, name, description: name, type: 'official' })))),
    }),
  );
  await page.route('**/api/v1/chat/react-agent', route =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: 'data: [DONE]\n\n',
    }),
  );
  await page.goto('/');
  await page.locator('textarea').first().fill('/');
  const picker = page.locator('.manus-skill-menu:visible');
  await expect(picker.getByText('3 个技能可用', { exact: true })).toBeVisible();
  await picker.getByPlaceholder('搜索技能').fill('dashboard');
  await expect(picker.getByText('dashboard-builder', { exact: true }).first()).toBeVisible();
  for (const name of editorSkills) await expect(picker.getByText(name, { exact: true })).toHaveCount(0);
  await picker.getByPlaceholder('搜索技能').fill('');
  await expect(picker.getByText('csv-data-analysis', { exact: true }).first()).toBeVisible();
  await expect(picker.getByText('learnhub-viz-design', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('home-dashboard-skill-entry.png') });
  await picker.getByText('dashboard-builder', { exact: true }).first().click();
  await expect(page.locator('textarea').first()).toHaveValue('/dashboard-builder ');
  await page.locator('textarea').first().fill('/dashboard-builder 创建销售看板');
  const sent = page.waitForRequest('**/api/v1/chat/react-agent');
  await page.locator('textarea').first().press('Enter');
  expect((await sent).postDataJSON().ext_info).toMatchObject({
    skill_id: 'dashboard-builder',
    skill_name: 'dashboard-builder',
  });
  // The conversation composer shares the same filtered picker as the home screen.
  await page
    .getByRole('button')
    .filter({ has: page.locator('.anticon-thunderbolt') })
    .first()
    .click();
  await expect(picker.getByText('3 个技能可用', { exact: true })).toBeVisible();
  for (const name of editorSkills) await expect(picker.getByText(name, { exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('dashboard language switches in place and keeps the active search', async ({ page }, testInfo) => {
  const errors = await fixture(page);
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template]')).toHaveCount(32);
  await page.getByRole('textbox', { name: '搜索模板' }).fill('零售');
  await page.locator('.anticon-global').click();
  await expect(page.getByRole('textbox', { name: 'Search templates' })).toHaveValue('零售');
  await expect(page.getByRole('button', { name: 'All templates', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Use template Retail overview', exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: 'Search templates' }).fill('retail overview');
  await expect(page.locator('[data-catalog-template="retail-overview"]')).toBeVisible();
  await page.getByRole('textbox', { name: 'Search templates' }).fill('零售');
  // Category values remain stable when their labels change language.
  await page.getByRole('button', { name: 'All', exact: true }).click();
  await expect(page.locator('[data-catalog-template="retail-overview"]')).toBeVisible();
  await page.getByRole('textbox', { name: 'Search templates' }).fill('');
  await page.screenshot({ path: testInfo.outputPath('english-gallery.png'), fullPage: true });
  await page.getByRole('textbox', { name: 'Search templates' }).fill('零售');
  await page.locator('.anticon-global').click();
  await expect(page.getByRole('textbox', { name: '搜索模板' })).toHaveValue('零售');
  await expect(page.getByRole('button', { name: '全部模板', exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('style Use opens creation, retains edits across language changes, and sends only after data selection', async ({
  page,
}) => {
  const errors = await fixture(page);
  let starts = 0;
  await page.route('**/api/v1/chat/react-agent', async route => {
    starts++;
    await route.fulfill({ contentType: 'text/event-stream', body: 'data: [DONE]\n\n' });
  });
  await page.goto('/dashboards/?tab=templates');
  await page
    .locator('[data-design-template="learnhub-viz-design"]')
    .getByRole('button', { name: '使用模板 学习成长' })
    .click();
  await expect(page).toHaveURL(/\/dashboards\/new\/?\?/);
  await expect(page.getByRole('textbox', { name: '分析需求' })).toHaveValue(/学习成长/);
  await expect(page.getByRole('textbox', { name: '分析需求' })).toHaveValue(/learnhub-viz-design.*dashboard-builder/);
  expect(starts).toBe(0);
  await page.getByRole('textbox', { name: '分析需求' }).fill('My edited learning dashboard request');
  await page.locator('.anticon-global').click();
  await expect(page.getByRole('textbox', { name: 'Analysis request' })).toHaveValue(
    'My edited learning dashboard request',
  );
  await page.getByRole('combobox', { name: 'Data source', exact: true }).click();
  await page.getByTitle('Walmart_Sales', { exact: true }).last().click();
  const request = page.waitForRequest('**/api/v1/chat/react-agent');
  await page.getByRole('button', { name: 'Send request', exact: true }).click();
  const body = (await request).postDataJSON();
  expect(body.user_input).toBe('My edited learning dashboard request');
  expect(body.ext_info).toMatchObject({
    creation_mode: 'dashboard',
    database_name: 'Walmart_Sales',
    skill_name: 'learnhub-viz-design',
    locale: 'en',
  });
  expect(starts).toBe(1);
  await expect(page.getByRole('alert').filter({ hasText: 'getReader' })).toHaveCount(0);
  expect(errors).toEqual([]);
});
