import { Button, Form, Input, Modal, Select } from 'antd';
import React, { useEffect } from 'react';
import { ConnectorCatalogEntry, ConnectorInstance, CreateConnectorRequest } from './types';

interface ConnectorFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateConnectorRequest) => void;
  catalog: ConnectorCatalogEntry[];
  catalogLoading?: boolean;
  initialValues?: ConnectorInstance;
}

const ConnectorForm: React.FC<ConnectorFormProps> = ({ open, onClose, onSubmit, catalog, catalogLoading, initialValues }) => {
  const [form] = Form.useForm<{
    display_name: string;
    connector_type: string;
    credentials: Record<string, string>;
  }>();

  const selectedType = Form.useWatch('connector_type', form);
  const selectedCatalog = catalog.find(c => c.type === selectedType);

  useEffect(() => {
    if (open) {
      if (initialValues) {
        form.setFieldsValue({
          display_name: initialValues.display_name,
          connector_type: initialValues.connector_type,
          credentials: (initialValues.config as Record<string, string>) ?? {},
        });
      } else {
        form.resetFields();
      }
    }
  }, [open, initialValues, form]);

  const handleFinish = (values: {
    display_name: string;
    connector_type: string;
    credentials?: Record<string, string>;
  }) => {
    const request: CreateConnectorRequest = {
      connector_type: values.connector_type,
      display_name: values.display_name,
      credentials: values.credentials ?? {},
    };
    onSubmit(request);
  };

  return (
    <Modal
      open={open}
      title={initialValues ? '编辑连接器' : '添加连接器'}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      <Form form={form} layout='vertical' onFinish={handleFinish} className='mt-4'>
        <Form.Item
          name='display_name'
          label='连接器名称'
          rules={[{ required: true, message: '请输入连接器名称' }]}
        >
          <Input placeholder='请输入连接器名称' />
        </Form.Item>

        <Form.Item
          name='connector_type'
          label='连接器类型'
          rules={[{ required: true, message: '请选择连接器类型' }]}
        >
          <Select
            placeholder='请选择连接器类型'
            loading={catalogLoading}
            options={catalog.map(entry => ({
              label: entry.display_name,
              value: entry.type,
            }))}
          />
        </Form.Item>

        {selectedCatalog &&
          selectedCatalog.auth.fields.map(field => (
            <Form.Item
              key={field.name}
              name={['credentials', field.name]}
              label={field.label}
              rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}
            >
              {field.type === 'password' ? (
                <Input.Password placeholder={`请输入${field.label}`} />
              ) : (
                <Input type={field.type} placeholder={`请输入${field.label}`} />
              )}
            </Form.Item>
          ))}

        <div className='flex justify-end gap-2'>
          <Button onClick={onClose}>取消</Button>
          <Button type='primary' htmlType='submit'>
            {initialValues ? '保存' : '添加'}
          </Button>
        </div>
      </Form>
    </Modal>
  );
};

export default ConnectorForm;
