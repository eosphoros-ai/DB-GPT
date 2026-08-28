import assert from 'node:assert/strict';
import test from 'node:test';

// @ts-expect-error Node's built-in TypeScript runner requires the extension.
import * as viewModel from './task-files-view-model.ts';

const { TASK_FILE_TABS, buildTaskFileView, getGeneratedTaskFileTab, getNextTaskFileTab, getTaskFileEmptyLabel } =
  viewModel;

const inputs = [{ id: 'input-1' }, { id: 'input-2' }];
const artifacts = [
  { name: 'report.html', type: 'html', id: 'document-1' },
  { name: 'chart-output', type: 'chart', id: 'image-1' },
  { name: 'analysis.py', type: 'file', id: 'code-1' },
];

test('defines one flat tab row with uploaded inputs as its own tab', () => {
  assert.deepEqual(
    TASK_FILE_TABS.map(tab => [tab.key, tab.label]),
    [
      ['all', '全部'],
      ['input', '上传资料'],
      ['document', '文档'],
      ['image', '图片'],
      ['code', '代码文件'],
    ],
  );
});

test('assigns every generated artifact to exactly one output tab', () => {
  assert.equal(getGeneratedTaskFileTab({ name: 'report.pdf', type: 'file' }), 'document');
  assert.equal(getGeneratedTaskFileTab({ name: 'chart-output', type: 'chart' }), 'image');
  assert.equal(getGeneratedTaskFileTab({ name: 'query.sql', type: 'file' }), 'code');
  assert.equal(getGeneratedTaskFileTab({ name: 'unknown.bin', type: 'file' }), 'document');
});

test('shows both sources in all and keeps tab counts mutually exclusive', () => {
  const view = buildTaskFileView(inputs, artifacts, 'all');

  assert.deepEqual(view.visibleInputFiles, inputs);
  assert.deepEqual(view.filteredArtifacts, artifacts);
  assert.deepEqual(view.counts, { all: 5, input: 2, document: 1, image: 1, code: 1 });
  assert.equal(view.counts.input + view.counts.document + view.counts.image + view.counts.code, view.counts.all);
});

test('shows only uploaded files in the input tab', () => {
  const view = buildTaskFileView(inputs, artifacts, 'input');

  assert.deepEqual(view.visibleInputFiles, inputs);
  assert.deepEqual(view.filteredArtifacts, []);
});

test('output tabs never include uploaded files', () => {
  const documentView = buildTaskFileView(inputs, artifacts, 'document');
  const imageView = buildTaskFileView(inputs, artifacts, 'image');
  const codeView = buildTaskFileView(inputs, artifacts, 'code');

  assert.deepEqual(documentView.visibleInputFiles, []);
  assert.deepEqual(
    documentView.filteredArtifacts.map(file => file.id),
    ['document-1'],
  );
  assert.deepEqual(
    imageView.filteredArtifacts.map(file => file.id),
    ['image-1'],
  );
  assert.deepEqual(
    codeView.filteredArtifacts.map(file => file.id),
    ['code-1'],
  );
});

test('keeps empty tabs stable and gives each one a contextual empty state', () => {
  const view = buildTaskFileView([], [], 'image');

  assert.deepEqual(view.counts, { all: 0, input: 0, document: 0, image: 0, code: 0 });
  assert.equal(getTaskFileEmptyLabel('input'), '暂无上传资料');
  assert.equal(getTaskFileEmptyLabel('image'), '暂无生成图片');
});

test('supports wrapped arrow-key navigation across the single tab row', () => {
  assert.equal(getNextTaskFileTab('all', 'ArrowLeft'), 'code');
  assert.equal(getNextTaskFileTab('code', 'ArrowRight'), 'all');
  assert.equal(getNextTaskFileTab('image', 'Home'), 'all');
  assert.equal(getNextTaskFileTab('input', 'End'), 'code');
});
