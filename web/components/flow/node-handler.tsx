import { Tooltip, Typography, message } from 'antd';
import React from 'react';
import { Connection, Handle, Position, useReactFlow } from 'reactflow';
import RequiredIcon from './required-icon';
import { InfoCircleOutlined } from '@ant-design/icons';
import { IFlowNode, IFlowNodeInput, IFlowNodeOutput, IFlowNodeParameter } from '@/types/flow';
import { useTranslation } from 'react-i18next';

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
      // operator to operator, only type_cls matched can be connected
      const sourceTypeCls = sourceNode?.data[sourceLabel!][sourceIndex!].type_cls;
      return sourceTypeCls === targetTypeCls;
    } else if (sourceFlowType === 'resource' && targetFlowType === 'operator') {
      // resource to operator, check operator type_cls and resource parent_cls
      const sourceParentCls = sourceNode?.data.parent_cls;
      return sourceParentCls.includes(targetTypeCls);
    }
    message.warning(t('connect_warning'));
    return false;
  }

  return (
    <div className="relative flex items-center">
      <Handle
        className="w-2 h-2"
        type={type}
        position={type === 'source' ? Position.Right : Position.Left}
        id={`${node.id}|${label}|${index}`}
        isValidConnection={(connection) => isValidConnection(connection)}
      />
      <Typography className="p-2">
        {data.label}:<RequiredIcon optional={data.optional} />
        {data.description && (
          <Tooltip title={data.description}>
            <InfoCircleOutlined className="ml-2" />
          </Tooltip>
        )}
      </Typography>
    </div>
  );
};

export default NodeHandler;
