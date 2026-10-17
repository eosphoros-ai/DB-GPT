import { expect, test } from '@playwright/test';

test.use({
  launchOptions: {
    args: ['--host-resolver-rules=MAP dashboard-http.test 127.0.0.1', '--no-proxy-server'],
  },
});

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
  const address = new URL(baseURL || 'http://127.0.0.1:5670');
  address.hostname = 'dashboard-http.test';
  await page.goto(`${address.origin}/dashboards/new/`);
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
