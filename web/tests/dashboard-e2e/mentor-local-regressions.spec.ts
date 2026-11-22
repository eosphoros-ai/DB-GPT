import { expect, test, type Page } from '@playwright/test';

const success = (data: unknown) => ({ success: true, data, err_code: null, err_msg: null });

async function chooseData(page: Page) {
  await page
    .getByRole('button')
    .filter({ has: page.locator('.anticon-database') })
    .last()
    .click();
  await page.locator('.manus-database-menu:visible').getByText('Walmart_Sales', { exact: true }).click();
}

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
  const editorSkills = [
    'dashboard-design',
    'dashboard-chart-configuration',
    'dashboard-filter-configuration',
    'dashboard-collaboration',
    'antv-g2-chart',
    'learnhub-viz-design',
    'brutal-viz-design',
    'pawspa-viz-design',
    'serenityspa-viz-design',
    'datapulse-viz-design',
    'nexusai-viz-design',
  ];
  const skills = ['dashboard-builder', ...editorSkills, 'csv-data-analysis', 'business-report'];
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
  await expect(picker.getByText('business-report', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('home-dashboard-skill-entry.png') });
  await picker.getByText('dashboard-builder', { exact: true }).first().click();
  await expect(page.locator('textarea').first()).toHaveValue('/dashboard-builder ');
  await chooseData(page);
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
  await expect(page.locator('[data-catalog-template]')).toHaveCount(6);
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

test('style Use opens home, retains edits across language changes, and sends only after data selection', async ({
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
    .locator('[data-design-template="brutal-viz-design"]')
    .getByRole('button', { name: '使用模板 海报式营销' })
    .click();
  await expect(page).toHaveURL(/\/\?creation_mode=dashboard/);
  expect(new URL(page.url()).searchParams.has('skill_prompt')).toBe(false);
  expect(page.url().length).toBeLessThan(200);
  const composer = page.locator('textarea').first();
  await expect(composer).toHaveValue(/海报式营销/);
  await expect(composer).toHaveValue(/保留所选模板的布局与配色/);
  expect(starts).toBe(0);
  await composer.press('Enter');
  const reminder = page.getByRole('dialog', { name: '请先选择数据库' });
  await expect(reminder).toBeVisible();
  expect(starts).toBe(0);
  await reminder.getByRole('button', { name: '继续编辑' }).click();
  await composer.fill('My edited learning dashboard request');
  await page.locator('.anticon-global').click();
  await expect(composer).toHaveValue('My edited learning dashboard request');
  await chooseData(page);
  const request = page.waitForRequest('**/api/v1/chat/react-agent');
  await composer.press('Enter');
  const body = (await request).postDataJSON();
  expect(body.user_input).toContain('My edited learning dashboard request');
  expect(body.ext_info).toMatchObject({
    creation_mode: 'dashboard',
    database_name: 'Walmart_Sales',
    skill_name: 'dashboard-builder',
    dashboard_template: 'design:brutal-viz-design',
    locale: 'en',
  });
  expect(starts).toBe(1);
  await expect(page.getByRole('alert').filter({ hasText: 'getReader' })).toHaveCount(0);
  expect(errors).toEqual([]);
});

for (const sendVia of ['button', 'Enter'] as const) {
  test(`missing dashboard database opens a reminder via ${sendVia} and keeps the draft`, async ({ page }, testInfo) => {
    const errors = await fixture(page);
    const requests: any[] = [];
    await page.route('**/api/v1/chat/react-agent', async route => {
      requests.push(route.request().postDataJSON());
      await route.fulfill({ contentType: 'text/event-stream', body: 'data: [DONE]\n\n' });
    });
    await page.goto('/?creation_mode=dashboard&template=retail-overview');
    const composer = page.locator('textarea').first();
    await expect(composer).toHaveValue(/零售经营总览/);
    const draft = '按门店分析销售额，保留我的筛选条件';
    await composer.fill(draft);
    const send = async () => {
      if (sendVia === 'Enter') await composer.press('Enter');
      else
        await page
          .getByRole('button')
          .filter({ has: page.locator('.anticon-arrow-up') })
          .click();
    };
    await send();
    const reminder = page.getByRole('dialog', { name: '请先选择数据库' });
    await expect(reminder).toBeVisible();
    await expect(reminder).toContainText('已输入的内容会保留');
    await expect(composer).toHaveValue(draft);
    expect(requests).toEqual([]);
    expect(new URL(page.url()).searchParams.has('id')).toBe(false);
    await page.screenshot({ path: testInfo.outputPath(`database-required-${sendVia}.png`), animations: 'disabled' });
    await reminder.getByRole('button', { name: '继续编辑' }).click();
    await expect(reminder).not.toBeVisible();
    await expect(composer).toHaveValue(draft);
    await send();
    await expect(reminder).toBeVisible();
    await reminder.getByRole('button', { name: '选择数据库' }).click();
    const picker = page.getByRole('dialog', { name: '选择数据库', exact: true });
    await expect(picker).toBeVisible();
    await picker.getByText('Walmart_Sales', { exact: true }).click();
    await expect(picker).not.toBeVisible();
    await expect(composer).toHaveValue(draft);
    expect(requests).toEqual([]);
    const sent = page.waitForRequest('**/api/v1/chat/react-agent');
    await send();
    const payload = (await sent).postDataJSON();
    expect(payload.user_input).toContain(draft);
    expect(payload.ext_info).toMatchObject({
      database_name: 'Walmart_Sales',
      skill_name: 'dashboard-builder',
    });
    expect(requests).toHaveLength(1);
    await expect(reminder).not.toBeVisible();
    expect(errors).toEqual([]);
  });
}

test('English style Use prefills a localized editable request', async ({ page }, testInfo) => {
  const errors = await fixture(page);
  let starts = 0;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/api/v1/chat/react-agent') starts++;
  });
  await page.goto('/dashboards/?tab=templates');
  await page.locator('.anticon-global').click();
  await page
    .locator('[data-design-template="brutal-viz-design"]')
    .getByRole('button', { name: 'Use template Poster-style marketing' })
    .click();
  await expect(page).toHaveURL(/\/\?creation_mode=dashboard/);
  const request = page.locator('textarea').first();
  await expect(request).toHaveValue(/^Use the Poster marketing style/);
  await expect(request).toHaveValue(/keep the selected layout and colors/);
  await expect(request).not.toHaveValue(/[\u4e00-\u9fff]/);
  await expect(request).toBeEditable();
  expect(starts).toBe(0);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('english-style-request.png') });
  await request.press('Enter');
  const reminder = page.getByRole('dialog', { name: 'Select a database first' });
  await expect(reminder).toBeVisible();
  await expect(reminder.getByRole('button', { name: 'Select Database' })).toBeVisible();
  await expect(reminder).not.toContainText(/[\u4e00-\u9fff]/);
  expect(starts).toBe(0);
});

