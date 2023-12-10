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
      params.forEach((param) => {
        initialValues[param.param_name] = param.default_value;
      });
      form.setFieldsValue(initialValues); // 设置表单字段的初始值
    }
  }, [params, form]);
  if (!params || params?.length < 1) {
    return null;
  }

  function renderItem(param: SupportModelParams) {
    switch (param.param_type) {
      case 'str':
        return <Input />;
      case 'int':
        return <InputNumber />;
      case 'bool':
        return <Checkbox />;
    }
  }
  return (
    <>
      {params?.map((param: SupportModelParams) => (
        <Form.Item
          key={param.param_name}
          label={
            <p className="whitespace-normal overflow-wrap-break-word">{param.description?.length > 20 ? param.param_name : param.description}</p>
          }
          name={param.param_name}
          initialValue={param.default_value}
          valuePropName={param.param_type === 'bool' ? 'checked' : 'value'}
          tooltip={param.description}
          rules={[{ required: param.required, message: `Please input ${param.description}` }]}
        >
          {renderItem(param)}
        </Form.Item>
      ))}
    </>
  );
}

export default ModelParams;
