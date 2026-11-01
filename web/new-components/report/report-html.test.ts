import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeReportHtml } from './report-html';

test('unwraps saved text nodes around inline evidence without changing bindings', () => {
  const evidence = `<span data-dbgpt-artifacts="python-1" data-dbgpt-artifact-selectors='{"python-1":{"field":"sales"}}'>7%</span>`;
  assert.equal(
    normalizeReportHtml(`<p>{'text': '假日占比 ${evidence}。'} {'text': '建议提前备货。'}</p>`),
    `<p>假日占比 ${evidence}。 建议提前备货。</p>`,
  );
});

test('preserves literal examples, script data, attributes and ordinary text', () => {
  const html = `<script>const x = {'text': 'script'};</script><pre>{'text': 'example'}</pre><code>{"text": "code"}</code><p title="{'text': 'attribute'}">text analysis '}</p>`;
  assert.equal(normalizeReportHtml(html), html);
});

test('handles double quoted text nodes and preserves prose apostrophes', () => {
  assert.equal(normalizeReportHtml(`<p>{"text": "Store's sales"}{'text': 'next'}</p>`), `<p>Store's salesnext</p>`);
});
