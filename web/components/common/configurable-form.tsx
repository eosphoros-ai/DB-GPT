import { ConfigurableParams } from '@/types/common';
import { Checkbox, Form, FormInstance, Input, InputNumber, Select } from 'antd';
import { useEffect } from 'react';
import NestedFormFields from './nested-form-fields';

interface ParamValues {
  [key: string]: string | number | boolean | Record<string, any>;
}

// Check if valid_values is an array of objects containing label and key
const isComplexValidValues = (values: any[]): boolean => {
  if (!Array.isArray(values) || values.length === 0) return false;
  return typeof values[0] === 'object' && values[0] !== null && 'key' in values[0] && 'label' in values[0];
};

function ConfigurableForm({ params, form }: { params: Array<ConfigurableParams> | null; form: FormInstance<any> }) {
  // Initialize the default value of the form
  useEffect(() => {
    if (params) {
      const initialValues: ParamValues = {};
      params.forEach(param => {
        if (!param.nested_fields) {
          // Only set default value when the field has not been modified by the user
          const currentValue = form.getFieldValue(param.param_name);
          if (currentValue === undefined) {
            initialValues[param.param_name] = param.default_value;
          }
        }
      });
      form.setFieldsValue(initialValues);
    }
  }, [params, form]);

  if (!params || params?.length < 1) {
    return null;
  }

  // Transform data structure before form submission
  const normalizeFormValues = (values: any) => {
    const normalized = { ...values };
    params?.forEach(param => {
      if (param.nested_fields && normalized[param.param_name]) {
        const nestedValue = normalized[param.param_name];
        if (nestedValue.type) {
          // Keep all field values instead of just type
          const nestedFields = param.nested_fields[nestedValue.type] || [];
          const fieldValues = {};
          nestedFields.forEach(field => {
            if (nestedValue[field.param_name] !== undefined) {
              fieldValues[field.param_name] = nestedValue[field.param_name];
            }
          });

          normalized[param.param_name] = {
            type: nestedValue.type,
            ...fieldValues,
          };
        }
      }
    });
    return normalized;
  };

  // Override the original submit method of the form
  const originalSubmit = form.submit;
  form.submit = () => {
    const values = form.getFieldsValue();
    const normalizedValues = normalizeFormValues(values);
    form.setFieldsValue(normalizedValues);
    originalSubmit.call(form);
  };

  function renderItem(param: ConfigurableParams) {
    if (param.nested_fields) {
      return (
        <NestedFormFields
          parentName={param.param_name}
          fields={param.nested_fields as Record<string, ConfigurableParams[]>}
          form={form}
        />
      );
    }

    const type = param.param_type.toLowerCase();
    const isFixed = param.ext_metadata?.tags?.includes('fixed');
    const isPrivacy = param.ext_metadata?.tags?.includes('privacy');

    if (type === 'str' || type === 'string') {
      // Handle dropdown selection box
      if (param.valid_values) {
        // Check if valid_values is an array of objects containing label and key
        if (isComplexValidValues(param.valid_values)) {
          return (
            <Select disabled={isFixed}>
              {param.valid_values.map((item: any) => (
                <Select.Option key={item.key} value={item.key}>
                  {item.label}
                </Select.Option>
              ))}
            </Select>
          );
        } else {
          // Simple string array
          return (
            <Select disabled={isFixed}>
              {param.valid_values.map((value: string) => (
                <Select.Option key={value} value={value}>
                  {value}
                </Select.Option>
              ))}
            </Select>
          );
        }
      }

      // Handle password input box
      if (isPrivacy) {
        return <Input.Password disabled={isFixed} autoComplete='new-password' placeholder='请输入密码' />;
      }

      // Handle normal text input box
      return <Input disabled={isFixed} />;
    }

    if (type === 'int' || type === 'integer' || type === 'number' || type === 'float') {
      return <InputNumber className='w-full' disabled={isFixed} />;
    }

    if (type === 'bool' || type === 'boolean') {
      return <Checkbox disabled={isFixed} />;
    }

    return <Input disabled={isFixed} />;
  }

  return (
    <div className='space-y-4'>
      {params?.map((param: ConfigurableParams) => (
        <Form.Item
          key={param.param_name}
          label={<p className='whitespace-normal overflow-wrap-break-word'>{param.label || param.param_name}</p>}
          name={param.param_name}
          initialValue={param.default_value}
          valuePropName={
            param.param_type.toLowerCase() === 'bool' || param.param_type.toLowerCase() === 'boolean'
              ? 'checked'
              : 'value'
          }
          tooltip={param.description}
          rules={param.required ? [{ required: true, message: `Please input ${param.label || param.param_name}` }] : []}
        >
          {renderItem(param)}
        </Form.Item>
      ))}
    </div>
  );
}

export default ConfigurableForm;
