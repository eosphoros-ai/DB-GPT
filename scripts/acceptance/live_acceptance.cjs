/* Real service checks for the Word checklist. No mocked API responses here. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const cfg = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const projectRequire = createRequire(path.join(cfg.root, 'web/package.json'));
const playwright = projectRequire('@playwright/test');
const { chromium, request } = playwright;
const expect = playwright.expect.configure({ timeout: 15000 });
const out = cfg.out;
for (const dir of ['api', 'screenshots', 'downloads']) fs.mkdirSync(path.join(out, dir), { recursive: true });
const state = { run_id: cfg.run_id, base_url: cfg.base_url, originals: {}, copies: {}, publications: {}, schedules: [], matrix: [] };
const owned = new Set();
const results = [];
let browser, context, apiContext, anonymous, page, active, serial = 0;
class Blocked extends Error {}
const clone = value => structuredClone(value);
const timestamp = () => new Date().toISOString();
const relative = file => path.relative(out, file).replaceAll('\\', '/');
function artifact(name, value) {
  const file = path.join(out, name);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, typeof value === 'string' || Buffer.isBuffer(value) ? value : JSON.stringify(value, null, 2));
  if (active) active.artifacts.push(relative(file));
  return file;
}
function saveState() { artifact('state.json', state); }
async function shot(name, target = page, fullPage = false) {
  const file = path.join(out, 'screenshots', `${name}.png`);
  await target.screenshot({ path: file, fullPage, animations: 'disabled', timeout: 20000 });
  if (active) active.artifacts.push(relative(file));
  return file;
}
async function run(ids, name, fn) {
  const item = { ids: Array.isArray(ids) ? ids : [ids], name, status: 'passed', started_at: timestamp(), artifacts: [], browser_errors: [] };
  active = item;
  console.log(`[开始] ${item.ids.join('/')} ${name}`);
  try {
    item.message = (await fn()) || '列出的自动断言通过。';
    assert.deepEqual(item.browser_errors, [], '浏览器出现未捕获的 JavaScript 异常');
  }
  catch (error) {
    item.status = error instanceof Blocked ? 'blocked' : 'failed';
    item.message = error.stack || String(error);
    if (page && !page.isClosed()) await shot(`${item.ids.join('-')}-${++serial}-issue`).catch(() => {});
  } finally {
    item.finished_at = timestamp();
    item.artifacts = [...new Set(item.artifacts)];
    fs.appendFileSync(path.join(out, 'checks.jsonl'), JSON.stringify(item) + '\n');
    results.push(item);
    console.log(`[${item.status}] ${item.ids.join('/')} ${name}`);
    active = undefined;
  }
  return item.status === 'passed';
}
function requireCopy(name) {
  const item = state.copies[name];
  if (!item) throw new Blocked(`依赖 A03：${name} 本轮副本未创建。`);
  return item;
}
function guard(method, endpoint) {
  if (method === 'GET') return;
  const match = endpoint.match(/^\/dashboards\/([^/?]+)(.*)$/);
  if (!match) throw new Error(`拒绝未声明的写入路径：${endpoint}`);
  const [_, id, suffix] = match;
  if (suffix === '/copy' && method === 'POST' && [cfg.walmart_id, cfg.apple_id, ...owned].includes(id)) return;
  assert(owned.has(id), `仅允许修改本次运行创建的副本：${id}`);
}
async function api(method, endpoint, data, allowed = [200], client = apiContext) {
  guard(method, endpoint);
  const response = await client.fetch(new URL(`/api/v1${endpoint}`, state.api_url || cfg.api_url || cfg.base_url).href, { method, data, timeout: 150000 });
  const raw = await response.text();
  let payload;
  try { payload = JSON.parse(raw); } catch { payload = { non_json: raw.slice(0, 1500) }; }
  artifact(`api/${String(++serial).padStart(4, '0')}.json`, { method, endpoint, http_status: response.status(), payload });
  assert(allowed.includes(response.status()), `${method} ${endpoint}: HTTP ${response.status()} ${raw.slice(0, 1200)}`);
  if (allowed.length === 1 && allowed[0] === 200) assert.equal(payload.success, true, `${endpoint}: ${raw.slice(0, 1500)}`);
  return allowed[0] === 200 && allowed.length === 1 ? payload.data : { status: response.status(), payload };
}
async function read(record) { return api('GET', `/dashboards/${record.id}`); }
async function update(record, schema) {
  return api('PUT', `/dashboards/${record.id}`, { schema, expected_revision: record.current_revision });
}
async function copy(sourceId, name) {
  const record = await api('POST', `/dashboards/${sourceId}/copy`, { title: `UAT-${name}-${cfg.run_id}` });
  assert(record.id && record.id !== sourceId);
  owned.add(record.id);
  // Persist immediately, even when the next assertion fails.
  state.copies[name] = record;
  saveState();
  return record;
}
async function refresh(record, filters = {}) {
  const data = await api('POST', `/dashboards/${record.id}/refresh`, { filters });
  for (const [id, result] of Object.entries(data.widgets)) {
    assert.equal(result.error, null, `${id} 查询失败：${JSON.stringify(result.error)}`);
    assert.equal(result.truncated, false, `${id} 结果被截断，不能完整对拍`);
  }
  return data;
}
async function preview(record, widget, sql) {
  const schema = clone(record.schema);
  const target = schema.widgets.find(w => w.id === widget.id);
  if (sql) target.query.sql = sql;
  return api('POST', `/dashboards/${record.id}/widgets/${widget.id}/preview`, { schema, filters: {} });
}
function widget(record, predicate) {
  const found = record.schema.widgets.find(predicate);
  assert(found, `缺少目标组件：${record.id}`);
  return found;
}
function rows(result) {
  assert.equal(result.error, null, JSON.stringify(result.error));
  assert.equal(result.truncated, false);
  return result.rows.map(row => Object.fromEntries(result.columns.map((field, i) => [field, row[i]])));
}
function closeNumber(actual, expected, precision = 0.005) {
  assert(Number.isFinite(Number(actual)), `不是数值：${actual}`);
  assert(Math.abs(Number(actual) - expected) <= precision, `实际 ${actual}，预期 ${expected}`);
}
const appleTruth = { 2022: [394328, 119437, 99803], 2023: [383285, 114301, 96995], 2024: [391035, 123216, 93736] };
function checkApple(record, snapshot) {
  const table = widget(record, w => w.type === 'table' && w.encoding.columns.includes('operating_income'));
  const tableRows = rows(snapshot.widgets[table.id]);
  assert.equal(tableRows.length, 3);
  assert.deepEqual(tableRows.map(r => Number(r.fiscal_year)).sort(), [2022, 2023, 2024]);
  for (const row of tableRows) for (const [i, metric] of ['revenue', 'operating_income', 'net_income'].entries())
    closeNumber(row[metric], appleTruth[row.fiscal_year][i], 0);
  const kpi = widget(record, w => w.type === 'kpi');
  closeNumber(rows(snapshot.widgets[kpi.id])[0][kpi.encoding.value], 391035, 0);
}
function checkSeries(record, snapshot) {
  const chart = widget(record, w => w.encoding.series === 'metric');
  assert.equal(chart.encoding.x, 'fiscal_year');
  assert.equal(chart.encoding.y, 'value');
  const values = rows(snapshot.widgets[chart.id]);
  assert.equal(values.length, 9);
  const labels = ['Revenue', 'Operating income', 'Net income'];
  assert.deepEqual([...new Set(values.map(r => r.metric))].sort(), [...labels].sort());
  const keys = new Set();
  for (const row of values) {
    assert(appleTruth[row.fiscal_year], `未知财年 ${row.fiscal_year}`);
    const key = `${row.fiscal_year}:${row.metric}`;
    assert(!keys.has(key), `重复财年/度量：${key}`); keys.add(key);
    closeNumber(row.value, appleTruth[row.fiscal_year][labels.indexOf(row.metric)], 0);
  }
}
function publicToken(publication, latest = false) {
  const value = latest ? publication.latest_share_path : publication.share_path;
  assert(value, '发布响应缺少分享链接');
  return value.split('/').filter(Boolean).at(-1);
}
async function publicData(publication, latest = false) {
  return api('GET', `/public/dashboards/${publicToken(publication, latest)}`, undefined, [200], anonymous.request);
}
async function publish(record) {
  return api('POST', `/dashboards/${record.id}/publish`, { expected_revision: record.current_revision, filters: {} });
}
const helpers = { cfg, state, owned, assert, expect, Blocked, clone, artifact, shot, run, api, read, update, copy, refresh,
  preview, widget, rows, closeNumber, checkSeries, checkApple, publicToken, publicData, publish, requireCopy, saveState };

async function dataChecks() {
  for (const [name, id, count] of [['Walmart', cfg.walmart_id, 3], ['Apple', cfg.apple_id, 5]]) {
    await run('A03', `${name} 创建并核对本轮副本`, async () => {
      const original = await api('GET', `/dashboards/${id}`);
      state.originals[name] = original;
      state.originals[`${name}Publications`] = await api('GET', `/dashboards/${id}/publications`);
      const record = await copy(id, name);
      assert.equal(record.schema.widgets.length, count);
      assert.equal(record.schema.filters.length, 0);
      assert.equal((await read(original)).current_revision, original.current_revision);
      if (name === 'Apple') assert.equal(widget(record, w => w.encoding.series === 'metric').encoding.y, 'value');
      return `${record.id}，初始草稿修订 ${record.current_revision}；来源 ${id}。`;
    });
  }
  const snapshots = {};
  await run('B01', 'Walmart 真实刷新、总额与独立源表行数', async () => {
    const record = requireCopy('Walmart');
    assert.equal(record.schema.dashboard.data_source_id, 'Walmart_Sales');
    const snapshot = await refresh(record); snapshots.Walmart = snapshot;
    const kpi = widget(record, w => w.type === 'kpi');
    closeNumber(rows(snapshot.widgets[kpi.id])[0][kpi.encoding.value], 6737218987.11);
    const probe = clone(record);
    const target = probe.schema.widgets.find(w => w.id === kpi.id);
    target.type = 'table'; target.encoding = { columns: ['source_rows', 'stores', 'weeks', 'total_sales'] };
    target.query.sql = 'SELECT COUNT(*) AS source_rows, COUNT(DISTINCT Store) AS stores, COUNT(DISTINCT Date) AS weeks, SUM(Weekly_Sales) AS total_sales FROM walmart_sales';
    target.query.output_fields = ['source_rows', 'stores', 'weeks', 'total_sales'].map(name => ({ name, type: 'number' }));
    const source = rows(await preview(probe, target))[0];
    assert.equal(source.source_rows, 6435); assert.equal(source.stores, 45); assert.equal(source.weeks, 143);
    closeNumber(source.total_sales, 6737218987.11);
    return '实时查询：6,435 行、45 门店、143 日期；总额 6,737,218,987.11。';
  });
  await run('B02', 'Walmart 33 个完整年月、起止与排序', async () => {
    const record = requireCopy('Walmart');
    const snapshot = snapshots.Walmart || await refresh(record);
    const chart = widget(record, w => /month/i.test(w.encoding.x || ''));
    const data = rows(snapshot.widgets[chart.id]);
    const months = data.map(r => r[chart.encoding.x]);
    assert.equal(months.length, 33); assert.equal(new Set(months).size, 33);
    assert(months.every(v => /^\d{4}-\d{2}$/.test(v)));
    assert.deepEqual(months, [...months].sort());
    assert.equal(months[0], '2010-02'); assert.equal(months.at(-1), '2012-10');
    closeNumber(data.reduce((sum, r) => sum + Number(r[chart.encoding.y]), 0), 6737218987.11);
  });
  await run('B03', 'Walmart 45 家门店及前五名', async () => {
    const record = requireCopy('Walmart');
    const snapshot = snapshots.Walmart || await refresh(record);
    const chart = widget(record, w => /store/i.test(w.encoding.x || ''));
    const data = rows(snapshot.widgets[chart.id]);
    assert.equal(data.length, 45); assert.equal(new Set(data.map(r => r[chart.encoding.x])).size, 45);
    assert.deepEqual(data.slice(0, 5).map(r => Number(r[chart.encoding.x])), [20, 4, 14, 13, 2]);
    assert(data.every((r, i) => !i || Number(data[i - 1][chart.encoding.y]) >= Number(r[chart.encoding.y])));
  });
  await run('B04', 'Apple KPI 与三财年九项金额实时对拍', async () => {
    const record = requireCopy('Apple'); const snapshot = await refresh(record); snapshots.Apple = snapshot;
    checkApple(record, snapshot);
    return 'FY2024 收入 391,035 百万美元，三财年收入/营业利润/净利润 9/9 一致。';
  });
  await run('B05', 'Apple 长表映射、三系列九行与刷新重读', async () => {
    const record = requireCopy('Apple');
    checkSeries(record, snapshots.Apple || await refresh(record));
    const reloaded = await read(record); checkSeries(reloaded, await refresh(reloaded));
    return '复核人工修正资产的本轮副本；不是本轮模型首次生成成功。';
  });
  await run('D02', '未保存的比较图临时表格试运行、恢复三系列', async () => {
    const record = await read(requireCopy('Apple')); const testRecord = clone(record);
    const chart = widget(testRecord, w => w.encoding.series === 'metric');
    chart.type = 'table'; chart.encoding = { columns: ['fiscal_year', 'metric', 'value'] };
    const result = await preview(testRecord, chart);
    assert.equal(rows(result).length, 9);
    assert.deepEqual((await read(record)).schema, record.schema);
    const original = widget(record, w => w.encoding.series === 'metric');
    const restored = await preview(record, original);
    checkSeries(record, { widgets: { [original.id]: restored } });
  });
}

async function recoveryChecks() {
  await run('R01', '错误 SQL 单组件失败、拒绝发布、恢复查询', async () => {
    const record = await copy(requireCopy('Walmart').id, 'SQL-Recovery');
    const baseline = clone(record.schema);
    const kpi = widget(record, w => w.type === 'kpi');
    const changed = clone(baseline);
    changed.widgets.find(w => w.id === kpi.id).query.sql = 'SELECT guaranteed_missing_uat_field AS total_sales FROM walmart_sales';
    const invalid = await api('POST', `/dashboards/${record.id}/widgets/${kpi.id}/preview`, { schema: changed, filters: {} }, [200, 422]);
    if (invalid.status === 200) assert(invalid.payload.data?.error, '错误 SQL 未返回组件错误');
    assert.match(JSON.stringify(invalid.payload), /guaranteed_missing_uat_field|query_validation_failed/);
    const before = await api('GET', `/dashboards/${record.id}/revisions`);
    // The current product validates on save: it correctly refuses to persist
    // this invalid query before publication can start. Never publish the old,
    // still-valid saved version and pretend it is the invalid draft.
    await api('PUT', `/dashboards/${record.id}`, { schema: changed, expected_revision: record.current_revision }, [422]);
    assert.deepEqual((await read(record)).schema, baseline);
    assert.deepEqual(await api('GET', `/dashboards/${record.id}/revisions`), before);
    const other = widget(record, w => w.type === 'line');
    assert.equal(rows(await preview(record, other)).length, 33);
    assert.equal((await preview(record, kpi)).error, null);
    return '无效 SQL 单组件失败且保存返回 422；未产生发布版本，原查询及其他组件正常。发布按钮的交互流程仍需人工复核。';
  });
  await run('R02', '2099 财年无数据与恢复后的正确 KPI', async () => {
    const record = await read(requireCopy('Apple')); const kpi = widget(record, w => w.type === 'kpi');
    assert(/fiscal_year\s*=\s*2024/i.test(kpi.query.sql));
    const empty = await preview(record, kpi, kpi.query.sql.replace(/fiscal_year\s*=\s*2024/i, 'fiscal_year = 2099'));
    assert.equal(rows(empty).length, 0); assert.equal(empty.row_count, 0);
    const restored = await preview(record, kpi); closeNumber(rows(restored)[0][kpi.encoding.value], 391035, 0);
  });
  await run('R04', '真实修订冲突不能覆盖先保存的版本', async () => {
    const base = await copy(requireCopy('Walmart').id, 'Conflict');
    const a = clone(base.schema); a.dashboard.title += '-A';
    const b = clone(base.schema); b.dashboard.title += '-B';
    const saved = await update(base, a);
    await api('PUT', `/dashboards/${base.id}`, { schema: b, expected_revision: base.current_revision }, [409]);
    const after = await read(base);
    assert.equal(after.current_revision, saved.current_revision); assert.equal(after.schema.dashboard.title, a.dashboard.title);
  });
}

async function publicationChecks() {
  for (const name of ['Walmart', 'Apple']) {
    await run('F01', `${name} 本轮副本刷新并发布`, async () => {
      const record = await read(requireCopy(name)); const snapshot = await refresh(record);
      if (name === 'Apple') { checkApple(record, snapshot); checkSeries(record, snapshot); }
      const publication = await publish(await read(record));
      state.publications[name] = { v1: publication }; saveState();
      const published = await publicData(publication);
      assert.equal(published.dashboard_id, record.id);
      assert.equal(published.schema.widgets.length, record.schema.widgets.length);
      if (name === 'Apple') checkSeries({ schema: published.schema }, published.snapshot);
      return `发布版本 ${publication.published_revision}，历史链接 ${publication.share_path}。`;
    });
    await run('F03', `${name} 仅存草稿不影响公开页、再发布与固定最新`, async () => {
      const record = await read(requireCopy(name)); const pubs = state.publications[name];
      if (!pubs) throw new Blocked('依赖 F01 发布成功。');
      const frozen = await publicData(pubs.v1);
      const changed = clone(record.schema); changed.dashboard.title += ' 第二版';
      changed.dashboard.theme = { preset: 'graphite', mode: 'dark', overrides: {} };
      const saved = await update(record, changed);
      assert.deepEqual(await publicData(pubs.v1), frozen);
      assert.equal((await publicData(pubs.v1, true)).published_revision, pubs.v1.published_revision);
      pubs.v2 = await publish(saved); saveState();
      const v2 = await publicData(pubs.v2); const latest = await publicData(pubs.v1, true);
      assert(pubs.v2.published_revision > pubs.v1.published_revision);
      assert.equal(v2.schema.dashboard.title, changed.dashboard.title);
      assert.equal(v2.schema.dashboard.theme.preset, 'graphite');
      assert.deepEqual(latest.snapshot, v2.snapshot);
      assert.equal(latest.published_revision, pubs.v2.published_revision);
      assert.deepEqual(await publicData(pubs.v1), frozen);
    });
    await run('F04', `${name} 恢复旧发布为新草稿且不改写历史`, async () => {
      const record = await read(requireCopy(name)); const pubs = state.publications[name];
      if (!pubs?.v2) throw new Blocked('依赖 F03 两次发布成功。');
      const old = await publicData(pubs.v1); const newer = await publicData(pubs.v2);
      const restored = await api('POST', `/dashboards/${record.id}/revisions/${pubs.v1.published_revision}/restore`, { expected_revision: record.current_revision });
      assert(restored.current_revision > record.current_revision);
      assert.equal(restored.schema.dashboard.title, old.schema.dashboard.title);
      assert.deepEqual(await publicData(pubs.v1), old); assert.deepEqual(await publicData(pubs.v2), newer);
      assert.equal((await publicData(pubs.v2, true)).published_revision, pubs.v2.published_revision);
      const revisions = await api('GET', `/dashboards/${record.id}/revisions`);
      assert.equal(revisions.length, 2); state.copies[name] = restored; saveState();
    });
    await run('F05', `${name} 工程文件与真实 ZIP 逐文件一致`, async () => {
      const record = await read(requireCopy(name));
      const bundle = await api('GET', `/dashboards/${record.id}/artifacts`);
      const schemaFile = bundle.files.find(f => f.path === 'dashboard.schema.json');
      assert(schemaFile); assert.deepEqual(JSON.parse(schemaFile.content), record.schema);
      for (const file of ['dashboard.plan.json', 'README.md', 'manifest.json']) assert(bundle.files.some(f => f.path === file));
      const sql = bundle.files.filter(f => /^queries\/.+\.sql$/.test(f.path));
      assert.equal(sql.length, record.schema.widgets.length); assert(sql.every(f => f.content.trim().length > 0));
      const zip = await apiContext.get(`/api/v1/dashboards/${record.id}/export`);
      assert.equal(zip.status(), 200);
      const zipPath = artifact(`downloads/${name}.zip`, await zip.body());
      // Python stdlib verifies CRC, names and bytes. Never extracts archive paths.
      const manifestPath = artifact(`downloads/${name}-expected.json`, bundle);
      const { spawnSync } = require('node:child_process');
      const script = 'import json,sys,zipfile; b=json.load(open(sys.argv[2],encoding="utf-8")); z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; expected={b["root"]+"/"+f["path"]:f["content"].encode("utf-8") for f in b["files"]}; assert set(z.namelist())==set(expected); assert all(z.read(k)==v for k,v in expected.items()); print("ZIP CRC / file names / contents passed")';
      const checked = spawnSync(cfg.python, ['-c', script, zipPath, manifestPath], { encoding: 'utf8', timeout: 30000 });
      assert.equal(checked.status, 0, checked.stderr || checked.error?.message);
      return `${bundle.files.length} 个文件；ZIP CRC、文件名、UTF-8 内容和当前 schema 一致。`;
    });
  }
}

async function main() {
  const launch = { headless: true };
  if (cfg.browser_channel && cfg.browser_channel !== 'chromium') launch.channel = cfg.browser_channel;
  browser = await chromium.launch(launch);
  context = await browser.newContext({ baseURL: cfg.base_url, viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1, locale: 'zh-CN', ...(cfg.storage_state ? { storageState: cfg.storage_state } : {}) });
  anonymous = await browser.newContext({ baseURL: cfg.api_url || cfg.base_url, viewport: { width: 1440, height: 900 } });
  const observe = p => p.on('pageerror', error => { if (active) active.browser_errors.push({ url: p.url(), message: error.message }); });
  context.on('page', observe); anonymous.on('page', observe);
  await context.tracing.start({ screenshots: true, snapshots: true });
  page = await context.newPage();
  Object.assign(helpers, { browser, context, anonymous, apiContext, page });
  const ui = require('./browser_checks.cjs');
  const apiOrigins = new Set();
  page.on('request', req => {
    const url = new URL(req.url());
    if (url.pathname.startsWith('/api/v1/dashboards')) apiOrigins.add(url.origin);
  });
  const environment = await run('A01', '真实首页、看板入口、BUILD_ID 与资源加载', async () => {
    for (const url of ['/', '/dashboards/']) {
      const errors = []; const failures = [];
      const onError = error => errors.push(error.message);
      const onResponse = response => { if (response.status() >= 400 && ['document', 'script', 'stylesheet'].includes(response.request().resourceType())) failures.push(`${response.status()} ${response.url()}`); };
      page.on('pageerror', onError); page.on('response', onResponse);
      try {
        const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
        assert.equal(response.status(), 200);
        await expect(page.getByText('数据看板', { exact: true }).first()).toBeVisible();
        const build = await page.locator('#__NEXT_DATA__').textContent();
        const buildId = JSON.parse(build).buildId;
        artifact(`api/A01-${url === '/' ? 'home' : 'dashboards'}-build.json`, { url: page.url(), build_id: buildId });
        if (cfg.expected_build_id) assert.equal(buildId, cfg.expected_build_id, '部署 BUILD_ID 与文档基线不一致；若已重新部署请显式指定 --expected-build-id');
        state.build_id = buildId; assert.deepEqual(errors, []); assert.deepEqual(failures, []);
        await shot(`A01-${url === '/' ? 'home' : 'dashboards'}-1440-evidence`);
      } finally { page.off('pageerror', onError); page.off('response', onResponse); }
    }
    assert(apiOrigins.size <= 1, '页面访问了多个 Dashboard 后端，需要核查部署配置。');
    const observedOrigin = [...apiOrigins][0];
    if (cfg.api_url && observedOrigin) assert.equal(new URL(cfg.api_url).origin, observedOrigin, '--api-url 与真实页面访问的后端不一致。');
    state.api_url = cfg.api_url || observedOrigin || cfg.base_url;
    apiContext = await request.newContext({ baseURL: state.api_url,
      ...(cfg.storage_state ? { storageState: cfg.storage_state } : {}) });
    helpers.apiContext = apiContext;
    await api('GET', '/dashboards/schema'); saveState();
  });
  if (!environment) {
    await run(cfg.source.cases.map(c => c.id).filter(id => id !== 'A01'), '前置环境未通过', () => { throw new Blocked('依赖 A01：页面/版本/资源/服务检查失败。'); });
    return;
  }
  await ui.entryChecks(helpers);
  await dataChecks();
  await recoveryChecks();
  await ui.editorChecks(helpers);
  await publicationChecks();
  await ui.evidenceChecks(helpers);
  await require('./optional_checks.cjs').runOptional(helpers);
  for (const name of ['Walmart', 'Apple']) {
    await run('F07', `${name} 仅撤销本轮历史分享且所有者仍可访问`, async () => {
      const record = requireCopy(name); const pub = state.publications[name]?.v1;
      if (!pub) throw new Blocked('依赖 F01 发布成功。');
      await api('DELETE', `/dashboards/${record.id}/publications/${pub.published_revision}`);
      await api('GET', `/public/dashboards/${publicToken(pub)}`, undefined, [404], anonymous.request);
      assert.equal((await read(record)).id, record.id);
      state.publications[name].v1_revoked = true; saveState();
    });
  }
  await run('A03', '完成后只读核对原资产与原分享未变化', async () => {
    for (const name of ['Walmart', 'Apple']) {
      const original = state.originals[name]; if (!original) throw new Blocked(`缺少 ${name} 原资产基线。`);
      assert.deepEqual(await read(original), original, `运行期间 ${name} 原资产变化（也可能有其他使用者修改，需核查）。`);
      assert.deepEqual(await api('GET', `/dashboards/${original.id}/publications`), state.originals[`${name}Publications`]);
    }
  });
}
main().catch(async error => {
  await run('A01', '自动化运行器异常', () => { throw error; });
  process.exitCode = 1;
}).finally(async () => {
  saveState();
  if (context) await context.tracing.stop({ path: path.join(out, 'browser-trace.zip') }).catch(() => {});
  if (apiContext) await apiContext.dispose();
  if (browser) await browser.close();
});
