const fs = require('node:fs');
const assert = require('node:assert/strict');
const ts = require('typescript');
const { JSDOM } = require('jsdom');
const source = fs.readFileSync('new-components/report/HtmlReportEvidence.tsx', 'utf8');
const metric = source.slice(source.indexOf('function isEvidenceMetric('), source.indexOf('/** Render an actual'));
const bridge = source.slice(source.indexOf('const bridgeHtml ='), source.indexOf('const formatMilliseconds'));
const compiled = ts.transpileModule(metric + '\n' + bridge + '\nmodule.exports = bridgeHtml;', {compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
const mod = { exports: {} };
new Function('module', compiled)(mod);
(async () => {
  {
    const excerpt = ('原始知识库表格 | GMV | 订单 | ').repeat(12);
    const dom = new JSDOM(mod.exports(`<html><head></head><body><p>已编写的口径说明<span id="kb" data-dbgpt-artifacts="reference-source" data-dbgpt-evidence-label="${excerpt}">${excerpt}</span></p><span id="quote" data-dbgpt-artifacts="reference-quote" data-dbgpt-artifact-selectors='{"reference-quote":{"quote":"短引用"}}'>短引用</span></body></html>`, {}), {runScripts:'dangerously', pretendToBeVisual:true});
    dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
    const kb = dom.window.document.getElementById('kb');
    assert.equal(kb.textContent, '知识库来源');
    assert.equal(kb.getAttribute('data-dbgpt-artifacts'), 'reference-source');
    assert.equal(dom.window.document.getElementById('quote').textContent, '短引用');
    assert.ok(dom.window.document.body.textContent.includes('已编写的口径说明'));
    let messages = [];
    dom.window.postMessage = message => messages.push(message);
    kb.dispatchEvent(new dom.window.MouseEvent('click', {bubbles:true}));
    assert.ok(messages.some(message => message.artifactIds?.includes('reference-source')));
    await new Promise(resolve => setTimeout(resolve, 50));
    dom.window.close();
  }
  for (const value of ['+5.90pp', '-2.10pp', '5.9百分点', '5.9个百分点', '50.26%', '45—60', '2.8—3.2', '高于 90', '低于 30', 'Revenue', '2018-09-01', '2018-09', '说明文字']) {
    const expected = !['Revenue', '2018-09-01', '2018-09', '说明文字'].includes(value);
    const dom = new JSDOM(mod.exports(`<html><head></head><body><span id="value" data-dbgpt-artifacts="python-ratio">${value}</span></body></html>`, {}), {runScripts:'dangerously', pretendToBeVisual:true});
    dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));
    const node = dom.window.document.getElementById('value');
    assert.equal(!!dom.window.document.querySelector('[data-dbgpt-evidence-control="true"]'), expected, value);
    let messages = [];
    dom.window.postMessage = message => messages.push(message);
    node.dispatchEvent(new dom.window.MouseEvent('click', {bubbles:true}));
    node.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key:'Enter', bubbles:true}));
    node.dispatchEvent(new dom.window.KeyboardEvent('keydown', {key:' ', bubbles:true}));
    assert.equal(messages.length, expected ? 3 : 0, `${value} mouse and keyboard`);
    await new Promise(resolve => setTimeout(resolve, 50));
    dom.window.close();
  }
  console.log('Evidence metric bridge: 13 values, controls, click, Enter and Space passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
