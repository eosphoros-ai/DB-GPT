/**
 * Unit tests for wiki diff utils (plain tsc + node runner, matching
 * the repo's existing test script pattern).
 */
import assert from 'assert';
import { diffWikiLines } from './line-diff';
import { diffWikiRevision } from './revision-diff';

function run() {
  // same lines are marked as 'same'
  const d1 = diffWikiLines('a\nb\nc', 'a\nb\nc');
  assert.deepStrictEqual(
    d1.map(l => l.type),
    ['same', 'same', 'same'],
  );

  // changed middle line -> del + add
  const d2 = diffWikiLines('a\nb\nc', 'a\nB\nc');
  assert.deepStrictEqual(d2[1], { type: 'del', text: 'b' });
  assert.deepStrictEqual(d2[2], { type: 'add', text: 'B' });

  // pure addition
  const d3 = diffWikiLines('a\nc', 'a\nb\nc');
  assert.deepStrictEqual(d3[1], { type: 'add', text: 'b' });
  assert.strictEqual(d3.filter(l => l.type === 'same').length, 2);

  // common suffix trimming
  const d4 = diffWikiLines('x\nend', 'y\nend');
  assert.deepStrictEqual(d4[0], { type: 'del', text: 'x' });
  assert.deepStrictEqual(d4[1], { type: 'add', text: 'y' });

  // revision diff omits unchanged fields
  const sections = diffWikiRevision(
    { title: 't', summary: 's1', content: 'a\nb' },
    { title: 't', summary: 's2', content: 'a\nc' },
  );
  assert.deepStrictEqual(
    sections.map(s => s.field),
    ['summary', 'content'],
  );
  const contentSection = sections[1];
  assert.strictEqual(
    contentSection.lines.some(l => l.type === 'del' && l.text === 'b'),
    true,
  );
  assert.strictEqual(
    contentSection.lines.some(l => l.type === 'add' && l.text === 'c'),
    true,
  );

  // degrade guard: over-limit input still returns del+add blocks
  const bigOld = Array.from({ length: 2000 }, (_, i) => `old-${i}`).join('\n');
  const bigNew = Array.from({ length: 2000 }, (_, i) => `new-${i}`).join('\n');
  const d5 = diffWikiLines(bigOld, bigNew);
  assert.strictEqual(d5.filter(l => l.type === 'del').length, 2000);
  assert.strictEqual(d5.filter(l => l.type === 'add').length, 2000);

  console.log('wiki diff utils: all assertions passed');
}

run();
