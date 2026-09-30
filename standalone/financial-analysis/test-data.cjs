// Headless rendering regression: real React/Ant Design, bounded stubs for charts
// and the existing Manus panel. Does not claim browser layout coverage.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const requireWeb = Module.createRequire(path.resolve(__dirname, '../../web/package.json'));
const ts = requireWeb('typescript');
const React = requireWeb('react');
const { renderToStaticMarkup } = requireWeb('react-dom/server');
const folder = path.resolve(__dirname, '../../web/new-components/financial-analysis');
const originalLoad = Module._load;
const captures = { charts: [], agents: [], buttons: [] };
const createElement = React.createElement;
React.createElement = (type, props, ...children) => {
  if (type === 'button') captures.buttons.push({ ...props, children });
  return createElement(type, props, ...children);
};
Module._load = function (id, parent, main) {
  if (id === 'next/router') return { useRouter: () => ({ push() {} }) };
  if (id === 'next/dynamic') return loader => {
    if (String(loader).includes('FinancialChart')) return ({ config }) => {
      captures.charts.push(config);
      return React.createElement('div', { 'data-chart': config.chartType });
    };
    return props => {
      captures.agents.push(props);
      return React.createElement('aside', null, props.userQuery, props.assistantText);
    };
  };
  return originalLoad.call(this, id, parent, main);
};
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  const result = ts.transpileModule(source, { fileName: filename, compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React,
    esModuleInterop: true,
  } });
  module._compile(result.outputText, filename);
};
require.extensions['.css'] = module => { module.exports = { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) }; };
const { ReportDataProvider } = require(path.join(folder, 'ReportDataContext.tsx'));
const { mockReportData } = require(path.join(folder, 'mock-report.ts'));
const { alternateReportFixture, emptyReportFixture } = require(path.join(folder, 'report-fixtures.ts'));
const { resolveEvidence, periodRange } = require(path.join(folder, 'report-data.ts'));
const sections = require(path.join(folder, 'ReportSections.tsx'));
const Page = require(path.join(folder, 'FinancialAnalysisPage.tsx')).default;
if (process.env.FINANCIAL_LAYOUT_CHILD !== 'baseline') {
  const embeddedOutput = renderToStaticMarkup(React.createElement(Page, { data: alternateReportFixture, embedded: true }));
  assert.ok(embeddedOutput.includes(alternateReportFixture.report.companyName));
  assert.ok(embeddedOutput.includes('财务分析章节'));
  assert.ok(!embeddedOutput.includes('DB-GPT Agent 任务'));
  assert.ok(!embeddedOutput.includes('Agent Workspace'));
}
const Evidence = require(path.join(folder, 'EvidencePanel.tsx')).default;
const Execution = require(path.join(folder, 'ExecutionProcessPanel.tsx')).default;
const Source = require(path.join(folder, 'SourcePreviewPanel.tsx')).default;
const { evidencePages } = require(path.join(folder, 'PdfPagePreview.tsx'));
assert.deepEqual(evidencePages({ page: 164, headerPage: 161, unitPage: 160 }), [164, 161, 160]);
assert.deepEqual(evidencePages({ page: 8, headerPage: 8, unitPage: 8 }), [8]);
const sourceProps = {
  document: { id: 'doc-source', fileName: 'original.pdf', fiscalPeriod: '2024', pageCount: 200, version: '原件' },
  evidence: { id: 'E-test', page: 164, snippet: '负债合计 80', headerPage: 161, headerSnippet: '2024年末', unitPage: 160, unitText: '单位：元' },
  onBack: () => {},
};
const sourceDemo = renderToStaticMarkup(React.createElement(Source, sourceProps));
assert.ok(!sourceDemo.includes('下载原 PDF'));
const realSource = renderToStaticMarkup(React.createElement(Source, { ...sourceProps, sourceAccess: { loadPage: () => { throw new Error('SSR must not fetch'); }, download: () => {} } }));
for (const text of ['PDF 物理页码', '指标所在页', '表头所在页', '单位所在页', '164', '161', '160', '负债合计 80', '下载原 PDF']) assert.ok(realSource.includes(text));
const Agent = require(path.join(folder, 'AgentRunPanel.tsx')).default;
const noop = () => {};
const render = (Component, data, props = {}) => renderToStaticMarkup(React.createElement(
  ReportDataProvider, { data }, React.createElement(Component, { onOpenEvidence: noop, ...props }),
));
const analysisStep = { id: 'analyze', order: 5, type: 'analysis', title: '生成并校验模型分析', detail: '财务数据已保存。', status: 'completed' };
const analysisBase = { ...alternateReportFixture, steps: [...alternateReportFixture.steps, analysisStep] };
for (const [status, expected] of Object.entries({
  running: '分析中', completed: '分析完成', partial: '部分分析', failed: '分析未完成',
})) {
  const report = { ...analysisBase, analysis: { status, modelName: 'qwen-test', rejectedCount: 0 } };
  let retried = false, refreshed = false;
  const actions = { retry: () => { retried = true; }, refresh: () => { refreshed = true; }, busy: false, error: '网络中断' };
  // Analysis state/actions must not change the report surface or add a banner.
  const withoutHeader = markup => markup.replace(/<header[\s\S]*?<\/header>/, '');
  assert.equal(withoutHeader(renderToStaticMarkup(React.createElement(Page, { data: report, analysisActions: actions }))),
    withoutHeader(renderToStaticMarkup(React.createElement(Page, { data: analysisBase }))));
  captures.buttons.length = 0;
  const panel = render(Execution, report, { activeStepId: 'analyze', onStepSelect: noop, analysisActions: actions });
  assert.ok(panel.includes(expected));
  assert.equal(panel.includes('重新分析此文件'), status === 'failed' || status === 'partial');
  if (status === 'failed' || status === 'partial') {
    captures.buttons.find(button => button.children.includes('重新分析此文件')).onClick();
    assert.ok(retried);
  }
  captures.buttons.find(button => button.children.includes('重新读取进度')).onClick();
  assert.ok(refreshed);
  const otherStep = render(Execution, report, { activeStepId: report.steps[0].id, onStepSelect: noop, analysisActions: actions });
  assert.ok(!otherStep.includes('重新分析此文件') && !otherStep.includes('网络中断'));
}
const forbidden = /2019|2018|2017|26\.61|21\.14|0\.57|0\.77|4\.06|3\.42|安靠|E35|finding-earnings/;
for (const data of [alternateReportFixture, emptyReportFixture]) {
  for (const Component of Object.values(sections)) {
    if (typeof Component !== 'function') continue;
    assert.doesNotMatch(render(Component, data), forbidden);
  }
  assert.doesNotMatch(render(Evidence, data, { selection: { metricId: 'metric-other' }, onFindingChange: noop, onOpenSource: noop }), forbidden);
  assert.doesNotMatch(render(Execution, data, { onStepSelect: noop }), forbidden);
  assert.doesNotMatch(renderToStaticMarkup(React.createElement(Page, { data })), forbidden);
}
const swapped = renderToStaticMarkup(React.createElement(Page, { data: alternateReportFixture }));
assert.match(swapped, /替换数据测试公司/);
assert.match(swapped, /alternate-2024.pdf/);
assert.match(swapped, /120/);
assert.match(swapped, /Running/);
const statements = render(sections.StatementsTab, alternateReportFixture);
for (const value of ['2024', '2022', '2020', '120 元', '未识别']) assert.ok(statements.includes(value));
const independent = resolveEvidence(alternateReportFixture, { metricId: 'metric-other' });
assert.equal(independent.finding, undefined);
assert.equal(independent.facts[0].id, 'value-other');
assert.equal(independent.evidence[0].id, 'source-other');
assert.equal(independent.documents[0].id, 'document-other');
assert.equal(resolveEvidence(alternateReportFixture, { calculationId: 'ratio-other' }).facts[0].id, 'value-other');
assert.equal(resolveEvidence(alternateReportFixture, { evidenceId: 'source-other' }).facts[0].id, 'value-other');
assert.equal(resolveEvidence(mockReportData, { findingId: 'missing' }).facts.length, 0);
let selected;
captures.buttons.length = 0;
render(sections.OverviewTab, alternateReportFixture, { onOpenEvidence: value => { selected = value; } });
captures.buttons.find(button => button['aria-label'] === '营业收入：查看source-other · PDF 12').onClick();
assert.equal(selected.metricId, 'metric-other');
assert.equal(resolveEvidence(alternateReportFixture, selected).evidence[0].id, 'source-other');
captures.buttons.length = 0;
render(sections.StatementsTab, mockReportData, { onOpenEvidence: value => { selected = value; } });
captures.buttons.find(button => button.children.includes('E4')).onClick();
assert.equal(selected.evidenceId, 'E4');
assert.ok(resolveEvidence(mockReportData, selected).facts.some(fact => fact.id === 'fact-revenue-2018'));
assert.equal(periodRange([{ year: '2024' }]), '2024');
assert.ok(captures.charts.some(chart => chart.data.some(point => point.value === -3)));
assert.ok(captures.charts.some(chart => chart.data.length === 1 && chart.data[0].year === '2024'));
render(Agent, alternateReportFixture, { onStepSelect: noop, onOpenArtifact: noop, onOpenFiles: noop });
assert.equal(captures.agents.at(-1).sections[0].isCompleted, false);
assert.equal(captures.agents.at(-1).artifacts.length, 0);
const demo = renderToStaticMarkup(React.createElement(Page, { data: mockReportData }));
assert.match(demo, /江苏安靠/);
assert.match(demo, /2017–2019/);
assert.match(demo, /21.14/);
assert.match(demo, /非经常性损益/);
console.log('Financial report regression passed: alternate/empty/demo rendering, periods, missing values, charts, independent evidence, agent state.');
if (process.env.FINANCIAL_LAYOUT_CHILD !== 'baseline') {
  const TopicCoverage = require(path.join(folder, 'TopicCoverage.tsx')).default;
  const topicReport = structuredClone(alternateReportFixture);
  topicReport.workflow = { status: 'draft', review: null, history: [], topics: [
    { id: 'expenses', title: '费用变化', status: 'failed', findingIds: [], note: '本专题失败，其他专题已保存', history: [] },
    { id: 'cashflow', title: '现金流', status: 'insufficient', findingIds: [], note: '缺少现金流数据', history: [] },
  ] };
  const retries = [];
  captures.buttons.length = 0;
  const output = render(TopicCoverage, topicReport, { onRetry: id => retries.push(id) });
  assert.ok(output.includes('分析失败') && output.includes('数据或依据不足'));
  captures.buttons.find(button => String(button.children).includes('重新分析')).onClick();
  assert.deepEqual(retries, ['expenses']);
  captures.buttons.length = 0;
  render(TopicCoverage, topicReport, { onRetry: noop, busy: true });
  assert.ok(captures.buttons.filter(button => String(button.children).includes('重新分析')).every(button => button.disabled));
  topicReport.workflow.topics = [];
  const cashId = topicReport.sections.cashflow.findingIds[0];
  const cashFinding = topicReport.findings.find(finding => finding.id === cashId);
  if (cashFinding) {
    topicReport.findings.push({ ...cashFinding, id: 'cash-extra', title: '额外现金流专题发现' });
    topicReport.sections.cashflow.findingIds.push('cash-extra');
    assert.ok(render(sections.CashFlowTab, topicReport).includes('额外现金流专题发现'));
  }
}

