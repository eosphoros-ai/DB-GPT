import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const output = path.resolve(process.env.DASHBOARD_E2E_ARTIFACTS || '../output/workspace-refinement-20260911');
test.setTimeout(180_000);
test.use({ actionTimeout: 15_000, navigationTimeout: 120_000 });
mkdirSync(output, { recursive: true });
const published = JSON.parse(
  readFileSync(path.resolve('../examples/dashboard/snapshots/walmart-sales.public.json'), 'utf8'),
);

async function setup(page: Page) {
  const record = {
    id: published.dashboard_id,
    owner_id: '001',
    conversation_id: 'feedback-test',
    source_turn_id: null,
    origin: 'manual',
    asset_state: 'saved',
    saved_at: '2026-09-10T00:00:00Z',
    current_revision: 1,
    status: 'draft',
    schema: structuredClone(published.schema),
    created_at: '2026-09-10T00:00:00Z',
    updated_at: '2026-09-10T00:00:00Z',
  };
  record.schema.dashboard.theme = { preset: 'clarity', mode: 'light', overrides: {} };
  record.schema.dashboard.data_source_id = 'Walmart_Sales';
  record.schema.widgets.forEach((widget: any) => {
    widget.query.data_source_id = 'Walmart_Sales';
  });
  const state = {
    clarify: true,
    failStream: false,
    created: [] as any[],
    querySql: [] as string[],
    handoffs: 0,
    applies: 0,
    prompts: [] as any[],
    generatedIds: [] as string[],
    generationInputs: [] as any[],
  };
  await page.addInitScript(() => {
    localStorage.setItem('__db_gpt_lng_key', 'zh');
    localStorage.setItem('__db_gpt_theme_key', 'light');
    localStorage.setItem('dbgpt-selected-model', 'deepseek-v4-flash');
  });
  await page.route('**/api/**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (pathname.endsWith('/model/types')) data = ['deepseek-v4-flash'];
    else if (pathname.includes('/datasources'))
      data = [{ id: 'walmart', db_name: 'Walmart_Sales', type: 'sqlite', params: { name: 'Walmart_Sales' } }];
    else if (pathname.endsWith('/dashboards/schema')) data = {};
    else if (pathname.endsWith('/annotation-intents')) {
      const input = request.postDataJSON();
      state.prompts.push(input);
      data = {
        reply:
          state.clarify && (input.items.length > 1 || /^\d+$/.test(input.items[0].prompt))
            ? '请补充需要解释的计算口径。'
            : null,
        items: input.items.map((item: { draft_id: string; prompt: string }, index: number) => ({
          draft_id: item.draft_id,
          tasks:
            state.clarify && (index === 1 || /^\d+$/.test(item.prompt))
              ? []
              : [{ intent: 'modify', prompt: item.prompt + '\n' + input.message }],
          question: state.clarify && (index === 1 || /^\d+$/.test(item.prompt)) ? '请补充需要解释的计算口径。' : null,
        })),
      };
    } else if (pathname.endsWith('/annotations') && request.method() === 'POST') {
      const input = request.postDataJSON();
      data = {
        ...input,
        id: 'annotation-' + (state.created.length + 1),
        dashboard_id: record.id,
        status: 'pending',
        created_at: record.created_at,
        updated_at: record.updated_at,
      };
      state.created.push(data);
    } else if (pathname.endsWith('/annotations') && request.method() === 'GET') {
      data = state.created;
    } else if (/\/annotations\/[^/]+\/generate$/.test(pathname)) {
      if (state.failStream)
        return route.fulfill({ status: 422, json: { detail: 'SQL 参数 category 必须用于 IN；批注已保留。' } });
      const id = pathname.split('/').at(-2);
      const item = state.created.find(annotation => annotation.id === id);
      expect(item).toBeTruthy();
      state.generatedIds.push(id!);
      state.generationInputs.push(request.postDataJSON());
      item.status = 'proposed';
      item.proposal = {
        summary: `修改 ${state.created.indexOf(item) + 1}`,
        stable_operations: [
          { op: 'replace', path: `/widgets/by-id/${item.target.widget_id}/title`, value: '修改后的标题' },
        ],
        operations: [],
      };
      data = item;
    } else if (pathname.endsWith('/assistant-task')) {
      state.handoffs++;
      data = { conversation_id: 'workspace-test-conversation' };
    } else if (pathname.endsWith('/chat/react-agent')) {
      if (state.failStream) return route.fulfill({ status: 503, json: { error: '模拟连接中断' } });
      state.created.forEach((item, index) => {
        item.status = 'proposed';
        item.proposal = {
          summary: `修改 ${index + 1}`,
          stable_operations: [
            { op: 'replace', path: `/widgets/${item.target.widget_id}/title`, value: `修改后 ${index + 1}` },
          ],
          operations: [],
        };
      });
      return route.fulfill({
        contentType: 'text/event-stream',
        body: 'data: ' + JSON.stringify({ type: 'final', content: '两条批注已生成修改方案，可以一起应用。' }) + '\n\n',
      });
    } else if (pathname.endsWith('/annotations/apply-batch')) {
      state.applies++;
      expect(request.postDataJSON().annotation_ids).toHaveLength(2);
      record.current_revision++;
      state.created.forEach(item => (item.status = 'applied'));
      data = { annotations: state.created, operation: { dashboard: record } };
    } else if (pathname.endsWith('/features')) {
      data = {
        template_id: 'retail-overview',
        title: '零售经营总览',
        prompt: '保留此模板的布局、配色和指标组合，匹配所选真实数据源。',
        widgets: record.schema.widgets.map((item: any) => ({ id: item.id, title: item.title })),
        theme: record.schema.dashboard.theme,
      };
    } else if (pathname.endsWith('/source')) {
      data = {
        data_source_id: 'Walmart_Sales',
        dialect: 'sqlite',
        builtin_available: true,
        roles: [],
        grain: 'store_week',
        tables: [],
        suggested_mapping: null,
      };
    } else if (pathname.endsWith('/adapt')) {
      expect(request.postDataJSON().prompt).toContain('布局');
      data = {
        schema: record.schema,
        snapshot: published.snapshot,
        validation: {
          records: null,
          widgets: record.schema.widgets.length,
          filter_checks: 1,
          publication_equivalent: false,
          grain: 'AI 适配',
        },
        adaptation: { changes: ['使用所选数据源的实际字段'] },
      };
    } else if (pathname.endsWith('/generate')) {
      expect(request.postDataJSON().schema).toEqual(record.schema);
      data = record;
    } else if (pathname.endsWith('/query-logic')) {
      const input = request.postDataJSON();
      state.querySql.push(input.sql);
      data = {
        tables: ['walmart_sales'],
        set_operations: [],
        stages: [
          {
            label: '最终结果',
            expressions: ['SUM(Weekly_Sales) AS value'],
            group_by: [],
            where: 'year = :year',
            joins: [],
          },
        ],
      };
    } else if (pathname.endsWith('/validate')) data = { valid: true, issues: [], widget_status: {} };
    else if (pathname.endsWith('/snapshot') || pathname.endsWith('/refresh')) data = published.snapshot;
    else if (pathname.endsWith('/dashboards/page'))
      data = {
        items: [{ ...record, title: record.schema.dashboard.title, data_source_id: 'Walmart_Sales' }],
        total: 1,
      };
    else if (pathname.endsWith('/dashboards'))
      data = [{ ...record, title: record.schema.dashboard.title, data_source_id: 'Walmart_Sales' }];
    else if (pathname.endsWith('/' + record.id)) data = record;
    else if (pathname.includes('/datasets/by-conversation/')) data = null;
    return route.fulfill({ json: { success: true, data } });
  });
  return { record, state };
}

