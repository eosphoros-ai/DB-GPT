import { ConfigurableParams } from '@/types/common';
import { Checkbox, Form, FormInstance, Input, InputNumber, Select } from 'antd';
import React, { useEffect, useState } from 'react';

interface NestedFormFieldsProps {
  parentName: string;
  fields: Record<string, ConfigurableParams[]>;
  form: FormInstance;
}
const NestedFormFields: React.FC<NestedFormFieldsProps> = ({ parentName, fields, form }) => {
  const [selectedType, setSelectedType] = useState<string | null>(null);

  useEffect(() => {
    const currentValue = form.getFieldValue(parentName);
    if (currentValue?.type && !selectedType) {
      setSelectedType(currentValue.type);
    }
  }, [form, parentName]);

  const handleTypeChange = (value: string) => {
    setSelectedType(value);

    // Get all field configurations for the current type
    const typeFields = fields[value] || [];

    // Create an object containing default values for all fields
    const defaultValues = {
      type: value,
    };

    // Set default values for each field
    typeFields.forEach(field => {
      defaultValues[field.param_name] = field.default_value;
    });

    // Set the entire object as the value of the form field
    form.setFieldsValue({
      [parentName]: defaultValues,
    });
  };

  const renderFormItem = (param: ConfigurableParams) => {
    const type = param.param_type.toLowerCase();
    // Use the complete field path
    const fieldPath = [parentName, param.param_name];

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
        key={param.param_name}
        label={param.label || param.param_name}
        name={fieldPath}
        valuePropName={type === 'bool' || type === 'boolean' ? 'checked' : 'value'}
        tooltip={param.description}
        rules={selectedType && param.required ? [{ required: true, message: `Please input ${param.param_name}` }] : []}
      >
        {control}
      </Form.Item>
    );
  };

  return (
    <div className='space-y-4 border rounded-md p-4'>
      <Form.Item label='Type' name={[parentName, 'type']}>
        <Select onChange={handleTypeChange} placeholder='Select a type'>
          {Object.keys(fields).map(type => (
            <Select.Option key={type} value={type}>
              {type}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      {selectedType && fields[selectedType] && (
        <div className='mt-4'>
          <h4 className='mb-4 text-base font-medium'>{selectedType} Configuration</h4>
          <div className='space-y-4'>{fields[selectedType].map(param => renderFormItem(param))}</div>
        </div>
      )}
    </div>
  );
};
export default NestedFormFields;
