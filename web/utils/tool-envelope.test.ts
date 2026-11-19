import { describe, expect, it } from 'vitest';
import { envelopeEmbeddedOutputs, extractEnvelopeObjects, publicToolProgressText } from './tool-envelope';

const html = '<body data-dbgpt-er="1"><svg><text>orders</text></svg></body>';
const files = ['drawio', 'dbml', 'mmd', 'svg', 'json'].map(ext => ({
  output_type: 'file',
  content: { name: `er-diagram.${ext}`, file_path: `/tmp/er-diagram.${ext}`, content: `actual-${ext}` },
}));
const erResult = { success: true, chunks: [{ output_type: 'html', content: html, title: 'ER' }, ...files] };
const parallel = () =>
  JSON.stringify([
    {
      name: 'todowrite',
      success: true,
      content: JSON.stringify({ chunks: [{ output_type: 'text', content: 'done' }] }),
    },
    {
      name: 'generate_er_diagram',
      success: true,
      content: '<persisted-output>Preview (first 1500 chars): ...</persisted-output>',
      observation: JSON.stringify(erResult),
    },
  ]);

describe('public tool progress', () => {
  it('unwraps completed text and markdown without exposing metadata', () => {
    expect(
      publicToolProgressText(
        JSON.stringify({
          chunks: [
            { output_type: 'text', content: '开始生成 4 个组件' },
            { output_type: 'markdown', content: '**正在验证 SQL**' },
          ],
          dashboard_id: 'internal-id',
        }),
      ),
    ).toBe('开始生成 4 个组件\n\n**正在验证 SQL**');
  });

  it('does not flash partially streamed JSON syntax', () => {
    for (const text of ['{', '{"', '{"c', '{"ch', '{"chunks"', '{"chunks":']) {
      expect(publicToolProgressText(text, true)).toBe('');
    }
    expect(publicToolProgressText('{"chunks": [', true)).toBe('');
    expect(publicToolProgressText('{"chunks": [{"output_type":"text","content":"开始生成"}', true)).toBe('开始生成');
  });

  it('preserves prose, unrelated JSON and fenced examples', () => {
    for (const text of ['开始生成', '{"status":"ok"}', '```json\n{"chunks":[]}\n```']) {
      expect(publicToolProgressText(text)).toBe(text);
    }
  });
});

describe('parallel tool artifacts', () => {
  it('recovers full ER and all downloads from uncapped observations', () => {
    const outputs = envelopeEmbeddedOutputs(parallel());
    expect(outputs).toHaveLength(6);
    expect(outputs[0]).toEqual({ type: 'html', content: { content: html, title: 'ER' } });
    expect(outputs.slice(1).map(item => item.content)).toEqual(files.map(item => item.content));
    expect(outputs[0].content.content).not.toContain('persisted-output');
  });

  it('uses content when a short tool result has no observation', () => {
    const text = JSON.stringify([{ name: 'generate_er_diagram', success: true, content: JSON.stringify(erResult) }]);
    expect(envelopeEmbeddedOutputs(text)).toHaveLength(6);
  });

  it('preserves query artifacts from concurrent sql calls', () => {
    const query = { columns: ['table'], rows: [['orders']], truncated: false };
    const text = JSON.stringify([
      {
        name: 'sql_query',
        success: true,
        observation: JSON.stringify({
          artifact_id: 'sql-1',
          chunks: [{ output_type: 'query', content: query }],
        }),
      },
    ]);
    expect(envelopeEmbeddedOutputs(text)).toEqual([{ type: 'query', content: query }]);
  });

  it('keeps direct, embedded and structured HTML envelopes compatible', () => {
    expect(envelopeEmbeddedOutputs(JSON.stringify(erResult))).toHaveLength(6);
    expect(extractEnvelopeObjects(`before ${JSON.stringify(erResult)} after`)).toEqual([erResult]);
    expect(
      envelopeEmbeddedOutputs(
        JSON.stringify({
          chunks: [
            {
              output_type: 'html',
              content: { content: html, title: 'PI ER' },
            },
          ],
        }),
      )[0].content,
    ).toEqual({ content: html, title: 'PI ER' });
  });

  it('ignores failed calls and non-artifact user data', () => {
    expect(
      envelopeEmbeddedOutputs(
        JSON.stringify([{ name: 'generate_er_diagram', success: false, observation: JSON.stringify(erResult) }]),
      ),
    ).toEqual([]);
    expect(envelopeEmbeddedOutputs(JSON.stringify({ content: JSON.stringify(erResult) }))).toEqual([]);
    expect(envelopeEmbeddedOutputs('<persisted-output>incomplete</persisted-output>')).toEqual([]);
  });
});
