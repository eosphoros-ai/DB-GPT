import { IFlowData, IFlowDataNode, IFlowNode, IVariableItem } from '@/types/flow';
import { Node } from 'reactflow';

export const getUniqueNodeId = (nodeData: IFlowNode, nodes: Node[]) => {
  let count = 0;
  nodes.forEach(node => {
    if (node.data.name === nodeData.name) {
      count++;
    }
  });
  return `${nodeData.id}_${count}`;
};

// function getUniqueNodeId will add '_${count}' to id, so we need to remove it when we want to get the original id
export const removeIndexFromNodeId = (id: string) => {
  const indexPattern = /_\d+$/;
  return id.replace(indexPattern, '');
};

// 驼峰转下划线，接口协议字段命名规范
export const mapHumpToUnderline = (flowData: IFlowData) => {
  /**
   * sourceHandle -> source_handle,
   * targetHandle -> target_handle,
   * positionAbsolute -> position_absolute
   */
  const { nodes, edges, ...rest } = flowData;
  const newNodes = nodes.map(node => {
    const { positionAbsolute, ...rest } = node;
    return {
      position_absolute: positionAbsolute,
      ...rest,
    };
  });
  const newEdges = edges.map(edge => {
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
  const newNodes = nodes.map(node => {
    const { position_absolute, ...rest } = node;
    return {
      positionAbsolute: position_absolute,
      ...rest,
    };
  });
  const newEdges = edges.map(edge => {
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

// Helper function to check if a dynamic input/output has enough connections
const checkDynamicConnections = (
  nodeId: string,
  fieldType: string,
  _fieldIndex: number,
  edges: any[],
  dynamicMinimum: number,
): boolean => {
  // Count connections for this specific field type
  const handlePrefix = `${nodeId}|${fieldType}|`;
  const connectionCount = edges.filter(edge => {
    // For inputs, check targetHandle; for outputs, check sourceHandle
    const handle = fieldType === 'inputs' ? edge.targetHandle : edge.sourceHandle;
    if (!handle) return false;

    // Check if the handle belongs to this node and field type
    return handle.startsWith(handlePrefix);
  }).length;

  // Return true if we have at least the minimum required connections
  return connectionCount >= dynamicMinimum;
};

// Helper function to identify dynamic field groups
const getDynamicFieldGroups = (fields: any[]) => {
  const groups: Record<string, any[]> = {};

  fields.forEach(field => {
    if (field.dynamic) {
      // Extract base name (remove _X suffix if present)
      const baseName = field.name.replace(/_\d+$/, '');
      if (!groups[baseName]) {
        groups[baseName] = [];
      }
      groups[baseName].push(field);
    }
  });

  return groups;
};

// Helper function to validate dynamic parameters
const validateDynamicParameters = (node: IFlowDataNode): [boolean, string] => {
  if (!node.data.parameters || node.data.parameters.length === 0) {
    return [true, ''];
  }

  // Find all dynamic parameter groups
  const dynamicParamGroups = getDynamicFieldGroups(node.data.parameters);

  // Check each group
  for (const [baseName, fields] of Object.entries(dynamicParamGroups)) {
    const minimumRequired = fields[0].dynamic_minimum || 0;

    // Skip if minimum is 0
    if (minimumRequired === 0) continue;

    // For dynamic parameters, we check if we have at least the minimum number
    if (fields.length < minimumRequired) {
      return [
        false,
        `The dynamic parameter ${baseName} of node ${node.data.label} requires at least ${minimumRequired} parameters`,
      ];
    }

    // Check if any required parameters are missing values
    const requiredFields = fields.filter(field => !field.optional);
    for (const field of requiredFields) {
      if (field.value === undefined || field.value === null) {
        return [false, `The parameter ${field.name} of node ${node.data.label} is required`];
      }
    }
  }

  return [true, ''];
};

export const checkFlowDataRequied = (flowData: IFlowData) => {
  const { nodes, edges } = flowData;
  // check the input, parameters that are required
  let result: [boolean, IFlowDataNode, string] = [true, nodes[0], ''];

  outerLoop: for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i].data;
    const { inputs = [], parameters = [] } = node;

    // Check dynamic input groups first
    const dynamicInputGroups = getDynamicFieldGroups(inputs);
    for (const [baseName, fields] of Object.entries(dynamicInputGroups)) {
      const minimumRequired = fields[0].dynamic_minimum || 0;
      if (minimumRequired > 0) {
        // For dynamic fields, we check connections across all fields of this type
        const hasEnoughConnections = checkDynamicConnections(nodes[i].id, 'inputs', 0, edges, minimumRequired);
        if (!hasEnoughConnections) {
          result = [
            false,
            nodes[i],
            `The dynamic input ${baseName} of node ${node.label} requires at least ${minimumRequired} connections`,
          ];
          break outerLoop;
        }
      }
    }

    // Check individual inputs
    for (let j = 0; j < inputs.length; j++) {
      const input = inputs[j];

      // Skip dynamic inputs that were checked above
      if (input.dynamic) continue;

      const isRequired = !input.optional;
      if (isRequired && !edges.some(edge => edge.targetHandle === `${nodes[i].id}|inputs|${j}`)) {
        result = [false, nodes[i], `The input ${inputs[j].type_name} of node ${node.label} is required`];
        break outerLoop;
      }
    }

    // Validate dynamic parameters
    const [paramsValid, errorMessage] = validateDynamicParameters(nodes[i]);
    if (!paramsValid) {
      result = [false, nodes[i], errorMessage];
      break outerLoop;
    }

    // Check dynamic parameter groups
    const dynamicParamGroups = getDynamicFieldGroups(parameters);
    for (const [baseName, fields] of Object.entries(dynamicParamGroups)) {
      const minimumRequired = fields[0].dynamic_minimum || 0;
      if (minimumRequired > 0 && fields[0].category === 'resource') {
        // For dynamic params, check connections across all params of this type
        const hasEnoughConnections = checkDynamicConnections(nodes[i].id, 'parameters', 0, edges, minimumRequired);
        if (!hasEnoughConnections) {
          result = [
            false,
            nodes[i],
            `The dynamic parameter ${baseName} of node ${node.label} requires at least ${minimumRequired} connections`,
          ];
          break outerLoop;
        }
      }
    }

    // check parameters
    for (let k = 0; k < parameters.length; k++) {
      const parameter = parameters[k];

      // Skip dynamic parameters that were checked above
      if (parameter.dynamic) continue;

      if (
        !parameter.optional &&
        parameter.category === 'resource' &&
        !edges.some(edge => edge.targetHandle === `${nodes[i].id}|parameters|${k}`)
      ) {
        result = [false, nodes[i], `The parameter ${parameter.type_name} of node ${node.label} is required`];
        break outerLoop;
      } else if (
        !parameter.optional &&
        parameter.category === 'common' &&
        (parameter.value === undefined || parameter.value === null)
      ) {
        result = [false, nodes[i], `The parameter ${parameter.type_name} of node ${node.label} is required`];
        break outerLoop;
      }
    }

    // Check dynamic output groups
    const dynamicOutputGroups = getDynamicFieldGroups(node.outputs || []);
    for (const [baseName, fields] of Object.entries(dynamicOutputGroups)) {
      const minimumRequired = fields[0].dynamic_minimum || 0;
      if (minimumRequired > 0) {
        // For dynamic outputs, check connections across all outputs of this type
        const hasEnoughConnections = checkDynamicConnections(nodes[i].id, 'outputs', 0, edges, minimumRequired);
        if (!hasEnoughConnections) {
          result = [
            false,
            nodes[i],
            `The dynamic output ${baseName} of node ${node.label} requires at least ${minimumRequired} connections`,
          ];
          break outerLoop;
        }
      }
    }
  }

  return result;
};

export const convertKeysToCamelCase = (obj: Record<string, any>): Record<string, any> => {
  function toCamelCase(str: string): string {
    return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
  }

  function isObject(value: any): boolean {
    return value && typeof value === 'object' && !Array.isArray(value);
  }

  function convert(obj: any): any {
    if (Array.isArray(obj)) {
      return obj.map(item => convert(item));
    } else if (isObject(obj)) {
      const newObj: Record<string, any> = {};
      for (const key in obj) {
        if (Object.prototype.hasOwnProperty.call(obj, key)) {
          const newKey = toCamelCase(key);
          newObj[newKey] = convert(obj[key]);
        }
      }
      return newObj;
    }
    return obj;
  }

  return convert(obj);
};

function escapeVariable(value: string, enableEscape: boolean): string {
  if (!enableEscape) {
    return value;
  }
  return value.replace(/@/g, '\\@').replace(/#/g, '\\#').replace(/%/g, '\\%').replace(/:/g, '\\:');
}

export function buildVariableString(variableDict: IVariableItem): string {
  const scopeSig = '@';
  const sysCodeSig = '#';
  const userSig = '%';
  const kvSig = ':';
  const enableEscape = true;

  const specialChars = new Set([scopeSig, sysCodeSig, userSig, kvSig]);

  const newVariableDict: Partial<IVariableItem> = {
    key: variableDict.key || '',
    name: variableDict.name || '',
    scope: variableDict.scope || '',
    scope_key: variableDict.scope_key || '',
    sys_code: variableDict.sys_code || '',
    user_name: variableDict.user_name || '',
  };

  // Check for special characters in values
  for (const [key, value] of Object.entries(newVariableDict)) {
    if (value && [...specialChars].some(char => (value as string).includes(char))) {
      if (enableEscape) {
        newVariableDict[key] = escapeVariable(value as string, enableEscape);
      } else {
        throw new Error(
          `${key} contains special characters, error value: ${value}, special characters: ${[...specialChars].join(', ')}`,
        );
      }
    }
  }

  const { key, name, scope, scope_key, sys_code, user_name } = newVariableDict;

  let variableStr = `${key}`;

  if (name) variableStr += `${kvSig}${name}`;
  if (scope || scope_key) {
    variableStr += `${scopeSig}${scope}`;
    if (scope_key) {
      variableStr += `${kvSig}${scope_key}`;
    }
  }
  if (sys_code) variableStr += `${sysCodeSig}${sys_code}`;
  if (user_name) variableStr += `${userSig}${user_name}`;
  return `\${${variableStr}}`;
}
