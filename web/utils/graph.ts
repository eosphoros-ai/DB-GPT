import { idOf } from "@antv/g6";
import { pick, groupBy } from "lodash";
import type { EdgeData, GraphData, ID } from "@antv/g6";

/**
 * Reassign the layout style to the original graph data
 * @param model - original graph data
 * @param layoutResult - layout result
 */
export function reassignLayoutStyle(model: GraphData, layoutResult: GraphData) {
  layoutResult.nodes?.forEach((layoutNode) => {
    const modelNode = model.nodes?.find((node) => node.id === layoutNode.id);
    if (modelNode?.style)
      Object.assign(
        modelNode.style || {},
        pick(layoutNode.style, ["x", "y", "z"])
      );
  });
}

/**
 * Calculate node size based on degree
 * @param degree - degree of the node
 * @param minSize - minimum size of the node
 * @param maxSize - maximum size of the node
 * @param minDegree - minimum degree
 * @param maxDegree - maximum degree
 * @returns size of the node
 */
export function getSize(
  degree: number,
  minSize = 24,
  maxSize = 60,
  minDegree = 1,
  maxDegree = 10
): number {
  const _degree = Math.max(minDegree, Math.min(maxDegree, degree));

  const size =
    minSize +
    ((_degree - minDegree) / (maxDegree - minDegree)) * (maxSize - minSize);

  return size;
}

/**
 * Get node degree, means the number of edges connected to the node
 * @param edges - all edges data
 * @param nodeId - node id
 * @returns degree of the node
 */
export function getDegree(edges: EdgeData[], nodeId: ID) {
  return getRelatedEdgesData(edges, nodeId).length;
}

/**
 * Get related edges data of a node
 * @param edges - all edges data
 * @param nodeId - node id
 * @returns related edges data
 */
export function getRelatedEdgesData(edges: EdgeData[], nodeId: ID) {
  return edges.filter(
    (edge) => edge.source === nodeId || edge.target === nodeId
  );
}

/**
 * Concatenate the labels of the related edges to the node as the node's edge key
 * @param edges - all edges data
 * @param nodeId - node id
 * @returns edge key
 */
export function getCommunityId(edges: EdgeData[], nodeId: ID) {
  const relatedEdges = getRelatedEdgesData(edges, nodeId);
  const key = relatedEdges
    .map((edge) => {
      const direction = edge.source === nodeId ? "->" : "<-";
      const otherEnd = edge.source === nodeId ? edge.target : edge.source;
      return `${direction}_${edge.data!.label}_${otherEnd}`;
    })
    .sort()
    .join("+");
  return key;
}

/**
 * Whether the node is in a community(same communityId) with more than `limit` nodes
 * @param data - graph data
 * @param nodeId - node id
 * @param limit - limit
 * @returns boolean
 */
export function isInCommunity(data: GraphData, nodeId: string, limit = 2) {
  const groupedNodes = groupBy(data.nodes, (node) => node.data!.communityId);
  const filtered = Object.values(groupedNodes).find((nodes) =>
    nodes.map(idOf).includes(nodeId)
  )!;
  return filtered.length > limit;
}
