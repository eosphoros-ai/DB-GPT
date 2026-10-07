import { expect, Page, Route, test } from '@playwright/test';
import { readFileSync } from 'fs';
import path from 'path';

type JsonRecord = Record<string, any>;

const loadJson = (relativePath: string): JsonRecord =>
  JSON.parse(readFileSync(path.resolve(process.cwd(), relativePath), 'utf-8'));

const success = (data: unknown) => ({ data, err_code: null, err_msg: null, success: true });

const fulfill = (route: Route, data: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(data) });

const applyPointer = (target: JsonRecord, pointer: string, value: unknown) => {
  const parts = pointer
    .split('/')
    .slice(1)
    .map(part => part.replace(/~1/g, '/').replace(/~0/g, '~'));
  let current = target;
  for (const part of parts.slice(0, -1)) current = current[part] as JsonRecord;
  current[parts.at(-1)!] = value;
};

const installDashboardApi = async (page: Page) => {
  const published = loadJson('../examples/dashboard/snapshots/walmart-sales.public.json');
  let record: JsonRecord = {
    id: published.dashboard_id,
    owner_id: 'e2e-user',
    conversation_id: 'e2e-conversation',
    source_turn_id: 'e2e-source-turn',
    origin: 'manual',
    asset_state: 'saved',
    saved_at: '2026-08-11T00:00:00Z',
    current_revision: 1,
    status: 'draft',
    schema: structuredClone(published.schema),
    created_at: '2026-08-11T00:00:00Z',
    updated_at: '2026-08-11T00:00:00Z',
  };

  await page.route('**/api/**', route => fulfill(route, success([])));
  await page.route('**/api/v1/dashboard-folders', route => fulfill(route, success([])));
  await page.route('**/api/v1/public/dashboards/**', route => {
    const request = route.request();
    if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/filter')) {
      const payload = request.postDataJSON() as JsonRecord;
      return fulfill(
        route,
        success({
          snapshot: { ...published.snapshot, filters: payload.filters },
          unsupported_widget_ids: [],
        }),
      );
    }
    return fulfill(route, success(published));
  });
  await page.route('**/api/v1/dashboards**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname.replace(/\/$/, '');
    const method = request.method();

    if (method === 'GET' && pathname.endsWith('/dashboards/schema')) {
      return fulfill(route, success({}));
    }
    if (method === 'GET' && pathname === '/api/v1/dashboards/page') {
      return fulfill(
        route,
        success({
          items: [
            {
              id: record.id,
              title: record.schema.dashboard.title,
              description: record.schema.dashboard.description,
              data_source_id: record.schema.dashboard.data_source_id,
              current_revision: record.current_revision,
              status: record.status,
              conversation_id: record.conversation_id,
              source_turn_id: record.source_turn_id,
              origin: record.origin,
              asset_state: record.asset_state,
              saved_at: record.saved_at,
              updated_at: record.updated_at,
            },
          ],
          total: 1,
          limit: 24,
          offset: 0,
        }),
      );
    }
    if (method === 'GET' && pathname === '/api/v1/dashboards') {
      return fulfill(
        route,
        success([
          {
            id: record.id,
            title: record.schema.dashboard.title,
            description: record.schema.dashboard.description,
            data_source_id: record.schema.dashboard.data_source_id,
            current_revision: record.current_revision,
            status: record.status,
            conversation_id: record.conversation_id,
            source_turn_id: record.source_turn_id,
            origin: record.origin,
            asset_state: record.asset_state,
            saved_at: record.saved_at,
            updated_at: record.updated_at,
          },
        ]),
      );
    }
    if (method === 'GET' && pathname === `/api/v1/dashboards/${record.id}`) {
      return fulfill(route, success(record));
    }
    if (method === 'GET' && pathname === `/api/v1/dashboards/${record.id}/snapshot`) {
      return fulfill(route, success(published.snapshot));
    }
    if (method === 'PUT' && pathname === `/api/v1/dashboards/${record.id}`) {
      const payload = request.postDataJSON() as JsonRecord;
      if (payload.expected_revision !== record.current_revision) {
        return fulfill(route, { detail: 'revision conflict' }, 409);
      }
      record = {
        ...record,
        current_revision: record.current_revision + 1,
        schema: payload.schema,
        updated_at: '2026-08-11T00:05:00Z',
      };
      return fulfill(route, success(record));
    }
    if (method === 'POST' && pathname === `/api/v1/dashboards/${record.id}/operations`) {
      const payload = request.postDataJSON() as JsonRecord;
      if (payload.expected_revision !== record.current_revision) {
        return fulfill(route, { detail: 'revision conflict' }, 409);
      }
      for (const operation of payload.operations as JsonRecord[]) {
        applyPointer(record.schema, operation.path as string, operation.value);
      }
      const baseRevision = record.current_revision;
      record = {
        ...record,
        current_revision: baseRevision + 1,
        updated_at: '2026-08-11T00:05:00Z',
      };
      return fulfill(
        route,
        success({
          dashboard: record,
          operation: {
            dashboard_id: record.id,
            operation_id: payload.operation_id,
            client_id: payload.client_id,
            actor_id: 'e2e-user',
            base_revision: baseRevision,
            applied_revision: record.current_revision,
            operations: payload.operations,
            created_at: record.updated_at,
          },
          replayed: false,
        }),
      );
    }
    if (method === 'POST' && pathname === `/api/v1/dashboards/${record.id}/collaboration-ticket`) {
      return fulfill(route, { detail: 'WebSocket collaboration is intentionally offline in deterministic E2E.' }, 503);
    }
    if (method === 'POST' && pathname.endsWith('/validate')) {
      return fulfill(route, success({ valid: true, issues: [], widget_status: {} }));
    }
    if (method === 'POST' && pathname.endsWith('/refresh')) {
      return fulfill(route, success(published.snapshot));
    }
    if (method === 'POST' && pathname.includes('/widgets/') && pathname.endsWith('/preview')) {
      const widgetId = pathname.split('/widgets/')[1].split('/')[0];
      return fulfill(route, success(published.snapshot.widgets[widgetId]));
    }
    if (method === 'POST' && pathname.endsWith('/publish')) {
      record = { ...record, status: 'published' };
      published.schema = structuredClone(record.schema);
      published.published_revision = record.current_revision;
      published.published_at = '2026-08-11T00:10:00Z';
      return fulfill(
        route,
        success({
          dashboard_id: record.id,
          published_revision: record.current_revision,
          share_token: 'deterministic-demo-token',
          share_path: '/dashboard-share/deterministic-demo-token',
          published_at: published.published_at,
        }),
      );
    }
    return fulfill(route, { detail: `Unhandled deterministic route: ${method} ${pathname}` }, 501);
  });
  return { record: () => structuredClone(record), published: () => structuredClone(published) };
};

