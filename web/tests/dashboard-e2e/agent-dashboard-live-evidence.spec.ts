import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const dashboardId = process.env.DASHBOARD_E2E_DASHBOARD_ID;
const appleDashboardId = process.env.DASHBOARD_E2E_APPLE_DASHBOARD_ID;
const northwindDashboardId = process.env.DASHBOARD_E2E_NORTHWIND_DASHBOARD_ID;
const olistDashboardId = process.env.DASHBOARD_E2E_OLIST_DASHBOARD_ID;

test.describe('Live dashboard acceptance evidence', () => {
  test.setTimeout(180_000);
  test.skip(
    !dashboardId || process.env.DASHBOARD_E2E_LIVE_AGENT !== '1',
    'Set the live Agent flag and the generated dashboard id.',
  );

  test('captures the real model edit and naturally scheduled refresh at 1440 and 1024', async ({ page }) => {
    const evidenceDir = path.resolve(process.cwd(), '../docs/dashboard/evidence/v9-migration');
    mkdirSync(evidenceDir, { recursive: true });
    const capture = async (name: string) => {
      await page.screenshot({ path: path.join(evidenceDir, name), fullPage: false, animations: 'disabled' });
    };

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboards/${encodeURIComponent(dashboardId!)}`);
    await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue('Walmart 经营看板（已编辑）');
    await expect(page.getByText('累计销售额（真实模型修改）', { exact: true })).toBeVisible();
    await expect(page.getByText('月度销售趋势', { exact: true })).toBeVisible();
    await expect(page.getByText('门店销售排行', { exact: true })).toBeVisible();
    const timeSeriesResponse = page.waitForResponse(
      response =>
        response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/refresh'),
      { timeout: 180_000 },
    );
    await page.getByRole('button', { name: '刷新看板数据', exact: true }).click();
    const timeSeriesRefresh = await timeSeriesResponse;
    expect(timeSeriesRefresh.ok()).toBe(true);
    const timeSeriesPayload = await timeSeriesRefresh.json();
    const monthlyTrend = timeSeriesPayload.data.widgets.widget_monthly_trend;
    expect(monthlyTrend.columns).toEqual(['month', 'monthly_sales']);
    expect(monthlyTrend.rows).toHaveLength(33);
    expect(monthlyTrend.rows[0]).toEqual(['2010-02', 190332983.04]);
    expect(monthlyTrend.rows.at(-1)).toEqual(['2012-10', 184361680.42]);
    await capture('12-real-model-lifecycle-1440.png');

    await page.setViewportSize({ width: 1024, height: 900 });
    await expect(page.getByRole('button', { name: '展开组件库' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: '展开属性设置' }).first()).toBeVisible();
    await capture('12-real-model-lifecycle-1024.png');

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole('button', { name: '打开版本与分享' }).click();
    await expect(page.getByText('编辑修订 4', { exact: true })).toBeVisible();
    await expect(page.getByText('AI 提案应用', { exact: true })).toBeVisible();
    await capture('13-real-ai-edit-1440.png');
    await page.setViewportSize({ width: 1024, height: 900 });
    await capture('13-real-ai-edit-1024.png');

    await page.locator('.ant-drawer:visible .ant-drawer-close').click();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole('button', { name: '设置定时刷新' }).click();
    await expect(page.getByText('定时刷新与运行记录', { exact: true })).toBeVisible();
    await expect(page.getByText('Walmart 真实数据持续刷新验收', { exact: true })).toBeVisible();
    await expect(page.getByText('已暂停', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: /运行记录/ }).click();
    await expect(page.getByText('成功', { exact: true }).first()).toBeVisible();
    const successfulRun = page.getByText(/refreshed 3 widgets and published/).first();
    await expect(successfulRun).toBeVisible();
    await successfulRun.scrollIntoViewIfNeeded();
    await capture('14-continuous-refresh-1440.png');
    await page.setViewportSize({ width: 1024, height: 900 });
    await capture('14-continuous-refresh-1024.png');
  });

  test('captures the generalized Apple financial dashboard at 1440 and 1024', async ({ page }) => {
    test.skip(!appleDashboardId, 'Set the generated Apple dashboard id.');
    const evidenceDir = path.resolve(process.cwd(), '../docs/dashboard/evidence/v9-migration');
    mkdirSync(evidenceDir, { recursive: true });
    const capture = async (name: string) => {
      await page.screenshot({ path: path.join(evidenceDir, name), fullPage: false, animations: 'disabled' });
    };

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboards/${encodeURIComponent(appleDashboardId!)}`);
    await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue('Apple 财务看板（已编辑）');
    await expect(page.getByText('收入与利润趋势', { exact: true })).toBeVisible();
    await expect(page.getByText('产品收入结构', { exact: true })).toBeVisible();
    await expect(page.getByText('资产结构', { exact: true })).toBeVisible();
    await expect(page.getByText('财务明细表', { exact: true })).toBeVisible();
    await capture('15-apple-real-model-1440.png');

    await page.setViewportSize({ width: 1024, height: 900 });
    await expect(page.getByRole('button', { name: '展开组件库' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: '展开属性设置' }).first()).toBeVisible();
    await capture('15-apple-real-model-1024.png');
  });

  for (const scenario of [
    {
      name: 'Walmart',
      id: dashboardId,
      title: 'Walmart 经营看板（已编辑）',
      summary: '检测到 1 条异常',
      prefix: '19-walmart-timeseries-anomaly-evidence',
    },
    {
      name: 'Apple',
      id: appleDashboardId,
      title: 'Apple 财务看板（已编辑）',
      summary: '检测到 1 条异常',
      prefix: '16-apple-anomaly-evidence',
    },
    {
      name: 'Northwind',
      id: northwindDashboardId,
      title: 'Northwind 多文件泛化验收（已编辑）',
      summary: '检测到 3 条异常',
      prefix: '17-northwind-anomaly-evidence',
    },
    {
      name: 'Olist',
      id: olistDashboardId,
      title: 'Olist 泛化验收（通用路径）',
      summary: '检测到 3 条异常',
      prefix: '18-olist-anomaly-evidence',
    },
  ]) {
    test(`${scenario.name}: expands deterministic anomaly evidence at 1440 and 1024`, async ({ page }) => {
      test.skip(!scenario.id, `Set the generated ${scenario.name} dashboard id.`);
      const evidenceDir = path.resolve(process.cwd(), '../docs/dashboard/evidence/v9-migration');
      mkdirSync(evidenceDir, { recursive: true });

      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`/dashboards/${encodeURIComponent(scenario.id!)}`);
      await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue(scenario.title);
      const evidence = page.getByTestId('dashboard-anomaly-evidence').first();
      await expect(evidence).toBeVisible({ timeout: 180_000 });
      await expect(evidence.getByText(scenario.summary, { exact: true })).toBeVisible();
      await evidence.getByText(scenario.summary, { exact: true }).click();
      for (const label of [
        '当前值',
        '基线值',
        '绝对变化',
        '变化比例',
        '阈值',
        '当前时间范围',
        '基线时间范围',
        '样本量',
        '命中的规则',
      ]) {
        await expect(evidence.getByText(label, { exact: true }).first()).toBeVisible();
      }
      await evidence.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: path.join(evidenceDir, `${scenario.prefix}-1440.png`),
        fullPage: false,
        animations: 'disabled',
      });

      await page.setViewportSize({ width: 1024, height: 900 });
      await expect(page.getByRole('button', { name: '展开组件库' }).first()).toBeVisible();
      await expect(page.getByRole('button', { name: '展开属性设置' }).first()).toBeVisible();
      await evidence.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: path.join(evidenceDir, `${scenario.prefix}-1024.png`),
        fullPage: false,
        animations: 'disabled',
      });
    });
  }
});
