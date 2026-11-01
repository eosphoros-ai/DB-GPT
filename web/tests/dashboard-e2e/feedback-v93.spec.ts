import { expect, test, type Locator, type Page } from '@playwright/test';
import { readDashboardFixture } from './fixtures';

test.describe.configure({ mode: 'parallel' });
const saved = readDashboardFixture('retail/record.json');
const snapshot = readDashboardFixture('retail/snapshot.json');

async function mock(page: Page, preset: string, mode: string) {
  const record = structuredClone(saved);
  record.schema.dashboard.theme = { preset, mode, overrides: {} };
  const folders = [
    { id: 'personal-apple', name: 'Apple 财务分析', count: 1 },
    { id: 'long-folder', name: '长名称文件夹'.repeat(10), count: 0 },
  ];
  await page.route('**/api/**', route => {
    const url = new URL(route.request().url());
    let data: any = [];
    if (url.pathname.includes('/public/dashboards/'))
      data = {
        dashboard_id: record.id,
        published_revision: 1,
        published_at: record.updated_at,
        schema: record.schema,
        snapshot,
        data_mode: 'live',
        refresh_interval: 60,
        unsupported_widget_ids: [],
      };
    else if (url.pathname.endsWith('/model/types')) data = ['deepseek-v4-flash'];
    else if (url.pathname.includes('/datasources'))
      data = [{ db_name: 'Walmart_Sales', params: { name: 'Walmart_Sales' } }];
    else if (url.pathname.endsWith('/dashboard-folders')) data = folders;
    else if (url.pathname.endsWith('/dashboards/page'))
      data = {
        items: [
          {
            id: record.id,
            title: record.schema.dashboard.title,
            data_source_id: 'Walmart_Sales',
            description: '真实数据布局',
            current_revision: 1,
            status: 'draft',
            updated_at: record.updated_at,
          },
        ],
        total: 1,
      };
    else if (url.pathname.endsWith('/live-share')) data = { active: true, published_revision: 1 };
    else if (url.pathname.endsWith('/' + record.id)) data = record;
    else if (url.pathname.endsWith('/refresh') || url.pathname.endsWith('/snapshot')) data = snapshot;
    else if (url.pathname.includes('/datasets/by-conversation/')) data = null;
    return route.fulfill({ json: { success: true, data } });
  });
  await page.addInitScript(
    ({ preset, mode }) => {
      localStorage.setItem('__db_gpt_lng_key', 'zh');
      localStorage.setItem('dbgpt.interface.theme', preset);
      // Deliberately oppose the dashboard mode: body-mounted portals must use the dashboard theme.
      localStorage.setItem('__db_gpt_theme_key', mode === 'dark' ? 'light' : 'dark');
    },
    { preset, mode },
  );
  return record;
}

test('component library survives transient viewport changes and collapses at a settled narrow width', async ({
  page,
}, info) => {
  const record = await mock(page, 'ocean', 'dark');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/dashboards/' + record.id + '/');
  const search = page.getByRole('textbox', { name: '搜索图表类型' });
  await expect(search).toBeVisible();
  await search.fill('折线');
  // Reproduce a brief viewport transition without asking the user to reopen the library.
  await page.setViewportSize({ width: 1024, height: 1000 });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(250);
  await expect(search).toBeVisible();
  await expect(search).toHaveValue('折线');
  await page.screenshot({ path: info.outputPath('library-stable.png'), fullPage: true, animations: 'disabled' });
  await expect(search).toBeVisible();
  await expect(search).toHaveValue('折线');
  await page.setViewportSize({ width: 1024, height: 1000 });
  await expect(search).toBeHidden();
  await page.getByRole('button', { name: '展开组件库', exact: true }).first().click();
  await expect(search).toBeVisible();
  await expect(search).toHaveValue('折线');
});

