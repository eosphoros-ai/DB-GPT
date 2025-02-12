import { SupportModelParams } from '@/types/model';
import { Checkbox, Form, FormInstance, Input, InputNumber } from 'antd';
import { useEffect } from 'react';

interface ParamValues {
  [key: string]: string | number | boolean;
}

function ModelParams({ params, form }: { params: Array<SupportModelParams> | null; form: FormInstance<any> }) {
  useEffect(() => {
    if (params) {
      const initialValues: ParamValues = {};
      params.forEach(param => {
        initialValues[param.param_name] = param.default_value;
      });
      form.setFieldsValue(initialValues);
    }
  }, [params, form]);

  if (!params || params?.length < 1) {
    return null;
  }

  function renderItem(param: SupportModelParams) {
    const type = param.param_type.toLowerCase();
    if (type === 'str' || type === 'string') {
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
    <>
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
    </>
  );
}

export default ModelParams;
