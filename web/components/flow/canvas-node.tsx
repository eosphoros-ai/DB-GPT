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

function TypeLabel({ label }: { label: string }) {
  return <div className="w-full h-8 align-middle font-semibold">{label}</div>;
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
            <Tooltip
              title={
                <>
                  <p className="font-bold">{node.label}</p>
                  <p>{node.description}</p>
                </>
              }
              placement="right"
            >
              <InfoCircleOutlined className="h-full text-lg cursor-pointer" />
            </Tooltip>
          </IconWrapper>
        </>
      }
    >
      <div
        className={classNames(
          'w-80 h-auto rounded-xl shadow-md px-2 py-4 border bg-white dark:bg-zinc-800 cursor-grab flex flex-col space-y-2 text-sm',
          {
            'border-blue-500': node.selected || isHovered,
            'border-stone-400 dark:border-white': !node.selected && !isHovered,
            'border-dashed': flowType !== 'operator',
            'border-red-600': node.invalid,
          },
        )}
        onMouseEnter={onHover}
        onMouseLeave={onLeave}
      >
        {/* icon and label */}
        <div className="flex flex-row items-center">
          <Image src={'/icons/node/vis.png'} width={24} height={24} alt="" />
          <p className="ml-2 text-lg font-bold text-ellipsis overflow-hidden whitespace-nowrap">{node.label}</p>
        </div>

        {inputs?.length > 0 && (
          <div className="bg-zinc-100 dark:bg-zinc-700 rounded p-2">
            <TypeLabel label="Inputs" />
            <div className="flex flex-col space-y-2">
              {inputs?.map((item, index) => (
                <NodeHandler key={`${node.id}_input_${index}`} node={node} data={item} type="target" label="inputs" index={index} />
              ))}
            </div>
          </div>
        )}

        {parameters?.length > 0 && (
          <div className="bg-zinc-100 dark:bg-zinc-700 rounded p-2">
            <TypeLabel label="Parameters" />
            <div className="flex flex-col space-y-3 text-neutral-500">
              {parameters?.map((item, index) => (
                <NodeParamHandler key={`${node.id}_param_${index}`} node={node} data={item} label="parameters" index={index} />
              ))}
            </div>
          </div>
        )}

        {outputs?.length > 0 && (
          <div className="bg-zinc-100 dark:bg-zinc-700 rounded p-2">
            <TypeLabel label="Outputs" />
            {flowType === 'operator' ? (
              <div className="flex flex-col space-y-3">
                {outputs.map((item, index) => (
                  <NodeHandler key={`${node.id}_output_${index}`} node={node} data={item} type="source" label="outputs" index={index} />
                ))}
              </div>
            ) : (
              flowType === 'resource' && <NodeHandler key={`${data.id}_output_0`} node={node} data={node} type="source" label="outputs" index={0} />
            )}
          </div>
        )}
      </div>
    </Popover>
  );
};

export default CanvasNode;
