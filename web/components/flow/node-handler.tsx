import { Popconfirm, Tooltip, Typography, message } from 'antd';
import React from 'react';
import { Connection, Handle, Position, useReactFlow } from 'reactflow';
import RequiredIcon from './required-icon';
import { InfoCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { IFlowNode, IFlowNodeInput, IFlowNodeOutput, IFlowNodeParameter } from '@/types/flow';
import { useTranslation } from 'react-i18next';
import classNames from 'classnames';
import { FLOW_NODES_KEY } from '@/utils';
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

  function isValidConnection(connection: Connection) {
    const { sourceHandle, targetHandle, source, target } = connection;
    const sourceNode = reactflow.getNode(source!);
    const targetNode = reactflow.getNode(target!);
    const { flow_type: sourceFlowType } = sourceNode?.data;
    const { flow_type: targetFlowType } = targetNode?.data;
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

  function showRelatedNodes() {
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
          node.outputs?.some((output: IFlowNodeOutput) => output.type_cls === typeCls && output.is_list === data?.is_list),
        );
    } else if (label === 'parameters') {
      // fint other resources and parent_cls including this parameter type_cls
      nodes = staticNodes.filter((node: IFlowNode) => node.flow_type === 'resource').filter((node: IFlowNode) => node.parent_cls?.includes(typeCls));
    } else if (label === 'outputs') {
      if (node.flow_type === 'operator') {
        // find other operators and inputs matching this output type_cls
        nodes = staticNodes
          .filter((node: IFlowNode) => node.flow_type === 'operator')
          .filter((node: IFlowNode) => node.inputs?.some((input: IFlowNodeInput) => input.type_cls === typeCls && input.is_list === data?.is_list));
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

  return (
    <div
      className={classNames('relative flex items-center', {
        'justify-start': label === 'parameters' || label === 'inputs',
        'justify-end': label === 'outputs',
      })}
    >
      <Handle
        className="w-2 h-2"
        type={type}
        position={type === 'source' ? Position.Right : Position.Left}
        id={`${node.id}|${label}|${index}`}
        isValidConnection={(connection) => isValidConnection(connection)}
      />
      <Typography
        className={classNames('p-2', {
          'pr-4': label === 'outputs',
        })}
      >
        <Popconfirm
          placement="left"
          icon={null}
          showCancel={false}
          okButtonProps={{ className: 'hidden' }}
          title={t('related_nodes')}
          description={
            <div className="w-60">
              <StaticNodes nodes={relatedNodes} />
            </div>
          }
        >
          {['inputs', 'parameters'].includes(label) && <PlusOutlined className="mr-2 cursor-pointer" onClick={showRelatedNodes} />}
        </Popconfirm>
        {data.type_name}:{label !== 'outputs' && <RequiredIcon optional={data.optional} />}
        {data.description && (
          <Tooltip title={data.description}>
            <InfoCircleOutlined className="ml-2 cursor-pointer" />
          </Tooltip>
        )}
        <Popconfirm
          placement="right"
          icon={null}
          showCancel={false}
          okButtonProps={{ className: 'hidden' }}
          title={t('related_nodes')}
          description={
            <div className="w-60">
              <StaticNodes nodes={relatedNodes} />
            </div>
          }
        >
          {['outputs'].includes(label) && <PlusOutlined className="ml-2 cursor-pointer" onClick={showRelatedNodes} />}
        </Popconfirm>
      </Typography>
    </div>
  );
};

export default NodeHandler;
