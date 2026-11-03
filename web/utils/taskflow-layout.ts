import type { ITaskflowDSL, ITaskflowNode } from '../types/taskflow';

/** Stable topological rows; independent siblings share a row on the canvas. */
export function layoutTaskflow(dsl: ITaskflowDSL): Array<{
  node: ITaskflowNode;
  position: { x: number; y: number };
}> {
  const pending = new Map(dsl.nodes.map(node => [node.id, node]));
  const done = new Set<string>();
  const result: Array<{ node: ITaskflowNode; position: { x: number; y: number } }> = [];
  let level = 0;
  while (pending.size) {
    const ready = [...pending.values()].filter(node =>
      dsl.edges.every(([source, target]) => target !== node.id || done.has(source)),
    );
    // Invalid in-progress edits must remain visible for the server to diagnose.
    const row = ready.length ? ready : [...pending.values()].slice(0, 1);
    row.forEach((node, index) => {
      result.push({
        node,
        position: { x: 340 + (index - (row.length - 1) / 2) * 380, y: 40 + level * 118 },
      });
      pending.delete(node.id);
      done.add(node.id);
    });
    level += 1;
  }
  return result;
}