test('floating annotations clarify in the same conversation, survive reload, retry and apply together', async ({
  page,
}) => {
  const { record, state } = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  const widgets = page.locator('[data-dashboard-widget-id]');
  await expect(widgets.first()).toBeVisible();
  await expect(page.getByRole('button', { name: '开启框选批注', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '批注修改', exact: true })).toHaveCount(0);
  for (const [index, text] of ['1', '2'].entries()) {
    await widgets.nth(index).getByRole('button', { name: '批注此组件', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(text);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  await expect(page.getByTestId('annotation-queue-item')).toHaveCount(0);
  await page.getByRole('button', { name: '本次批注 2 条', exact: true }).click();
  const tray = page.getByTestId('annotation-tray');
  await expect(tray.getByTestId('annotation-queue-item')).toHaveCount(2);
  await expect(tray).toContainText(record.schema.dashboard.title);
  await page.screenshot({ path: path.join(output, 'annotation-floating-list.png'), fullPage: true });
  await tray.getByRole('button', { name: /一起发送给 AI/ }).click();
  const panel = page.getByTestId('dashboard-assistant-panel');
  await expect(panel.getByText(/请补充需要解释的计算口径/)).toBeVisible();
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(2);
  await expect(page.getByText('批注尚未发送', { exact: true })).toHaveCount(0);
  expect(state.created).toHaveLength(0);
  expect(page.url()).toContain('/dashboards/' + record.id);
  await page.reload();
  await page.getByTestId('dashboard-component-library').getByText('AI 助手', { exact: true }).click();
  await expect(panel.getByText(/请补充需要解释的计算口径/)).toBeVisible();
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(2);
  state.clarify = false;
  state.failStream = true;
  await panel
    .getByRole('textbox', { name: '给看板 AI 助手发消息' })
    .fill('第1个标题改为销售总额，第2个标题改为月度趋势');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByRole('button', { name: '重试这次请求' })).toBeVisible();
  await expect(panel.getByText('SQL 参数 category 必须用于 IN；批注已保留。')).toBeVisible();
  expect(state.created).toHaveLength(2);
  state.failStream = false;
  await panel.getByRole('button', { name: '重试这次请求' }).click();
  await expect(panel.getByText('修改方案已通过验证，请审阅后应用。')).toBeVisible();
  expect(state.created).toHaveLength(2);
  expect(state.prompts.at(-1).message).toContain('第1个标题');
  expect(state.generatedIds).toEqual(state.created.map(item => item.id));
  expect(state.generationInputs.map(input => JSON.parse(input.user_prompt).annotation)).toEqual(['1', '2']);
  expect(JSON.parse(state.generationInputs[0].user_prompt).message).toContain('第1个标题');
  expect(state.handoffs).toBe(0);
  await panel.getByText('2 项修改待确认', { exact: true }).click();
  await panel.getByRole('button', { name: '应用本批修改', exact: true }).click();
  await expect(panel.getByText('已一起应用 2 项修改。可以继续批注或讨论。')).toBeVisible();
  expect(state.applies).toBe(1);
  expect(record.current_revision).toBe(2);
  expect(page.url()).toContain('/dashboards/' + record.id);
  await page.screenshot({ path: path.join(output, 'annotation-conversation.png'), fullPage: true });
});

test('pending annotations can be resent from the tray and its trigger moves freely without opening', async ({
  page,
}) => {
  const { record, state } = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  for (const [index, text] of ['2', '3'].entries()) {
    await page
      .locator('[data-dashboard-widget-id]')
      .nth(index)
      .getByRole('button', { name: '批注此组件', exact: true })
      .click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(text);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  const trigger = page.getByTestId('annotation-tray-trigger');
  const tray = page.getByTestId('annotation-tray');
  await trigger.click();
  await tray.getByRole('button', { name: '一起发送给 AI（2 条）', exact: true }).click();
  await expect(page.getByTestId('dashboard-assistant-panel').getByText(/请补充需要解释的计算口径/)).toBeVisible();
  await page.reload();
  await trigger.click();
  await expect(tray.getByText(/对话中补充/)).toHaveCount(2);
  await expect(tray.getByRole('button', { name: '一起发送给 AI（2 条）', exact: true })).toBeEnabled();
  state.clarify = false;
  await tray.getByRole('button', { name: '一起发送给 AI（2 条）', exact: true }).click();
  await expect.poll(() => state.created.length).toBe(2);
  expect(state.prompts.at(-1).items.map((item: any) => item.target.widget_id)).toEqual(
    record.schema.widgets.slice(0, 2).map((widget: any) => widget.id),
  );
  await expect(
    page.getByTestId('dashboard-assistant-panel').getByText('修改方案已通过验证，请审阅后应用。'),
  ).toBeVisible();
  await trigger.click();
  await expect(tray.getByRole('button', { name: '一起发送给 AI（0 条）', exact: true })).toBeDisabled();
  // Drag both axes, including while the tray is open. Releasing must not reopen it.
  let box = (await trigger.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(340, 240, { steps: 12 });
  await page.mouse.up();
  await expect(tray).not.toBeVisible();
  box = (await trigger.boundingBox())!;
  expect(box.x).toBeLessThan(350);
  expect(box.y).toBeLessThan(250);
  const moved = box;
  await page.reload();
  await expect.poll(async () => (await trigger.boundingBox())!.x).toBeCloseTo(moved.x, 0);
  await expect.poll(async () => (await trigger.boundingBox())!.y).toBeCloseTo(moved.y, 0);
  await trigger.click();
  await expect(tray).toBeVisible();
  await trigger.click();
  await trigger.focus();
  await trigger.press('Alt+ArrowRight');
  expect((await trigger.boundingBox())!.x).toBeCloseTo(moved.x + 10, 0);
  box = (await trigger.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(1438, 998, { steps: 10 });
  await page.mouse.up();
  await page.setViewportSize({ width: 390, height: 640 });
  await expect
    .poll(async () => {
      const bounds = (await trigger.boundingBox())!;
      return bounds.x + bounds.width;
    })
    .toBeLessThanOrEqual(383);
  box = (await trigger.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(633);
  const touch = await page.context().newCDPSession(page);
  await touch.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x: box.x + box.width / 2, y: box.y + box.height / 2 }],
  });
  await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 100, y: 150 }] });
  await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await touch.detach();
  await expect(tray).not.toBeVisible();
  await expect.poll(async () => (await trigger.boundingBox())!.y).toBeLessThan(160);
  await trigger.click();
  await expect(tray).toBeVisible();
  const popup = page.locator('.ant-popover:visible');
  await expect(popup).toHaveCSS('opacity', '1');
  await expect.poll(async () => (await popup.boundingBox())!.x).toBeGreaterThanOrEqual(0);
  await expect
    .poll(async () => {
      const bounds = (await popup.boundingBox())!;
      return bounds.x + bounds.width;
    })
    .toBeLessThanOrEqual(390);
  await page.screenshot({ path: path.join(output, 'annotation-tray-mobile.png'), fullPage: true });
});

