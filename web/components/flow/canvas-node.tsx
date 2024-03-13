import { IFlowNode } from '@/types/flow';
import Image from 'next/image';
import NodeParamHandler from './node-param-handler';
import classNames from 'classnames';
import { useState } from 'react';
import NodeHandler from './node-handler';
import { Popover, Tooltip } from 'antd';
import { CopyOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useReactFlow } from 'reactflow';
import IconWrapper from '../common/icon-wrapper';
import { getUniqueNodeId } from '@/utils/flow';
import { cloneDeep } from 'lodash';

type CanvasNodeProps = {
  data: IFlowNode;
};

const ICON_PATH_PREFIX = '/icons/node/';

function TypeLabel({ label }: { label: string }) {
  return <div className="w-full h-8 bg-stone-100 dark:bg-zinc-700 px-2 flex items-center justify-center">{label}</div>;
}

const CanvasNode: React.FC<CanvasNodeProps> = ({ data }) => {
  const node = data;
  const { inputs, outputs, parameters, flow_type: flowType } = node;
  const [isHovered, setIsHovered] = useState(false);
  const reactFlow = useReactFlow();

  function onHover() {
    setIsHovered(true);
  }

  function onLeave() {
    setIsHovered(false);
  }

  function copyNode(e: React.MouseEvent<HTMLButtonElement, MouseEvent>) {
    e.preventDefault();
    e.stopPropagation();
    const nodes = reactFlow.getNodes();
    const originalNode = nodes.find((item) => item.id === node.id);
    if (originalNode) {
      const newNodeId = getUniqueNodeId(originalNode as IFlowNode, nodes);
      const cloneNode = cloneDeep(originalNode);
      const duplicatedNode = {
        ...cloneNode,
        id: newNodeId,
        position: {
          x: cloneNode.position.x + 400,
          y: cloneNode.position.y,
        },
        positionAbsolute: {
          x: cloneNode.positionAbsolute!.x + 400,
          y: cloneNode.positionAbsolute!.y,
        },
        data: {
          ...cloneNode.data,
          id: newNodeId,
        },
        selected: false,
      };
      reactFlow.setNodes((nodes) => [...nodes, duplicatedNode]);
    }
  }

  function deleteNode(e: React.MouseEvent<HTMLButtonElement, MouseEvent>) {
    e.preventDefault();
    e.stopPropagation();
    reactFlow.setNodes((nodes) => nodes.filter((item) => item.id !== node.id));
    reactFlow.setEdges((edges) => edges.filter((edge) => edge.source !== node.id && edge.target !== node.id));
  }

  function renderOutput(data: IFlowNode) {
    if (flowType === 'operator' && outputs?.length > 0) {
      return (
        <>
          <TypeLabel label="Outputs" />
          {(outputs || []).map((output, index) => (
            <NodeHandler key={`${data.id}_input_${index}`} node={data} data={output} type="source" label="outputs" index={index} />
          ))}
        </>
      );
    } else if (flowType === 'resource') {
      // resource nodes show output default
      return (
        <>
          <TypeLabel label="Outputs" />
          <NodeHandler key={`${data.id}_input_0`} node={data} data={data} type="source" label="outputs" index={0} />
        </>
      );
    }
  }

  return (
    <Popover
      placement="rightTop"
      trigger={['hover']}
      content={
        <>
          <IconWrapper className="hover:text-blue-500">
            <CopyOutlined className="h-full text-lg cursor-pointer" onClick={copyNode} />
          </IconWrapper>
          <IconWrapper className="mt-2 hover:text-red-500">
            <DeleteOutlined className="h-full text-lg cursor-pointer" onClick={deleteNode} />
          </IconWrapper>
          <IconWrapper className="mt-2">
            <Tooltip title={node.description} placement="right">
              <InfoCircleOutlined className="h-full text-lg cursor-pointer" />
            </Tooltip>
          </IconWrapper>
        </>
      }
    >
      <div
        className={classNames('w-72 h-auto rounded-xl shadow-md p-0 border bg-white dark:bg-zinc-800 cursor-grab', {
          'border-blue-500': node.selected || isHovered,
          'border-stone-400 dark:border-white': !node.selected && !isHovered,
          'border-dashed': flowType !== 'operator',
          'border-red-600': node.invalid,
        })}
        onMouseEnter={onHover}
        onMouseLeave={onLeave}
      >
        {/* icon and label */}
        <div className="flex flex-row items-center p-2">
          <Image src={'/icons/node/vis.png'} width={24} height={24} alt="" />
          <p className="ml-2 text-lg font-bold text-ellipsis overflow-hidden whitespace-nowrap">{node.label}</p>
        </div>
        {inputs && inputs.length > 0 && (
          <>
            <TypeLabel label="Inputs" />
            {(inputs || []).map((input, index) => (
              <NodeHandler key={`${node.id}_input_${index}`} node={node} data={input} type="target" label="inputs" index={index} />
            ))}
          </>
        )}
        {parameters && parameters.length > 0 && (
          <>
            <TypeLabel label="Parameters" />
            {(parameters || []).map((parameter, index) => (
              <NodeParamHandler key={`${node.id}_param_${index}`} node={node} data={parameter} label="parameters" index={index} />
            ))}
          </>
        )}
        {renderOutput(node)}
      </div>
    </Popover>
  );
};

export default CanvasNode;
