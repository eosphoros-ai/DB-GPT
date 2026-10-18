import { expect, test, type Page } from '@playwright/test';
import { readDashboardFixture } from './fixtures';

test.use({ actionTimeout: 20_000 });

async function setup(page: Page, holdFirstRefresh = false) {
  await page.clock.setFixedTime(new Date('2026-10-18T12:00:00Z'));
  let record = readDashboardFixture('walmart/record.json');
  const snapshot = readDashboardFixture('walmart/snapshot.json');
  record.schema.filters = [
    {
      id: 'review_dates',
      type: 'date_range',
      label: 'Review dates',
      field: 'Date',
      default: ['2020-01-01', '2020-01-31'],
      options: [],
      relative_date: { anchor: 'today', start_offset_days: -6, end_offset_days: 0 },
    },
  ];
  let release!: () => void;
  const firstRefresh = new Promise<void>(resolve => {
    release = resolve;
  });
  const filters: Array<Record<string, unknown>> = [];
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem('__db_gpt_lng_key', 'zh'));
  await page.route('**/api/**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname.replace(/\/$/, '');
    let data: unknown = [];
    if (pathname.endsWith('/collaboration-ticket')) {
      await route.fulfill({ status: 503, json: { detail: 'Fixture runs without collaboration' } });
      return;
    }
    if (pathname.endsWith('/dashboards/schema')) data = {};
    else if (pathname.endsWith('/refresh')) {
      const supplied = request.postDataJSON().filters;
      filters.push(supplied);
      if (holdFirstRefresh && filters.length === 1) await firstRefresh;
      data = { ...snapshot, dashboard_id: record.id, filters: supplied };
    } else if (pathname.endsWith('/operations')) {
      const operation = request.postDataJSON();
      const title = operation.operations.find((item: { path: string }) => item.path === '/dashboard/title').value;
      record = structuredClone(record);
      record.schema.dashboard.title = title;
      record.current_revision++;
      data = { dashboard: record, operation_id: operation.operation_id, rebased: false };
    } else if (pathname.endsWith('/' + record.id)) {
      data = record;
    }
    await route.fulfill({ json: { success: true, data } });
  });
  await page.goto(`/dashboards/${record.id}/`);
  await expect(page.getByRole('textbox', { name: '看板标题' })).toBeVisible();
  return { filters, errors, release, revision: record.current_revision };
}

test('manual date range matches requests through refresh and reset', async ({ page }) => {
  const state = await setup(page);
  await expect.poll(() => state.filters.length).toBe(1);
  await expect(page.getByRole('button', { name: '刷新看板数据' })).not.toHaveClass(/ant-btn-loading/);
  const inputs = page.locator('.ant-picker-input input');
  await expect(page.getByText('45 行', { exact: true })).toBeVisible();
  await inputs.nth(0).fill('2026-09-01');
  await inputs.nth(0).press('Tab');
  await inputs.nth(1).fill('2026-09-30');
  await inputs.nth(1).press('Tab');
  await page.getByText('全局筛选', { exact: true }).click();
  const selected = ['2026-09-01', '2026-09-30'];
  await expect.poll(() => state.filters.at(-1)?.review_dates).toEqual(selected);
  await expect(inputs.nth(0)).toHaveValue(selected[0]);
  await expect(inputs.nth(1)).toHaveValue(selected[1]);
  const count = state.filters.length;
  await page.getByRole('button', { name: '刷新看板数据' }).click();
  await expect.poll(() => state.filters.length).toBeGreaterThan(count);
  expect(state.filters.at(-1)?.review_dates).toEqual(selected);
  await page.getByRole('button', { name: /重置筛选/ }).click();
  await expect.poll(() => state.filters.at(-1)?.review_dates).not.toEqual(selected);
  expect(state.errors).toEqual([]);
});

test('saving during first fetch loads the saved revision and clears loading', async ({ page }) => {
  const state = await setup(page, true);
  try {
    await expect.poll(() => state.filters.length).toBe(1);
    await page.getByRole('textbox', { name: '看板标题' }).fill('Saved during first fetch');
    await page.getByRole('button', { name: '保存看板', exact: true }).click();
    await expect(page.getByText(`修订 ${state.revision + 1}`, { exact: true })).toBeVisible();
    await expect.poll(() => state.filters.length).toBe(2);
    await expect(page.getByRole('button', { name: '刷新看板数据' })).not.toHaveClass(/ant-btn-loading/);
    state.release();
    await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue('Saved during first fetch');
    expect(state.errors).toEqual([]);
  } finally {
    state.release();
  }
});
