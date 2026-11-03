import assert from 'node:assert/strict';
import type { ITaskflowDSL } from '../types/taskflow';
import { layoutTaskflow } from './taskflow-layout';

const flow: ITaskflowDSL = {
  format: 'taskflow/1',
  nodes: ['output', 'quality', 'plan', 'start', 'trend', 'review'].map(id => ({
    id,
    kind: id === 'start' || id === 'output' ? id : 'agent',
    config: {},
  })),
  edges: [
    ['start', 'plan'],
    ['plan', 'trend'],
    ['plan', 'quality'],
    ['trend', 'review'],
    ['quality', 'review'],
    ['review', 'output'],
  ],
};
const layout = layoutTaskflow(flow);
const positions = new Map(layout.map(item => [item.node.id, item.position]));
assert.equal(positions.get('trend')!.y, positions.get('quality')!.y);
assert.notEqual(positions.get('trend')!.x, positions.get('quality')!.x);
assert(positions.get('review')!.y > positions.get('trend')!.y);
assert.equal(layout[0].node.id, 'start');
assert.equal(layout.at(-1)!.node.id, 'output');
assert.equal(new Set(layout.map(item => item.node.id)).size, flow.nodes.length);
console.log('TaskFlow fork/join layout checks passed');