test('new chart annotations remain in the composer after chat and travel with the next message', async ({ page }) => {
  const { record, state } = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  await page.getByTestId('dashboard-component-library').getByText('AI 助手', { exact: true }).click();
  const panel = page.getByTestId('dashboard-assistant-panel');
  await panel.getByRole('textbox').fill('我想调整这个看板');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('修改方案已通过验证，请审阅后应用。')).toBeVisible();
  for (const [index, text] of ['改为收入总额', '改为折线图'].entries()) {
    await page
      .locator('[data-dashboard-widget-id]')
      .nth(index)
      .getByRole('button', { name: '批注此组件', exact: true })
      .click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(text);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(2);
  await page.reload();
  await page.getByTestId('dashboard-component-library').getByText('AI 助手', { exact: true }).click();
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(2);
  const second = panel.getByTestId('annotation-composer-item').nth(1);
  await second.getByRole('button', { name: /编辑 .* 批注/ }).click();
  const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
  await dialog.getByRole('textbox', { name: '批注内容' }).fill('改为面积图');
  await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  await expect(second).toContainText('改为面积图');
  await page.screenshot({ path: path.join(output, 'annotations-after-existing-chat.png'), fullPage: true });
  state.clarify = false;
  await panel.getByRole('textbox').fill('这两处一起修改，保留原配色');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect.poll(() => state.prompts.at(-1).items.length).toBe(2);
  const sent = state.prompts.at(-1).items;
  expect(sent.map((item: any) => item.target.widget_id)).toEqual(
    record.schema.widgets.slice(0, 2).map((item: any) => item.id),
  );
  expect(state.prompts.at(-1).message).toContain('保留原配色');
  expect(state.prompts.at(-1).conversation).toContain('我想调整这个看板');
  expect(state.prompts.at(-1).view_context.widgets[0].query.sql).toBeTruthy();
  expect(sent[1].prompt).toContain('改为面积图');
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(0);
  const sentAttachments = panel.locator('article[data-message-role="user"] details').last();
  await sentAttachments.locator('summary').click();
  await expect(sentAttachments).toContainText('改为面积图');
  await page.screenshot({ path: path.join(output, 'sent-annotation-attachments.png'), fullPage: true });
});

