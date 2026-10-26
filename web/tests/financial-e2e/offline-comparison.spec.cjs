const { test, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '../../node_modules/.cache/financial-comparison');
const open = (page, name) => page.goto(pathToFileURL(path.join(root, name + '.html')).href);

test('English export keeps its selected language without changing report data', async ({ page }) => {
  await open(page, 'published-en');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByPlaceholder('Ask DB-GPT about this report')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Overview', exact: true })).toBeVisible();
  await expect(page.getByLabel('Comparison baseline', { exact: true })).toBeVisible();
  await page.getByPlaceholder('Ask DB-GPT about this report').fill('What does this report show?');
  await page.getByLabel('Send question', { exact: true }).click();
  await expect(page.getByText(/Offline snapshots cannot answer online questions/)).toBeVisible();
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'published-en.json'), 'utf8'));
  expect(await page.locator('#financial-report-data').textContent()).toBeTruthy();
  expect(JSON.parse(await page.locator('#financial-report-data').textContent())).toEqual(snapshot);
});

test('comparison controls, table headers and conflicts follow the dark theme', async ({ page }) => {
  await open(page, 'conflict');
  const baseline = page.getByLabel('比较基准', { exact: true });
  await expect(baseline).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.evaluate(() => document.documentElement.classList.add('dark'));
  await expect(baseline).toHaveCSS('background-color', 'rgb(17, 18, 23)');
  await expect(baseline).toHaveCSS('color', 'rgb(226, 230, 237)');
  const matrix = page.getByLabel('财务对比矩阵，可横向滚动');
  await expect(matrix.locator('thead th').first()).toHaveCSS('background-color', 'rgb(26, 28, 35)');
  await expect(matrix.locator('td[data-status="conflict"]').first()).toHaveCSS('background-color', 'rgb(48, 38, 27)');
  await page.screenshot({ path: path.join(root, 'comparison-dark.png'), fullPage: true });
});

test('offline report shows readable financial citation labels without application URLs', async ({ page }) => {
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'published.json'), 'utf8'));
  const label = 'OFFLINE_EVIDENCE_LABEL';
  snapshot.agent.summary = `**Verified finding** [${label}](#financial-report/${snapshot.report.run.id}/fact/revenue?revision=saved)`;
  const html = fs.readFileSync(path.join(root, 'published.html'), 'utf8').replace(
    /(<script type="application\/json" id="financial-report-data">)[\s\S]*?(<\/script>)/,
    (_, start, end) => start + JSON.stringify(snapshot).replace(/</g, '\\u003c') + end,
  );
  const target = path.join(root, 'citation-labels.html');
  fs.writeFileSync(target, html);
  await page.goto(pathToFileURL(target).href);
  await expect(page.getByText(new RegExp(label)).first()).toBeVisible();
  expect(await page.locator('body').innerText()).not.toContain('#financial-report/');
  expect(await page.locator('body').innerText()).not.toContain(`[${label}](`);
});

for (const state of ['normal', 'missing', 'conflict', 'incomparable', 'file-failure', 'analyzing', 'published']) {
  test(`offline formal comparison protocol: ${state}`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const network = [];
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await open(page, state);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('合成');
    await expect(page.getByLabel('财务对比矩阵，可横向滚动')).toBeVisible();
    if (state === 'missing') await expect(page.getByText('缺少可用数据').first()).toBeVisible();
    if (state === 'conflict') await expect(page.getByText('冲突 · 待核对').first()).toBeVisible();
    if (state === 'incomparable') await expect(page.getByText(/不可比：/).first()).toBeVisible();
    if (state === 'file-failure') await expect(page.getByText(/合成的文件提取失败/)).toBeVisible();
    if (state === 'published') await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
    if (state === 'analyzing') await expect(page.getByLabel('报告状态')).toHaveText('分析中');
    expect(network).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('difference expands both source documents and offline preview explains access', async ({ page }) => {
  await open(page, 'normal');
  await page.getByRole('button', { name: /较基准：/ }).first().click();
  await expect(page.getByText('确定性计算', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('a.pdf', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('b.pdf', { exact: false }).first()).toBeVisible();
  await page.getByRole('button', { name: /定位原文/ }).first().click();
  await expect(page.getByText(/原 PDF 预览和下载需要回到应用授权访问/)).toBeVisible();
});

test('mobile matrix scroll keeps evidence actions available', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, 'normal');
  const matrix = page.getByLabel('财务对比矩阵，可横向滚动');
  await expect(matrix).toBeVisible();
  expect(await matrix.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true);
  await matrix.evaluate(element => { element.scrollLeft = element.scrollWidth; });
  await page.getByRole('button', { name: /较基准：/ }).first().click();
  await expect(page.getByText('证据链', { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(root, 'mobile.png'), fullPage: true });
});

test('existing single-report offline workspace still renders', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await open(page, 'single');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('合成甲');
  await expect(page.getByRole('navigation', { name: '财务分析章节' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('saved real-PDF result preserves its actual state and both evidence sources offline', async ({ page }) => {
  test.skip(!fs.existsSync(path.join(root, 'real-peer.json')), 'Real acceptance snapshot is not available');
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'real-peer.json'), 'utf8'));
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await open(page, 'real-peer');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('浙江海翔药业');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('北方华锦');
  if (snapshot.workflow.status === 'published')
    await expect(page.getByLabel('报告状态')).toHaveText('报告已生成');
  else if (snapshot.lifecycle.stage === 'awaiting_revision')
    await expect(page.getByLabel('报告状态')).toHaveText('待修订 · 数据已保留');
  await page.getByRole('button', { name: /较基准：/ }).first().click();
  await expect(page.getByText('证据链', { exact: true })).toBeVisible();
  await page.screenshot({ path: path.join(root, 'real-peer.png'), fullPage: true });
  expect(errors).toEqual([]);
});