test('filter changes query data automatically and preserve unrelated unsaved edits', async ({ page }) => {
  const record = await mock(page, 'clarity', 'light');
  const requests: { method: string; path: string; body: any }[] = [];
  await page.route('**/api/v1/dashboards/' + record.id + '/widgets/*/preview', route => {
    const id = new URL(route.request().url()).pathname.split('/').at(-2)!;
    return route.fulfill({ json: { success: true, data: snapshot.widgets[id] } });
  });
  page.on('request', request => {
    if (request.url().includes('/api/v1/dashboards/' + record.id) && request.method() !== 'GET') {
      requests.push({ method: request.method(), path: new URL(request.url()).pathname, body: request.postDataJSON() });
    }
  });
  await page.goto('/dashboards/' + record.id + '/');
  await expect(page.getByRole('textbox', { name: '看板标题' })).toBeVisible();
  const selectYear = async (year: string) => {
    await page
      .locator('.ant-select')
      .filter({ has: page.getByRole('combobox', { name: '年份筛选', exact: true }) })
      .locator('.ant-select-selector')
      .click();
    await page
      .locator('.ant-select-dropdown:visible .ant-select-item-option-content')
      .getByText(year, { exact: true })
      .click();
  };
  await selectYear('2010');
  await expect
    .poll(() => requests.filter(r => r.path.endsWith('/refresh') && r.body.filters.year === '2010').length)
    .toBe(1);
  await page.getByRole('textbox', { name: '看板标题' }).fill('尚未保存的标题');
  await selectYear('2011');
  await expect
    .poll(() => requests.filter(r => r.path.endsWith('/preview') && r.body.filters.year === '2011').length)
    .toBe(record.schema.widgets.length);
  // Private cover cache does not save the dashboard or create a revision.
  expect(requests.filter(r => r.method === 'PUT' && !r.path.endsWith('/cover'))).toHaveLength(0);
  await expect(page.getByRole('textbox', { name: '看板标题' })).toHaveValue('尚未保存的标题');
  for (const r of requests.filter(r => r.path.endsWith('/preview')))
    expect(r.body.schema.dashboard.title).toBe('尚未保存的标题');
});

async function legible(locator: Locator) {
  const measured = await locator.evaluate(element => {
    const read = (v: string) => (v.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const lum = (v: string) =>
      read(v)
        .map(n => n / 255)
        .map(n => (n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4))
        .reduce((s, n, i) => s + n * [0.2126, 0.7152, 0.0722][i], 0);
    let node: Element | null = element,
      bg = '';
    while (node) {
      const value = getComputedStyle(node).backgroundColor;
      if (value !== 'transparent' && !value.endsWith(', 0)')) {
        bg = value;
        break;
      }
      node = node.parentElement;
    }
    const fg = getComputedStyle(element).color;
    const lights = [lum(fg), lum(bg)].sort((a, b) => b - a);
    return {
      text: element.textContent,
      foreground: fg,
      background: bg,
      contrast: (lights[0] + 0.05) / (lights[1] + 0.05),
    };
  });
  expect(measured.contrast, JSON.stringify(measured)).toBeGreaterThanOrEqual(4.5);
  return measured;
}

async function fit(page: Page, controls: Locator) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  const rects = await controls.evaluateAll(nodes =>
    nodes.flatMap(node => {
      const r = node.getBoundingClientRect();
      return r.width && r.height
        ? [
            {
              label: node.getAttribute('aria-label') || node.textContent,
              x: r.x,
              right: r.right,
              y: r.y,
              bottom: r.bottom,
            },
          ]
        : [];
    }),
  );
  for (const r of rects) {
    expect(r.x, String(r.label)).toBeGreaterThanOrEqual(-1);
    expect(r.right, String(r.label)).toBeLessThanOrEqual(page.viewportSize()!.width + 1);
  }
  for (let i = 0; i < rects.length; i++)
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i],
        b = rects[j];
      expect(
        Math.min(a.right, b.right) - Math.max(a.x, b.x) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > 1,
        `${a.label} overlaps ${b.label}`,
      ).toBe(false);
    }
}

