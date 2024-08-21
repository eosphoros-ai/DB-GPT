import { IFlowNode, IFlowRefreshParams } from '@/types/flow';
import Image from 'next/image';
import NodeParamHandler from './node-param-handler';
import classNames from 'classnames';
import { useState } from 'react';
import NodeHandler from './node-handler';
import { Form, Popover, Tooltip } from 'antd';
import { CopyOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useReactFlow } from 'reactflow';
import IconWrapper from '../common/icon-wrapper';
import { getUniqueNodeId, removeIndexFromNodeId } from '@/utils/flow';
import { cloneDeep } from 'lodash';
import { apiInterceptors, refreshFlowNodeById } from '@/client/api';

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
    reactFlow.setEdges((edges) => edges.filter((edge) => edge.source !== node.id && edge.target !== node.id));
  }

  // function onChange(value: any) {
  //   data.value = value;
  // }

  function onValuesChange(changedValues: any, allValues: any) {
    // onChange(changedValues);
    console.log('Changed xxx', changedValues);
    console.log('All xxx', allValues);
    console.log('xxxx', parameters);

    const [changedKey, changedVal] = Object.entries(changedValues)[0];
    console.log('====', changedKey, changedVal);

    // 获取以当前改变项目为 refresh_depends 的参数name
    const needChangeNodes = parameters.filter(({ ui }) => ui?.refresh_depends?.includes(changedKey));
    console.log('needChangeNodes====', needChangeNodes);

    if (needChangeNodes?.length === 0) return;

    needChangeNodes.forEach(async (item) => {
      const params = {
        id: removeIndexFromNodeId(data?.id),
        type_name: data.type_name,
        type_cls: data.type_cls,
        flow_type: 'operator' as const,
        refresh: [
          {
            name: item.name, // 要刷新的参数的name
            depends: [
              {
                name: changedKey, // 依赖的参数的name
                value: changedVal, // 依赖的参数的值
                has_value: true,
              },
            ],
          },
        ],
      };

      // const params = {
      //   id: 'operator_example_refresh_operator___$$___example___$$___v1',
      //   type_name: 'ExampleFlowRefreshOperator',
      //   type_cls: 'unusual_prefix_90027f35e50ecfda77e3c7c7b20a0272d562480c_awel_flow_ui_components.ExampleFlowRefreshOperator',
      //   flow_type: 'operator' as const,
      //   refresh: [
      //     {
      //       name: 'recent_time', // 要刷新的参数的name
      //       depends: [
      //         {
      //           name: 'time_interval', // 依赖的参数的name
      //           value: 3, // 依赖的参数的值
      //           has_value: true,
      //         },
      //       ],
      //     },
      //   ],
      // };

      const [_, res] = await apiInterceptors(refreshFlowNodeById(params));
    });
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
            {/* <div className="flex flex-col space-y-3 text-neutral-500"> */}

            <Form form={form} layout="vertical" onValuesChange={onValuesChange} className="flex flex-col text-neutral-500">
              {parameters?.map((item, index) => (
                <NodeParamHandler key={`${node.id}_param_${index}`} node={node} data={item} label="parameters" index={index} />
              ))}
            </Form>

            {/* </div> */}
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
