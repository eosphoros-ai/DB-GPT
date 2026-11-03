import { expect, test, type Page } from '@playwright/test';

const sessionId = 'history-recovery-session';
const report = {
  revision: 'saved-revision',
  report: { companyName: '恢复测试公司', run: { id: '7fe43ba4-a567-493a-b329-1b8691596252' } },
};

async function mockApi(page: Page, history: unknown[]) {
  const latestRequests: string[] = [];
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    const pathname = url.pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (pathname.endsWith('/model/types')) data = ['qwen-plus'];
    else if (pathname.endsWith('/messages/history')) data = history;
    else if (pathname.endsWith('/financial-analysis/runs/latest')) {
      latestRequests.push(url.searchParams.get('session_id') || '');
      data = report;
    }
    return route.fulfill({ json: { success: true, data } });
  });
  return latestRequests;
}

test('loopback HMR connects and an interrupted task survives another reload', async ({ page }) => {
  const logs: string[] = [];
  page.on('console', message => logs.push(message.text()));
  const latest = await mockApi(page, [
    { role: 'human', context: '为我分析这份年报', order: 1 },
    {
      role: 'view',
      order: 1,
      context: JSON.stringify({
        version: 2,
        protocol_version: 2,
        type: 'react-agent',
        execution_status: 'interrupted',
        final_content: '任务执行已中断，已保存的进度和结果已保留，可继续任务。',
        steps: [
          {
            id: 'step-1',
            title: 'prepare_financial_report',
            status: 'failed',
            outputs: [{ output_type: 'text', content: '财务数据已保存。' }],
          },
        ],
      }),
    },
  ]);
  await page.goto(`/?id=${sessionId}`);
  await expect(page.getByText('为我分析这份年报', { exact: true })).toBeVisible();
  await expect(
    page.getByText('任务执行已中断，已保存的进度和结果已保留，可继续任务。', { exact: true }).first(),
  ).toBeVisible();
  await expect.poll(() => logs.some(message => message.includes('[HMR] connected'))).toBe(true);
  await page.reload();
  await expect(page.getByText('为我分析这份年报', { exact: true })).toBeVisible();
  expect(page.url()).toContain(`id=${sessionId}`);
  expect(latest).toEqual([]);
});

test('an older empty history recovers the saved financial report in the same session', async ({ page }) => {
  const latest = await mockApi(page, []);
  await page.goto(`/?id=${sessionId}`);
  await expect(
    page.getByText('已恢复上次保存的财报分析，可查看结果或继续分析。', { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText('恢复测试公司财报分析.html', { exact: true }).first()).toBeVisible();
  expect(latest).toEqual([sessionId]);
  await page.reload();
  await expect(
    page.getByText('已恢复上次保存的财报分析，可查看结果或继续分析。', { exact: true }).first(),
  ).toBeVisible();
  expect(latest).toEqual([sessionId, sessionId]);
});

test('a running checkpoint restores progress without pretending the step completed', async ({ page }) => {
  await mockApi(page, [
    { role: 'human', context: '检查正在分析的年报', order: 1 },
    {
      role: 'view',
      order: 1,
      context: JSON.stringify({
        version: 2,
        protocol_version: 2,
        type: 'react-agent',
        execution_status: 'running',
        final_content: '',
        steps: [{ id: 'step-1', title: 'prepare_financial_report', status: 'running', outputs: [] }],
      }),
    },
  ]);
  await page.goto(`/?id=${sessionId}`);
  await expect(page.getByText('已恢复任务记录，可查看已保存的执行进度和结果。', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('检查正在分析的年报', { exact: true })).toBeVisible();
  expect(page.url()).toContain(`id=${sessionId}`);
});

test('optional report recovery failure leaves an empty conversation usable', async ({ page }) => {
  await mockApi(page, []);
  await page.route('**/financial-analysis/runs/latest?*', route => route.abort('failed'));
  await page.goto(`/?id=${sessionId}`);
  await expect(page.locator('textarea:visible').first()).toBeEnabled();
  await expect(page.getByText('加载历史对话失败', { exact: true })).toHaveCount(0);
  await page.locator('textarea:visible').first().fill('新的普通问题');
  expect(page.url()).toContain(`id=${sessionId}`);
});
