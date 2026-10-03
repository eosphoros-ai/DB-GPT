import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const dashboardId = process.env.DASHBOARD_E2E_FRED_DASHBOARD_ID;
const editedTitle = 'FRED 美国零售销售监测（已编辑）';

test.describe('FRED public time-series generalization', () => {
  test.setTimeout(300_000);
  test.skip(
    process.env.DASHBOARD_E2E_LIVE_AGENT !== '1' || !dashboardId,
    'Set the live Agent flag and generated FRED dashboard id.',
  );

  test('edits, refreshes, inspects anomalies, exports, publishes, and captures both widths', async ({
    page,
    context,
  }) => {
    const evidenceDir = path.resolve(process.cwd(), '../docs/dashboard/evidence/v9-migration');
    mkdirSync(evidenceDir, { recursive: true });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/dashboards/${encodeURIComponent(dashboardId!)}`);
    const titleInput = page.getByRole('textbox', { name: '看板标题' });
    await expect(titleInput).toBeVisible({ timeout: 30_000 });
    for (const title of ['最新月销售额', '月度销售趋势', '同比增长率趋势']) {
      await expect(page.getByText(title, { exact: true })).toBeVisible();
    }

    if ((await titleInput.inputValue()) !== editedTitle) {
      await titleInput.fill(editedTitle);
      await page.getByRole('button', { name: '保存看板', exact: true }).click();
      await expect(page.getByText('草稿已保存', { exact: true })).toBeVisible();
    }

    const refreshResponse = page.waitForResponse(
      response =>
        response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/refresh'),
      { timeout: 180_000 },
    );
    await page.getByRole('button', { name: '刷新看板数据', exact: true }).click();
    const refresh = await refreshResponse;
    expect(refresh.ok()).toBe(true);
    const refreshPayload = await refresh.json();
    expect(refreshPayload.data.widgets.widget_l1_kpi.rows).toEqual([['2026-07-01', 763602]]);
    expect(refreshPayload.data.widgets.widget_l2_trend.rows).toHaveLength(415);
    expect(refreshPayload.data.widgets.widget_l2_trend.rows.at(-1)).toEqual(['2026-07-01', 763602]);
    expect(refreshPayload.data.widgets.widget_l3_yoy.rows.at(-1)).toEqual(['2026-07-01', 5.01]);

    const anomalyEvidence = page.getByTestId('dashboard-anomaly-evidence').first();
    await expect(anomalyEvidence).toBeVisible();
    await anomalyEvidence.getByText('检测到 1 条异常', { exact: true }).click();
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
      await expect(anomalyEvidence.getByText(label, { exact: true }).first()).toBeVisible();
    }
    await anomalyEvidence.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(evidenceDir, '20-fred-public-timeseries-1440.png'),
      fullPage: false,
      animations: 'disabled',
    });

    await page.setViewportSize({ width: 1024, height: 900 });
    await expect(page.getByRole('button', { name: '展开组件库' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: '展开属性设置' }).first()).toBeVisible();
    await anomalyEvidence.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(evidenceDir, '20-fred-public-timeseries-1024.png'),
      fullPage: false,
      animations: 'disabled',
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole('button', { name: '工程文件' }).click();
    await expect(page.getByText('看板工程文件', { exact: true })).toBeVisible();
    for (const file of ['dashboard.schema.json', 'dashboard.plan.json', 'README.md', 'manifest.json']) {
      await expect(page.getByText(file, { exact: true })).toBeVisible();
    }
    await expect(page.getByText(/queries\/.+\.sql/)).toHaveCount(3);
    const exportRequest = page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/export'));
    await page.getByRole('button', { name: 'ZIP 下载' }).click();
    await exportRequest;
    await page.locator('.ant-drawer:visible .ant-drawer-close').last().click();

    const publishResponse = page.waitForResponse(
      response =>
        response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/publish'),
      { timeout: 180_000 },
    );
    await page.getByRole('button', { name: '发布看板', exact: true }).click();
    expect((await publishResponse).ok()).toBe(true);
    const shareLink = page.locator('a[href*="/dashboard-share/"]').first();
    await expect(shareLink).toBeVisible();
    const href = await shareLink.getAttribute('href');
    expect(href).toBeTruthy();

    const anonymous = await context.browser()!.newContext();
    const publicPage = await anonymous.newPage();
    await publicPage.goto(new URL(href!, page.url()).href);
    await expect(publicPage.getByText(editedTitle, { exact: true })).toBeVisible();
    await expect(
      publicPage.getByText('这是发布时保存的只读数据快照；打开此页面不会连接或查询原始数据库。', {
        exact: true,
      }),
    ).toBeVisible();
    await expect(publicPage.getByText('月度销售趋势', { exact: true })).toBeVisible();
    await anonymous.close();
  });
});
