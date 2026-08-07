import assert from 'node:assert/strict';
import test from 'node:test';

import { decodeAgentFinalAnswer, decodeAgentHistoryAnswer } from './react-agent-final';

test('decodes protocol v2 final answer without mixing citations into content', () => {
  const answer = decodeAgentFinalAnswer({
    type: 'final',
    protocol_version: 2,
    content: '结论来自知识库 [1]。',
    citations: [
      {
        index: 1,
        id: 'chunk-1',
        sourceName: 'sales.md',
        excerpt: '华东销售额同比增长 12%。',
        score: 0.91,
        path: '/reports/sales.md',
      },
    ],
  });

  assert.deepEqual(answer, {
    content: '结论来自知识库 [1]。',
    citations: [
      {
        index: 1,
        id: 'chunk-1',
        sourceName: 'sales.md',
        excerpt: '华东销售额同比增长 12%。',
        score: 0.91,
        path: '/reports/sales.md',
      },
    ],
  });
});

test('strips legacy generic references without promoting script output to a citation', () => {
  const legacyPayload = JSON.stringify([
    {
      name: 'Knowledge Base',
      chunks: [
        {
          index: 1,
          id: 7,
          content: "def log():\n    print('do not leak script output')",
          recall_score: 0.82,
        },
      ],
    },
  ]);
  const answer = decodeAgentFinalAnswer(
    `页面内容已经输出完成。\n\n<references title="References" references='${legacyPayload}'></references>`,
  );

  assert.equal(answer.content, '页面内容已经输出完成。');
  assert.deepEqual(answer.citations, []);
});

test('keeps an oversized legacy references envelope out of visible summary content', () => {
  const leakedScript = "do not leak script source\nprint('secret')\n".repeat(2500);
  const legacyPayload = JSON.stringify([
    {
      name: 'Knowledge Base',
      chunks: [{ index: 1, id: 7, content: leakedScript }],
    },
  ]);

  const answer = decodeAgentFinalAnswer(
    `分析摘要已完成。\n\n<references title="References" references='${legacyPayload}'></references>`,
  );

  assert.deepEqual(answer, { content: '分析摘要已完成。', citations: [] });
  assert.equal(answer.content.includes('do not leak script source'), false);
});

test('does not trust a legacy SQL result label as a document identity', () => {
  const legacyPayload = JSON.stringify([
    {
      name: 'SQL Results',
      chunks: [{ index: 1, id: 8, content: 'SELECT secret FROM credentials' }],
    },
  ]);

  const answer = decodeAgentFinalAnswer(
    `查询完成<references title="References" references='${legacyPayload}'></references>`,
  );

  assert.deepEqual(answer, { content: '查询完成', citations: [] });
});

test('keeps a legacy citation when a generic group carries a concrete document path', () => {
  const legacyPayload = JSON.stringify([
    {
      name: 'Knowledge Base',
      chunks: [
        {
          index: 1,
          id: 9,
          sourceName: 'Knowledge Base',
          file_path: '/handbook/security.md',
          content: 'Never expose tool output as final answer content.',
        },
      ],
    },
  ]);

  const answer = decodeAgentFinalAnswer(
    `安全结论<references title='References' references='${legacyPayload}'></references>`,
  );

  assert.deepEqual(answer, {
    content: '安全结论',
    citations: [
      {
        index: 1,
        id: '9',
        sourceName: '/handbook/security.md',
        excerpt: 'Never expose tool output as final answer content.',
        path: '/handbook/security.md',
      },
    ],
  });
});

test('finds the outer legacy envelope when a cited excerpt contains references markup', () => {
  const excerpt = '文档示例：<references title="References" references=\'[{"fake":true}]\'></references>';
  const legacyPayload = JSON.stringify([
    {
      name: 'guide.md',
      chunks: [{ index: 1, id: 8, content: excerpt }],
    },
  ]);

  const answer = decodeAgentFinalAnswer(
    `正常回答\n\n<references title="References" references='${legacyPayload}'></references>`,
  );

  assert.deepEqual(answer, {
    content: '正常回答',
    citations: [{ index: 1, id: '8', sourceName: 'guide.md', excerpt }],
  });
});

test('fails closed for malformed legacy reference payload while keeping the answer clean', () => {
  const answer = decodeAgentFinalAnswer(
    `正常回答\n\n<references title="References" references='[{broken json}]'></references>`,
  );

  assert.deepEqual(answer, { content: '正常回答', citations: [] });
});

test('decodes the XML-escaped self-closing legacy envelope', () => {
  const answer = decodeAgentFinalAnswer(
    '旧知识问答\n<references title="References" references="[{&quot;name&quot;:&quot;guide.md&quot;,&quot;chunks&quot;:[{&quot;index&quot;:1,&quot;id&quot;:9,&quot;content&quot;:&quot;引用内容&quot;}]}]" />',
  );

  assert.deepEqual(answer, {
    content: '旧知识问答',
    citations: [
      {
        index: 1,
        id: '9',
        sourceName: 'guide.md',
        excerpt: '引用内容',
      },
    ],
  });
});

test('does not strip references-like text that is not the legacy trailing envelope', () => {
  const content = '示例代码：`<references title="demo">`，后面仍然有正文。';
  assert.deepEqual(decodeAgentFinalAnswer(content), { content, citations: [] });
});

test('normalizes persisted history final_content and structured citations', () => {
  const answer = decodeAgentHistoryAnswer({
    version: 1,
    type: 'react-agent',
    final_content: '历史结论 [1]',
    citations: [
      {
        index: 1,
        id: 3,
        source_name: 'handbook.md',
        content: '历史知识片段',
        recall_score: '0.75',
      },
    ],
  });

  assert.deepEqual(answer, {
    content: '历史结论 [1]',
    citations: [
      {
        index: 1,
        id: '3',
        sourceName: 'handbook.md',
        excerpt: '历史知识片段',
        score: 0.75,
      },
    ],
  });
});

test('keeps ordinary JSON answers even when they contain content and citations keys', () => {
  const content = JSON.stringify({
    content: 'This is user-visible JSON, not a history envelope.',
    citations: [{ sourceName: 'model-output', excerpt: 'must not be trusted' }],
  });

  assert.deepEqual(decodeAgentHistoryAnswer(content), {
    content,
    citations: [],
  });
});

test('drops malformed citations instead of exposing arbitrary tool output', () => {
  const answer = decodeAgentFinalAnswer({
    content: '安全回答',
    citations: [{ index: 1, sourceName: 'missing excerpt' }, "print('tool output')", null],
  });

  assert.deepEqual(answer, { content: '安全回答', citations: [] });
});

test('bounds citation count and excerpt size at the compatibility seam', () => {
  const citations = Array.from({ length: 12 }, (_, offset) => ({
    index: offset + 1,
    id: `chunk-${offset + 1}`,
    sourceName: `doc-${offset + 1}.md`,
    excerpt: 'x'.repeat(3_000),
  }));

  const answer = decodeAgentFinalAnswer({ content: 'answer', citations });

  assert.equal(answer.citations.length, 6);
  assert.ok(answer.citations.every(citation => citation.excerpt.length === 2_000));
  assert.equal(
    answer.citations.reduce((total, citation) => total + citation.excerpt.length, 0),
    12_000,
  );
});