test('editing or removing a failed attachment excludes its previous proposal from batch apply', async ({ page }) => {
  const { record, state } = await setup(page);
  state.clarify = false;
  state.failStream = true;
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id, { waitUntil: 'domcontentloaded' });
  for (const [index, text] of ['修改第一个标题', '修改第二个标题'].entries()) {
    await page
      .locator('[data-dashboard-widget-id]')
      .nth(index)
      .getByRole('button', { name: '批注此组件', exact: true })
      .click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(text);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  const panel = page.getByTestId('dashboard-assistant-panel');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByRole('button', { name: '重试这次请求' })).toBeVisible();
  expect(state.created).toHaveLength(2);
  await panel
    .getByTestId('annotation-composer-item')
    .first()
    .getByRole('button', { name: /移除 .* 批注/ })
    .click();
  await panel
    .getByTestId('annotation-composer-item')
    .first()
    .getByRole('button', { name: /编辑 .* 批注/ })
    .click();
  const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
  await dialog.getByRole('textbox', { name: '批注内容' }).fill('第二个改为销售趋势');
  await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  await expect(panel.getByRole('button', { name: '重试这次请求' })).toHaveCount(0);
  state.failStream = false;
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('1 项修改待确认', { exact: true })).toBeVisible();
  await expect(panel.getByText('3 项修改待确认', { exact: true })).toHaveCount(0);
  expect(state.prompts.at(-1).items).toHaveLength(1);
  expect(state.prompts.at(-1).items[0].target.widget_id).toBe(record.schema.widgets[1].id);
  expect(state.created).toHaveLength(3);
});

