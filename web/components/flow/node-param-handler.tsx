import { IFlowNode, IFlowNodeParameter } from '@/types/flow';
import { Checkbox, Input, InputNumber } from 'antd';
import React from 'react';
import RequiredIcon from './required-icon';
import NodeHandler from './node-handler';

interface NodeParamHandlerProps {
  node: IFlowNode;
  data: IFlowNodeParameter;
  label: 'inputs' | 'outputs' | 'parameters';
  index: number; // index of array
}

// render node parameters item
const NodeParamHandler: React.FC<NodeParamHandlerProps> = ({ node, data, label, index }) => {
  function handleChange(value: any) {
    data.value = value;
  }

  if (data.category === 'resource') {
    return <NodeHandler node={node} data={data} type="target" label={label} index={index} />;
  } else if (data.category === 'common') {
    const defaultValue = data.default || data.value;
    switch (data.type_name) {
      case 'int':
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
            </p>
            <InputNumber
              className="w-full"
              defaultValue={defaultValue}
              onChange={(e) => {
                handleChange(e.target.value);
              }}
            />
          </div>
        );
      case 'str':
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
            </p>
            <Input
              className="w-full"
              defaultValue={defaultValue}
              onChange={(e) => {
                handleChange(e.target.value);
              }}
            />
          </div>
        );
      case 'bool':
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
              <Checkbox
                className="ml-2"
                defaultChecked={defaultValue}
                onChange={(e) => {
                  handleChange(e.target.value);
                }}
              />
            </p>
          </div>
        );
    }
  }
};

export default NodeParamHandler;
