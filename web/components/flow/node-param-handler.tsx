import { IFlowNode, IFlowNodeParameter } from '@/types/flow';
import { Checkbox, Input, InputNumber, Select, Tooltip } from 'antd';
import React from 'react';
import RequiredIcon from './required-icon';
import NodeHandler from './node-handler';
import { InfoCircleOutlined } from '@ant-design/icons';
import {
  RenderSelect,
  RenderCheckbox,
  RenderRadio,
  RenderCascader,
  RenderDatePicker,
  RenderInput,
  RenderSlider,
  RenderTreeSelect,
  RenderTimePicker,
  RenderTextArea,
  RenderUpload,
  RenderCodeEditor,
  RenderPassword,
  RenderVariables,
} from './node-renderer';

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

  function renderLabelWithTooltip(data: IFlowNodeParameter) {
    return (
      <div>
        {data.label}:<RequiredIcon optional={data.optional} />
        {data.description && (
          <Tooltip title={data.description}>
            <InfoCircleOutlined className="ml-2 cursor-pointer" />
          </Tooltip>
        )}
      </div>
    );
  }

  // render node parameters based on AWEL1.0
  function renderNodeWithoutUiParam(data: IFlowNodeParameter) {
    let defaultValue = data.value ?? data.default;

    switch (data.type_name) {
      case 'int':
      case 'float':
        return (
          <div className="text-sm">
            {renderLabelWithTooltip(data)}
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
          <div className="text-sm">
            {renderLabelWithTooltip(data)}
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
      case 'bool':
        defaultValue = defaultValue === 'False' ? false : defaultValue;
        defaultValue = defaultValue === 'True' ? true : defaultValue;
        return (
          <div className="text-sm">
            {renderLabelWithTooltip(data)}
            <Checkbox
              className="ml-2"
              defaultChecked={defaultValue}
              onChange={(e) => {
                onChange(e.target.checked);
              }}
            />
          </div>
        );
    }
  }

  function renderComponentByType(type: string, props?: any) {
    switch (type) {
      case 'select':
        return <RenderSelect {...props} />;
      case 'cascader':
        return <RenderCascader {...props} />;
      case 'checkbox':
        return <RenderCheckbox {...props} />;
      case 'radio':
        return <RenderRadio {...props} />;
      case 'input':
        return <RenderInput {...props} />;
      case 'text_area':
        return <RenderTextArea {...props} />;
      case 'slider':
        return <RenderSlider {...props} />;
      case 'date_picker':
        return <RenderDatePicker {...props} />;
      case 'time_picker':
        return <RenderTimePicker {...props} />;
      case 'tree_select':
        return <RenderTreeSelect {...props} />;
      case 'password':
        return <RenderPassword {...props} />;
      case 'upload':
        return <RenderUpload {...props} />;
      case 'variables':
        return <RenderVariables {...props} />;
      case 'code_editor':
        return <RenderCodeEditor {...props} />;
      default:
        return null;
    }
  }

  // render node parameters based on AWEL2.0
  function renderNodeWithUiParam(data: IFlowNodeParameter) {
    let defaultValue = data.value ?? data.default;
    const props = { data, defaultValue, onChange };

    return (
      <div>
        {renderLabelWithTooltip(data)}
        {renderComponentByType(data?.ui?.ui_type, props)}
      </div>
    );
  }

  if (data.category === 'resource') {
    return <NodeHandler node={node} data={data} type="target" label={label} index={index} />;
  } else if (data.category === 'common') {
    return data?.ui ? renderNodeWithUiParam(data) : renderNodeWithoutUiParam(data);
  }
};

export default NodeParamHandler;