test('SQL logic and parameter values are visible before the advanced editor', async ({ page }) => {
  const { record, state } = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  await page.locator('[data-dashboard-widget-id]').first().getByRole('button', { name: 'SQL 与参数设置' }).click();
  await expect(page.getByTestId('dashboard-query-logic').getByText('计算口径', { exact: true })).toBeVisible();
  await expect(page.getByLabel('图表实际 SQL')).not.toBeVisible();
  await page
    .locator('summary')
    .filter({ hasText: /^实际 SQL$/ })
    .click();
  await expect(page.getByLabel('图表实际 SQL')).toBeVisible();
  const params = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: /^当前筛选参数$/ }) });
  await expect(params).not.toHaveAttribute('open');
  await params.locator('summary').click();
  await expect(params).toHaveAttribute('open');
  await expect(page.getByText('SUM(Weekly_Sales) AS value', { exact: true })).toBeVisible();
  const advanced = page.getByTestId('query-advanced-settings');
  await expect(advanced).not.toHaveAttribute('open');
  await page.screenshot({ path: path.join(output, 'sql-logic.png'), fullPage: true });
  await advanced.getByText('高级数据设置', { exact: true }).click();
  await page.getByTestId('dashboard-query-sql-input').fill('SELECT COUNT(*) AS value FROM walmart_sales');
  await expect(page.getByLabel('图表实际 SQL')).toContainText('COUNT(*)');
  await expect.poll(() => state.querySql.at(-1)).toBe('SELECT COUNT(*) AS value FROM walmart_sales');
});

