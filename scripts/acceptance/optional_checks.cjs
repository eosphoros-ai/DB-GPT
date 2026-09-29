'use strict';
const fs = require('node:fs');
const path = require('node:path');

async function uploadChecks(h) {
  const sampleDir = path.join(__dirname, 'fixtures', 'upload-samples');
  const conversation = `uat-upload-${h.cfg.run_id}`;
  async function upload(names) {
    const boundary = `uat-${h.cfg.run_id}`;
    const parts = [Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="conv_uid"\r\n\r\n${conversation}\r\n`)];
    for (const name of names) {
      parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="files"; filename="${name}"\r\nContent-Type: text/plain\r\n\r\n`));
      parts.push(fs.readFileSync(path.join(sampleDir, name)), Buffer.from('\r\n'));
    }
    parts.push(Buffer.from(`--${boundary}--\r\n`));
    const response = await h.apiContext.post('/api/v1/python/files/upload', {
      headers: { 'Content-Type': `multipart/form-data; boundary=${boundary}` }, data: Buffer.concat(parts), timeout: 120000 });
    const payload = await response.json();
    h.artifact(`api/upload-${names.length === 1 ? 'rejection' : 'three-files'}.json`, { status: response.status(), payload });
    return { response, payload };
  }
  await h.run('X03', '本批三文件真实上传、预览与独立关联金额核对', async () => {
    const names = ['customers.csv', 'orders.csv', 'order_items.csv'];
    const { response, payload } = await upload(names);
    h.assert.equal(response.status(), 200); h.assert.equal(payload.success, true);
    const dataset = payload.data;
    h.state.upload = { dataset_id: dataset.dataset_id, conversation_id: conversation }; h.saveState();
    h.assert.equal(dataset.files.length, 3);
    const previews = {};
    for (const [i, name] of names.entries()) {
      const file = dataset.files.find(f => f.name === name); h.assert(file, `${name} 未出现在上传结果`);
      const response = await h.apiContext.get(`/api/v1/python/datasets/${dataset.dataset_id}/files/${file.file_id}/preview`, { params: { conv_uid: conversation, rows: 50 } });
      h.assert.equal(response.status(), 200); const result = await response.json(); h.assert.equal(result.success, true);
      h.assert.equal(result.data.file_name, name); h.assert.equal(result.data.rows.length, [3, 4, 5][i]);
      previews[name] = result.data.rows;
      h.artifact(`api/X03-${name}-preview.json`, result);
    }
    const customers = previews['customers.csv']; const orders = previews['orders.csv']; const items = previews['order_items.csv'];
    h.assert.equal(new Set(customers.map(r => r.customer_id)).size, 3);
    h.assert.equal(new Set(orders.map(r => r.order_id)).size, 4);
    h.assert.equal(customers[0].customer_name, '甲客户');
    const months = {}, regions = {}; let total = 0;
    for (const item of items) {
      const order = orders.find(o => o.order_id === item.order_id); h.assert(order);
      const customer = customers.find(c => c.customer_id === order.customer_id); h.assert(customer);
      const amount = Number(item.quantity) * Number(item.unit_price); total += amount;
      const month = order.order_date.slice(0, 7); months[month] = (months[month] || 0) + amount;
      regions[customer.region] = (regions[customer.region] || 0) + amount;
    }
    h.assert.equal(total, 1500);
    h.assert.deepEqual(months, { '2024-01': 250, '2024-02': 1100, '2024-03': 150 });
    h.assert.deepEqual(regions, { '华东': 350, '华南': 1000, '华北': 150 });
    h.artifact('api/X03-reconciliation.json', { total, months, regions, customers: 3, orders: 4, items: 5, evidence_type: 'independent calculation from actual uploaded previews; not model output' });
    return '真实上传/预览 3/4/5 行，中文正确；从返回数据独立计算 1500 与月金额。模型回答未自动判定。';
  });
  await h.run('X04', '本批 TXT 的真实服务端拒绝', async () => {
    const { response, payload } = await upload(['not-a-table.txt']);
    h.assert([200, 400, 415, 422].includes(response.status()));
    h.assert.equal(payload.success, false); h.assert.match(payload.err_msg || '', /Unsupported|not supported|不支持/i);
    return '服务端明确拒绝 TXT；未把服务端拒绝等同于浏览器队列断网重试。';
  });
}

async function anomalyCheck(h) {
  await h.run('X06', '目标值异常规则的真实计算与空数据无法判断', async () => {
    let record = await h.copy(h.requireCopy('Apple').id, 'Anomaly');
    const schema = h.clone(record.schema); const kpi = h.widget({ schema }, w => w.type === 'kpi');
    kpi.anomaly_rules = [{ id: 'uat-target', label: '收入低于目标', baseline: 'target_value', value_field: kpi.encoding.value,
      target_value: 400000, direction: 'below', threshold: { mode: 'absolute_change', value: 5000 }, min_samples: 1, enabled: true }];
    record = await h.update(record, schema);
    const result = await h.preview(record, kpi); const evidence = result.anomalies.find(a => a.rule_id === 'uat-target');
    h.assert(evidence); h.assert.equal(evidence.status, 'anomaly'); h.assert.equal(evidence.current_value, 391035);
    h.assert.equal(evidence.baseline_value, 400000); h.assert.equal(evidence.absolute_change, -8965);
    const empty = await h.preview(record, kpi, kpi.query.sql.replace(/fiscal_year\s*=\s*2024/i, 'fiscal_year = 2099'));
    h.assert(empty.anomalies.length > 0); h.assert(empty.anomalies.every(a => a.status !== 'anomaly'));
    return '391035 − 400000 = −8965，低于目标超过 5000；无数据不报告异常。AI 解释未调用。';
  });
}