test('new dashboard example keeps the original cards and sends only its bound data and builder', async ({ page }) => {
  const errors = await fixture(page);
  await page.route('**/api/v2/serve/datasources', route =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(success([{ id: 2, db_name: 'Olist_Ecommerce', type: 'sqlite' }])),
    }),
  );
  const preparations: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/v1/examples/prepare')) preparations.push(request.url());
  });
  await page.route('**/api/v1/chat/react-agent', route =>
    route.fulfill({ contentType: 'text/event-stream', body: 'data: [DONE]\n\n' }),
  );
  await page.goto('/?creation_mode=dashboard&skill=brutal-viz-design');
  const titles = [
    'Olist 巴西电商经营诊断',
    '沃尔玛销售数据分析',
    '数据库画像与分析报告',
    '金融财报深度分析',
    '创建SQL分析技能',
    '电商经营分析看板',
  ];
  await expect(page.locator('button h3')).toHaveText(titles);
  const request = page.waitForRequest('**/api/v1/chat/react-agent');
  await page.getByRole('button', { name: /电商经营分析看板/ }).click();
  const body = (await request).postDataJSON();
  expect(body.ext_info).toMatchObject({
    database_name: 'Olist_Ecommerce',
    skill_name: 'dashboard-builder',
    creation_mode: 'dashboard',
  });
  expect(body.ext_info.dashboard_template).toBeUndefined();
  expect(body.ext_info.knowledge_space_name).toBeUndefined();
  expect(body.user_input).toContain('共 3 个图表');
  expect(preparations).toEqual([]);
  expect(errors).toEqual([]);
});

test('dashboard example without its data does not start a model request', async ({ page }) => {
  await fixture(page);
  let starts = 0;
  page.on('request', request => {
    if (request.url().includes('/api/v1/chat/react-agent')) starts++;
  });
  await page.goto('/');
  await page.getByRole('button', { name: /电商经营分析看板/ }).click();
  await expect(page.getByText('示例依赖的数据源“Olist_Ecommerce”尚未创建或不可访问')).toBeVisible();
  expect(starts).toBe(0);
});

