// Stateful checks with host controls; these do not replace browser acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '../..');
const requireWeb = Module.createRequire(path.join(root, 'web/package.json'));
const React = requireWeb('react');
const ts = requireWeb('typescript');
const originalLoad = Module._load;
const host = tag => props => React.createElement(tag, props, props.children);
const List = props => React.createElement('ul', null, props.dataSource.length ? props.dataSource.map(item => React.cloneElement(props.renderItem(item), { key: item.id })) : props.locale.emptyText);
List.Item = props => React.createElement('li', null, props.children, props.actions);
List.Item.Meta = props => React.createElement('div', null, props.title, props.description);
Module._load = function (id, parent, main) {
  if (id === 'react') return React;
  if (id === 'antd') return { Button: host('button'), Space: host('div'), Typography: { Title: host('h4') }, List };
  return originalLoad.call(this, id, parent, main);
};
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  const result = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true,
  } });
  module._compile(result.outputText, filename);
};
require.extensions['.css'] = module => { module.exports = { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) }; };
const { act, create } = require(path.resolve(process.argv[2]));
const folder = path.join(root, 'web/new-components/financial-analysis');
const History = require(path.join(folder, 'ReportHistory.tsx')).default;
const Exports = require(path.join(folder, 'ReportExports.tsx')).default;
const { ReportDataProvider } = require(path.join(folder, 'ReportDataContext.tsx'));
const { alternateReportFixture: report } = require(path.join(folder, 'report-fixtures.ts'));
const { reportRunState } = require(path.join(folder, 'report-data.ts'));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
async function main() {
  let view, selected;
  const text = () => JSON.stringify(view.toJSON(), (key, value) => key === 'props' ? undefined : value);
  const button = label => view.root.findAllByType('button').find(b => b.props.children === label);
  const requests = [];
  const load = (page, signal) => { const gate = deferred(); requests.push({ page, signal, ...gate }); return gate.promise; };
  await act(async () => { view = create(React.createElement(History, { load, onOpen: run => { selected = run; } })); });
  const run = { id: 'run-a', session_id: 'session-a', created_at: '2026-09-27T00:00:00Z', report_ready: true, status: 'completed', analysis_status: 'running', title: '真实公司' };
  await act(async () => requests[0].resolve({ items: [run], total: 11, page: 1, page_size: 10 }));
  assert.ok(text().includes('分析中'));
  act(() => button('打开报告').props.onClick());
  assert.equal(selected, run);
  await act(async () => button('下一页').props.onClick());
  assert.equal(requests[1].page, 2);
  assert.ok(requests[0].signal.aborted);
  await act(async () => requests[1].reject(new Error('network')));
  assert.ok(text().includes('历史记录读取失败'));
  await act(async () => button('重试').props.onClick());
  await act(async () => requests[2].resolve({ items: [], total: 0, page: 2, page_size: 10 }));
  assert.ok(text().includes('暂无历史报告'));
  await act(async () => button('刷新').props.onClick());
  act(() => view.unmount());
  assert.ok(requests[3].signal.aborted);
  await act(async () => requests[3].resolve({ items: [run], total: 1, page: 2, page_size: 10 }));

  const listing = deferred();
  let generation = deferred();
  const creates = [], downloads = [];
  const file = { id: 'export-a', file_name: 'actual.json', revision: report.revision, size_bytes: 1200 };
  const access = {
    list: () => listing.promise,
    create: (format, revision) => { creates.push({ format, revision }); return generation.promise; },
    download: async value => { downloads.push(value); },
  };
  const tree = data => React.createElement(ReportDataProvider, { data }, React.createElement(Exports, { access }));
  await act(async () => { view = create(tree(report)); });
  await act(async () => { button('导出 JSON').props.onClick(); button('导出 JSON').props.onClick(); });
  assert.deepEqual(creates, [{ format: 'json', revision: report.revision }]);
  assert.ok(!text().includes(file.file_name));
  await act(async () => generation.resolve(file));
  assert.deepEqual(downloads, [file]);
  assert.ok(text().includes(file.file_name));
  // A slow initial listing must not erase the file just created.
  await act(async () => listing.resolve([]));
  assert.ok(text().includes(file.file_name));
  await act(async () => button('下载 →').props.onClick());
  assert.equal(creates.length, 1);
  assert.equal(downloads.length, 2);
  generation = deferred();
  await act(async () => button('导出 HTML').props.onClick());
  await act(async () => generation.reject(new Error('HTML 组件尚未构建')));
  assert.ok(text().includes('HTML 组件尚未构建'));
  assert.equal(view.root.findAllByType('strong').length, 1);
  await act(async () => view.update(tree({ ...report, analysis: { status: 'running' } })));
  assert.ok(button('导出 JSON').props.disabled);
  assert.ok(button('导出 HTML').props.disabled);
  act(() => view.unmount());
  for (const [status, label, working] of [['running', '分析中', true], ['partial', '分析中', true], ['failed', '数据可用 · 分析未完成', false]]) {
    const state = reportRunState({ ...report, analysis: { status } });
    assert.equal(state.label, label);
    assert.equal(state.working, working);
    assert.equal(state.complete, false);
  }
  for (const status of ['partial', 'completed']) {
    const analysis = {status, completedAt:'2026-10-18T00:00:00Z'};
    assert.deepEqual(reportRunState({...report, analysis}), {label:'报告已生成', working:false, complete:true});
    assert.deepEqual(reportRunState({...report, analysis, workflow:{status:'draft'}}), {label:'分析中', working:true, complete:false});
    assert.deepEqual(reportRunState({...report, analysis, workflow:{status:'published'}}), {label:'报告已生成', working:false, complete:true});
  }
  console.log('PASS history pagination/reopen/retry/cancel; export duplicate guard, persistence, slow list, failure and analysis status.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