test.describe('Deterministic dashboard browser lifecycle', () => {
  test.skip(!process.env.DASHBOARD_E2E_BASE_URL, 'Start the built web app and set DASHBOARD_E2E_BASE_URL.');

  test('keeps newer edits when a pending save completes, then saves them at the new revision', async ({ page }) => {
    const api = await installDashboardApi(page);
    let release!: () => void;
    const pending = new Promise<void>(resolve => (release = resolve));
    let received!: () => void;
    const submitted = new Promise<void>(resolve => (received = resolve));
    let requests = 0;
    await page.route(`**/api/v1/dashboards/${api.record().id}/operations`, async route => {
      if (++requests === 1) {
        received();
        await pending;
      }
      await route.fallback();
    });
    await page.goto(`/dashboards/${api.record().id}/`);
    const title = page.getByRole('textbox', { name: '看板标题' });
    await title.fill('Submitted title');
    await page.getByRole('button', { name: '保存看板', exact: true }).click();
    await submitted;
    await title.fill('Edited while saving');
    release();
    await expect(page.getByText('修订 2', { exact: true })).toBeVisible();
    await expect(title).toHaveValue('Edited while saving');
    await expect(page.getByText('未保存', { exact: true })).toBeVisible();
    expect(api.record().schema.dashboard.title).toBe('Submitted title');
    await page.getByRole('button', { name: '保存看板', exact: true }).click();
    await expect(page.getByText('修订 3', { exact: true })).toBeVisible();
    expect(api.record().schema.dashboard.title).toBe('Edited while saving');
    await expect(page.getByText('未保存', { exact: true })).toHaveCount(0);
    await page.reload();
    await expect(title).toHaveValue('Edited while saving');
  });

  test('keeps Redo after undoing an edit while a save is pending', async ({ page }) => {
    const api = await installDashboardApi(page);
    let release!: () => void;
    const pending = new Promise<void>(resolve => (release = resolve));
    let received!: () => void;
    const submitted = new Promise<void>(resolve => (received = resolve));
    await page.route(`**/api/v1/dashboards/${api.record().id}/operations`, async route => {
      received();
      await pending;
      await route.fallback();
    });
    await page.goto(`/dashboards/${api.record().id}/`);
    const title = page.getByRole('textbox', { name: '看板标题' });
    await title.fill('Submitted title');
    await page.getByRole('button', { name: '保存看板', exact: true }).click();
    await submitted;
    await title.fill('Work to redo');
    await page.getByRole('button', { name: '撤销', exact: true }).click();
    await expect(title).toHaveValue('Submitted title');
    release();
    await expect(page.getByText('修订 2', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '重做', exact: true }).click();
    await expect(title).toHaveValue('Work to redo');
    await expect(page.getByText('未保存', { exact: true })).toBeVisible();
  });

  test('blocks single-annotation application while manual edits are unsaved', async ({ page }) => {
    const api = await installDashboardApi(page);
    const record = api.record();
    const widget = record.schema.widgets[0];
    const annotation = {
      id: 'persistence-proposal',
      dashboard_id: record.id,
      base_revision: record.current_revision,
      target: { kind: 'widget', widget_id: widget.id, datum_key: {}, row_key: {} },
      prompt: 'Rename this widget',
      status: 'proposed',
      created_at: record.created_at,
      updated_at: record.updated_at,
      proposal: {
        summary: 'Rename this widget',
        before: [widget.title],
        after: ['Agent title'],
        operations: [],
        stable_operations: [],
        validation: { valid: true, issues: [], widget_status: {} },
      },
    };
    let applies = 0;
    await page.route(
      url => url.pathname === `/api/v1/dashboards/${record.id}/annotations`,
      route => fulfill(route, success([annotation])),
    );
    await page.route(`**/api/v1/dashboards/${record.id}/annotations/${annotation.id}/apply`, route => {
      applies++;
      return fulfill(route, { detail: 'Unsaved edits must stop this request.' }, 409);
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/dashboards/${record.id}/`);
    const title = page.getByRole('textbox', { name: '看板标题' });
    await title.fill('Unsaved manual title');
    await page
      .locator(`[data-dashboard-widget-id="${widget.id}"]`)
      .getByRole('button', { name: '批注此组件', exact: true })
      .click();
    await page
      .getByRole('dialog', { name: '看板批注', exact: true })
      .getByRole('button', { name: '应用到草稿' })
      .click();
    await expect(page.getByText('请先保存当前手动修改，再应用 AI 方案', { exact: true })).toBeVisible();
    expect(applies).toBe(0);
    await expect(title).toHaveValue('Unsaved manual title');
    await expect(page.getByText('未保存', { exact: true })).toBeVisible();
    expect(api.record().current_revision).toBe(1);
  });

  test('honors released layout controls and preserves layouts across screen sizes and publication', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1600, height: 1050 });
    const api = await installDashboardApi(page);
    const original = api.record().schema;
    const originalPublication = api.published().schema;
    const pageErrors: string[] = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.setViewportSize({ width: 1600, height: 1050 });
    await page.goto('/dashboards/walmart-sales-demo');
    await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue(original.dashboard.title);
    await expect(page.locator('[data-dashboard-widget-id]')).toHaveCount(original.widgets.length);
    const originalTableStyle = await page
      .locator('[data-dashboard-table-style]')
      .getAttribute('data-dashboard-table-style');
    await page.screenshot({ path: testInfo.outputPath('layout-editor-before.png'), fullPage: true });

    const released = loadJson(
      '../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/schema/dashboard-release-features.json',
    );
    if (!released.layout_templates) {
      await expect(page.getByRole('button', { name: '布局模板', exact: true })).toHaveCount(0);
      await page.setViewportSize({ width: 390, height: 844 });
      await expect(page.locator('[data-dashboard-widget-id]')).toHaveCount(original.widgets.length);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath('released-layout-mobile.png'), fullPage: true });
      expect(api.record().schema.layouts).toEqual(original.layouts);
      expect(pageErrors).toEqual([]);
      return;
    }
    const picker = page.getByRole('dialog', { name: '选择看板布局' });
    await page.getByRole('button', { name: '布局模板', exact: true }).click();
    await picker.getByRole('button', { name: /运营明细/ }).click();
    await expect(
      picker.getByTestId('dashboard-layout-preview').locator('[data-dashboard-table-style]'),
    ).toHaveAttribute('data-dashboard-table-style', 'striped');
    await picker.getByRole('checkbox', { name: '同时应用配套样式' }).uncheck();
    await expect(
      picker.getByTestId('dashboard-layout-preview').locator('[data-dashboard-table-style]'),
    ).toHaveAttribute('data-dashboard-table-style', originalTableStyle!);
    await picker.getByRole('button', { name: /^取\s*消$/ }).click();
    await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeDisabled();
    expect(api.record().schema).toEqual(original);

    for (const [name, id, main] of [
      ['趋势聚焦', 'trend-focus', 'monthly-trend'],
      ['指标概览', 'metric-overview', 'store-ranking'],
      ['运营明细', 'operations-detail', 'sales-detail'],
    ]) {
      await page.getByRole('button', { name: '布局模板', exact: true }).click();
      await picker.getByRole('button', { name: new RegExp(name) }).click();
      await expect(picker.getByRole('button', { name: new RegExp(name) })).toHaveAttribute('aria-pressed', 'true');
      await picker.getByRole('button', { name: '应用模板', exact: true }).click();
      await expect(picker).not.toBeVisible();
      await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
      const primary = page.locator(`[data-dashboard-widget-id="${main}"]`);
      await expect(primary).toBeVisible();
      if (id !== 'metric-overview') {
        const support = page.locator(
          `[data-dashboard-widget-id="${id === 'trend-focus' ? 'store-ranking' : 'monthly-trend'}"]`,
        );
        await expect
          .poll(async () => (await primary.boundingBox())!.width / (await support.boundingBox())!.width)
          .toBeGreaterThan(1.9);
      }
      await page.screenshot({ path: testInfo.outputPath(`layout-${id}-desktop.png`), fullPage: true });
      if (id !== 'operations-detail') {
        await page.getByRole('button', { name: '撤销', exact: true }).click();
        await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeDisabled();
      }
    }
    const saved = page.waitForResponse(
      response => response.request().method() === 'POST' && response.url().includes('/operations') && response.ok(),
    );
    await page.getByRole('button', { name: '保存看板', exact: true }).click();
    await saved;
    expect(api.record().schema.widgets).toEqual(original.widgets);
    expect(api.record().schema.filters).toEqual(original.filters);
    expect(api.published().schema).toEqual(originalPublication);
    expect(
      api.record().schema.layouts.desktop.find((item: JsonRecord) => item.widget_id === 'sales-detail'),
    ).toMatchObject({ x: 0, y: 3, w: 8 });
    await page.reload();
    await expect(page.locator('[data-dashboard-table-style]')).toHaveAttribute('data-dashboard-table-style', 'striped');
    await page.setViewportSize({ width: 390, height: 844 });
    const expectedOrder = ['total-sales', 'sales-detail', 'monthly-trend', 'store-ranking', 'holiday-share'];
    await expect
      .poll(() =>
        page
          .locator('[data-dashboard-widget-id]')
          .evaluateAll(elements => elements.map(element => element.getAttribute('data-dashboard-widget-id'))),
      )
      .toEqual(expectedOrder);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('layout-operations-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1600, height: 1050 });
    await page.getByRole('button', { name: '发布看板', exact: true }).click();
    await page.getByRole('button', { name: '发布固定快照', exact: true }).click();
    await expect(page.locator('a[href*="/dashboard-share/"]').first()).toBeVisible();
    await page.goto('/dashboard-share/deterministic-demo-token');
    await expect(page.locator('[data-dashboard-table-style]')).toHaveAttribute('data-dashboard-table-style', 'striped');
    expect(api.published().schema.layouts).toEqual(api.record().schema.layouts);
    await page.screenshot({ path: testInfo.outputPath('layout-operations-public.png'), fullPage: true });
    expect(pageErrors).toEqual([]);
  });

  test('opens dashboard details from the asset gallery and keeps visual settings separate from SQL settings', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1600, height: 1000 });
    await installDashboardApi(page);

    await page.goto('/dashboards/?tab=all');
    await expect(page.getByRole('heading', { name: '数据看板', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '打开看板 Walmart 门店经营看板', exact: true }).click();
    await expect(page).toHaveURL(/\/dashboards\/walmart-sales-demo/);

    await page.getByRole('button', { name: '编辑可视化设置' }).first().click();
    await expect(page.getByText('可视化设置', { exact: true })).toBeVisible();
    await expect(page.getByRole('combobox', { name: '图表字体' })).toBeVisible();
    await expect(page.getByRole('spinbutton', { name: '图表标题字号' })).toBeVisible();
    await expect(page.getByText('参数化 SQL', { exact: true })).toHaveCount(0);

    await page.getByRole('button', { name: 'SQL 与参数设置' }).first().click();
    await page.getByTestId('query-advanced-settings').locator(':scope > summary').click();
    await expect(page.getByText('SQL 与数据设置', { exact: true }).first()).toBeVisible();
    await page.getByTestId('dashboard-query-editor').scrollIntoViewIfNeeded();
    await expect(page.getByTestId('dashboard-query-sql-input')).toBeVisible();
    await expect(page.getByRole('combobox', { name: '图表字体' })).toHaveCount(0);
    await expect(page.getByRole('spinbutton', { name: '图表标题字号' })).toHaveCount(0);

    const publicationSettings = page.getByTestId('dashboard-publication-binding-settings');
    await publicationSettings.scrollIntoViewIfNeeded();
    await publicationSettings.locator('summary').click();
    await expect(page.getByTestId('dashboard-publication-query-sql-input')).toBeVisible();
    await expect(page.getByText('匿名分享页不会访问数据库', { exact: false })).toBeVisible();
  });

  test('lists, edits, refreshes, reloads, publishes, and opens an anonymous snapshot', async ({
    page,
    context,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await installDashboardApi(page);

    await page.goto('/dashboards/?tab=all');
    await expect(page.getByRole('heading', { name: '数据看板', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '打开看板 Walmart 门店经营看板', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '打开看板 Walmart 门店经营看板', exact: true }).click();

    await expect(page).toHaveURL(/\/dashboards\/walmart-sales-demo/);
    const title = page.getByRole('textbox', { name: '看板标题' });
    await expect(title).toHaveValue('Walmart 门店经营看板');
    await title.fill('Walmart 经营看板（浏览器验收）');
    await expect(page.getByText('未保存', { exact: true })).toBeVisible();
    const saveCompleted = page.waitForResponse(
      response =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname === '/api/v1/dashboards/walmart-sales-demo/operations' &&
        response.ok(),
    );
    await page.getByRole('button', { name: /保存/ }).click();
    await saveCompleted;
    await expect(page.getByText('已保存资产', { exact: true })).toBeVisible();
    await expect(page.getByText('修订 2', { exact: true })).toBeVisible();

    const refreshCompleted = page.waitForResponse(
      response =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname === '/api/v1/dashboards/walmart-sales-demo/refresh' &&
        response.ok(),
    );
    await page.getByRole('button', { name: '刷新看板数据', exact: true }).click();
    await refreshCompleted;
    await expect(page.getByText('月度销售趋势')).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath('walmart-editor.png'),
      fullPage: true,
    });

    await page.reload();
    await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue('Walmart 经营看板（浏览器验收）');
    await page.getByRole('button', { name: '发布看板', exact: true }).click();
    await page.getByRole('button', { name: '发布固定快照', exact: true }).click();
    const shareLink = page.locator('a[href*="/dashboard-share/"]').first();
    await expect(shareLink).toBeVisible();
    const sharePath = await shareLink.getAttribute('href');
    expect(sharePath).toContain('/dashboard-share/deterministic-demo-token');

    const anonymous = await context.browser()!.newContext({ viewport: { width: 1440, height: 900 } });
    const publicPage = await anonymous.newPage();
    await installDashboardApi(publicPage);
    await publicPage.goto(new URL(sharePath!, page.url()).href);
    await expect(publicPage.getByText('发布版本')).toBeVisible();
    await expect(publicPage.getByText(/打开此页面不会连接或查询原始数据库/)).toBeVisible();
    await publicPage.screenshot({
      path: testInfo.outputPath('walmart-public.png'),
      fullPage: true,
    });
    await anonymous.close();
  });

  test('renders the financial case through the same public renderer', async ({ page }, testInfo) => {
    const published = loadJson('../examples/dashboard/snapshots/apple-financial.public.json');
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.route('**/api/**', route => fulfill(route, success([])));
    await page.route('**/api/v1/dashboard-folders', route => fulfill(route, success([])));
    await page.route('**/api/v1/public/dashboards/**', route => {
      const request = route.request();
      if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/filter')) {
        const payload = request.postDataJSON() as JsonRecord;
        return fulfill(
          route,
          success({
            snapshot: { ...published.snapshot, filters: payload.filters },
            unsupported_widget_ids: [],
          }),
        );
      }
      return fulfill(route, success(published));
    });

    await page.goto('/dashboard-share/apple-financial-demo-token');
    await expect(page.getByRole('heading', { name: 'Apple 财务分析看板' })).toBeVisible();
    await expect(page.getByText('年度收入')).toBeVisible();
    const kpi = page.getByText('$391,035M');
    await expect(kpi).toBeVisible();
    const kpiBox = await kpi.boundingBox();
    expect(kpiBox).not.toBeNull();
    expect(kpiBox!.x).toBeGreaterThanOrEqual(0);
    expect(kpiBox!.x + kpiBox!.width).toBeLessThanOrEqual(1440);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(
      0,
    );
    await expect(page.getByText(/打开此页面不会连接或查询原始数据库/)).toBeVisible();
    await page.screenshot({
      path: testInfo.outputPath('apple-financial-public.png'),
      fullPage: true,
    });
  });
});