for (const filename of process.argv.slice(2)) {
  const data = JSON.parse(fs.readFileSync(filename, 'utf8'));
  assert.equal(data.mode, 'report');
  const output = renderToStaticMarkup(React.createElement(Page, { data }));
  assert.ok(output.includes(data.report.companyName));
  captures.buttons.length = 0;
  const overview = render(sections.OverviewTab, data, { onOpenEvidence: value => { selected = value; } });
  for (const metric of data.metrics) {
    assert.ok(overview.includes(metric.changeDisplay));
    captures.buttons.find(button => button['aria-label'] === `${metric.name}：查看${metric.citationLabel}`).onClick();
    const resolved = resolveEvidence(data, selected);
    assert.equal(resolved.calculations[0].id, metric.calculationId);
    assert.ok(resolved.facts.length >= 2);
    assert.ok(resolved.evidence.length > 0);
  }
  const statements = render(sections.StatementsTab, data);
  for (const fact of data.facts) assert.ok(statements.includes(fact.displayValue));
  if (data.sections.profitability.rateComparisons?.length) {
    captures.buttons.length = 0;
    const profitability = render(sections.ProfitabilityTab, data, { onOpenEvidence: value => { selected = value; } });
    assert.ok(profitability.includes('毛利率与费用率'));
    assert.ok(profitability.includes('变动（百分点）'));
    for (const row of data.sections.profitability.rateComparisons) {
      for (const key of ['currentCalculationId', 'previousCalculationId', 'changeCalculationId']) {
        const calculation = data.calculations.find(c => c.id === row[key]);
        assert.ok(profitability.includes(calculation.displayResult));
        captures.buttons.find(button => button.title === calculation.name).onClick();
        assert.equal(selected.calculationId, calculation.id);
        const resolved = resolveEvidence(data, selected);
        assert.deepEqual(new Set(resolved.facts.map(f => f.id)), new Set(calculation.inputFactIds));
        assert.ok(resolved.evidence.length > 0);
      }
    }
    for (const point of data.trends.expenses) {
      assert.ok(captures.charts.some(chart => chart.data.includes(point)));
      const calculation = data.calculations.find(c => c.id === point.calculationId);
      assert.equal(point.value, Number(calculation.result));
      assert.equal(point.year, calculation.fiscalPeriod);
    }
  }
  for (const calculation of data.calculations) {
    const details = render(Evidence, data, { selection: { calculationId: calculation.id }, onFindingChange: noop, onOpenSource: noop });
    assert.ok(details.includes(calculation.displayResult));
    for (const step of calculation.steps) assert.ok(details.includes(step));
  }
  for (const finding of data.findings) {
    const resolved = resolveEvidence(data, { findingId: finding.id });
    assert.ok(resolved.facts.length && resolved.evidence.length);
    const details = render(Evidence, data, { selection: { findingId: finding.id }, onFindingChange: noop, onOpenSource: noop });
    assert.ok(details.includes(finding.title));
    assert.ok(!finding.summary.includes('{{'));
    for (const id of finding.factIds) assert.ok(resolved.facts.some(fact => fact.id === id));
  }
  console.log(`Real report rendering and metric-to-evidence navigation passed: ${path.basename(filename)}`);
}
