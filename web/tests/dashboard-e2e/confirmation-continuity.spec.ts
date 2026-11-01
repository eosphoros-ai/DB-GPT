import { openDashboardCreation } from './creation-entry';
import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const evidence = path.resolve(
  process.cwd(),
  process.env.DASHBOARD_E2E_EVIDENCE_DIR || '../output/layout-v9-2-browser-evidence',
);
const published = JSON.parse(
  readFileSync(path.resolve(process.cwd(), '../examples/dashboard/snapshots/walmart-sales.public.json'), 'utf8'),
);
const success = (data: unknown) => ({ success: true, data });

for (const width of [1440, 1024]) {
  test(`confirmation continuity ${width}: one click advances the same plan, failure stays visible`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    await page.addInitScript(() => {
      localStorage.setItem('dbgpt-selected-model', 'deepseek-v4-flash');
      const original = window.fetch.bind(window);
      (window as any).__generationRequests = [];
      window.fetch = async (input, init) => {
        const url = String(input instanceof Request ? input.url : input);
        if (url.includes('/api/v1/chat/react-agent')) {
          (window as any).__generationRequests.push(JSON.parse(String(init?.body)));
          const encoder = new TextEncoder();
          return new Response(
            new ReadableStream({
              start(controller) {
                (window as any).__emitGeneration = (event: Record<string, unknown>) => {
                  controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
                  if (event.type === 'done') controller.close();
                };
              },
            }),
            { headers: { 'Content-Type': 'text/event-stream' } },
          );
        }
        return original(input, init);
      };
    });
    await page.route('**/api/**', route => {
      const url = new URL(route.request().url());
      let data: unknown = [];
      if (url.pathname.includes('/model/types')) data = ['deepseek-v4-flash'];
      if (url.pathname.includes('/datasources'))
        data = [{ id: 'walmart', db_name: 'Walmart_Sales', type: 'sqlite', params: { name: 'Walmart_Sales' } }];
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(success(data)) });
    });
    await page.goto('/');
    const prompt = await openDashboardCreation(page, 'Walmart_Sales');
    await prompt.fill('生成 Walmart 看板');
    await page.getByRole('button', { name: '发送需求', exact: true }).click();
    await page.waitForFunction(() => (window as any).__generationRequests.length === 1);
    const emit = (event: Record<string, unknown>) =>
      page.evaluate(payload => (window as any).__emitGeneration(payload), event);
    const plan = {
      metrics: ['sales'],
      widgets: published.schema.widgets.map((w: any) => ({ id: w.id, type: w.type, title: w.title })),
    };
    const identity = {
      dashboard_id: 'bound-plan',
      source_turn_id: 'plan-source-turn',
      title: '确认连续性回归',
      current_revision: 3,
      total_widgets: plan.widgets.length,
    };
    await emit({
      type: 'dashboard.plan.awaiting_confirmation',
      ...identity,
      data_source_id: 'Walmart_Sales',
      plan,
      confirmation_prompt:
        '[[confirm-dashboard:bound-plan]] I confirm this dashboard plan at expected revision 3. Generate and validate its SQL queries now.',
    });
    await emit({ type: 'final', content: '请确认规划。', citations: [] });
    await emit({ type: 'done' });
    const confirm = page.getByRole('button', { name: '确认并生成 SQL' });
    await expect(confirm).toBeEnabled();
    await confirm.click();
    await page.waitForFunction(() => (window as any).__generationRequests.length === 2);
    const requests = await page.evaluate(() => (window as any).__generationRequests);
    expect(requests[1].user_input).toContain('expected revision 3');
    expect(requests[1].ext_info.database_name).toBe('Walmart_Sales');
    await emit({ type: 'dashboard.generation.started', ...identity, data_source_id: 'Walmart_Sales', plan });
    await expect(page.getByText('正在生成并试运行组件查询', { exact: true })).toBeVisible();
    await expect(page.getByText('确认连续性回归', { exact: true })).toHaveCount(1);
    await expect(confirm).toHaveCount(0);
    mkdirSync(evidence, { recursive: true });
    await page.screenshot({
      path: path.join(evidence, `generating-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    await emit({
      type: 'dashboard.generation.failed',
      ...identity,
      message: '本次看板生成未完成，已保存的规划仍保留。',
    });
    await emit({ type: 'final', content: '生成未完成，请查看工具错误。', citations: [] });
    await emit({ type: 'done' });
    await expect(page.getByText('本次看板生成未完成，已保存的规划仍保留。', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '查看看板' })).toHaveCount(0);
    await expect(page.getByText('正在生成并试运行组件查询', { exact: true })).toHaveCount(0);
    // A structured terminal failure closes this request; a late final must not
    // replace its visible failure or restart the transport.
    await expect(page.getByText('生成未完成，请查看工具错误。', { exact: true })).toHaveCount(0);
    await page.screenshot({
      path: path.join(evidence, `incomplete-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    });
    expect(await page.evaluate(() => (window as any).__generationRequests.length)).toBe(2);
    expect(errors).toEqual([]);
  });
}
