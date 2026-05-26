import { Button, Form, Input, Modal, Select } from 'antd';
import React, { useEffect, useMemo } from 'react';
import { ConnectorAuthField, ConnectorCatalogEntry, ConnectorInstance, CreateConnectorRequest } from './types';

interface ConnectorFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateConnectorRequest) => void;
  catalog: ConnectorCatalogEntry[];
  catalogLoading?: boolean;
  initialValues?: ConnectorInstance;
}

// Fields that for custom_mcp belong to `config` (not `credentials`)
const CUSTOM_MCP_CONFIG_FIELDS = new Set(['server_uri', 'auth_type', 'header_name']);

type FormShape = {
  display_name: string;
  connector_type: string;
  // All field values are flat, keyed by field.name; we split into credentials/config on submit.
  fields: Record<string, string>;
};

const ConnectorForm: React.FC<ConnectorFormProps> = ({
  open,
  onClose,
  onSubmit,
  catalog,
  catalogLoading,
  initialValues,
}) => {
  const [form] = Form.useForm<FormShape>();

  const selectedType = Form.useWatch('connector_type', form);
  const watchedFields = Form.useWatch('fields', form) ?? {};
  const selectedCatalog = catalog.find(c => c.type === selectedType);

  const isCustomMcp = selectedType === 'custom_mcp';
  const authType = watchedFields?.auth_type;

  const visibleFields: ConnectorAuthField[] = useMemo(() => {
    if (!selectedCatalog) return [];
    if (!isCustomMcp) return selectedCatalog.auth_fields ?? [];
    // For custom_mcp, hide token/header_name based on auth_type
    return (selectedCatalog.auth_fields ?? []).filter(field => {
      if (field.name === 'token') return authType === 'bearer' || authType === 'token';
      if (field.name === 'header_name') return authType === 'token';
      return true;
    });
  }, [selectedCatalog, isCustomMcp, authType]);

  useEffect(() => {
    if (!open) return;
    if (initialValues) {
      // Re-hydrate from stored config (custom_mcp) or credentials (built-in).
      const merged: Record<string, string> = {};
      if (initialValues.config) {
        for (const [k, v] of Object.entries(initialValues.config)) {
          if (v != null) merged[k] = String(v);
        }
      }
      form.setFieldsValue({
        display_name: initialValues.display_name,
        connector_type: initialValues.connector_type,
        fields: merged,
      });
    } else {
      form.resetFields();
    }
  }, [open, initialValues, form]);

  // Apply defaults when a type is (re)selected.
  useEffect(() => {
    if (!selectedCatalog) return;
    const current = form.getFieldValue('fields') ?? {};
    let changed = false;
    const next: Record<string, string> = { ...current };
    for (const field of selectedCatalog.auth_fields ?? []) {
      if (field.default !== undefined && (next[field.name] === undefined || next[field.name] === '')) {
        next[field.name] = field.default;
        changed = true;
      }
    }
    if (changed) {
      form.setFieldsValue({ fields: next });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedType]);

  const handleFinish = (values: FormShape) => {
    const all = values.fields ?? {};
    const credentials: Record<string, string> = {};
    const config: Record<string, unknown> = {};

    for (const field of selectedCatalog?.auth_fields ?? []) {
      const value = all[field.name];
      if (value === undefined || value === '') continue;
      if (isCustomMcp && CUSTOM_MCP_CONFIG_FIELDS.has(field.name)) {
        config[field.name] = value;
      } else {
        credentials[field.name] = value;
      }
    }

    const request: CreateConnectorRequest = {
      connector_type: values.connector_type,
      display_name: values.display_name,
      credentials,
    };
    if (isCustomMcp) {
      request.config = config;
    }
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

        {visibleFields.map(field => {
          const placeholder = `请输入${field.label}`;
          let control: React.ReactNode;
          if (field.type === 'select') {
            control = (
              <Select
                placeholder={`请选择${field.label}`}
                options={(field.options ?? []).map(opt => ({ label: opt, value: opt }))}
              />
            );
          } else if (field.type === 'password') {
            control = <Input.Password placeholder={placeholder} />;
          } else {
            control = <Input type={field.type} placeholder={placeholder} />;
          }
          return (
            <Form.Item
              key={field.name}
              name={['fields', field.name]}
              label={field.label}
              rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}
            >
              {control}
            </Form.Item>
          );
        })}

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
