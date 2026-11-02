const { test, expect } = require('@playwright/test');
const { syntheticComparison } = require('../../new-components/financial-analysis/comparison/synthetic-fixture');

const baseURL = process.env.FINANCIAL_LIVE_BASE_URL || 'http://127.0.0.1:3000';
const report = syntheticComparison();
report.lifecycle.publicationStatus = 'published';
report.analysis = {
  status: 'completed',
  modelName: 'synthetic',
  startedAt: '',
  completedAt: '2026-10-25',
  rejectedCount: 0,
};
const title = '合成报告实时交付测试';
const stages = ['读取财报', '分析财务数据', '核对结论', '生成报告'];

async function setup(page, history = []) {
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('dbgpt-selected-model', 'synthetic-model');
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, options) => {
      if (!String(input).endsWith('/api/v1/chat/react-agent')) return originalFetch(input, options);
      window.financialTestRequest = JSON.parse(options.body);
      const body = new ReadableStream({
        start(controller) {
          window.financialTestStream = controller;
        },
      });
      options.signal.addEventListener('abort', () =>
        window.financialTestStream.error(new DOMException('Stopped', 'AbortError')),
      );
      return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } });
    };
  });
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname.replace(/\/$/, '');
    let data = [];
    if (pathname.endsWith('/model/types')) data = ['synthetic-model'];
    else if (pathname.endsWith('/messages/history')) data = history;
    else if (pathname.endsWith('/financial-analysis/runs/latest')) {
      return route.fulfill({ json: { success: false, err_code: 'REPORT_NOT_FOUND', err_msg: 'No saved report' } });
    } else if (pathname.endsWith('/report')) {
      data = new URL(route.request().url()).searchParams.has('revision') ? report : syntheticComparison();
    }
    return route.fulfill({ json: { success: true, data } });
  });
}

