import { openDashboardCreation } from './creation-entry';
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const evidence = path.resolve(
  process.cwd(),
  process.env.DASHBOARD_E2E_EVIDENCE_DIR || '../output/layout-v9-2-browser-evidence',
);

for (const width of [1440, 1024]) {
  test(`generation timeout ${width}: truthful progress, stopped spinner, manual recovery`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    await page.addInitScript(() => {
      localStorage.setItem('dbgpt-selected-model', 'deepseek-v4-flash');
      const original = window.fetch.bind(window);
      (window as any).__timeoutRequests = [];
      window.fetch = async (input, init) => {
        const url = String(input instanceof Request ? input.url : input);
        if (!url.includes('/api/v1/chat/react-agent')) return original(input, init);
        (window as any).__timeoutRequests.push(JSON.parse(String(init?.body)));
        const encoder = new TextEncoder();
        return new Response(
          new ReadableStream({
            start(controller) {
              (window as any).__timeoutEmit = (event: Record<string, unknown>) => {
                controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
                if (event.type === 'done') controller.close();
              };
            },
          }),
          { headers: { 'Content-Type': 'text/event-stream' } },
        );
      };
    });
    await page.route('**/api/**', route => {
      const url = new URL(route.request().url());
      let data: unknown = [];
      if (url.pathname.includes('/model/types')) data = ['deepseek-v4-flash'];
      if (url.pathname.includes('/datasources'))
        data = [
          {
            id: 'walmart',
            db_name: 'Walmart_Sales',
            type: 'sqlite',
            params: { name: 'Walmart_Sales' },
          },
        ];
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ success: true, data }) });
    });
    await page.goto('/');
    const input = await openDashboardCreation(page, 'Walmart_Sales');
    await input.fill('生成一个复杂经营看板');
    await page.getByRole('button', { name: '发送需求', exact: true }).click();
    await page.waitForFunction(() => (window as any).__timeoutRequests.length === 1);
    const emit = (event: Record<string, unknown>) =>
      page.evaluate(payload => (window as any).__timeoutEmit(payload), event);
    const widgets = [
      { id: 'sales', title: '销售总额', type: 'kpi' },
      { id: 'trend', title: '月度销售趋势', type: 'line' },
      { id: 'stores', title: '门店销售排名', type: 'bar' },
    ];
    const identity = {
      dashboard_id: 'timeout-plan',
      source_turn_id: 'timeout-source-turn',
      title: '复杂看板生成回归',
      data_source_id: 'Walmart_Sales',
      current_revision: 1,
      total_widgets: 3,
    };
    await emit({
      type: 'dashboard.plan.awaiting_confirmation',
      ...identity,
      plan: { widgets },
      confirmation_prompt: '[[confirm-dashboard:timeout-plan]] confirm revision 1',
    });
    await emit({ type: 'final', content: '请确认规划。', citations: [] });
    await emit({ type: 'done' });
    await page.getByRole('button', { name: '确认并生成 SQL' }).click();
    await page.waitForFunction(() => (window as any).__timeoutRequests.length === 2);
    const run = { ...identity, generation_id: 'bounded-run' };
    await emit({ type: 'dashboard.generation.started', ...run, limit_seconds: 180, plan: { widgets } });
    await emit({ type: 'dashboard.widget.validated', ...run, widget_id: 'sales', title: '销售总额' });
    await expect(page.getByText('已校验 1/3', { exact: true })).toBeVisible();
    await expect(page.getByText('本轮生成最多 180 秒，超时将停止并保留规划，不会自动重试。')).toBeVisible();
    mkdirSync(evidence, { recursive: true });
    await page.screenshot({
      path: path.join(evidence, `bounded-running-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    const message =
      '本次看板生成未完成：达到 180 秒时限，停在「公开分享数据绑定校验」。原规划仍保留，本轮未保存为可用看板。';
    await emit({
      type: 'dashboard.generation.failed',
      ...run,
      reason: 'timeout',
      message,
      summary: '本次看板生成未完成：达到 180 秒时限。',
      limit_seconds: 180,
      stage_label: '公开分享数据绑定校验',
      validated_widgets: 1,
      failed_widgets: 0,
      validated_widget_ids: ['sales'],
      pending_widget_ids: ['trend', 'stores'],
      plan: { widgets },
      editor_path: '/dashboards/timeout-plan',
      revision_prompt:
        '[[revise-dashboard-plan:timeout-plan]] Revise this dashboard plan at expected revision 1 as follows: ',
      retry_hint: '可缩小为 3–4 个核心组件，明确必要筛选条件后再确认。不会自动重试。',
    });
    // Deliberate late events must not revive the closed generation.
    await emit({ type: 'dashboard.widget.validated', ...run, widget_id: 'trend' });
    await emit({ type: 'dashboard.created', ...run, validated_widgets: 3 });
    await emit({ type: 'final', content: message, citations: [] });
    await emit({ type: 'done' });
    await expect(page.getByRole('alert', { name: '看板生成未完成' })).toContainText(
      'SQL 试运行通过（不等于已保存）：销售总额',
    );
    await expect(page.getByRole('alert', { name: '看板生成未完成' })).toContainText(
      '尚未通过试运行：月度销售趋势、门店销售排名',
    );
    await expect(page.getByText('已校验 1/3', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '查看保留的规划/草稿' })).toBeEnabled();
    await expect(page.getByRole('button', { name: '查看看板', exact: true })).toHaveCount(0);
    await expect(page.locator('.anticon-loading')).toHaveCount(0);
    await page.getByRole('button', { name: '修改计划后重试' }).scrollIntoViewIfNeeded();
    await expect(page.getByText(message, { exact: true })).toHaveCount(0);
    await expect(page.getByText('本次看板生成未完成：达到 180 秒时限。', { exact: true })).toBeVisible();
    await page.screenshot({
      path: path.join(evidence, `timeout-recovery-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await page.getByRole('button', { name: '修改计划后重试' }).click();
    await expect(input).toHaveValue(/\[\[revise-dashboard-plan:timeout-plan\]\].*expected revision 1/);
    expect(await page.evaluate(() => (window as any).__timeoutRequests.length)).toBe(2);
    expect(errors).toEqual([]);
  });
}