test('five new chart types render data, expose values and remain available in the library', async ({ page }) => {
  const { record } = await setup(page);
  const variants = ['funnel', 'treemap', 'radar', 'waterfall', 'geo_map'];
  const labels = ['漏斗图', '矩形树图', '雷达图', '瀑布图', '地理分布图'];
  record.schema.schema_version = '1.4';
  record.schema.widgets = variants.map((visualization, index) => ({
    ...structuredClone(record.schema.widgets[0]),
    id: `extended-${visualization}`,
    title: labels[index],
    type: 'bar',
    encoding: { x: 'category', y: 'value', columns: [] },
    query: {
      ...record.schema.widgets[0].query,
      sql: "SELECT 'USA' AS category, 100 AS value",
      output_fields: [
        { name: 'category', type: 'string' },
        { name: 'value', type: 'number' },
      ],
    },
    presentation: {
      visualization,
      unit: '元',
      precision: 0,
      currency: '',
      colors: [],
      default_sort: { field: null, direction: 'default' },
    },
  }));
  record.schema.layouts.desktop = variants.map((visualization, index) => ({
    widget_id: `extended-${visualization}`,
    x: (index % 2) * 6,
    y: Math.floor(index / 2) * 8,
    w: 6,
    h: 8,
  }));
  const snapshot = {
    ...published.snapshot,
    widgets: Object.fromEntries(
      variants.map(visualization => [
        `extended-${visualization}`,
        {
          widget_id: `extended-${visualization}`,
          columns: ['category', 'value'],
          rows: [
            ['USA', 100],
            ['UK', visualization === 'waterfall' ? -30 : 60],
            ['Germany', 25],
            ['未知市场', 10],
          ],
          row_count: 4,
          elapsed_ms: 2,
          error: null,
        },
      ]),
    ),
  };
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname.replace(/\/$/, '');
    if (pathname.endsWith('/refresh') || pathname.endsWith('/snapshot'))
      return route.fulfill({ json: { success: true, data: snapshot } });
    await route.fallback();
  });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[data-extended-chart]')).toHaveCount(5);
  const search = page.getByRole('textbox', { name: '搜索图表类型' });
  for (const label of labels) {
    await search.fill(label);
    await expect(page.getByRole('button', { name: new RegExp(label) }).first()).toBeVisible();
  }
  for (const visualization of variants) {
    const plot = page.locator(`[data-extended-chart="${visualization}"]`);
    expect(
      await plot.locator('svg').evaluate(svg => {
        const viewport = svg.parentElement!;
        return svg.getBoundingClientRect().top >= viewport.getBoundingClientRect().top - 1;
      }),
    ).toBe(true);
    await plot.screenshot({ path: path.join(output, `chart-${visualization}.png`) });
  }
  const map = page.locator('[data-extended-chart="geo_map"]');
  await expect(map).toContainText('未匹配 1 项：未知市场');
  await map.locator('g[tabindex]').first().focus();
  await expect(map).toContainText('USA · 100 元');
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('editor folds tools, chart types and freshness without losing access', async ({ page }) => {
  const { record } = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: 'KPI 指标卡', exact: true })).toHaveCount(0);
  await page.getByRole('textbox', { name: '搜索图表类型' }).click();
  await expect(page.getByRole('button', { name: /KPI 指标卡/ })).toBeVisible();
  await page.getByRole('textbox', { name: '搜索图表类型' }).press('Escape');
  await expect(page.getByRole('button', { name: '定时刷新', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '更多看板操作', exact: true }).click();
  await page.getByRole('menuitem', { name: /定时任务/ }).click();
  await expect(page.getByRole('dialog')).toContainText('关联看板');
  await expect(page.getByRole('dialog').getByRole('link', { name: record.schema.dashboard.title })).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('沿用创建任务时的筛选条件');
  await page.screenshot({ path: path.join(output, 'schedule-folded-tools.png'), fullPage: true });
});

