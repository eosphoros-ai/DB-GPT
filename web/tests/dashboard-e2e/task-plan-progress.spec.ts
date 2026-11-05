import { expect, test } from '@playwright/test';

const success = (data: unknown) => ({ success: true, data });
const tasks = (status: string) => [
  { content: '计算销售数据', status: 'completed', priority: 'high' },
  { content: '调用 generate_report 生成报告', status, priority: 'high' },
];

for (const completed of [true, false]) {
  test(`final plan remains consistent after reload: ${completed ? 'completed' : 'partial'}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => localStorage.setItem('__db_gpt_lng_key', 'zh'));
    const plan = tasks(completed ? 'completed' : 'in_progress');
    const meta = { state: completed ? 'done' : 'progress', done: completed ? 2 : 1, total: 2 };
    const title = `TODO::${meta.state}:${meta.done}/${meta.total}`;
    const summary = completed ? '销售分析已完成。' : '报告部分完成，仍有未完成内容。';
    const history = {
      type: 'react-agent',
      protocol_version: 2,
      version: 2,
      final_content: summary,
      task_plan: plan,
      steps: [{ id: 'plan', action: 'todowrite', title, status: 'done', todo_meta: meta, outputs: [] }],
    };
    let submitted = false;
    let historyLoads = 0;
    await page.route('**/api/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      if (pathname === '/api/v1/chat/react-agent') {
        submitted = true;
        const events = [
          { type: 'step.start', id: 'plan', action: 'todowrite', title: 'TODO::progress:1/2' },
          { type: 'step.meta', id: 'plan', action: 'todowrite', todo_meta: { state: 'progress', done: 1, total: 2 } },
          { type: 'plan.update', tasks: tasks('in_progress') },
          { type: 'final', protocol_version: 2, content: summary, task_plan: plan, todo_meta: meta, citations: [] },
          { type: 'done' },
        ];
        await route.fulfill({
          contentType: 'text/event-stream',
          body: events.map(e => `data: ${JSON.stringify(e)}\n\n`).join(''),
        });
        return;
      }
      let data: unknown = [];
      if (pathname === '/api/v1/model/types') data = ['fixture-model'];
      if (pathname === '/api/v1/chat/dialogue/messages/history' && submitted) {
        historyLoads++;
        data = [
          { role: 'human', context: '分析销售' },
          { role: 'view', context: JSON.stringify(history) },
        ];
      }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(success(data)) });
    });
    await page.goto('/');
    await page.locator('textarea').first().fill('分析销售');
    await page.locator('textarea').first().press('Enter');
    const label = completed ? '2 个任务全部完成' : '共 2 个任务，已完成 1 个';
    const localizedTitle = completed ? '任务全部完成 (2/2)' : '更新任务状态 (1/2 完成)';
    const planStep = page.getByTestId('task-plan-step');
    const assertVisiblePlan = async () => {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
      await expect(planStep.getByText(localizedTitle, { exact: true })).toBeVisible();
      await expect(planStep.getByText(`${meta.done}/${meta.total}`, { exact: true })).toBeVisible();
      await expect(planStep.getByText(/^TODO::/)).toHaveCount(0);
    };
    // Wait for the final event to select the summary view, rather than matching
    // an internal title that happens to be visible in the execution panel.
    await expect(page.getByTestId('right-panel-content').getByText(summary, { exact: true })).toBeVisible();
    await assertVisiblePlan();
    const loadsBeforeReload = historyLoads;
    await page.reload();
    await expect.poll(() => historyLoads).toBeGreaterThan(loadsBeforeReload);
    await assertVisiblePlan();
    expect(errors).toEqual([]);
  });
}
