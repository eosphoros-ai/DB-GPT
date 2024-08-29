import { IFlowNode, IFlowNodeParameter } from '@/types/flow';
import { InfoCircleOutlined } from '@ant-design/icons';
import { Checkbox, Form, Input, InputNumber, Select } from 'antd';
import React from 'react';
import NodeHandler from './node-handler';
import {
  renderCascader,
  renderCheckbox,
  renderCodeEditor,
  renderDatePicker,
  renderInput,
  renderPassword,
  renderRadio,
  renderSelect,
  renderSlider,
  renderTextArea,
  renderTimePicker,
  renderTreeSelect,
  renderUpload,
  renderVariables,
} from './node-renderer';

interface NodeParamHandlerProps {
  formValuesChange: any;
  node: IFlowNode;
  paramData: IFlowNodeParameter;
  label: 'inputs' | 'outputs' | 'parameters';
  index: number; // index of array
}

// render node parameters item
const NodeParamHandler: React.FC<NodeParamHandlerProps> = ({ formValuesChange, node, paramData, label, index }) => {
  // render node parameters based on AWEL1.0
  function renderNodeWithoutUiParam(data: IFlowNodeParameter) {
    let defaultValue = data.value ?? data.default;

    switch (data.type_name) {
      case 'int':
      case 'float':
        return (
          <Form.Item
            className='mb-2 text-sm'
            name={data.name}
            initialValue={defaultValue}
            rules={[{ required: !data.optional }]}
            label={<span className='text-neutral-500'>{data.label}</span>}
            tooltip={data.description ? { title: data.description, icon: <InfoCircleOutlined /> } : ''}
          >
            <InputNumber className='w-full nodrag' />
          </Form.Item>
        );

      case 'str':
        return (
          <Form.Item
            className='mb-2 text-sm'
            name={data.name}
            initialValue={defaultValue}
            rules={[{ required: !data.optional }]}
            label={<span className='text-neutral-500'>{data.label}</span>}
            tooltip={data.description ? { title: data.description, icon: <InfoCircleOutlined /> } : ''}
          >
            {data.options?.length > 0 ? (
              <Select
                className='w-full nodrag'
                options={data.options.map((item: any) => ({ label: item.label, value: item.value }))}
              />
            ) : (
              <Input className='w-full' />
            )}
          </Form.Item>
        );

      case 'bool':
        defaultValue = defaultValue === 'False' ? false : defaultValue;
        defaultValue = defaultValue === 'True' ? true : defaultValue;
        return (
          <Form.Item
            className='mb-2 text-sm'
            name={data.name}
            initialValue={defaultValue}
            rules={[{ required: !data.optional }]}
            label={<span className='text-neutral-500'>{data.label}</span>}
            tooltip={data.description ? { title: data.description, icon: <InfoCircleOutlined /> } : ''}
          >
            <Checkbox className='ml-2' />
          </Form.Item>
        );
    }
  }

  function renderComponentByType(type: string, data: IFlowNodeParameter, formValuesChange: any) {
    switch (type) {
      case 'select':
        return renderSelect(data);
      case 'cascader':
        return renderCascader(data);
      case 'checkbox':
        return renderCheckbox(data);
      case 'radio':
        return renderRadio(data);
      case 'input':
        return renderInput(data);
      case 'text_area':
        return renderTextArea(data);
      case 'slider':
        return renderSlider(data);
      case 'date_picker':
        return renderDatePicker({ data, formValuesChange });
      case 'time_picker':
        return renderTimePicker({ data, formValuesChange });
      case 'tree_select':
        return renderTreeSelect(data);
      case 'password':
        return renderPassword(data);
      case 'upload':
        return renderUpload({ data, formValuesChange });
      case 'variables':
        return renderVariables(data);
      case 'code_editor':
        return renderCodeEditor(data);
      default:
        return null;
    }
  }

  // render node parameters based on AWEL2.0
  function renderNodeWithUiParam(data: IFlowNodeParameter, formValuesChange: any) {
    const { refresh_depends, ui_type } = data.ui;
    let defaultValue = data.value ?? data.default;
    if (ui_type === 'slider' && data.is_list) {
      defaultValue = [0, 1];
    }
    return (
      <Form.Item
        className='mb-2'
        initialValue={defaultValue}
        name={data.name}
        rules={[{ required: !data.optional }]}
        label={<span className='text-neutral-500'>{data.label}</span>}
        {...(refresh_depends && { dependencies: refresh_depends })}
        {...(data.description && { tooltip: { title: data.description, icon: <InfoCircleOutlined /> } })}
      >
        {renderComponentByType(ui_type, data, formValuesChange)}
      </Form.Item>
    );
  }

  if (paramData.category === 'resource') {
    return <NodeHandler node={node} data={paramData} type='target' label={label} index={index} />;
  } else if (paramData.category === 'common') {
    return paramData?.ui ? renderNodeWithUiParam(paramData, formValuesChange) : renderNodeWithoutUiParam(paramData);
  }
};

export default NodeParamHandler;
