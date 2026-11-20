const { test, expect } = require('@playwright/test');

test('workspace uploads and creates a run when randomUUID is unavailable on HTTP', async ({ page }) => {
  const base = process.env.FINANCIAL_HTTP_LAN_BASE_URL || process.env.FINANCIAL_LIVE_BASE_URL || 'http://127.0.0.1:5688';
  const requests = [];
  let run;
  if (!process.env.FINANCIAL_HTTP_LAN_BASE_URL) {
    await page.addInitScript(() => Object.defineProperty(Crypto.prototype, 'randomUUID', { value: undefined }));
  }
  await page.route('**/api/**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace(/\/$/, '');
    let data = [];
    if (pathname.endsWith('/model/types')) data = ['synthetic-model'];
    else if (pathname.endsWith('/agent/files') && request.method() === 'POST') {
      data = [{ file_id: 'test-pdf', name: 'synthetic.pdf', status: 'ready' }];
    } else if (pathname.endsWith('/financial-analysis/runs') && request.method() === 'POST') {
      const input = request.postDataJSON();
      requests.push(input);
      run = { id: '12345678-1234-4234-8234-123456789012', session_id: input.session_id,
        file_id: 'test-pdf', status: 'pending', stage: 'queued', error: null };
      data = run;
    } else if (pathname.endsWith('/financial-analysis/runs')) {
      data = { items: [], total: 0, page: 1, page_size: 20 };
    } else if (pathname.includes('/financial-analysis/runs/')) data = run;
    return route.fulfill({ json: { success: true, data } });
  });
  await page.goto(`${base}/financial-analysis`);
  expect(await page.evaluate(() => typeof crypto.randomUUID)).toBe('undefined');
  if (process.env.FINANCIAL_HTTP_LAN_BASE_URL) {
    expect(await page.evaluate(() => window.isSecureContext)).toBe(false);
  }
  await page.locator('input[type=file]').setInputFiles({
    name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.7 synthetic input'),
  });
  await page.getByRole('button', { name: '开始分析', exact: true }).click();
  await expect.poll(() => requests.length).toBe(1);
  const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
  expect(requests[0].request_id).toMatch(uuid);
  expect(requests[0].session_id.replace(/^financial-/, '')).toMatch(uuid);
  expect(requests[0].file_ids).toEqual(['test-pdf']);
  await expect(page).toHaveURL(/run_id=12345678/);
});
