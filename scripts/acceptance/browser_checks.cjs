'use strict';

async function openEditor(h, record) {
  const { page, expect } = h;
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/dashboards/${record.id}/`);
  await expect(page.getByRole('textbox', { name: '看板标题', exact: true })).toBeVisible();
  const [response] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(`/${record.id}/refresh`)),
    page.getByRole('button', { name: '刷新看板数据', exact: true }).click(),
  ]);
  const data = await response.json();
  h.assert.equal(data.success, true);
  for (const result of Object.values(data.data.widgets)) h.assert.equal(result.error, null);
  await expect(page.locator('[data-dashboard-widget-id]')).toHaveCount(record.schema.widgets.length);
}
async function save(h) {
  const [response] = await Promise.all([
    h.page.waitForResponse(r => ['POST', 'PUT'].includes(r.request().method()) && /\/dashboards\/[^/]+(?:\/operations)?$/.test(new URL(r.url()).pathname)),
    h.page.getByRole('button', { name: '保存看板', exact: true }).click(),
  ]);
  h.assert.equal(response.status(), 200);
  h.assert.equal((await response.json()).success, true);
  await h.expect(h.page.getByText('未保存', { exact: true })).toHaveCount(0);
}

async function settledBox(h, locator) {
  let last, stable = 0;
  await h.expect.poll(async () => {
    const box = await locator.boundingBox();
    stable = box && last && ['x', 'y', 'width', 'height'].every(k => Math.abs(box[k] - last[k]) < 0.5) ? stable + 1 : 0;
    last = box;
    return stable;
  }, { intervals: [100], timeout: 5000 }).toBeGreaterThanOrEqual(3);
  return last;
}

// Inspect G2's real canvas scene graph, as the repository's rendering tests do.
// This measures rendered content; no fake labels or production test hooks.
function readPlot(canvas) {
  const holder = canvas.parentElement;
  let fiber = holder[Object.keys(holder).find(key => key.startsWith('__reactFiber'))];
  for (let depth = 0; fiber && depth < 24; depth++, fiber = fiber.return) {
    for (let hook = fiber.memoizedState, count = 0; hook && count < 32; count++, hook = hook.next) {
      const plot = hook.memoizedState?.current;
      if (!plot?.chart?.getContext) continue;
      const root = plot.chart.getContext().canvas.document.documentElement;
      const rect = canvas.getBoundingClientRect();
      const measured = node => {
        const b = node.getBounds();
        return { text: String(node.style.text ?? ''), className: String(node.className), visible: node.isVisible(),
          min: [...b.min], max: [...b.max] };
      };
      return { width: rect.width, height: rect.height, x: rect.x, y: rect.y,
        labels: root.querySelectorAll('text').map(measured),
        elements: root.querySelectorAll('.element').map(measured) };
    }
  }
  return null;
}

exports.entryChecks = async h => {
  await h.run('A02', '三个业务模板、生成规划文案与需求带入', async () => {
    await h.page.goto('/dashboards/');
    for (const title of ['经营健康总览', '增长异常诊断', '区域干预优先级'])
      await h.expect(h.page.getByText(title, { exact: true })).toBeVisible();
    await h.expect(h.page.getByText('生成规划', { exact: true })).toHaveCount(3);
    await h.expect(h.page.getByLabel('布局模板', { exact: true })).toHaveCount(0);
    await h.shot('A02-templates-1440-evidence');
    await h.page.getByRole('button').filter({ hasText: '经营健康总览' }).click();
    const input = h.page.getByPlaceholder(/数据库|CSV|报告/).first();
    await h.expect(input).toBeVisible();
    await h.expect(input).not.toHaveValue('');
    h.artifact('api/A02-template-prompt.json', { url: h.page.url(), input: await input.inputValue(), submitted: false });
    await h.shot('A02-template-prompt-evidence');
  });
};

exports.editorChecks = async h => {
  const { page, expect, assert } = h;
  await h.run('D01', '真实组件标题编辑、SQL 定位与保存', async () => {
    const record = await h.read(h.requireCopy('Walmart'));
    await openEditor(h, record);
    const target = record.schema.widgets[0];
    const card = page.locator(`[data-dashboard-widget-id="${target.id}"]`);
    await card.getByRole('button', { name: '编辑可视化设置', exact: true }).click();
    const settings = page.getByTestId('dashboard-settings-panel');
    await expect(settings.getByLabel('标题', { exact: true })).toHaveValue(target.title);
    await settings.getByLabel('标题', { exact: true }).fill(target.title + '（自动验收）');
    await card.getByRole('button', { name: 'SQL 与参数设置', exact: true }).click();
    await expect(page.getByTestId('dashboard-query-sql-input')).toHaveValue(target.query.sql);
    await h.shot('D01-widget-and-sql-evidence');
    await save(h);
    const saved = await h.read(record);
    assert.equal(saved.schema.widgets[0].title, target.title + '（自动验收）');
    for (const other of record.schema.widgets.slice(1))
      assert.equal(saved.schema.widgets.find(w => w.id === other.id).title, other.title);
    const next = record.schema.widgets[1];
    await page.locator(`[data-dashboard-widget-id="${next.id}"]`).getByRole('button', { name: '编辑可视化设置', exact: true }).click();
    await expect(settings.getByLabel('标题', { exact: true })).toHaveValue(next.title);
  });
  await h.run('D03', '实际拖拽/缩放、撤销重做与保存重载', async () => {
    const record = await h.copy(h.requireCopy('Walmart').id, 'Layout'); await openEditor(h, record);
    for (const label of ['折叠属性设置', '折叠组件库']) {
      const button = page.getByRole('button', { name: label, exact: true });
      if (await button.isVisible()) await button.click();
    }
    const card = page.locator(`[data-dashboard-widget-id="${record.schema.widgets[0].id}"]`);
    const initial = await settledBox(h, card); await h.shot('D03-before-1440-evidence');
    const header = card.locator('.dashboard-widget-drag-handle');
    const box = await header.boundingBox();
    await page.mouse.move(box.x + 30, box.y + box.height / 2);
    await page.mouse.down(); await page.mouse.move(box.x + 160, box.y + 95, { steps: 15 }); await page.mouse.up();
    await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
    const dragged = await settledBox(h, card);
    assert(Math.abs(dragged.x - initial.x) > 5 || Math.abs(dragged.y - initial.y) > 5, '拖拽后目标组件位置未变化');
    const gridItem = card.locator('..');
    const resize = gridItem.locator('.react-resizable-handle').first();
    await expect(resize).toBeAttached();
    const handle = await resize.boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down(); await page.mouse.move(handle.x + 70, handle.y + 90, { steps: 15 }); await page.mouse.up();
    const resized = await settledBox(h, card);
    h.artifact('api/D03-geometry-before-undo.json', { initial, dragged, resized });
    assert(Math.abs(resized.height - dragged.height) > 5 || Math.abs(resized.width - dragged.width) > 5, '缩放后实际尺寸未变化');
    await page.getByRole('button', { name: '撤销', exact: true }).click();
    await expect.poll(async () => {
      const undone = await card.boundingBox();
      return Math.max(Math.abs(undone.height - resized.height), Math.abs(undone.width - resized.width));
    }, { message: '撤销应在布局动画结束后恢复尺寸' }).toBeGreaterThan(5);
    const undone = await settledBox(h, card);
    assert(Math.abs(undone.height - dragged.height) <= 2 && Math.abs(undone.width - dragged.width) <= 2);
    await page.getByRole('button', { name: '重做', exact: true }).click();
    await expect.poll(async () => Math.abs((await card.boundingBox()).height - resized.height)).toBeLessThan(2);
    h.artifact('api/D03-geometry-after-undo-redo.json', { initial, dragged, resized, undone, redone: await settledBox(h, card) });
    await h.shot('D03-after-1440-evidence'); await save(h);
    const saved = await h.read(record); await page.reload();
    await expect(page.locator('[data-dashboard-widget-id]')).toHaveCount(3);
    const loaded = await h.read(record);
    assert.deepEqual(loaded.schema.layouts, saved.schema.layouts);
    assert(saved.current_revision > record.current_revision);
    await h.shot('D03-reloaded-1440-evidence');
  });
  await h.run('R03', '未保存离开提醒、浏览器断网保存失败与恢复', async () => {
    const record = await h.copy(h.requireCopy('Walmart').id, 'Offline'); await openEditor(h, record);
    const title = page.getByRole('textbox', { name: '看板标题', exact: true });
    const wanted = record.schema.dashboard.title + '-待保存'; await title.fill(wanted);
    const dialogPromise = page.waitForEvent('dialog', { timeout: 10000 });
    const reload = page.reload({ timeout: 10000 }).catch(() => {});
    const dialog = await dialogPromise; assert.equal(dialog.type(), 'beforeunload'); await dialog.dismiss(); await reload;
    await expect(title).toHaveValue(wanted);
    try {
      await h.context.setOffline(true);
      await page.getByRole('button', { name: '保存看板', exact: true }).click();
      await expect(page.getByText('未保存', { exact: true })).toBeVisible();
      await expect(page.locator('.ant-message-notice')).toContainText(/失败|网络|Network|连接/);
      await expect(title).toHaveValue(wanted); await h.shot('R03-offline-save-evidence');
    } finally { await h.context.setOffline(false); }
    await save(h); await page.reload();
    await expect(title).toHaveValue(wanted); assert.equal((await h.read(record)).schema.dashboard.title, wanted);
    await h.shot('R03-online-retry-evidence');
  });
  // Do not carry a failed editor interaction's unsaved draft into unrelated tests.
  page.on('dialog', dialog => dialog.dismiss().catch(() => {}));
  for (const name of ['Walmart', 'Apple']) {
    await h.run('B08', `${name} 四主题深浅模式保存及重载`, async () => {
      let record = await h.read(h.requireCopy(name)); const baseline = h.clone(record.schema.dashboard.theme);
      const original = await h.refresh(record);
      try {
        for (const preset of ['clarity', 'ocean', 'warm', 'graphite']) for (const mode of ['light', 'dark']) {
          const schema = h.clone(record.schema); schema.dashboard.theme = { preset, mode, overrides: {} };
          record = await h.update(record, schema);
          await page.goto(`/dashboards/${record.id}/`);
          const renderer = page.locator('[data-dashboard-theme]').last();
          await expect(renderer).toHaveAttribute('data-dashboard-theme', preset);
          await expect(renderer).toHaveAttribute('data-dashboard-mode', mode);
          const saved = await h.read(record); assert.equal(saved.schema.dashboard.theme.preset, preset);
          await h.shot(`B08-${name}-${preset}-${mode}-1440-evidence`);
        }
        const changed = h.clone(record.schema);
        changed.dashboard.theme = { preset: 'clarity', mode: 'light', overrides: { primary_color: '#2457a7' } };
        record = await h.update(record, changed);
        assert.equal((await h.read(record)).schema.dashboard.theme.overrides.primary_color, '#2457a7');
        const refreshed = await h.refresh(record);
        for (const id of Object.keys(original.widgets)) assert.deepEqual(refreshed.widgets[id].rows, original.widgets[id].rows);
      } finally {
        const latest = await h.read(record); const schema = h.clone(latest.schema); schema.dashboard.theme = baseline;
        await h.update(latest, schema);
      }
    });
  }
};

async function tableAlignment(h, target, name) {
  const card = target.locator('[data-dashboard-widget-id="w_3yr_financial_table"]');
  await card.scrollIntoViewIfNeeded();
  const body = card.locator('.ant-table-body');
  await h.expect(card.locator('thead th').first()).toBeAttached();
  const observations = [];
  for (const side of ['left', 'right', 'left-again']) {
    await body.evaluate((el, direction) => { el.scrollLeft = direction === 'right' ? el.scrollWidth : 0; }, side);
    await target.waitForTimeout(150); // Browser scroll synchronization, not network readiness.
    const values = await card.evaluate(el => {
      const rect = node => { const b = node.getBoundingClientRect(); return { text: node.innerText, x: b.x, width: b.width }; };
      return { headers: [...el.querySelectorAll('thead th:not(.ant-table-cell-scrollbar)')].map(rect) };
    });
    // Collect the actual FY2024 data row, excluding Ant Design's hidden sizing row.
    values.row = await card.evaluate(el => {
      const row = [...el.querySelectorAll('.ant-table-tbody tr[data-row-key]')].find(row => row.innerText.includes('2024'));
      return row ? [...row.querySelectorAll('td')].map(node => { const b = node.getBoundingClientRect(); return { text: node.innerText, x: b.x, width: b.width }; }) : [];
    });
    observations.push({ side, ...values });
    await h.shot(`B09-${name}-${side}-evidence`, target);
  }
  h.artifact(`api/B09-${name}-alignment.json`, observations);
  for (const observation of observations) {
    h.assert.equal(observation.row.length, 7, '没有读到完整 FY2024 七列明细');
    h.assert.equal(observation.headers.length, 7);
    for (let i = 0; i < 7; i++) {
      const head = observation.headers[i]; const cell = observation.row[i];
      h.assert(Math.abs(head.x - cell.x) <= 2 && Math.abs(head.width - cell.width) <= 2,
        `${name} ${observation.side} 第 ${i + 1} 列错位：表头 x=${head.x.toFixed(1)} width=${head.width.toFixed(1)}；数据 x=${cell.x.toFixed(1)} width=${cell.width.toFixed(1)}`);
    }
  }
}

exports.evidenceChecks = async h => {
  const { expect, assert } = h;
  let views = 0;
  for (const name of ['Walmart', 'Apple']) for (const kind of ['editor', 'public']) for (const width of [1440, 1024]) {
    const target = kind === 'editor' ? h.page : await h.anonymous.newPage();
    const key = `${name}-${kind}-${width}`;
    const loaded = await h.run('F06', `${key} 本轮页面与完整组件截图`, async () => {
      const record = await h.read(h.requireCopy(name)); const pub = h.state.publications[name]?.v1;
      if (!pub) throw new h.Blocked('依赖 F01：尚无本轮发布版本。');
      await target.setViewportSize({ width, height: 900 });
      await target.goto(kind === 'editor' ? `${h.cfg.base_url}/dashboards/${record.id}/` : `${h.cfg.base_url}${pub.share_path}`);
      if (kind === 'editor') await expect(target.getByRole('textbox', { name: '看板标题', exact: true })).toHaveValue(record.schema.dashboard.title);
      else await expect(target.getByText(record.schema.dashboard.title, { exact: true }).first()).toBeVisible();
      const cards = target.locator('[data-dashboard-widget-id]'); await expect(cards).toHaveCount(record.schema.widgets.length);
      for (const widget of record.schema.widgets) {
        const card = target.locator(`[data-dashboard-widget-id="${widget.id}"]`);
        await card.scrollIntoViewIfNeeded();
        if (['line', 'bar', 'pie', 'donut'].includes(widget.type)) {
          await expect(card.locator('canvas').first()).toBeAttached();
          await expect.poll(async () => (await card.locator('canvas').first().evaluate(readPlot))?.elements.length || 0).toBeGreaterThan(0);
        }
        await h.shot(`F06-${key}-${widget.id}-evidence`, target);
      }
      await target.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(el => { if (el.scrollTop) el.scrollTop = 0; }); });
      await h.shot(`F06-${key}-evidence`, target); await h.shot(`F06-${key}-full-evidence`, target, true);
      h.artifact(`api/F06-${key}.json`, { url: target.url(), dashboard_id: record.id, draft_revision: record.current_revision,
        published_revision: pub.published_revision, width, height: 900, widget_count: await cards.count() });
      views++;
    });
    if (loaded) {
      await h.run('B06', `${key} 页面与卡片横向边界`, async () => {
        const geometry = await target.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
          cards: [...document.querySelectorAll('[data-dashboard-widget-id]')].map(el => {
            const b = el.getBoundingClientRect(); return { id: el.dataset.dashboardWidgetId, left: b.left, right: b.right, width: b.width };
          }) }));
        h.artifact(`api/B06-${key}.json`, geometry);
        assert(geometry.scroll <= width + 1, `页面宽度 ${geometry.scroll} 超出 ${width}`);
        assert(geometry.cards.every(c => c.left >= -1 && c.right <= width + 1), JSON.stringify(geometry.cards));
      });
      await h.run(['B07', 'B10'], `${key} 实际图元、标签与绘图区测量`, async () => {
        const observations = [];
        for (const canvas of await target.locator('[data-dashboard-widget-id] canvas').all()) {
          await canvas.scrollIntoViewIfNeeded(); const plot = await canvas.evaluate(readPlot);
          assert(plot && plot.elements.length, '图表没有实际绘制的数据图元');
          const ys = plot.elements.flatMap(el => [el.min[1], el.max[1]]).filter(Number.isFinite);
          observations.push({ ...plot, data_height: Math.max(...ys) - Math.min(...ys) });
        }
        assert(observations.length > 0); h.artifact(`api/B10-${key}-plot-measurements.json`, observations);
        return '已记录实际图元/标签/数据区高度；绘图区是否偏扁、标签是否可读仍需人工判断。';
      });
      if (name === 'Apple') await h.run('B09', `${key} 真实表头/表体左移右移列对齐`, () => tableAlignment(h, target, key));
      if (kind === 'public') {
        await h.run('F02', `${key} 独立无登录上下文只读页面`, async () => {
          for (const label of ['保存看板', 'SQL 与参数设置', '开启框选批注', '发布看板'])
            await expect(target.getByRole('button', { name: label, exact: true })).toHaveCount(0);
          await expect(target.getByText(/只读数据快照/).first()).toBeVisible();
          assert.equal((await h.anonymous.cookies()).length, 0, '匿名上下文产生了登录 Cookie，需检查');
        });
        await h.run('B11', `${key} 公开页顶部信息证据`, async () => {
          await target.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('*').forEach(el => { if (el.scrollTop) el.scrollTop = 0; }); });
          await h.shot(`B11-${key}-top-evidence`, target);
          const top = await target.evaluate(() => [...document.querySelectorAll('h1,h2,header,p,button')].filter(el => {
            const b = el.getBoundingClientRect(); return b.top >= 0 && b.top < 320 && b.width > 0;
          }).map(el => { const b = el.getBoundingClientRect(); return { text: el.innerText, x: b.x, y: b.y, width: b.width, height: b.height,
            clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, overflow: getComputedStyle(el).overflow }; }));
          assert(top.length > 0); h.artifact(`api/B11-${key}-top.json`, top);
          return '记录顶部可见内容及容器尺寸；文字互相遮挡和被裁切的视觉判断保留待复核。';
        });
      }
    }
    if (kind === 'public') await target.close();
  }
  await h.run('F06', '八个不同案例/页面/宽度的证据齐全', () => { assert.equal(views, 8); return '8 个真实页面已拍摄；文件名使用 evidence，未将截图数量当作视觉验收通过。'; });
  await h.run('X07', '390×844 匿名公开页堆叠与横向边界', async () => {
    for (const name of ['Walmart', 'Apple']) {
      const pub = h.state.publications[name]?.v1; if (!pub) throw new h.Blocked(`缺少 ${name} 本轮发布。`);
      const mobile = await h.anonymous.newPage();
      try {
        await mobile.setViewportSize({ width: 390, height: 844 });
        await mobile.goto(`${h.cfg.base_url}${pub.share_path}`);
        await expect(mobile.locator('[data-dashboard-widget-id]').first()).toBeVisible();
        await h.shot(`X07-${name}-390-top-evidence`, mobile);
        await mobile.locator('[data-dashboard-widget-id]').last().scrollIntoViewIfNeeded();
        await h.shot(`X07-${name}-390-bottom-evidence`, mobile);
        assert(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), '390 公开页横向溢出');
      } finally { await mobile.close(); }
    }
  });
};
