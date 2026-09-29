import { expect, test, type Locator, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { readDashboardFixture } from './fixtures';

test.describe.configure({ mode: 'parallel' });
const saved = readDashboardFixture('northwind/record.json');
const snapshot = readDashboardFixture('northwind/snapshot.json');
const image =
  'data:image/png;base64,' +
  readFileSync(path.resolve(process.cwd(), 'public/dashboard-templates/v94/northwind-customers.png')).toString(
    'base64',
  );
const roles = [
  { id: 'date', label: '业务日期', column: 'purchased_on' },
  { id: 'segment', label: '筛选维度', column: 'country' },
  { id: 'category', label: '分类维度', column: 'customer_name' },
  { id: 'entity', label: '稳定客户标识', column: 'customer_id' },
  { id: 'record_id', label: '唯一订单编号', column: 'order_id' },
];

async function fixture(page: Page, preset = 'clarity', mode = 'light') {
  const record = structuredClone(saved);
  record.schema.dashboard.theme = { preset, mode, overrides: {} };
  const calls: { method: string; path: string; body?: any }[] = [];
  const state = {
    folders: [
      { id: 'business', name: '经营分析', count: 1 },
      { id: 'long', name: '长名称文件夹'.repeat(8), count: 0 },
    ],
    membership: 'business' as string | null,
    stale: true,
    image,
    queryError: false,
  };
  await page.addInitScript(
    ({ preset, mode }) => {
      localStorage.setItem('__db_gpt_lng_key', 'zh');
      localStorage.setItem('dbgpt.interface.theme', preset);
      localStorage.setItem('__db_gpt_theme_key', mode);
    },
    { preset, mode },
  );
  await page.route('**/api/**', async route => {
    const request = route.request(),
      url = new URL(request.url()),
      method = request.method();
    const body = ['POST', 'PUT'].includes(method) ? request.postDataJSON() : undefined;
    calls.push({ method, path: url.pathname, body: body?.image ? { ...body, image: '[PNG captured]' } : body });
    let data: any = [];
    if (url.pathname.endsWith('/datasources'))
      data = [{ db_name: 'own_orders', type: 'sqlite', params: { name: 'own_orders' } }];
    else if (url.pathname.includes('/datasets/by-conversation/')) data = null;
    else if (url.pathname.endsWith('/dashboard-folders')) {
      if (method === 'POST') {
        const folder = { id: 'new-folder', name: body.name, count: 0 };
        state.folders.push(folder);
        data = folder;
      } else data = state.folders.map(f => ({ ...f, count: state.membership === f.id ? 1 : 0 }));
    } else if (url.pathname.includes('/dashboard-folders/')) {
      const id = url.pathname.split('/').at(-1);
      if (method === 'DELETE') {
        state.folders = state.folders.filter(f => f.id !== id);
        if (state.membership === id) state.membership = null;
        data = { deleted: true };
      } else {
        const folder = state.folders.find(f => f.id === id)!;
        folder.name = body.name;
        data = folder;
      }
    } else if (url.pathname.endsWith('/folder')) {
      state.membership = body.folder_id;
      data = { moved: true };
    } else if (url.pathname.endsWith('/dashboards/page')) {
      const folder = url.searchParams.get('folder_id');
      const visible =
        !folder ||
        folder === '__main__' ||
        (folder === 'unfiled' ? state.membership === null : state.membership === folder);
      data = {
        items: visible
          ? [
              {
                id: record.id,
                title: record.schema.dashboard.title,
                description: '按首次购买观察客户复购留存',
                data_source_id: 'own_orders',
                current_revision: record.current_revision,
                status: 'draft',
                updated_at: record.updated_at,
              },
            ]
          : [],
        total: visible ? 1 : 0,
      };
    } else if (url.pathname.endsWith('/cover')) {
      if (method === 'PUT') {
        expect(body.expected_revision).toBe(record.current_revision);
        expect(body.image).toMatch(/^data:image\/png;base64,/);
        state.image = body.image;
        state.stale = false;
        data = { saved: true };
      } else data = { available: true, image: state.image, revision: record.current_revision, stale: state.stale };
    } else if (url.pathname.includes('/dashboard-catalog/') && url.pathname.endsWith('/features')) {
      data = { widgets: record.schema.widgets, prompt: '按客户订单分析复购留存' };
    } else if (url.pathname.includes('/dashboard-catalog/') && url.pathname.endsWith('/source')) {
      data = {
        data_source_id: 'own_orders',
        dialect: 'sqlite',
        tables: [{ name: 'my_orders', columns: roles.map(r => ({ name: r.column, type: 'TEXT' })) }],
        roles: roles.map(r => ({ ...r, required: true, hint: '匹配实际业务字段' })),
        grain: 'order',
        builtin_available: false,
      };
    } else if (url.pathname.includes('/dashboard-catalog/') && url.pathname.endsWith('/preview')) {
      data = {
        schema: record.schema,
        snapshot,
        validation: { records: 830, widgets: 4, filter_checks: 3, publication_equivalent: true, grain: 'order' },
      };
    } else if (url.pathname.endsWith('/refresh') || url.pathname.endsWith('/snapshot')) {
      if (state.queryError)
        return route.fulfill({ status: 503, json: { success: false, err_msg: '验证查询暂时不可用' } });
      data = snapshot;
    } else if (url.pathname.endsWith('/' + record.id)) data = record;
    return route.fulfill({ json: { success: true, data } });
  });
  return { calls, state, record };
}

async function select(page: Page, label: string, text: string) {
  const input = page.getByRole('combobox', { name: label, exact: true });
  await input.locator('..').locator('..').click();
  if ((await input.getAttribute('readonly')) === null) await input.fill(text);
  await page
    .locator('.ant-select-dropdown:visible .ant-select-item-option-content')
    .filter({ hasText: text })
    .first()
    .click();
}

async function fit(page: Page, targets: Locator) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  const rects = await targets.evaluateAll(nodes =>
    nodes.flatMap(node => {
      const r = node.getBoundingClientRect();
      return r.width && r.height
        ? [
            {
              label: node.getAttribute('aria-label') || node.textContent,
              x: r.x,
              y: r.y,
              right: r.right,
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

async function cohortContrast(page: Page) {
  const result = await page
    .getByRole('table', { name: '客户首购与复购留存矩阵' })
    .locator('td[data-observed="true"]')
    .first()
    .evaluate(cell => {
      const canvas = document.createElement('canvas');
      canvas.width = 1;
      canvas.height = 1;
      const ctx = canvas.getContext('2d')!;
      const luminance = (color: string) => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 1, 1);
        return [...ctx.getImageData(0, 0, 1, 1).data]
          .slice(0, 3)
          .map(n => n / 255)
          .map(n => (n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4))
          .reduce((s, n, i) => s + n * [0.2126, 0.7152, 0.0722][i], 0);
      };
      const style = getComputedStyle(cell),
        fg = style.color,
        bg = style.backgroundColor;
      const a = luminance(fg),
        b = luminance(bg);
      return { fg, bg, contrast: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) };
    });
  expect(result.contrast, JSON.stringify(result)).toBeGreaterThanOrEqual(4.5);
  return result;
}

for (const width of [1440, 360, 390])
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm'])
    for (const mode of ['light', 'dark']) {
      test(`v94 workspace ${preset} ${mode} ${width}`, async ({ page }, info) => {
        await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
        const { calls, record, state } = await fixture(page, preset, mode);
        const errors: string[] = [];
        page.on('pageerror', e => errors.push(e.message));
        const shot = async (name: string) => {
          const file = info.outputPath(name + '.png');
          await page.screenshot({ path: file, animations: 'disabled' });
          await info.attach(name, { path: file, contentType: 'image/png' });
        };
        await page.goto('/dashboards/?tab=folders');
        await expect(page.getByRole('button', { name: '打开文件夹 经营分析', exact: true })).toBeVisible();
        await expect(page.locator('[aria-label="文件夹列表"] button').first()).toHaveAttribute(
          'aria-label',
          '新建文件夹',
        );
        await fit(page, page.locator('[aria-label="文件夹列表"] button'));
        expect(calls.filter(r => r.path.endsWith('/dashboards/page') || r.path.endsWith('/refresh'))).toHaveLength(0);
        await shot('folder-workspace');
        await page.getByRole('button', { name: '打开文件夹 经营分析', exact: true }).click();
        await expect(page.getByRole('img', { name: record.schema.dashboard.title + '实际渲染预览' })).toBeVisible();
        await expect.poll(() => state.stale).toBe(false);
        expect(calls.filter(r => r.path.endsWith('/refresh'))).toHaveLength(1);
        await fit(page, page.locator('[aria-label="看板文件夹"] button'));
        await shot('cached-cover');
        await page.getByRole('button', { name: record.schema.dashboard.title + '更多操作' }).click();
        await page.getByRole('menuitem', { name: '移动到文件夹', exact: true }).click();
        await expect(page.getByRole('combobox', { name: '目标文件夹', exact: true })).toBeVisible();
        await fit(page, page.locator('.ant-modal-footer button'));
        await shot('move-folder');
        await page
          .getByRole('dialog')
          .getByRole('button', { name: /^取\s*消$/ })
          .click();
        await page.goto('/dashboards/');
        await page.getByRole('button', { name: '预览模板 客户订购分析', exact: true }).click();
        await page.getByRole('radio', { name: /手动匹配字段/ }).check();
        await select(page, '业务明细表', 'my_orders');
        for (const role of roles) await select(page, '匹配' + role.label, 'my_orders.' + role.column);
        await page.getByRole('textbox', { name: '主要数值单位', exact: true }).fill('单');
        await page.getByRole('checkbox').check();
        await fit(page, page.locator('.ant-modal-footer button'));
        await shot('field-mapping');
        await page.getByRole('button', { name: '验证并预览', exact: true }).click();
        await expect(page.getByRole('table', { name: '客户首购与复购留存矩阵' })).toBeVisible();
        await fit(page, page.locator('.ant-modal-footer button'));
        const contrast = await cohortContrast(page);
        await shot('cohort-preview');
        const matrix = page.locator('[aria-label="留存矩阵，可横向查看后续周期"]');
        await matrix.evaluate(e => {
          e.scrollLeft = e.scrollWidth;
          e.scrollTop = e.scrollHeight;
        });
        await expect(matrix.getByText('未到期', { exact: true }).last()).toBeVisible();
        await shot('future-cohort-cells');
        expect(errors).toEqual([]);
        await info.attach('observations', {
          body: JSON.stringify({ preset, mode, width, contrast, errors, requests: calls }),
          contentType: 'application/json',
        });
      });
    }

test('v94 folders create, move, rename and delete preserve the dashboard', async ({ page }) => {
  const { state, record } = await fixture(page);
  await page.goto('/dashboards/?tab=folders');
  await page.getByRole('button', { name: '新建文件夹', exact: true }).click();
  await page.getByRole('textbox', { name: '文件夹名称' }).fill('我的留存分析');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^确\s*定$/ })
    .click();
  await expect(page.getByRole('button', { name: '打开文件夹 我的留存分析', exact: true })).toBeVisible();
  await page
    .getByRole('navigation', { name: '看板分类' })
    .getByRole('button', { name: '全部看板', exact: true })
    .click();
  await page.getByRole('button', { name: record.schema.dashboard.title + '更多操作' }).click();
  await page.getByRole('menuitem', { name: '移动到文件夹', exact: true }).click();
  await select(page, '目标文件夹', '我的留存分析');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^移\s*动$/ })
    .click();
  await expect.poll(() => state.membership).toBe('new-folder');
  await page
    .getByRole('navigation', { name: '看板分类' })
    .getByRole('button', { name: '所有文件夹', exact: true })
    .click();
  const tile = page.getByRole('button', { name: '打开文件夹 我的留存分析', exact: true });
  await expect(tile).toContainText('1 个看板');
  await tile.click();
  await page.getByRole('button', { name: '重命名文件夹', exact: true }).click();
  await page.getByRole('textbox', { name: '文件夹名称' }).fill('客户洞察');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^确\s*定$/ })
    .click();
  await expect.poll(() => state.folders.find(f => f.id === 'new-folder')?.name).toBe('客户洞察');
  await page.getByRole('button', { name: '删除文件夹', exact: true }).click();
  await page.getByRole('button', { name: /^确\s*定$/ }).click();
  await expect.poll(() => state.membership).toBeNull();
  await page
    .getByRole('navigation', { name: '看板分类' })
    .getByRole('button', { name: '全部看板', exact: true })
    .click();
  await expect(page.getByRole('button', { name: '打开看板 ' + record.schema.dashboard.title })).toBeVisible();
});

