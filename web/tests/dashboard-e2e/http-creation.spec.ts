import { expect, test, type Page } from '@playwright/test';
import { readDashboardFixture } from './fixtures';

async function serveInsecureOrigin(page: Page, baseURL?: string) {
  const server = new URL(baseURL || 'http://127.0.0.1:5670');
  const insecureOrigin = `http://dashboard-http.test:${server.port || '80'}`;
  // Serve the actual application under an insecure origin without depending
  // on machine DNS or proxy settings. API calls still use the fixtures below.
  await page.route(`${insecureOrigin}/**`, async route => {
    const target = new URL(route.request().url());
    if (target.pathname.startsWith('/api/')) return route.fallback();
    target.protocol = server.protocol;
    target.host = server.host;
    await route.fulfill({ response: await route.fetch({ url: target.href }) });
  });
  return insecureOrigin;
}

test('plain HTTP can send the first Dashboard request and continue the conversation', async ({ page, baseURL }) => {
  const requests: Record<string, any>[] = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.includes('/chat/react-agent')) {
      requests.push(route.request().postDataJSON());
      await route.fulfill({
        contentType: 'text/event-stream',
        body: 'data: {"type":"final","content":"已收到分析需求"}\n\ndata: {"type":"done"}\n\n',
      });
      return;
    }
    let data: unknown = [];
    if (pathname.includes('/model/types')) data = ['fixture-model'];
    if (pathname.includes('/datasources'))
      data = [{ db_name: 'http-fixture', type: 'sqlite', params: { name: 'http-fixture' } }];
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data }) });
  });
  const insecureOrigin = await serveInsecureOrigin(page, baseURL);
  await page.goto(`${insecureOrigin}/dashboards/new/`);
  expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe('undefined');
  await page.getByRole('combobox', { name: '数据源', exact: true }).click();
  await page.getByText('http-fixture', { exact: true }).last().click();
  await page.getByRole('textbox', { name: '分析需求', exact: true }).fill('分析销售趋势');
  const send = page.getByRole('button', { name: '发送需求', exact: true });
  await send.click();
  await expect.poll(() => requests.length).toBe(1);
  await expect(send).toBeEnabled();
  await send.click();
  await expect.poll(() => requests.length).toBe(2);
  const conversation = requests[0].conv_uid;
  expect(conversation).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(requests[1].conv_uid).toBe(conversation);
  expect(errors).toEqual([]);
});

test('plain HTTP applies a batch of AI annotation proposals', async ({ page, baseURL }) => {
  const record = readDashboardFixture('walmart/record.json');
  const snapshot = readDashboardFixture('walmart/snapshot.json');
  const annotations: Record<string, any>[] = [];
  const batches: Record<string, any>[] = [];
  const errors: string[] = [];
  const revision = record.current_revision;
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('dbgpt-selected-model', 'fixture-model');
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (pathname.endsWith('/model/types')) data = ['fixture-model'];
    else if (pathname.endsWith('/annotation-intents')) {
      data = {
        items: request.postDataJSON().items.map((item: any) => ({
          draft_id: item.draft_id,
          tasks: [{ intent: 'modify', prompt: item.prompt }],
        })),
      };
    } else if (pathname.endsWith('/annotations') && request.method() === 'POST') {
      data = {
        ...request.postDataJSON(),
        id: `http-annotation-${annotations.length + 1}`,
        dashboard_id: record.id,
        status: 'pending',
        created_at: record.created_at,
        updated_at: record.updated_at,
      };
      annotations.push(data as Record<string, any>);
    } else if (pathname.endsWith('/annotations')) data = annotations;
    else if (/\/annotations\/[^/]+\/generate$/.test(pathname)) {
      const annotation = annotations.find(item => item.id === pathname.split('/').at(-2))!;
      annotation.status = 'proposed';
      annotation.proposal = {
        summary: annotation.prompt,
        stable_operations: [
          { op: 'replace', path: `/widgets/by-id/${annotation.target.widget_id}/title`, value: 'HTTP 批量修改' },
        ],
        operations: [],
      };
      data = annotation;
    } else if (pathname.endsWith('/annotations/apply-batch')) {
      batches.push(request.postDataJSON());
      record.current_revision++;
      annotations.forEach(item => (item.status = 'applied'));
      data = { annotations, operation: { dashboard: record } };
    } else if (pathname.endsWith('/snapshot') || pathname.endsWith('/refresh')) data = snapshot;
    else if (pathname.endsWith('/' + record.id)) data = record;
    await route.fulfill({ json: { success: true, data } });
  });
  const insecureOrigin = await serveInsecureOrigin(page, baseURL);
  await page.goto(`${insecureOrigin}/dashboards/${record.id}/`);
  expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe('undefined');
  const widgets = page.locator('[data-dashboard-widget-id]');
  await expect(widgets.first()).toBeVisible();
  for (const index of [0, 1]) {
    await widgets.nth(index).getByRole('button', { name: '批注此组件', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(`将标题改为 HTTP 指标 ${index + 1}`);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  await page.getByRole('button', { name: '本次批注 2 条', exact: true }).click();
  await page
    .getByTestId('annotation-tray')
    .getByRole('button', { name: /一起发送给 AI/ })
    .click();
  const panel = page.getByTestId('dashboard-assistant-panel');
  await panel.getByText('2 项修改待确认', { exact: true }).click();
  await panel.getByRole('button', { name: '应用本批修改', exact: true }).click();
  await expect(panel.getByText('已一起应用 2 项修改。可以继续批注或讨论。')).toBeVisible();
  expect(batches).toHaveLength(1);
  expect(batches[0]).toMatchObject({
    annotation_ids: ['http-annotation-1', 'http-annotation-2'],
    expected_revision: revision,
    client_id: `dashboard-editor-${record.id}`,
  });
  expect(batches[0].operation_id).toMatch(/^annotation-batch-[a-z0-9]+-[a-z0-9]+$/);
  expect(record.current_revision).toBe(revision + 1);
  expect(errors).toEqual([]);
});