for (const width of [1440, 360, 390])
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm'])
    for (const mode of ['light', 'dark']) {
      test(`feedback portals ${preset} ${mode} ${width}`, async ({ page }, info) => {
        await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
        const record = await mock(page, preset, mode),
          errors: string[] = [],
          contrast = [];
        page.on('pageerror', e => errors.push(e.message));
        const shot = async (name: string) => {
          const file = info.outputPath(name + '.png');
          await page.screenshot({ path: file, animations: 'disabled' });
          await info.attach(name, { path: file, contentType: 'image/png' });
        };
        await page.goto('/dashboard-share/v93-theme-proof/');
        await page
          .locator('.ant-select')
          .filter({ has: page.getByRole('combobox', { name: '年份筛选', exact: true }) })
          .locator('.ant-select-selector')
          .click();
        const option = page
          .locator('.ant-select-dropdown:visible .ant-select-item-option-content')
          .filter({ hasText: /^2010$/ });
        await expect(option).toBeVisible();
        contrast.push(await legible(option));
        await fit(page, page.locator('.ant-select-dropdown:visible .ant-select-item-option'));
        await shot('public-year-options');
        await page.goto(`/dashboards/${record.id}/`);
        await expect(page.getByRole('textbox', { name: '看板标题' })).toBeVisible();
        const expand = page.getByRole('button', { name: '展开组件库', exact: true }).first();
        if (width < 1060) await expand.click();
        await page.getByRole('button', { name: '让数据助理配置筛选器 年份', exact: true }).first().click();
        const overlay = page.getByTestId('dashboard-annotation-overlay');
        await expect(overlay).toBeVisible();
        await overlay.getByRole('button', { name: /^取\s*消$/ }).hover();
        contrast.push(
          await legible(
            overlay
              .getByRole('button', { name: /^取\s*消$/ })
              .locator('span')
              .last(),
          ),
        );
        contrast.push(await legible(overlay.locator('.ant-input-data-count')));
        const countBox = await overlay.locator('.ant-input-data-count').boundingBox();
        const actionBox = await overlay.getByRole('button', { name: /^取\s*消$/ }).boundingBox();
        expect(actionBox!.y - (countBox!.y + countBox!.height)).toBeGreaterThanOrEqual(8);
        await fit(page, overlay.locator('button'));
        await shot('annotation-controls');
        await page.getByRole('button', { name: '关闭批注' }).click();
        await page.getByRole('button', { name: /更多/ }).click();
        await page.getByRole('menuitem', { name: /版本与分享/ }).click();
        await expect(page.getByText('编辑版本、发布历史与分享', { exact: true })).toBeVisible();
        await expect
          .poll(async () => {
            const box = await page.locator('.ant-drawer-content-wrapper').boundingBox();
            return (box?.x || 0) + (box?.width || 0);
          })
          .toBeLessThanOrEqual(width + 1);
        await fit(page, page.locator('.ant-drawer-content-wrapper button:visible'));
        contrast.push(
          await legible(page.getByRole('button', { name: '发布与分享', exact: true }).locator('span').last()),
        );
        await shot('live-share-controls');
        await page.goto('/dashboards/?tab=folders');
        await expect(page.getByRole('button', { name: '打开文件夹 Apple 财务分析', exact: true })).toBeVisible();
        await fit(page, page.locator('[aria-label="看板文件夹"] button'));
        await page.getByRole('button', { name: '新建文件夹', exact: true }).click();
        await page.getByRole('textbox', { name: '文件夹名称' }).fill('我的经营分析');
        await fit(page, page.getByRole('dialog').locator('button'));
        await shot('folder-dialog');
        expect(errors).toEqual([]);
        await info.attach('contrast-and-theme', {
          body: JSON.stringify({ preset, mode, width, contrast, errors }),
          contentType: 'application/json',
        });
      });
    }