async function scheduleCheck(h) {
  await h.run('X05', '本轮副本实际立即运行、自然调度和暂停', async () => {
    const record = await h.copy(h.requireCopy('Walmart').id, 'Schedule');
    const beforePublications = await h.api('GET', `/dashboards/${record.id}/revisions`);
    const schedule = await h.api('POST', `/dashboards/${record.id}/schedules`, { task_name: `UAT-${h.cfg.run_id}`,
      cron_expression: '* * * * *', filters: {}, publish_after_refresh: false, timeout_seconds: 30, max_attempts: 1 });
    const id = schedule.task_id; h.assert(id);
    h.state.schedules.push({ dashboard_id: record.id, task_id: id, paused: false }); h.saveState();
    const endpoint = `/dashboards/${record.id}/schedules/${id}`;
    const getRuns = () => h.api('GET', `${endpoint}/runs`);
    const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
    try {
      const manual = await h.api('POST', `${endpoint}/run`); h.assert(manual.run_id);
      let runs = [];
      const deadline = Date.now() + 125000;
      while (Date.now() < deadline) {
        runs = await getRuns();
        if (runs.some(r => r.run_id !== manual.run_id && r.finished_at)) break;
        console.log('[X05] 等待自然调度，立即运行不计入自然触发。'); await wait(10000);
      }
      const natural = runs.filter(r => r.run_id !== manual.run_id && r.finished_at);
      if (!natural.length) throw new h.Blocked('125 秒内没有自然调度记录；请核对服务端调度器和时区。');
      const immediate = runs.find(r => r.run_id === manual.run_id); h.assert(immediate?.finished_at);
      h.assert.equal(immediate.status, 'success'); h.assert(natural.every(r => r.status === 'success'), JSON.stringify(natural));
      const paused = await h.api('POST', `${endpoint}/toggle`, { enabled: false }); h.assert.equal(paused.enabled, false);
      // Drain already-started executions before comparing a full minute after pause.
      for (let i = 0; i < 12 && (await getRuns()).some(r => !r.finished_at); i++) await wait(5000);
      const drained = await getRuns(); h.assert(drained.every(r => r.finished_at), '暂停时仍有未结束运行');
      const ids = drained.map(r => r.run_id).sort();
      for (let i = 0; i < 7; i++) { console.log('[X05] 观察暂停后是否有新调度。'); await wait(10000); }
      h.assert.deepEqual((await getRuns()).map(r => r.run_id).sort(), ids);
      h.assert.deepEqual(await h.api('GET', `/dashboards/${record.id}/revisions`), beforePublications);
      h.artifact('api/X05-manual-and-natural.json', { manual, natural, scheduler_next_run_time: schedule.next_run_time, observed_at: new Date().toISOString() });
    } finally {
      const paused = await h.api('POST', `${endpoint}/toggle`, { enabled: false });
      h.assert.equal(paused.enabled, false); h.state.schedules.find(s => s.task_id === id).paused = true; h.saveState();
    }
  });
}

async function matrixCheck(h) {
  for (const name of ['Walmart', 'Apple']) {
    let record;
    const ready = await h.run('X08', `${name} 主题矩阵专用副本`, async () => { record = await h.copy(h.requireCopy(name).id, `Matrix-${name}`); });
    if (!ready) continue;
    for (const preset of ['clarity', 'ocean', 'warm', 'graphite']) for (const mode of ['light', 'dark']) {
      let publication;
      const published = await h.run('X08', `${name} ${preset} ${mode} 真实发布`, async () => {
        record = await h.read(record); const schema = h.clone(record.schema); schema.dashboard.theme = { preset, mode, overrides: {} };
        record = await h.update(record, schema); publication = await h.publish(record);
      });
      for (const width of [1440, 1024]) await h.run('X08', `${name}-${preset}-${mode}-${width} 真实公开页`, async () => {
        if (!published) throw new h.Blocked('此主题的发布步骤失败。');
        const page = await h.anonymous.newPage();
        try {
          await page.setViewportSize({ width, height: 900 }); await page.goto(`${h.cfg.base_url}${publication.share_path}`);
          const renderer = page.locator('[data-dashboard-theme]').last();
          await h.expect(renderer).toHaveAttribute('data-dashboard-theme', preset);
          await h.expect(renderer).toHaveAttribute('data-dashboard-mode', mode);
          await h.expect(page.locator('[data-dashboard-widget-id]')).toHaveCount(record.schema.widgets.length);
          await h.expect(page.locator('canvas').first()).toBeVisible();
          await h.shot(`X08-${name}-${preset}-${mode}-${width}-evidence`, page, true);
          h.assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), '主题公开页横向溢出');
          h.state.matrix.push({ name, preset, mode, width, dashboard_id: record.id, publication, visual_status: '待人工复核' }); h.saveState();
        } finally { await page.close(); }
      });
    }
  }
  await h.run('X08', '完整矩阵 32 个真实发布视图', () => { h.assert.equal(h.state.matrix.length, 32); });
}

exports.runOptional = async h => {
  await uploadChecks(h); await anomalyCheck(h);
  if (h.cfg.live_model) await require('./model_checks.cjs').runModel(h);
  if (h.cfg.schedule) await scheduleCheck(h);
  if (h.cfg.theme_matrix) await matrixCheck(h);
};
