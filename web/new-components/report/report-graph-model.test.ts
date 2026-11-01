declare function require(name: string): any;
const assert = require('node:assert/strict');
import type { ReportArtifact, ReportRun } from '../../types/report';
import { buildGraph, projectedEdges, relatedNodes, type GeneratedReportFile } from './report-graph-model';
import { artifactSourceName } from './report-source';

function artifact(id: string, step: string, extra: Partial<ReportArtifact> = {}): ReportArtifact {
  return {
    artifact_id: id,
    type: 'sql',
    name: '经营分析',
    status: 'succeeded',
    database: 'Olist',
    metadata: {},
    input_artifact_ids: [],
    execution: { conv_uid: 'conv', step_id: step, action: 'sql_query' },
    ...extra,
  };
}
function run(artifacts: ReportArtifact[]): ReportRun {
  return {
    run_id: 'run',
    report_id: 'report',
    revision: 1,
    schema_version: 3,
    trigger_type: 'test',
    status: 'completed',
    created_at: '',
    document: {
      schema_version: 3,
      report_id: 'report',
      conv_uid: 'conv',
      title: '经营报告',
      created_at: '',
      metadata: {},
      artifacts,
      sections: [
        {
          section_id: 'summary',
          title: '摘要',
          blocks: [
            {
              block_id: 'text',
              type: 'text',
              metadata: {},
              evidence: artifacts
                .filter(item => item.type !== 'reference')
                .map(item => ({ artifact_id: item.artifact_id, role: 'support', selector: {}, target_selector: {} })),
            },
          ],
        },
      ],
    },
  };
}
const references = Array.from({ length: 14 }, (_, index) =>
  artifact(`ref-${index}`, 'step-1', {
    type: 'reference',
    database: undefined,
    reference_type: 'knowledge',
    source_name: 'metrics.md',
    excerpt: `原文 ${index}`,
    execution: { conv_uid: 'conv', step_id: 'step-1', action: 'knowledge.cat' },
    locator: { space_id: 1, document_id: 7, chunk_id: `chunk-${index}`, start_line: index + 1 },
  }),
);
const files: GeneratedReportFile[] = [
  { id: 'report-file', type: 'html', name: 'report.html' },
  { id: 'python-a', type: 'file', name: 'analysis.py', filePath: 'E:/workspace/analysis.py' },
  { id: 'python-b', type: 'file', name: 'chart.py', filePath: 'E:/workspace/chart.py', stepId: 'step-3' },
];
const sql = artifact('sql-result', 'step-2', {
  input_artifact_ids: ['ref-0'],
  result: { uri: 'artifact://internal-result.json' },
});
const python = artifact('python-result', 'step-3', {
  type: 'python',
  database: undefined,
  input_artifact_ids: ['sql-result'],
  code: 'print(1)',
  metadata: { file_path: 'E:/workspace/analysis.py' },
});
const snapshot = run([...references, sql, python]);
const graph = buildGraph(snapshot, files, { '1': 'Olist 指标口径' });
assert.equal(graph.nodes.filter(node => node.stage === 'output').length, 3, 'Only generated task files become outputs');
assert.equal(
  graph.nodes.filter(node => node.stage === 'execution').length,
  2,
  'Reference snapshots stay in source details; SQL and Python each have one execution node',
);
assert.equal(
  graph.nodes.filter(node => node.sourceGroup === 'KNOWLEDGE BASE').length,
  2,
  'Knowledge space and one file, with no slice nodes',
);
const file = graph.nodes.find(node => node.parentId)!;
assert.equal(file.artifacts?.length, 14);
assert.equal(file.artifacts?.[13].excerpt, '原文 13');
assert.equal(file.artifacts?.[13].locator?.start_line, 14, 'Aggregating nodes preserves precise evidence');
assert.equal(artifactSourceName(references[0], { '1': 'Olist 指标口径' }), 'Olist 指标口径');
assert.equal(
  artifactSourceName({ ...references[0], locator: { knowledge_id: 'Olist_Analytics_Governance' } }),
  'Olist_Analytics_Governance',
);
assert.equal(
  artifactSourceName(references[0]),
  '知识库（1）',
  'Missing historical names never fall back to the filename',
);
assert.ok(
  graph.nodes.every(
    node => !node.id.startsWith('agent:') && !node.id.startsWith('block:') && !node.id.startsWith('section:'),
  ),
);
assert.ok(graph.nodes.every(node => !node.title.includes('chunk-') && !node.title.includes('sql-result')));
const outputs = graph.nodes.filter(node => node.stage === 'output');
assert.ok(
  outputs.slice(1).every(node => graph.edges.some(edge => edge.to === node.id && edge.relation === 'PRODUCES')),
);
assert.equal(
  buildGraph(snapshot, []).nodes.filter(node => node.stage === 'output').length,
  0,
  'An unfinished task does not invent a report file',
);

