// Agent artifact persistence and async scope tests; no browser claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '../..');
const requireWeb = Module.createRequire(path.join(root, 'web/package.json'));
const React = requireWeb('react');
const ts = requireWeb('typescript');
const originalLoad = Module._load;
const folder = path.join(root, 'web/new-components/financial-analysis');
const requests = [];
const calls = [];
const api = {
  getReport: (sessionId, runId, signal) => new Promise((resolve, reject) => requests.push({ sessionId, runId, signal, resolve, reject })),
  getSourcePage: (...args) => calls.push(['page', ...args]),
  downloadSource: (...args) => calls.push(['source', ...args]),
  listExports: (...args) => calls.push(['list', ...args]),
  createExport: async (...args) => { calls.push(['create', ...args]); return { id: 'export' }; },
  downloadExport: (...args) => calls.push(['download', ...args]),
  requestError: error => error.message,
};
Module._load = function (id, parent, main) {
  if (id === 'react') return React;
  if (id === 'antd') return {
    Alert: props => React.createElement('aside', null, props.message, props.action),
    Button: props => React.createElement('button', props, props.children),
    Spin: () => React.createElement('i'),
  };
  if (parent?.filename === path.join(folder, 'FinancialReportArtifact.tsx')) {
    if (id === './api') return api;
    if (id === './FinancialAnalysisPage') return props => React.createElement('report', props);
  }
  return originalLoad.call(this, id, parent, main);
};
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  const result = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true,
  } });
  module._compile(result.outputText, filename);
};
const { act, create } = require(path.resolve(process.argv[2]));
const { isFinancialReportReference, reportArtifactContent } = require(path.join(folder, 'agent-artifact.ts'));
const { default: Artifact, downloadFinancialReport } = require(path.join(folder, 'FinancialReportArtifact.tsx'));
const ref = { kind: 'financial-report', title: '真实财报', runId: 'f2345678-1234-1234-1234-123456789abc', sessionId: 'conversation-a', revision: 'v1' };
assert.ok(isFinancialReportReference(ref));
assert.deepEqual(reportArtifactContent(JSON.parse(JSON.stringify(ref))), ref); // history replay
assert.equal(reportArtifactContent({ html: '<h1>Old report</h1>' }), '<h1>Old report</h1>');
assert.equal(isFinancialReportReference({ ...ref, sessionId: '../other' }), false);
assert.equal(isFinancialReportReference({ ...ref, runId: 'https://other' }), false);
async function main() {
  let view;
  await act(async () => { view = create(React.createElement(Artifact, { reference: ref })); });
  const first = requests[0];
  const next = { ...ref, sessionId: 'conversation-b' };
  await act(async () => { view.update(React.createElement(Artifact, { reference: next })); });
  assert.equal(first.signal.aborted, true);
  await act(async () => first.resolve({ company: 'stale' }));
  assert.equal(view.root.findAllByType('report').length, 0);
  const data = { revision: 'v2', company: 'current' };
  await act(async () => requests[1].resolve(data));
  let props = view.root.findByType('report').props;
  assert.equal(props.embedded, true);
  assert.equal(props.questionAccess, undefined); // main agent remains the only chat
  assert.equal(props.data, data);
  const retries = [];
  await act(async () => view.update(React.createElement(Artifact, {
    reference: next, onTopicRetry: (reference, topicId) => retries.push([reference, topicId]),
  })));
  props = view.root.findByType('report').props;
  props.onTopicRetry('expenses');
  assert.deepEqual(retries, [[next, 'expenses']]);
  props.sourceAccess.loadPage('doc', 7, undefined);
  assert.deepEqual(calls.pop(), ['page', 'conversation-b', ref.runId, 'doc', 7, undefined]);
  await props.exportAccess.create('json', data.revision);
  assert.deepEqual(calls.pop(), ['create', 'conversation-b', ref.runId, 'v2', 'json']);
  await act(async () => view.update(React.createElement(Artifact, { reference: { ...next, revision: 'v3' } })));
  assert.equal(view.root.findAllByType('report').length, 0);
  await act(async () => requests[2].reject(new Error('暂不可用')));
  assert.ok(JSON.stringify(view.toJSON()).includes('暂不可用'));
  await act(async () => view.root.findByType('button').props.onClick());
  await act(async () => requests[3].resolve(data));
  const download = downloadFinancialReport(next);
  requests[4].resolve(data);
  await download;
  assert.deepEqual(calls.slice(-2), [
    ['create', 'conversation-b', ref.runId, 'v2', 'html'],
    ['download', 'conversation-b', ref.runId, { id: 'export' }],
  ]);
  act(() => view.unmount());
  console.log('PASS agent artifact: history descriptor, scope switch, stale response, embedded report, sources, export, retry.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
