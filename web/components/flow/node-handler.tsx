import { IFlowNode, IFlowNodeInput, IFlowNodeOutput, IFlowNodeParameter } from '@/types/flow';
import { FLOW_NODES_KEY } from '@/utils';
import { InfoCircleOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Popconfirm, Tooltip, Typography, message } from 'antd';
import classNames from 'classnames';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Connection, Handle, Position, useReactFlow } from 'reactflow';
import RequiredIcon from './required-icon';
import StaticNodes from './static-nodes';

interface NodeHandlerProps {
  node: IFlowNode;
  data: IFlowNodeInput | IFlowNodeParameter | IFlowNodeOutput;
  type: 'source' | 'target';
  label: 'inputs' | 'outputs' | 'parameters';
  index: number;
}

// render react flow handle item
const NodeHandler: React.FC<NodeHandlerProps> = ({ node, data, type, label, index }) => {
  const { t } = useTranslation();
  const reactflow = useReactFlow();
  const [relatedNodes, setRelatedNodes] = React.useState<IFlowNode[]>([]);

  const dynamic = data.dynamic || false;
  const dynamicMinimum = data.dynamic_minimum || 0;

  // Determine if input is optional based on dynamic and dynamicMinimum
  const isOptional = () => {
    if (dynamic) {
      // When dynamic is true, it's optional if dynamicMinimum is 0
      return dynamicMinimum === 0;
    } else {
      // When dynamic is false, use the original logic
      return data.optional;
    }
  };

  function isValidConnection(connection: Connection) {
    const { sourceHandle, targetHandle, source, target } = connection;
    const sourceNode = reactflow.getNode(source!);
    const targetNode = reactflow.getNode(target!);
    const { flow_type: sourceFlowType } = sourceNode?.data ?? {};
    const { flow_type: targetFlowType } = targetNode?.data ?? {};
    const sourceLabel = sourceHandle?.split('|')[1];
    const targetLabel = targetHandle?.split('|')[1];
    const sourceIndex = sourceHandle?.split('|')[2];
    const targetIndex = targetHandle?.split('|')[2];
    const targetTypeCls = targetNode?.data[targetLabel!][targetIndex!].type_cls;
    if (sourceFlowType === targetFlowType && sourceFlowType === 'operator') {
      // operator to operator, only type_cls and is_list matched can be connected
      const sourceTypeCls = sourceNode?.data[sourceLabel!][sourceIndex!].type_cls;
      const sourceIsList = sourceNode?.data[sourceLabel!][sourceIndex!].is_list;
      const targetIsList = targetNode?.data[targetLabel!][targetIndex!].is_list;
      return sourceTypeCls === targetTypeCls && sourceIsList === targetIsList;
    } else if (sourceFlowType === 'resource' && (targetFlowType === 'operator' || targetFlowType === 'resource')) {
      // resource to operator, check operator type_cls and resource parent_cls
      const sourceParentCls = sourceNode?.data.parent_cls;
      return sourceParentCls.includes(targetTypeCls);
    }
    message.warning(t('connect_warning'));
    return false;
  }

  function showRelatedNodes(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();

    // find all nodes that can be connected to this node
    const cache = localStorage.getItem(FLOW_NODES_KEY);
    if (!cache) {
      return;
    }

    const staticNodes = JSON.parse(cache);
    const typeCls = data.type_cls;
    let nodes: IFlowNode[] = [];

    if (label === 'inputs') {
      // find other operators and outputs matching this input type_cls
      nodes = staticNodes
        .filter((node: IFlowNode) => node.flow_type === 'operator')
        .filter((node: IFlowNode) =>
          node.outputs?.some(
            (output: IFlowNodeOutput) => output.type_cls === typeCls && output.is_list === data?.is_list,
          ),
        );
    } else if (label === 'parameters') {
      // fint other resources and parent_cls including this parameter type_cls
      nodes = staticNodes
        .filter((node: IFlowNode) => node.flow_type === 'resource')
        .filter((node: IFlowNode) => node.parent_cls?.includes(typeCls));
    } else if (label === 'outputs') {
      if (node.flow_type === 'operator') {
        // find other operators and inputs matching this output type_cls
        nodes = staticNodes
          .filter((node: IFlowNode) => node.flow_type === 'operator')
          .filter((node: IFlowNode) =>
            node.inputs?.some((input: IFlowNodeInput) => input.type_cls === typeCls && input.is_list === data?.is_list),
          );
      } else if (node.flow_type === 'resource') {
        // find other resources or operators that this output parent_cls includes their type_cls
        nodes = staticNodes.filter(
          (item: IFlowNode) =>
            item.inputs?.some((input: IFlowNodeInput) => node.parent_cls?.includes(input.type_cls)) ||
            item.parameters?.some((parameter: IFlowNodeParameter) => node.parent_cls?.includes(parameter.type_cls)),
        );
      }
    }

    setRelatedNodes(nodes);
  }

  // Add new dynamic field
  function addDynamicField(e: React.MouseEvent) {
    console.log('addDynamicField clicked', e);
    e.stopPropagation();
    e.preventDefault();

    console.log(`Adding dynamic field for node ${node.id}, label=${label}, current field name=${data.name}`);

    // Get current IO array
    const ioArray = [...node[label]];
    // Get the original field template
    const fieldTemplate = { ...data };

    // CHECK: How many dynamic fields of this type already exist
    const dynamicFieldsCount = ioArray.filter(
      item => item.type_cls === data.type_cls && item.name.startsWith(data.name),
    ).length;

    // Create a new field based on the template
    const newField = {
      ...fieldTemplate,
      name: `${data.name}_${dynamicFieldsCount}`,
      // keep the dynamic flag but reset the value
      value: null,
    };

    // Push the new field to the array
    ioArray.push(newField);

    // Update the nodes in the flow
    reactflow.setNodes(nodes => {
      return nodes.map(n => {
        if (n.id === node.id) {
          return {
            ...n,
            data: {
              ...n.data,
              [label]: ioArray,
            },
          };
        }
        return n;
      });
    });
  }

  // Remove dynamic field
  function removeDynamicField(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();

    // Get the count of dynamic fields of this type
    const ioArray = [...node[label]];
    const dynamicFields = ioArray.filter(item => item.type_cls === data.type_cls && item.name.startsWith(data.name));

    console.log(
      `Removing dynamic field at index ${index}, total count: ${dynamicFields.length}, minimum: ${dynamicMinimum}`,
    );

    // Make sure we don't go below the minimum
    if (dynamicFields.length <= dynamicMinimum) {
      console.log(`Cannot remove: already at minimum (${dynamicMinimum})`);
      message.warning(t('minimum_dynamic_fields_warning', { count: dynamicMinimum }));
      return;
    }
    // Remove the field at the current index
    const updatedArray = ioArray.filter((_, idx) => idx !== index);

    // Update the node data in the flow
    reactflow.setNodes(nodes => {
      return nodes.map(n => {
        if (n.id === node.id) {
          return {
            ...n,
            data: {
              ...n.data,
              [label]: updatedArray,
            },
          };
        }
        return n;
      });
    });

    // Update the edges connected to this handle
    const handleId = `${node.id}|${label}|${index}`;
    reactflow.setEdges(edges => {
      return edges.filter(
        edge =>
          (type === 'source' && edge.sourceHandle !== handleId) ||
          (type === 'target' && edge.targetHandle !== handleId),
      );
    });
  }

  // Check if this field is the last one of this type (for dynamic fields)
  const isLastDynamicField = () => {
    if (!dynamic) return false;

    const ioArray = node[label];
    const dynamicFields = ioArray.filter(item => item.type_cls === data.type_cls && item.name.startsWith(data.name));

    return index === ioArray.indexOf(dynamicFields[dynamicFields.length - 1]);
  };

  return (
    <div
      className={classNames('relative flex items-center', {
        'justify-start': label === 'parameters' || label === 'inputs',
        'justify-end': label === 'outputs',
      })}
    >
      <Handle
        className={classNames('w-2 h-2', type === 'source' ? '-mr-4' : '-ml-4')}
        type={type}
        position={type === 'source' ? Position.Right : Position.Left}
        id={`${node.id}|${label}|${index}`}
        isValidConnection={connection => isValidConnection(connection)}
      />
      <Typography
        className={classNames('bg-white dark:bg-[#232734] w-full px-2 py-1 rounded text-neutral-500', {
          'text-right': label === 'outputs',
        })}
      >
        <Popconfirm
          placement='left'
          icon={null}
          showCancel={false}
          okButtonProps={{ className: 'hidden' }}
          title={t('related_nodes')}
          description={
            <div className='w-60'>
              <StaticNodes nodes={relatedNodes} />
            </div>
          }
        >
          {['inputs', 'parameters'].includes(label) && (
            <PlusOutlined
              className='cursor-pointer mr-1'
              onClick={e => {
                e.stopPropagation();
                e.preventDefault();
                showRelatedNodes(e);
              }}
            />
          )}
        </Popconfirm>

        {['inputs', 'parameters'].includes(label) && dynamic && index >= dynamicMinimum && (
          <MinusCircleOutlined
            className='cursor-pointer text-red-500 mr-1'
            onClick={e => {
              e.stopPropagation();
              e.preventDefault();
              removeDynamicField(e);
            }}
          />
        )}

        {label !== 'outputs' && <RequiredIcon optional={isOptional()} />}
        {data.type_name}
        {data.description && (
          <Tooltip title={data.description}>
            <InfoCircleOutlined className='ml-2 cursor-pointer' />
          </Tooltip>
        )}

        <Popconfirm
          placement='right'
          icon={null}
          showCancel={false}
          okButtonProps={{ className: 'hidden' }}
          title={t('related_nodes')}
          description={
            <div className='w-60'>
              <StaticNodes nodes={relatedNodes} />
            </div>
          }
        >
          {['outputs'].includes(label) && (
            <PlusOutlined
              className='ml-2 cursor-pointer'
              onClick={e => {
                e.stopPropagation();
                e.preventDefault();
                showRelatedNodes(e);
              }}
            />
          )}
        </Popconfirm>

        {['outputs'].includes(label) && dynamic && index >= dynamicMinimum && (
          <MinusCircleOutlined
            className='ml-2 cursor-pointer text-red-500'
            onClick={e => {
              e.stopPropagation();
              e.preventDefault();
              removeDynamicField(e);
            }}
          />
        )}

        {/* Add dynamic field button */}
        {dynamic && isLastDynamicField() && (
          <Button
            type='primary'
            size='small'
            className='ml-2'
            onClick={e => {
              e.stopPropagation();
              e.preventDefault();
              addDynamicField(e);
            }}
            style={{ float: label === 'outputs' ? 'left' : 'right' }}
          >
            add
          </Button>
        )}
      </Typography>
    </div>
  );
};

export default NodeHandler;
