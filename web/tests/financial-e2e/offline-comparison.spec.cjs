const { test, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');

const root = path.resolve(__dirname, '../../node_modules/.cache/financial-comparison');
const open = (page, name) => page.goto(pathToFileURL(path.join(root, name + '.html')).href);

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
