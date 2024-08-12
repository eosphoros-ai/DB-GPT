import { IFlowNode, IFlowNodeParameter } from '@/types/flow';
import { Checkbox, Input, InputNumber, Select, Tooltip } from 'antd';
import React from 'react';
import RequiredIcon from './required-icon';
import NodeHandler from './node-handler';
import { InfoCircleOutlined } from '@ant-design/icons';
import { RenderSelect, RenderCheckbox, RenderRadio, RenderCascader, RenderDataPicker, RenderInput } from './node-renderer';

interface NodeParamHandlerProps {
  node: IFlowNode;
  data: IFlowNodeParameter;
  label: 'inputs' | 'outputs' | 'parameters';
  index: number; // index of array
}

// render node parameters item
const NodeParamHandler: React.FC<NodeParamHandlerProps> = ({ node, data, label, index }) => {
  function onChange(value: any) {
    data.value = value;
  }

  // render node parameters based on AWEL1.0
  function renderNodeWithoutUiParam(data: IFlowNodeParameter) {
    let defaultValue = data.value !== null && data.value !== undefined ? data.value : data.default;

    switch (data.type_name) {
      case 'int':
      case 'float':
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
              {data.description && (
                <Tooltip title={data.description}>
                  <InfoCircleOutlined className="ml-2 cursor-pointer" />
                </Tooltip>
              )}
            </p>
            <InputNumber
              className="w-full"
              defaultValue={defaultValue}
              onChange={(value: number | null) => {
                onChange(value);
              }}
            />
          </div>
        );
      case 'str':
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
              {data.description && (
                <Tooltip title={data.description}>
                  <InfoCircleOutlined className="ml-2 cursor-pointer" />
                </Tooltip>
              )}
            </p>
            {data.options?.length > 0 ? (
              <Select
                className="w-full nodrag"
                defaultValue={defaultValue}
                options={data.options.map((item: any) => ({ label: item.label, value: item.value }))}
                onChange={onChange}
              />
            ) : (
              <Input
                className="w-full"
                defaultValue={defaultValue}
                onChange={(e) => {
                  onChange(e.target.value);
                }}
              />
            )}
          </div>
        );
      case 'checkbox':
        defaultValue = defaultValue === 'False' ? false : defaultValue;
        defaultValue = defaultValue === 'True' ? true : defaultValue;
        return (
          <div className="p-2 text-sm">
            <p>
              {data.label}:<RequiredIcon optional={data.optional} />
              {data.description && (
                <Tooltip title={data.description}>
                  <InfoCircleOutlined className="ml-2 cursor-pointer" />
                </Tooltip>
              )}
              <Checkbox
                className="ml-2"
                defaultChecked={defaultValue}
                onChange={(e) => {
                  onChange(e.target.checked);
                }}
              />
            </p>
          </div>
        );
    }
  }

  // render node parameters based on AWEL2.0
  function renderNodeWithUiParam(data: IFlowNodeParameter) {
    let defaultValue = data.value ?? data.default;
    const props = { data, defaultValue, onChange };

    switch (data?.ui?.ui_type) {
      case 'select':
        return <RenderSelect {...props} />;
      case 'cascader':
        return <RenderCascader {...props} />;
      case 'checkbox':
        return <RenderCheckbox {...props} />;
      case 'radio':
        return <RenderRadio {...props} />;
      case 'data_picker':
        return <RenderDataPicker {...props} />;
      case 'input':
        return <RenderInput {...props} />;
      default:
        return null;
    }
  }

  if (data.category === 'resource') {
    return <NodeHandler node={node} data={data} type="target" label={label} index={index} />;
  } else if (data.category === 'common') {
    return data?.ui ? renderNodeWithUiParam(data) : renderNodeWithoutUiParam(data);
  }
};

export default NodeParamHandler;
