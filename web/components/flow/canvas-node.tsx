import { IFlowNode } from '@/types/flow';
import Image from 'next/image';
import NodeParamHandler from './node-param-handler';
import classNames from 'classnames';
import { useState } from 'react';
import NodeHandler from './node-handler';
import { Form, Popover, Tooltip } from 'antd';
import {
  CopyOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { useReactFlow } from 'reactflow';
import IconWrapper from '../common/icon-wrapper';
import { getUniqueNodeId, removeIndexFromNodeId } from '@/utils/flow';
import { cloneDeep } from 'lodash';
import { apiInterceptors, refreshFlowNodeById } from '@/client/api';

type CanvasNodeProps = {
  data: IFlowNode;
};

function TypeLabel({ label }: { label: string }) {
  return <div className='w-full h-8 align-middle font-semibold'>{label}</div>;
}
const forceTypeList = ['file', 'multiple_files', 'time','images','csv_file'];

const CanvasNode: React.FC<CanvasNodeProps> = ({ data }) => {
  const node = data;
  const { inputs, outputs, parameters, flow_type: flowType } = node;
  const [isHovered, setIsHovered] = useState(false);
  const reactFlow = useReactFlow();
  const [form] = Form.useForm();

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
    reactFlow.setEdges((edges) =>
      edges.filter((edge) => edge.source !== node.id && edge.target !== node.id)
    );
  }

  function updateCurrentNodeValue(changedKey: string, changedVal: any) {
    parameters.forEach((item) => {
      if (item.name === changedKey) {
        item.value = changedVal;
      }
    });
  }

  async function updateDependsNodeValue(changedKey: string, changedVal: any) {
    const dependParamNodes = parameters.filter(({ ui }) =>
      ui?.refresh_depends?.includes(changedKey)
    );

    if (dependParamNodes?.length === 0) return;
    dependParamNodes.forEach(async (item) => {
      const params = {
        id: removeIndexFromNodeId(data?.id),
        type_name: data.type_name,
        type_cls: data.type_cls,
        flow_type: 'operator' as const,
        refresh: [
          {
            name: item.name,
            depends: [
              {
                name: changedKey,
                value: changedVal,
                has_value: true,
              },
            ],
          },
        ],
      };

      const [_, res] = await apiInterceptors(refreshFlowNodeById(params));

      // update value of the node
      if (res) {
        reactFlow.setNodes((nodes) =>
          nodes.map((n) => {
            return n.id === node.id
              ? {
                  ...n,
                  data: {
                    ...n.data,
                    parameters: res.parameters,
                  },
                }
              : n;
          })
        );
      }
    });
  }

  function onParameterValuesChange(changedValues: any, allValues: any) {
    const [changedKey, changedVal] = Object.entries(changedValues)[0];

    if (!allValues?.force && forceTypeList.includes(changedKey)) {
      return;
    }
    updateCurrentNodeValue(changedKey, changedVal);
    if (changedVal) {
      updateDependsNodeValue(changedKey, changedVal);
    }
  }

  function renderOutput(data: IFlowNode) {
    if (flowType === 'operator' && outputs?.length > 0) {
      return (
        <div className='bg-zinc-100 dark:bg-zinc-700 rounded p-2'>
          <TypeLabel label='Outputs' />
          {(outputs || []).map((output, index) => (
            <NodeHandler
              key={`${data.id}_input_${index}`}
              node={data}
              data={output}
              type='source'
              label='outputs'
              index={index}
            />
          ))}
        </div>
      );
    } else if (flowType === 'resource') {
      // resource nodes show output default
      return (
        <div className='bg-zinc-100 dark:bg-zinc-700 rounded p-2'>
          <TypeLabel label='Outputs' />
          <NodeHandler
            key={`${data.id}_input_0`}
            node={data}
            data={data}
            type='source'
            label='outputs'
            index={0}
          />
        </div>
      );
    }
  }

  return (
    <Popover
      placement='rightTop'
      trigger={['hover']}
      content={
        <>
          <IconWrapper className='hover:text-blue-500'>
            <CopyOutlined
              className='h-full text-lg cursor-pointer'
              onClick={copyNode}
            />
          </IconWrapper>

          <IconWrapper className='mt-2 hover:text-red-500'>
            <DeleteOutlined
              className='h-full text-lg cursor-pointer'
              onClick={deleteNode}
            />
          </IconWrapper>

          <IconWrapper className='mt-2'>
            <Tooltip
              title={
                <>
                  <p className='font-bold'>{node.label}</p>
                  <p>{node.description}</p>
                </>
              }
              placement='right'
            >
              <InfoCircleOutlined className='h-full text-lg cursor-pointer' />
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
          }
        )}
        onMouseEnter={onHover}
        onMouseLeave={onLeave}
      >
        {/* icon and label */}
        <div className='flex flex-row items-center'>
          <Image src={'/icons/node/vis.png'} width={24} height={24} alt='' />
          <p className='ml-2 text-lg font-bold text-ellipsis overflow-hidden whitespace-nowrap'>
            {node.label}
          </p>
        </div>

        {inputs?.length > 0 && (
          <div className='bg-zinc-100 dark:bg-zinc-700 rounded p-2'>
            <TypeLabel label='Inputs' />
            <div className='flex flex-col space-y-2'>
              {inputs?.map((item, index) => (
                <NodeHandler
                  key={`${node.id}_input_${index}`}
                  node={node}
                  data={item}
                  type='target'
                  label='inputs'
                  index={index}
                />
              ))}
            </div>
          </div>
        )}

        {parameters?.length > 0 && (
          <div className='bg-zinc-100 dark:bg-zinc-700 rounded p-2'>
            <TypeLabel label='Parameters' />
            <Form
              form={form}
              layout='vertical'
              onValuesChange={onParameterValuesChange}
              className='flex flex-col space-y-3 text-neutral-500'
            >
              {parameters?.map((item, index) => (
                <NodeParamHandler
                  key={`${node.id}_param_${index}`}
                  formValuesChange={onParameterValuesChange}
                  node={node}
                  paramData={item}
                  label='parameters'
                  index={index}
                />
              ))}
            </Form>
          </div>
        )}

        {renderOutput(node)}
      </div>
    </Popover>
  );
};

export default CanvasNode;
