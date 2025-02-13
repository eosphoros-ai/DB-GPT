import { SupportModelParams } from '@/types/model';
import { Checkbox, Form, FormInstance, Input, InputNumber, Select } from 'antd';
import { useEffect } from 'react';
import NestedFormFields from './nested-form-fields';

interface ParamValues {
  [key: string]: string | number | boolean | Record<string, any>;
}

function ModelParams({ params, form }: { params: Array<SupportModelParams> | null; form: FormInstance<any> }) {
  useEffect(() => {
    if (params) {
      const initialValues: ParamValues = {};
      params.forEach(param => {
        // 对于嵌套字段，我们不在这里设置初始值
        if (!param.nested_fields) {
          initialValues[param.param_name] = param.default_value;
        }
      });
      form.setFieldsValue(initialValues);
    }
  }, [params, form]);

  if (!params || params?.length < 1) {
    return null;
  }

  // 在表单提交前转换数据结构
  const normalizeFormValues = (values: any) => {
    const normalized = { ...values };
    params?.forEach(param => {
      if (param.nested_fields && normalized[param.param_name]) {
        const nestedValue = normalized[param.param_name];
        // 移除多余的嵌套结构，只保留选中类型的配置
        if (nestedValue.type) {
          const type = nestedValue.type;
          normalized[param.param_name] = {
            type,
            ...nestedValue
          };
        }
      }
    });
    return normalized;
  };

  // 覆盖表单的原始提交方法
  const originalSubmit = form.submit;
  form.submit = () => {
    const values = form.getFieldsValue();
    const normalizedValues = normalizeFormValues(values);
    form.setFieldsValue(normalizedValues);
    originalSubmit.call(form);
  };

  function renderItem(param: SupportModelParams) {
    if (param.nested_fields) {
      return (
        <NestedFormFields
          parentName={param.param_name}
          fields={param.nested_fields as Record<string, SupportModelParams[]>}
          form={form}
        />
      );
    }

    const type = param.param_type.toLowerCase();
    if (type === 'str' || type === 'string') {
      if (param.valid_values) {
        return (
          <Select>
            {param.valid_values.map(value => (
              <Select.Option key={value} value={value}>
                {value}
              </Select.Option>
            ))}
          </Select>
        );
      }
      return <Input />;
    }
    if (type === 'int' || type === 'integer' || type === 'number' || type === 'float') {
      return <InputNumber className='w-full' />;
    }
    if (type === 'bool' || type === 'boolean') {
      return <Checkbox />;
    }
    return <Input />;
  }

  return (
    <div className="space-y-4">
      {params?.map((param: SupportModelParams) => (
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
          rules={[{ required: param.required, message: `Please input ${param.param_name}` }]}
        >
          {renderItem(param)}
        </Form.Item>
      ))}
    </div>
  );
}

export default ModelParams;
