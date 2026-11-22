const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const ts = require('../../../web/node_modules/typescript');

// Evaluate the actual export adapter with no runtime imports available.
const source = fs.readFileSync(path.join(__dirname, 'taskflow.ts'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
const api = {};
vm.runInNewContext(compiled, {
  exports: api,
  require(name) { throw new Error(`Offline parser imported runtime module: ${name}`); },
});
const plain = value => JSON.parse(JSON.stringify(value));
const marker = value => '```vis-flow-step\n' + JSON.stringify(value) + '\n```\n';

test('saved final frames retain their earlier execution trace without duplicating answers', () => {
  const trace = [{ id: 'tool', action: 'read_financial_report', status: 'completed' }];
  const result = api.parseTaskflowStream(
    'Saved context\n' + marker({ step_id: 'read', steps: trace }) + 'Working\n' +
    marker({ step_id: 'read' }) + 'Verified financial result',
  );
  assert.equal(result.sections.length, 1);
  assert.equal(result.cleanText, 'Saved context\n\nVerified financial result');
  assert.deepEqual(plain(result.sections[0].marker.steps), trace);
  assert.deepEqual(plain(result.markers[0].steps), trace);
});

test('saved inline query payloads and file metadata survive artifact extraction', () => {
  const query = { sql: 'SELECT 1', columns: ['value'], rows: [[1]] };
  const content = 'Conclusion\n```vis-flow-artifact\n' + JSON.stringify([
    { type: 'query', name: 'Saved data', query, row_count: 1 },
    { type: 'html', name: 'Report', path: '/reports/saved.html', size: 123 },
  ]) + '\n```';
  const result = api.extractFlowArtifacts(content);
  assert.equal(result.clean, 'Conclusion');
  assert.deepEqual(plain(result.artifacts), [
    { type: 'query', name: 'Saved data', path: '', query, row_count: 1 },
    { type: 'html', name: 'Report', path: '/reports/saved.html', size: 123 },
  ]);
});

test('malformed markers remain readable and display filters keep conclusions', () => {
  assert.match(api.parseTaskflowStream('```vis-flow-step\n{bad}\n```').residual, /bad/);
  assert.equal(api.stripVisBlocks('Conclusion\n```vis-chart\n{}\n```'), 'Conclusion');
  assert.equal(api.stripFlowNarration('💭 Working\nVerified finding\n🔧 read_report'), 'Verified finding');
});
