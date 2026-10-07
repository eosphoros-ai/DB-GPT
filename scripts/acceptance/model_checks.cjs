'use strict';

// Opt-in live model run. Exactly one planning attempt / confirmation per stage.
// Complete response bodies and prompts are retained under a new run directory.
exports.runModel = async h => {
  const { page, expect, assert } = h;
  const existing = await h.api('GET', '/dashboards?include_generated=true&include_archived=true');
  const knownIds = new Set(existing.map(r => r.id));
  const events = [], pending = [];
  let responseNumber = 0;
  const listener = response => {
    if (response.request().method() !== 'POST' || !/\/chat\/react-agent$/.test(new URL(response.url()).pathname)) return;
    const number = ++responseNumber;
    const capture = response.text().then(text => {
      const parsed = [];
      for (const line of text.split(/\r?\n/)) if (line.startsWith('data:')) {
        try { parsed.push(JSON.parse(line.slice(5).trim())); } catch { /* [DONE] is not JSON. */ }
      }
      events.push(...parsed);
      h.artifact(`model/attempt-01-response-${number}.json`, { http_status: response.status(),
        request: response.request().postDataJSON(), finished_at: new Date().toISOString(), events: parsed, raw_sse: text });
    }).catch(error => { h.artifact(`model/attempt-01-response-${number}-error.txt`, String(error)); });
    pending.push(capture);
  };
  page.on('response', listener);
  const flush = async () => {
    let timer;
    try {
      await Promise.race([Promise.all(pending), new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('模型 SSE 在 240 秒内未关闭；保留当前结果，不重试。')), 240000);
      })]);
    } finally { clearTimeout(timer); }
  };
  const lastPlan = () => events.filter(e => e.type === 'dashboard.plan.awaiting_confirmation').at(-1);
  async function send(prompt) {
    const input = page.getByPlaceholder(/数据库|CSV|报告/).first();
    await input.fill(prompt); await input.press('Enter');
  }
  async function selectSource(source) {
    await page.goto('/');
    await page.locator('button').filter({ has: page.locator('.anticon-database') }).last().click();
    await page.getByPlaceholder('搜索数据库').fill(source);
    await page.getByText(source, { exact: true }).click();
  }
  async function waitPlan() {
    await expect(page.getByRole('button', { name: '确认并生成 SQL', exact: true }).last()).toBeEnabled({ timeout: 180000 });
    await flush(); const plan = lastPlan(); assert(plan?.dashboard_id, '真实 SSE 没有可确认的规划事件');
    return plan;
  }
  async function claim(plan, name) {
    assert(!knownIds.has(plan.dashboard_id), '模型指向运行前已有资产，禁止自动修改');
    const record = await h.api('GET', `/dashboards/${plan.dashboard_id}`);
    h.owned.add(record.id); h.state.copies[name] = record; h.saveState(); return record;
  }
  let walmartPlan, walmartRecord, appleRecord;
  try {
    const planned = await h.run('C01', 'Walmart 真实模型首次规划、不提前生成 SQL', async () => {
      assert(h.cfg.source.prompts.W, 'DOCX 没有解析到提示词 W'); await selectSource('Walmart_Sales');
      const started = new Date().toISOString(); await send(h.cfg.source.prompts.W); walmartPlan = await waitPlan();
      walmartRecord = await claim(walmartPlan, 'Model-Walmart');
      assert.equal(walmartPlan.plan.widgets.length, 3); assert.equal(walmartPlan.plan.filters.length, 0);
      assert(!events.some(e => e.type === 'dashboard.generation.started' && e.dashboard_id === walmartRecord.id));
      assert(walmartRecord.schema.widgets.every(w => !w.query.sql.trim()), '用户确认前已有组件 SQL');
      h.artifact('model/W-attempt-01.json', { started_at: started, finished_at: new Date().toISOString(), prompt: h.cfg.source.prompts.W, plan: walmartPlan, url: page.url() });
      await h.shot('C01-Walmart-first-plan-evidence');
    });
    const revised = await h.run('C02', '真实修改计划后仍需确认、保持同一 ID', async () => {
      if (!planned) throw new h.Blocked('依赖 C01：没有首轮规划；不自动重试。');
      const previous = walmartPlan; const wanted = `UAT-Walmart-${h.cfg.run_id}`;
      await page.getByRole('button', { name: '修改计划', exact: true }).last().click();
      const input = page.getByPlaceholder(/数据库|CSV|报告/).first();
      const prefix = await input.inputValue();
      assert(prefix.includes(`[[revise-dashboard-plan:${previous.dashboard_id}]]`), '修改计划入口没有绑定当前规划');
      await send(`${prefix}保持这三个组件和无筛选器不变，把看板标题改为‘${wanted}’，更新规划后等待我确认。`);
      walmartPlan = await waitPlan();
      assert.equal(walmartPlan.dashboard_id, previous.dashboard_id);
      assert.equal(walmartPlan.plan.title, wanted); assert.equal(walmartPlan.plan.widgets.length, 3);
      assert.equal(walmartPlan.plan.filters.length, 0);
      assert(Number(walmartPlan.current_revision) > Number(previous.current_revision));
      await h.shot('C02-Walmart-revised-plan-evidence');
    });
    const generated = await h.run('C03', 'Walmart 一次确认后自动完成 SQL 生成', async () => {
      if (!revised) throw new h.Blocked('依赖 C02：规划未通过；没有发送额外催促。');
      const count = responseNumber;
      await page.getByRole('button', { name: '确认并生成 SQL', exact: true }).last().click();
      await expect(page.getByTestId('task-dashboard-panel')).toBeVisible({ timeout: 210000 });
      await flush(); assert.equal(responseNumber, count + 1, '确认后发生了多次模型请求');
      assert(events.some(e => e.type === 'dashboard.generation.started' && e.dashboard_id === walmartPlan.dashboard_id));
      walmartRecord = await h.read(walmartRecord); assert.equal(walmartRecord.schema.widgets.length, 3);
      assert(walmartRecord.schema.widgets.every(w => w.query.sql.trim())); await h.refresh(walmartRecord);
      await h.shot('C03-Walmart-generated-evidence');
    });
    await h.run('C04', '生成任务重载、首次保存前后列表可见性与 ID', async () => {
      if (!generated) throw new h.Blocked('依赖 C03：未成功生成；保留首次结果。');
      const url = page.url(); await page.reload();
      if (!await page.getByTestId('task-dashboard-panel').isVisible())
        await page.getByRole('button', { name: /查看看板|继续编辑/ }).last().click();
      await expect(page.getByTestId('task-dashboard-panel')).toBeVisible();
      const before = await h.api('GET', '/dashboards'); assert(!before.some(r => r.id === walmartRecord.id));
      await page.getByTestId('task-dashboard-panel').getByRole('button', { name: '保存看板', exact: true }).click();
      await expect(page.getByText('草稿已保存', { exact: true })).toBeVisible();
      const after = await h.api('GET', '/dashboards'); assert(after.some(r => r.id === walmartRecord.id));
      assert.equal((await h.read(walmartRecord)).asset_state, 'saved');
      h.artifact('model/C04-task.json', { task_url: url, dashboard_id: walmartRecord.id }); await h.shot('C04-Walmart-saved-evidence');
    });
    await h.run('C05', 'Apple 原始筛选提示词、一次确认、新建并保存 A-筛选', async () => {
      assert(h.cfg.source.prompts.A, 'DOCX 没有解析到提示词 A'); await selectSource('apple_financial_demo');
      await send(h.cfg.source.prompts.A); const plan = await waitPlan();
      appleRecord = await claim(plan, 'Model-Apple');
      await h.shot('C05-Apple-first-plan-evidence');
      await page.getByRole('button', { name: '确认并生成 SQL', exact: true }).last().click();
      await expect(page.getByTestId('task-dashboard-panel')).toBeVisible({ timeout: 210000 }); await flush();
      appleRecord = await h.read(appleRecord); assert.equal(appleRecord.schema.widgets.length, 5);
      assert(appleRecord.schema.filters.length >= 2, 'Apple 生成结果缺少截至财年/产品筛选');
      const snapshot = await h.refresh(appleRecord); const kpi = h.widget(appleRecord, w => w.type === 'kpi');
      h.closeNumber(h.rows(snapshot.widgets[kpi.id])[0][kpi.encoding.value], 391035, 0);
      const chart = h.widget(appleRecord, w => w.encoding.series);
      const chartRows = h.rows(snapshot.widgets[chart.id]);
      assert.equal(new Set(chartRows.map(r => r[chart.encoding.series])).size, 3);
      assert.equal(chartRows.length, 9); assert.equal(chart.type, 'bar');
      await page.getByTestId('task-dashboard-panel').getByRole('button', { name: '保存看板', exact: true }).click();
      await expect(page.getByText('草稿已保存', { exact: true })).toBeVisible();
      h.state.filter_asset = { id: appleRecord.id, created_this_run: true }; h.saveState();
      await h.shot('C05-Apple-filtered-result-evidence');
    });
    for (const id of ['E01', 'E02']) await h.run(id, id === 'E01' ? 'A-筛选财年参数与截止数据' : 'A-筛选产品多选影响范围', async () => {
      if (!h.state.filter_asset) throw new h.Blocked('依赖 C05：本轮没有成功保存 A-筛选；不能使用无筛选演示资产替代。');
      const record = await h.read(appleRecord);
      const year = record.schema.filters.find(f => /财年|fiscal|year/i.test(`${f.id} ${f.label}`));
      const product = record.schema.filters.find(f => /产品|product/i.test(`${f.id} ${f.label}`));
      assert(year && product, '无法识别财年和产品筛选器');
      const kpi = h.widget(record, w => w.type === 'kpi');
      const revenue = snapshot => h.rows(snapshot.widgets[kpi.id])[0][kpi.encoding.value];
      const yearValue = y => year.options.find(o => String(o.value).includes(String(y)))?.value ?? y;
      if (id === 'E01') {
        const old = await h.refresh(record, { [year.id]: yearValue(2022) }); h.closeNumber(revenue(old), 394328, 0);
        for (const result of Object.values(old.widgets)) for (const row of h.rows(result))
          for (const field of Object.keys(row).filter(f => /fiscal_year/i.test(f))) assert(Number(row[field]) <= 2022);
        h.closeNumber(revenue(await h.refresh(record, { [year.id]: yearValue(2024) })), 391035, 0);
      } else {
        const base = await h.refresh(record, { [year.id]: yearValue(2024) });
        const target = h.widget(record, w => /product|产品/i.test(w.encoding.x || w.encoding.category || ''));
        for (const selected of [['iPhone'], ['iPhone', 'Mac']]) {
          const next = await h.refresh(record, { [year.id]: yearValue(2024), [product.id]: selected }); h.closeNumber(revenue(next), 391035, 0);
          const data = h.rows(next.widgets[target.id]); const category = target.encoding.x || target.encoding.category;
          assert.deepEqual(data.map(r => r[category]).sort(), [...selected].sort());
          for (const w of record.schema.widgets.filter(w => w.id !== target.id)) assert.deepEqual(next.widgets[w.id].rows, base.widgets[w.id].rows);
        }
      }
    });
  } finally { page.off('response', listener); await flush(); }
};