const differentDoc = {
  ...references[0],
  artifact_id: 'different-document',
  locator: { space_id: 1, document_id: 8, chunk_id: 'other' },
  execution: { ...references[0].execution, step_id: 'step-4' },
};
const twoDocuments = buildGraph(run([...references, differentDoc]), []);
assert.equal(
  twoDocuments.nodes.filter(node => node.parentId).length,
  2,
  'Different documents sharing a filename stay distinct',
);
const firstFile = twoDocuments.nodes.find(
  node => node.artifacts?.some(item => item.artifact_id === 'ref-0') && node.parentId,
)!;
const otherFile = twoDocuments.nodes.find(
  node => node.artifacts?.some(item => item.artifact_id === 'different-document') && node.parentId,
)!;
assert.ok(
  !relatedNodes(firstFile.id, twoDocuments.edges).has(otherFile.id),
  'Focus must not reverse at the shared knowledge-space node and include unrelated files',
);
const collapsed = projectedEdges(
  graph.edges,
  graph.nodes,
  new Set(graph.nodes.filter(node => !node.parentId).map(node => node.id)),
);
assert.ok(
  collapsed.some(
    edge => edge.from.startsWith('knowledge:') && graph.nodes.find(node => node.id === edge.to)?.stage === 'execution',
  ),
  'Collapsed files retain the source-to-execution connection',
);
const parallel = buildGraph(
  run([
    artifact('task-a', 'step-1', { execution: { conv_uid: 'conv', task_id: 'a', step_id: 'step-1' } }),
    artifact('task-b', 'step-1', { execution: { conv_uid: 'conv', task_id: 'b', step_id: 'step-1' } }),
  ]),
  [],
);
assert.equal(
  parallel.nodes.filter(node => node.stage === 'execution').length,
  2,
  'Equal step labels in different sub-tasks never merge',
);
const noProducer = buildGraph(snapshot, [{ id: 'unknown', type: 'file', name: 'unrelated.py' }]);
assert.ok(
  !noProducer.edges.some(edge => edge.to.startsWith('output:')),
  'Never invent a producer for a file without a recorded association',
);
const mixedIdentity = buildGraph(
  run([
    references[0],
    { ...references[1], locator: { knowledge_id: 'Olist 指标口径', document_id: 7, chunk_id: 'named-space' } },
  ]),
  [],
  { '1': 'Olist 指标口径' },
);
assert.equal(
  mixedIdentity.nodes.filter(node => node.sourceGroup === 'KNOWLEDGE BASE').length,
  2,
  'Numeric and named identities of the same knowledge space share one root and file',
);
const imageCapture = artifact('image-result', 'image-capture-id', {
  type: 'chart',
  database: undefined,
  input_artifact_ids: ['python-result'],
  execution: { conv_uid: 'conv', step_id: 'image-capture-id', action: 'code_interpreter.image' },
});
const withImage = buildGraph(run([sql, python, imageCapture]), [
  { id: 'image-file', type: 'image', name: 'chart.png', content: { artifact_id: 'image-result' } },
]);
assert.equal(
  withImage.nodes.filter(node => node.stage === 'execution').length,
  2,
  'A captured image does not duplicate its real Python execution',
);
assert.ok(
  withImage.nodes
    .find(node => node.artifact?.artifact_id === 'python-result')
    ?.artifacts?.some(item => item.artifact_id === 'image-result'),
);
assert.ok(withImage.edges.some(edge => edge.to === 'output:image-file' && edge.relation === 'PRODUCES'));
console.log('Report graph aggregation, provenance and output-file tests passed');
