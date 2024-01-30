import { IFlowNode, IFlowNodeParameter } from '@/types/flow';
import Image from 'next/image';
import NodeParamHandler from './node-param-handler';
import classNames from 'classnames';
import { useState } from 'react';
import NodeHandler from './node-handler';
import { Popover } from 'antd';
import { CopyOutlined, DeleteOutlined } from '@ant-design/icons';
import { useReactFlow } from 'reactflow';

type CanvasNodeProps = {
  data: IFlowNode;
};

const ICON_PATH_PREFIX = '/icons/node/';

function TypeLabel({ label }: { label: string }) {
  return <div className="w-full h-8 bg-stone-100 dark:bg-zinc-700 px-2 flex items-center justify-center">{label}</div>;
}

const CanvasNode: React.FC<CanvasNodeProps> = ({ data }) => {
  const node = data;
  const { inputs, outputs, flow_type: flowType } = node;
  const parameters = orderParams(node.parameters || []);
  const [isHovered, setIsHovered] = useState(false);
  const reactFlow = useReactFlow();

  function orderParams(params: Array<IFlowNodeParameter>) {
    // we show resource params first, and build-int params last
    const resourceParams = params.filter((param) => param.category === 'resource');
    const commonParams = params.filter((param) => param.category === 'common');
    return [...resourceParams, ...commonParams];
  }

  function onHover() {
    setIsHovered(true);
  }

  function onLeave() {
    setIsHovered(false);
  }

  function copyNode() {}

  function deleteNode() {
    const nodes = reactFlow.getNodes();
    console.log('delete node', nodes);
    reactFlow.setNodes((nodes) => {
      const list = nodes.filter((item) => item.id !== node.id);
      return list;
    });
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
      content={
        <div>
          <CopyOutlined className="block text-lg cursor-pointer" onClick={copyNode} />
          <DeleteOutlined className="block text-lg cursor-pointer" onClick={deleteNode} />
        </div>
      }
    >
      <div
        className={classNames('w-72 h-auto rounded-xl shadow-md p-0 border bg-white dark:bg-zinc-800 cursor-grab', {
          'border-blue-500': node.selected || isHovered,
          'border-stone-400 dark:border-white': !node.selected && !isHovered,
          'border-dashed': flowType !== 'operator',
        })}
        onMouseEnter={onHover}
        onMouseLeave={onLeave}
      >
        {/* icon and label */}
        <div className="flex flex-row items-center p-2">
          <Image src={node.icon || `${ICON_PATH_PREFIX}${node.name || 'default_node_icon'}.svg`} width={24} height={24} alt="" />
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