test('catalog preview and Use share the home entry without starting adaptation', async ({ page }, testInfo) => {
  const errors = await fixture(page);
  let started = 0;
  page.on('request', request => {
    if (/\/adapt$|\/chat\/react-agent$/.test(new URL(request.url()).pathname)) started++;
  });
  await page.goto('/dashboards/?tab=templates');
  await page.getByRole('button', { name: '预览模板 门店营销沙盘', exact: true }).click();
  const preview = page.getByRole('dialog');
  await expect(preview.getByRole('img', { name: '门店营销沙盘模板示例预览' })).toBeVisible();
  await preview.getByRole('button', { name: '选择数据并创建看板' }).click();
  await expect(page.locator('textarea').first()).toHaveValue(/营销/);
  expect(new URL(page.url()).pathname).toBe('/');
  expect(started).toBe(0);
  await page.screenshot({ path: testInfo.outputPath('catalog-home-draft.png') });
  expect(errors).toEqual([]);
});

test('retained gallery offers exactly eight templates with working preview and creation entries', async ({
  page,
}, testInfo) => {
  const errors = await fixture(page);
  await page.setViewportSize({ width: 1450, height: 1050 });
  const entries = [
    { id: 'brutal-viz-design', kind: 'design', title: '海报式营销' },
    { id: 'serenityspa-viz-design', kind: 'design', title: '美业预约管理' },
    { id: 'voice-observatory', kind: 'catalog', title: 'AI 语音趋势实验室' },
    { id: 'store-marketing', kind: 'catalog', title: '门店营销沙盘' },
    { id: 'national-command', kind: 'catalog', title: '全国经营指挥大屏' },
    { id: 'brand-revenue', kind: 'catalog', title: '品牌营收驾驶舱' },
    { id: 'northwind-revenue', kind: 'catalog', title: '品类收入与市场' },
    { id: 'retail-overview', kind: 'catalog', title: '零售经营总览' },
  ];
  let starts = 0;
  page.on('request', request => {
    if (/\/adapt$|\/chat\/react-agent$/.test(new URL(request.url()).pathname)) starts++;
  });
  for (const entry of entries) {
    await page.goto('/dashboards/?tab=templates');
    const cards = page.locator('[data-catalog-template], [data-design-template]');
    await expect(cards).toHaveCount(8);
    expect(
      await cards.evaluateAll(items =>
        items.map(item => item.getAttribute('data-catalog-template') || item.getAttribute('data-design-template')),
      ),
    ).toEqual(entries.map(item => item.id));
    await page.getByRole('button', { name: `预览模板 ${entry.title}`, exact: true }).click();
    const preview = page.getByRole('dialog');
    await expect(preview).toBeVisible();
    await expect(preview).toContainText(entry.title);
    if (entry.kind === 'catalog') {
      const cover = preview.getByRole('img', { name: `${entry.title}模板示例预览` });
      await expect(cover).toBeVisible();
      await expect.poll(() => cover.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    }
    await preview.getByRole('button', { name: '选择数据并创建看板' }).click();
    await expect(page).toHaveURL(
      url => url.pathname === '/' && url.searchParams.get(entry.kind === 'design' ? 'skill' : 'template') === entry.id,
      { timeout: 60_000 },
    );
    await expect(page.locator('textarea').first()).not.toHaveValue('');
    expect(new URL(page.url()).searchParams.get(entry.kind === 'design' ? 'skill' : 'template')).toBe(entry.id);
    expect(starts).toBe(0);
  }
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template]')).toHaveCount(6);
  await expect(page.locator('[data-design-template]')).toHaveCount(2);
  await page.screenshot({
    path: testInfo.outputPath('eight-retained-templates.png'),
    fullPage: true,
    animations: 'disabled',
  });
  expect(errors).toEqual([]);
});

test('retained gallery excludes removed entries from search, categories and favorite counts', async ({ page }) => {
  const errors = await fixture(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      'dbgpt.template.favorites.v1',
      JSON.stringify(['design:learnhub-viz-design', 'store-coverage', 'design:brutal-viz-design', 'retail-overview']),
    );
  });
  await page.goto('/dashboards/?tab=templates');
  await expect(page.locator('[data-catalog-template], [data-design-template]')).toHaveCount(8);
  await expect(page.getByRole('button', { name: /收藏夹\s*2/ })).toBeVisible();
  await expect(page.getByRole('button', { name: '教育', exact: true })).toHaveCount(0);
  await page.getByRole('textbox', { name: '搜索模板' }).fill('学习成长');
  await expect(page.locator('[data-catalog-template], [data-design-template]')).toHaveCount(0);
  await page.getByRole('textbox', { name: '搜索模板' }).fill('');
  await page.getByRole('button', { name: /收藏夹\s*2/ }).click();
  await expect(page.locator('[data-catalog-template]')).toHaveCount(1);
  await expect(page.locator('[data-design-template]')).toHaveCount(1);
  await expect(page.locator('[data-design-template="brutal-viz-design"]')).toBeVisible();
  await page.getByRole('button', { name: '风格技能', exact: true }).click();
  await expect(page.locator('[data-design-template]')).toHaveCount(2);
  await expect(page.locator('[data-catalog-template]')).toHaveCount(0);
  expect(errors).toEqual([]);
});