async function emit(page, events) {
  await page.evaluate(items => {
    for (const event of items)
      window.financialTestStream.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`));
  }, events);
}

async function start(page) {
  await setup(page);
  await page.goto(baseURL);
  const composer = page.locator('textarea:visible').first();
  await composer.fill('分析这份合成年报');
  await composer.press('Enter');
  await expect.poll(() => page.evaluate(() => !!window.financialTestStream)).toBe(true);
  const sessionId = await page.evaluate(() => window.financialTestRequest.conv_uid);
  return {
    kind: 'financial-report',
    mode: 'comparison',
    title,
    sessionId,
    runId: report.report.run.id,
    revision: report.revision,
    published: true,
  };
}

async function publish(page, reference) {
  await emit(page, [
    {
      type: 'step.start',
      id: 'review',
      step: 1,
      title: 'review_financial_report',
      detail: 'Thought/Action/Observation',
    },
    { type: 'step.meta', id: 'review', action: 'review_financial_report', title: 'review_financial_report' },
    {
      type: 'plan.update',
      tasks: stages.map((content, index) => ({
        id: `stage-${index}`,
        kind: 'financial-stage',
        content,
        status: 'completed',
        priority: 'high',
        detail: index === 3 ? '报告已生成，可查看原文依据。' : '本阶段已完成。',
      })),
    },
    {
      type: 'step.chunk',
      id: 'review',
      output_type: 'text',
      content: '[00:10] 生成报告：报告已生成，可查看原文依据。\n',
    },
    { type: 'step.chunk', id: 'review', output_type: 'html', content: reference },
    { type: 'step.done', id: 'review', status: 'done' },
  ]);
}

async function finish(page) {
  await emit(page, [{ type: 'final', content: '合成最终要点，报告已可查看。' }, { type: 'done' }]);
  await page.evaluate(() => window.financialTestStream.close());
}

test('opens the published report before final, keeps manual navigation after final, and deduplicates repeats', async ({
  page,
}) => {
  const reference = await start(page);
  await publish(page, reference);
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await expect(page.getByRole('status').filter({ hasText: '正在整理回复' })).toBeVisible();
  await expect(page.getByText('合成最终要点，报告已可查看。', { exact: true })).toHaveCount(0);
  await expect(page.getByText('任务已完成', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('log', { name: '财报分析进展' })).toContainText('报告已生成');
  await page.screenshot({ path: test.info().outputPath('published-before-summary.png'), fullPage: true });
  await page.getByText('查看此任务中的所有文件', { exact: true }).click();
  await expect(page.getByRole('tablist', { name: /任务文件/ })).toBeVisible();
  await emit(page, [{ type: 'step.chunk', id: 'review', output_type: 'html', content: reference }]);
  await finish(page);
  await expect(page.getByText('合成最终要点，报告已可查看。', { exact: true })).toBeVisible();
  await expect(page.getByRole('tablist', { name: /任务文件/ })).toBeVisible();
  await expect(page.getByRole('tabpanel').getByText(`${title}.html`, { exact: true })).toHaveCount(1);
});

test('keeps a published report visible when the connection closes without a final answer', async ({ page }) => {
  const reference = await start(page);
  await publish(page, reference);
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await page.evaluate(() => window.financialTestStream.close());
  await expect(page.getByText('报告已生成，可查看报告与原文依据；本次回复未完成。', { exact: true })).toBeVisible();
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await expect(page.getByRole('status').filter({ hasText: '正在整理回复' })).toHaveCount(0);
});

test('removes rejected thinking placeholders without losing the report or showing completed fake steps', async ({
  page,
}) => {
  const reference = await start(page);
  await publish(page, reference);
  await emit(page, [
    { type: 'step.start', id: 'invalid-thinking', step: 2, title: '思考中', detail: 'Thought/Action/Observation' },
    { type: 'step.remove', id: 'invalid-thinking' },
    // A late completion/chunk must not recreate a discarded placeholder.
    { type: 'step.chunk', id: 'invalid-thinking', output_type: 'text', content: '无效回复不应显示' },
    { type: 'step.done', id: 'invalid-thinking', status: 'done' },
    { type: 'step.meta', id: 'invalid-thinking', action: 'read_financial_report' },
    { type: 'step.start', id: 'invalid-thinking', step: 2, title: '思考中' },
  ]);
  const execution = page.getByTestId('financial-left-execution');
  await execution.getByText('工具调用详情', { exact: true }).click();
  await expect(execution.getByText('思考中', { exact: true })).toHaveCount(0);
  await expect(page.getByText('无效回复不应显示', { exact: true })).toHaveCount(0);
  await expect(execution.getByText('核对结论与原文依据', { exact: true })).toBeVisible();
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await finish(page);
  await expect(page.getByRole('status').filter({ hasText: '正在整理回复' })).toHaveCount(0);
  await expect(page.getByText('合成最终要点，报告已可查看。', { exact: true })).toBeVisible();
});

test('does not auto-open a draft or steal a view selected before publication', async ({ page }) => {
  const reference = await start(page);
  await emit(page, [
    {
      type: 'step.start',
      id: 'prepare',
      step: 1,
      title: 'prepare_financial_report',
      detail: 'Thought/Action/Observation',
    },
    {
      type: 'step.chunk',
      id: 'prepare',
      output_type: 'text',
      content: '[00:03] 读取财报：已提取财务数据。\n已读取财务科目：营业收入、净利润。\n',
    },
    {
      type: 'step.chunk',
      id: 'prepare',
      output_type: 'html',
      content: { ...reference, published: false, revision: 'draft' },
    },
  ]);
  await expect(page.getByText('读取财报并分析财务数据', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('log', { name: '财报分析进展' })).toContainText('营业收入');
  await expect(
    page.getByTestId('right-panel-content').getByText('读取财报并分析财务数据', { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel('报告状态')).toHaveText('分析中');
  await page.getByText('查看此任务中的所有文件', { exact: true }).click();
  await publish(page, reference);
  await expect(page.getByRole('tablist', { name: /任务文件/ })).toBeVisible();
  await expect(page.getByLabel('报告状态')).toHaveCount(0);
  await page.getByRole('button', { name: '查看报告与原文依据' }).click();
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await finish(page);
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
});

test('restores public observations and the latest report identity from saved history', async ({ page }) => {
  const sessionId = 'financial-delivery-history';
  const reference = {
    kind: 'financial-report',
    mode: 'comparison',
    title,
    sessionId,
    runId: report.report.run.id,
    revision: report.revision,
    published: true,
  };
  await setup(page, [
    { role: 'human', context: '已保存的合成报告', order: 1 },
    {
      role: 'view',
      order: 1,
      context: JSON.stringify({
        version: 2,
        protocol_version: 2,
        type: 'react-agent',
        final_content: '已保存的合成结果。',
        financial_report: reference,
        steps: [
          {
            id: 'prepare',
            title: 'prepare_financial_report',
            detail: 'Thought/Action/Observation',
            status: 'done',
            outputs: [
              { output_type: 'html', content: { ...reference, revision: 'draft', published: false, title: '旧标题' } },
              { output_type: 'text', content: '[00:03] 读取财报：已提取财务数据。\n' },
            ],
          },
        ],
      }),
    },
  ]);
  await page.goto(`${baseURL}/?id=${sessionId}`);
  await expect(page.getByText('读取财报并分析财务数据', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('log', { name: '财报分析进展' })).toContainText('已提取财务数据');
  await expect(page.getByText('旧标题.html', { exact: true })).toHaveCount(0);
  await page.getByText(`${title}.html`, { exact: true }).click();
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
});

test('keeps the report and progress accessible on a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const reference = await start(page);
  await publish(page, reference);
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  const workspace = page.getByTestId('right-panel-content');
  expect((await workspace.boundingBox()).width).toBeGreaterThan(350);
  await page.getByRole('button', { name: '返回对话' }).click();
  await expect(page.getByRole('button', { name: '查看报告与原文依据' })).toBeVisible();
  await page.getByRole('button', { name: '查看报告与原文依据' }).click();
  await finish(page);
  await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  await page.screenshot({ path: test.info().outputPath('narrow-report.png'), fullPage: true, animations: 'disabled' });
});
