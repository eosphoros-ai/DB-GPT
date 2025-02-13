import { SupportModelParams } from '@/types/model';
import { Checkbox, Form, FormInstance, Input, InputNumber, Select } from 'antd';
import React, { useEffect, useState } from 'react';

interface NestedFormFieldsProps {
  parentName: string;
  fields: Record<string, SupportModelParams[]>;
  form: FormInstance;
}

const NestedFormFields: React.FC<NestedFormFieldsProps> = ({ parentName, fields, form }) => {
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // 当父组件的表单值变化时，尝试恢复已选择的类型
  useEffect(() => {
    const currentValue = form.getFieldValue(parentName);
    if (currentValue?.type && !selectedType) {
      setSelectedType(currentValue.type);
    }
  }, [form, parentName]);

  const renderFormItem = (param: SupportModelParams) => {
    const type = param.param_type.toLowerCase();
    // 不再使用嵌套的路径，而是直接使用参数名
    const itemName = [parentName, param.param_name].join('.');

    let control;
    if (type === 'str' || type === 'string') {
      if (param.valid_values) {
        control = (
          <Select>
            {param.valid_values.map(value => (
              <Select.Option key={value} value={value}>
                {value}
              </Select.Option>
            ))}
          </Select>
        );
      } else {
        control = <Input />;
      }
    } else if (type === 'int' || type === 'integer' || type === 'number' || type === 'float') {
      control = <InputNumber className='w-full' />;
    } else if (type === 'bool' || type === 'boolean') {
      control = <Checkbox />;
    } else {
      control = <Input />;
    }

    return (
      <Form.Item
        key={itemName}
        label={<p className='whitespace-normal overflow-wrap-break-word'>{param.label || param.param_name}</p>}
        name={itemName}
        initialValue={param.default_value}
        valuePropName={type === 'bool' || type === 'boolean' ? 'checked' : 'value'}
        tooltip={param.description}
        rules={[{ required: param.required, message: `Please input ${param.param_name}` }]}
      >
        {control}
      </Form.Item>
    );
  };

  const handleTypeChange = (value: string) => {
    setSelectedType(value);

    // 获取新类型的默认值
    const newFields = fields[value] || [];
    const defaultValues = {
      type: value,
      ...Object.fromEntries(newFields.map(field => [field.param_name, field.default_value])),
    };

    // 更新表单中的所有相关字段
    form.setFieldValue(parentName, defaultValues);
  };

  return (
    <div className='space-y-4 border rounded-md p-4'>
      <Form.Item
        label='Type'
        name={`${parentName}.type`}
        required
        tooltip='Select the type to see specific configuration options'
      >
        <Select value={selectedType} onChange={handleTypeChange} placeholder='Select a type' className='w-full'>
          {Object.keys(fields).map(type => (
            <Select.Option key={type} value={type}>
              {type}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      {selectedType && (
        <div className='mt-4'>
          <h4 className='mb-4 text-base font-medium'>{selectedType} Configuration</h4>
          <div className='space-y-4'>{fields[selectedType].map(param => renderFormItem(param))}</div>
        </div>
      )}
    </div>
  );
};

export default NestedFormFields;
