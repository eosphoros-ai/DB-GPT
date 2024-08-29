import { connectedComponent } from "@antv/algorithm";
import type { NodeConfig } from "@antv/algorithm/lib/types";
import { BaseLayout, ConcentricLayout, idOf } from "@antv/g6";
import { layoutAdapter } from "@antv/g6/lib/utils/layout";
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

export class ConnectedComponent extends BaseLayout {
  id = "connected-component";

  async execute(model: GraphData): Promise<GraphData> {
    const { nodes = [], edges = [] } = model;
    const components = connectedComponent({ nodes, edges });
    const AdaptiveConcentricLayout = layoutAdapter(
      ConcentricLayout,
      this.context
    );
    const layout = new AdaptiveConcentricLayout(this.context);
    if (!components?.length || components.length <= 1) return model;
    const num = components.length;
    const rows = Math.floor(Math.sqrt(num)) || 1;
    const cols = Math.ceil(num / rows) || 1;
    // 连通子图初始化布局后分布范围边缘之间的间距
    const gap = 150;
    // 连通子图初始化为同心圆布局的中心位置，根据左边子图的右边缘、上一行子图的最大高度决定
    let centerX = gap;
    let centerY = 0;
    const maxRowHeight: number[] = [];

    const layoutPromises = components.map(async (componentNodes, i) => {
      const row = Math.floor(i / rows);
      const col = Math.floor(i % cols);
      // 每行第一个连通子图的中心位置为 [gap, 累加上面所有行的高度]
      if (col === 0) {
        centerX = gap;
        centerY += (maxRowHeight[row - 1] || 0) + gap;
        const nodeIds = nodes.map((node) => node.id);
        const componentEdges = edges.filter(
          (edge) =>
            nodeIds.includes(edge.source) && nodeIds.includes(edge.target)
        );

        const layoutResult = await layout.execute(
          { nodes: componentNodes, edges: componentEdges },
          {
            center: [centerX, centerY],
          }
        );

        reassignLayoutStyle(model, layoutResult);

        // 根据当前连通子图的布局范围决定后面的连通子图 center
        const { width, height } = getNodesSize(componentNodes);
        // 由于同心圆布局比较紧凑，后续力导向布局会扩散，因此将 height 和 width 扩大一些
        const expandRatioX = 8;
        const expandRatioY = 6;
        maxRowHeight[row] = Math.max(
          maxRowHeight[row] || 0,
          height * expandRatioY
        );
        centerX += width * expandRatioX;
      }
    });

    await Promise.all(layoutPromises);

    return model;
  }
}

/**
 * 根据给定的一组节点，计算分布范围的宽和高
 * @param nodes - 节点数据数组
 * @returns 返回节点数据数组的分布范围的宽和高
 */
const getNodesSize = (nodes: NodeConfig[]) => {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  nodes.forEach((node) => {
    const { x, y } = node;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  });
  return {
    width: maxX - minX,
    height: maxY - minY,
  };
};

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
