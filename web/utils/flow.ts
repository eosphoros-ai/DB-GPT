import { IFlowData, IFlowNode } from '@/types/flow';
import { Node } from 'reactflow';

export const getUniqueNodeId = (nodeData: IFlowNode, nodes: Node[]) => {
  let count = 0;
  nodes.forEach((node) => {
    if (node.data.name === nodeData.name) {
      count++;
    }
  });
  return `${nodeData.id}_${count}`;
};

// 驼峰转下划线，接口协议字段命名规范
export const mapHumpToUnderline = (flowData: IFlowData) => {
  /**
   * sourceHandle -> source_handle,
   * targetHandle -> target_handle,
   * positionAbsolute -> position_absolute
   */
  const { nodes, edges, ...rest } = flowData;
  const newNodes = nodes.map((node) => {
    const { positionAbsolute, ...rest } = node;
    return {
      position_absolute: positionAbsolute,
      ...rest,
    };
  });
  const newEdges = edges.map((edge) => {
    const { sourceHandle, targetHandle, ...rest } = edge;
    return {
      source_handle: sourceHandle,
      target_handle: targetHandle,
      ...rest,
    };
  });
  return {
    nodes: newNodes,
    edges: newEdges,
    ...rest,
  };
};

export const mapUnderlineToHump = (flowData: IFlowData) => {
  /**
   * source_handle -> sourceHandle,
   * target_handle -> targetHandle,
   * position_absolute -> positionAbsolute
   */
  const { nodes, edges, ...rest } = flowData;
  const newNodes = nodes.map((node) => {
    const { position_absolute, ...rest } = node;
    return {
      positionAbsolute: position_absolute,
      ...rest,
    };
  });
  const newEdges = edges.map((edge) => {
    const { source_handle, target_handle, ...rest } = edge;
    return {
      sourceHandle: source_handle,
      targetHandle: target_handle,
      ...rest,
    };
  });
  return {
    nodes: newNodes,
    edges: newEdges,
    ...rest,
  };
};