const pendingPlan = {
  type: 'dashboard.plan.awaiting_confirmation',
  dashboard_id: 'plan-home',
  title: '销售计划',
  data_source_id: 'Walmart_Sales',
  source_turn_id: 'turn-home',
  current_revision: 1,
  confirmation_prompt: '[[confirm-dashboard:plan-home]]',
  revision_prompt: '[[revise-dashboard-plan:plan-home]]',
  plan: { metrics: ['销售额'], widgets: [{ id: 'trend', title: '销售趋势', type: 'line' }] },
};
const stream = (...events: unknown[]) => events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('');

test('home renders plan actions, confirms once, and opens the created dashboard', async ({ page }, testInfo) => {
  const errors = await fixture(page);
  await page.route('**/api/v1/dashboards/plan-home', route =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: false, err_msg: 'Fixture dashboard' }),
    }),
  );
  const requests: any[] = [];
  await page.route('**/api/v1/chat/react-agent', async route => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      contentType: 'text/event-stream',
      body:
        requests.length === 1
          ? stream(
              pendingPlan,
              { type: 'final', content: '确认生成：[[confirm-dashboard:plan-home]]' },
              { type: 'done' },
            )
          : stream(
              { type: 'dashboard.generation.started', dashboard_id: 'plan-home', generation_id: 'run-home' },
              {
                type: 'dashboard.created',
                dashboard_id: 'plan-home',
                title: '销售看板',
                total_widgets: 1,
                validated_widgets: 1,
              },
              { type: 'done' },
            ),
    });
  });
  await page.goto('/?creation_mode=dashboard&template=retail-overview');
  await chooseData(page);
  await page.locator('textarea').first().press('Enter');
  await expect(page.getByRole('button', { name: '确认并生成 SQL' })).toBeEnabled();
  await expect(page.getByText('[[confirm-dashboard:plan-home]]', { exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('home-plan-confirmation.png') });
  await page.getByRole('button', { name: '确认并生成 SQL' }).click();
  await expect(page.getByRole('button', { name: '查看看板', exact: true })).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[1].user_input).toContain(pendingPlan.confirmation_prompt);
  expect(requests[0].ext_info.dashboard_template).toBe('catalog:retail-overview');
  expect(requests[1].conv_uid).toBe(requests[0].conv_uid);
  await expect(page.getByRole('button', { name: '确认并生成 SQL' })).toHaveCount(0);
  await page.getByRole('button', { name: '查看看板', exact: true }).click();
  await expect(page).toHaveURL(/\/dashboards\/plan-home\/?\?view=preview$/, { timeout: 60_000 });
  expect(errors).toEqual([]);
});

test('history restores actionable dashboard plans instead of raw markers', async ({ page }) => {
  await fixture(page);
  await page.route('**/api/v1/chat/dialogue/messages/history?*', route =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(
        success([
          { role: 'human', context: '创建销售看板' },
          {
            role: 'view',
            context: JSON.stringify({
              version: 1,
              type: 'react-agent',
              final: '请确认计划',
              dashboard_refs: [{ ...pendingPlan, status: 'awaiting_confirmation' }],
            }),
          },
        ]),
      ),
    }),
  );
  await page.goto('/?id=previous-home');
  await expect(page.getByRole('button', { name: '确认并生成 SQL' })).toBeEnabled();
  await page.getByRole('button', { name: '修改计划', exact: true }).click();
  await expect(page.locator('textarea').first()).toHaveValue(`${pendingPlan.revision_prompt} `);
});

for (const end of ['error', 'disconnect']) {
  test(`home clears dashboard progress after ${end}`, async ({ page }) => {
    await fixture(page);
    await page.route('**/api/v1/chat/react-agent', route =>
      route.fulfill({
        contentType: 'text/event-stream',
        body: stream(
          { type: 'dashboard.generation.started', dashboard_id: 'broken', title: '销售看板' },
          ...(end === 'error' ? [{ type: 'error', message: '模型服务暂时不可用' }] : []),
        ),
      }),
    );
    await page.goto('/?creation_mode=dashboard&template=retail-overview');
    await chooseData(page);
    await page.locator('textarea').first().press('Enter');
    await expect(page.getByText('生成已中断，已完成的计划或草稿仍保留，请重试。')).toBeVisible();
    if (end === 'error') await expect(page.getByText('模型服务暂时不可用').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '查看看板', exact: true })).toHaveCount(0);
  });
}