test('v94 stale cover refresh saves a PNG once and creates no dashboard revision', async ({ page }) => {
  const { state, calls } = await fixture(page);
  await page.goto('/dashboards/?tab=folders');
  await page
    .getByRole('navigation', { name: '看板分类' })
    .getByRole('button', { name: '全部看板', exact: true })
    .click();
  await expect.poll(() => state.stale).toBe(false);
  await expect(page.getByText('历史预览 · 待更新')).toHaveCount(0);
  expect(calls.filter(r => r.path.endsWith('/refresh'))).toHaveLength(1);
  expect(calls.filter(r => r.method === 'PUT' && r.path.endsWith('/cover'))).toHaveLength(1);
  expect(calls.filter(r => r.method === 'PUT' && !r.path.endsWith('/cover'))).toHaveLength(0);
});

test('v94 failed cover refresh preserves the previous real preview', async ({ page }) => {
  const { state, calls, record } = await fixture(page);
  state.queryError = true;
  await page.goto('/dashboards/?tab=folders');
  await page
    .getByRole('navigation', { name: '看板分类' })
    .getByRole('button', { name: '全部看板', exact: true })
    .click();
  await expect(page.getByRole('img', { name: record.schema.dashboard.title + '实际渲染预览' })).toBeVisible();
  await expect(page.getByText('预览更新失败 · 已保留原图')).toBeVisible();
  await expect(page.getByRole('img', { name: record.schema.dashboard.title + '实际渲染预览' })).toBeVisible();
  expect(state.stale).toBe(true);
  expect(calls.filter(r => r.method === 'PUT')).toHaveLength(0);
});