test('template assistant extracts an editable prompt and creates from verified preview', async ({ page }) => {
  await setup(page);
  await page.goto('/dashboards/?tab=templates', { waitUntil: 'domcontentloaded' });
  await page
    .locator('[data-catalog-template="retail-overview"]')
    .getByRole('button', { name: /预览模板/ })
    .click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByTestId('template-ai-assistant')).toBeVisible();
  await expect(dialog.getByRole('textbox', { name: '模板 AI 生成要求' })).toHaveValue(/布局/);
  await dialog.getByRole('button', { name: 'AI 适配并预览', exact: true }).click();
  await dialog.locator('summary').filter({ hasText: 'AI 做了哪些适配' }).click();
  await expect(dialog.getByText('使用所选数据源的实际字段')).toBeVisible();
  await page.screenshot({ path: path.join(output, 'template-ai-preview.png'), fullPage: true });
  await dialog.getByRole('button', { name: '创建看板', exact: true }).click();
  await expect(page).toHaveURL(/dashboards\//);
});

test('assistant discussion includes current data and conversation without creating changes', async ({ page }) => {
  const { record, state } = await setup(page);
  const requests: any[] = [];
  await page.route('**/annotation-intents', route => {
    const input = route.request().postDataJSON();
    requests.push(input);
    return route.fulfill({
      json: {
        success: true,
        data: {
          model: 'deepseek-v4-flash',
          reply:
            requests.length === 1
              ? '建议补充销售卡的时间范围，并明确门店排名的单位。'
              : '门店排名的单位建议与销售卡保持一致；按你说的先不修改。',
          items: input.items.map((item: any) => ({ draft_id: item.draft_id, tasks: [], answered: true })),
        },
      },
    });
  });
  await page.goto('/dashboards/' + record.id, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('dashboard-component-library').getByText('AI 助手', { exact: true }).click();
  const panel = page.getByTestId('dashboard-assistant-panel');
  await panel.getByRole('textbox').fill('有什么改进建议？');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('建议补充销售卡的时间范围，并明确门店排名的单位。')).toBeVisible();
  expect(requests[0].view_context.widgets[0].query.sql).toBeTruthy();
  expect(requests[0].view_context.widgets[0].result.rows_sample.length).toBeGreaterThan(0);
  expect(requests[0].view_context.filter_values).toBeTruthy();
  await panel.getByRole('textbox').fill('第二条展开讲讲，先不改');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('门店排名的单位建议与销售卡保持一致；按你说的先不修改。')).toBeVisible();
  expect(requests[1].conversation).toContain('有什么改进建议');
  expect(requests[1].conversation).toContain('明确门店排名的单位');
  expect(state.created).toHaveLength(0);
  expect(state.handoffs).toBe(0);
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(0);
});

test('one ambiguous annotation does not block clear changes in the same batch', async ({ page }) => {
  const { record, state } = await setup(page);
  await page.goto('/dashboards/' + record.id, { waitUntil: 'domcontentloaded' });
  for (const [index, content] of ['标题改为销售总额', '2'].entries()) {
    await page
      .locator('[data-dashboard-widget-id]')
      .nth(index)
      .getByRole('button', { name: '批注此组件', exact: true })
      .click();
    const dialog = page.getByRole('dialog', { name: '看板批注', exact: true });
    await dialog.getByRole('textbox', { name: '批注内容' }).fill(content);
    await dialog.getByRole('button', { name: '保存批注', exact: true }).click();
  }
  const panel = page.getByTestId('dashboard-assistant-panel');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('请补充需要解释的计算口径。', { exact: true })).toBeVisible();
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(1);
  expect(state.created).toHaveLength(1);
  expect(state.created[0].target.widget_id).toBe(record.schema.widgets[0].id);
  state.clarify = false;
  await panel.getByRole('textbox').fill('剩下的标题改为门店数量');
  await panel.getByRole('button', { name: '发送消息', exact: true }).click();
  await expect(panel.getByText('2 项修改待确认', { exact: true })).toBeVisible();
  await expect(panel.getByTestId('annotation-composer-item')).toHaveCount(0);
  expect(state.created).toHaveLength(2);
  expect(state.created[1].target.widget_id).toBe(record.schema.widgets[1].id);
});

