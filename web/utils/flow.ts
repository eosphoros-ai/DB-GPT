import { IFlowData, IFlowDataNode, IFlowNode } from '@/types/flow';
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

export const checkFlowDataRequied = (flowData: IFlowData) => {
  const { nodes, edges } = flowData;
  // check the input, parameters that are required
  let result: [boolean, IFlowDataNode, string] = [true, nodes[0], ''];
  outerLoop: for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i].data;
    const { inputs = [], parameters = [] } = node;
    // check inputs
    for (let j = 0; j < inputs.length; j++) {
      if (!edges.some((edge) => edge.targetHandle === `${nodes[i].id}|inputs|${j}`)) {
        result = [false, nodes[i], `The input ${inputs[j].type_name} of node ${node.label} is required`];
        break outerLoop;
      }
    }
    // check parameters
    for (let k = 0; k < parameters.length; k++) {
      const parameter = parameters[k];
      if (!parameter.optional && parameter.category === 'resource' && !edges.some((edge) => edge.targetHandle === `${nodes[i].id}|parameters|${k}`)) {
        result = [false, nodes[i], `The parameter ${parameter.type_name} of node ${node.label} is required`];
        break outerLoop;
      } else if (!parameter.optional && parameter.category === 'common' && (parameter.value === undefined || parameter.value === null)) {
        result = [false, nodes[i], `The parameter ${parameter.type_name} of node ${node.label} is required`];
        break outerLoop;
      }
    }
  }
  return result;
};