test('editor and SQL panes resize independently, remember widths and fit compact screens', async ({ page }) => {
  const { record } = await setup(page);
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto('/dashboards/' + record.id, { waitUntil: 'domcontentloaded' });
  const library = page.getByTestId('dashboard-component-library');
  const settings = page.getByTestId('dashboard-settings-panel');
  const left = page.getByRole('separator', { name: '调整左侧编辑栏宽度' });
  const right = page.getByRole('separator', { name: '调整右侧设置与 SQL 栏宽度' });
  const width = async (locator: typeof library) => Math.round((await locator.boundingBox())!.width);
  const drag = async (locator: typeof left, delta: number) => {
    const box = (await locator.boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + 150);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + delta, box.y + 150, { steps: 12 });
    await page.mouse.up();
  };
  await expect(left).toBeVisible();
  const initialRight = await width(settings);
  const initialLeft = await width(library);
  await drag(left, 120);
  await expect.poll(() => width(library)).toBe(initialLeft + 120);
  expect(await width(settings)).toBe(initialRight);
  await drag(right, -110);
  await expect.poll(() => width(settings)).toBe(initialRight + 110);
  await page.reload();
  await expect.poll(() => width(library)).toBe(initialLeft + 120);
  await expect.poll(() => width(settings)).toBe(initialRight + 110);
  await library.getByText('AI 助手', { exact: true }).click();
  await drag(left, 70);
  const assistantWidth = await width(library);
  await page.locator('[data-dashboard-widget-id]').first().getByRole('button', { name: 'SQL 与参数设置' }).click();
  await expect(right).toBeVisible();
  const initialSql = await width(settings);
  await drag(right, -80);
  await expect.poll(() => width(settings)).toBe(initialSql + 80);
  await right.focus();
  await right.press('ArrowRight');
  await expect.poll(() => width(settings)).toBe(initialSql + 70);
  await library.getByText('AI 助手', { exact: true }).click();
  await expect.poll(() => width(library)).toBe(assistantWidth);
  await page.screenshot({ path: path.join(output, 'resizable-assistant-sql.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '展开组件库', exact: true }).click();
  await expect.poll(() => width(library)).toBeLessThanOrEqual(346);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('folders have their own top tab and test/archive lists stay inside all dashboards', async ({ page }) => {
  await setup(page);
  await page.goto('/dashboards/?tab=all', { waitUntil: 'domcontentloaded' });
  const top = page.getByRole('navigation', { name: '看板分类', exact: true });
  const all = page.getByRole('navigation', { name: '全部看板分类', exact: true });
  await expect(top.getByRole('button', { name: '所有文件夹', exact: true })).toBeVisible();
  await expect(top.getByRole('button', { name: '验收测试' })).toHaveCount(0);
  await expect(top.getByRole('button', { name: '已归档' })).toHaveCount(0);
  await all.getByRole('button', { name: '验收测试' }).click();
  await expect(top.getByRole('button', { name: '全部看板' })).toHaveAttribute('aria-pressed', 'true');
  await all.getByRole('button', { name: '已归档' }).click();
  await expect(page).toHaveURL(/tab=archived/);
  await top.getByRole('button', { name: '所有文件夹', exact: true }).click();
  await expect(all).toHaveCount(0);
  await page.screenshot({ path: path.join(output, 'folders-top-tab.png'), fullPage: true });
});
