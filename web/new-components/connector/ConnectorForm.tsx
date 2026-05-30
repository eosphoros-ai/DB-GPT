import { Alert, Button, Form, Input, Modal, Radio, Select } from 'antd';
import React, { useEffect, useMemo } from 'react';
import { ConnectorAuthField, ConnectorCatalogEntry, ConnectorInstance, CreateConnectorRequest } from './types';

interface ConnectorFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateConnectorRequest) => void;
  catalog: ConnectorCatalogEntry[];
  catalogLoading?: boolean;
  initialValues?: ConnectorInstance;
  prefilledType?: string;
  /**
   * True while a create/update request is in flight. Drives the submit
   * button's loading spinner and disables both action buttons so the
   * modal can't be re-submitted or torn down mid-request.
   */
  submitting?: boolean;
}

// Fields that for custom_mcp belong to `config` (not `credentials`).
// `transport` + `description` join the trio because they are connection-level /
// UI-level metadata, not secrets.
const CUSTOM_MCP_CONFIG_FIELDS = new Set([
  'server_uri',
  'auth_type',
  'header_name',
  'transport',
  'description',
]);

// Fields rendered with bespoke widgets at fixed positions in the form, not
// via the generic visibleFields map. Excluded from that map so they don't
// render twice.
const CUSTOM_RENDERED_FIELDS = new Set(['transport', 'description']);

// server_uri is rendered as a top-level field for ALL connector types
// (built-in templates AND custom_mcp), and stored under request.config.server_uri.

type FormShape = {
  display_name: string;
  connector_type: string;
  server_uri: string;
  // All field values are flat, keyed by field.name; we split into credentials/config on submit.
  fields: Record<string, string>;
};

// UI-facing transport metadata. Keep keys aligned with backend
// `_normalise_transport` accepted values in `mcp_utils.py`.
const TRANSPORT_META: Record<
  string,
  { displayName: string; label: string; placeholder: string; hint: string }
> = {
  sse: {
    displayName: 'SSE',
    label: 'SSE Endpoint URL',
    placeholder: 'http://your-mcp-server/sse',
    hint: '完整的 MCP Server SSE 端点,例如 http://localhost:3001/sse',
  },
  streamable_http: {
    displayName: 'Streamable HTTP',
    label: 'Streamable HTTP Endpoint URL',
    placeholder: 'https://your-mcp-server/mcp',
    hint: 'MCP Streamable HTTP 端点,例如 https://example.com/api/v1/mcps/.../mcp',
  },
};

// Auth-type select labels. Backend still accepts the lowercase keys (`bearer`,
// `none`, `token`) — we only swap what the user sees, not the wire value.
const AUTH_TYPE_LABELS: Record<string, string> = {
  none: '无认证',
  bearer: 'Bearer Token',
  token: '自定义 Header Token',
};

const ConnectorForm: React.FC<ConnectorFormProps> = ({
  open,
  onClose,
  onSubmit,
  catalog,
  catalogLoading,
  initialValues,
  prefilledType,
  submitting,
}) => {
  const [form] = Form.useForm<FormShape>();

  const selectedType = Form.useWatch('connector_type', form);
  const watchedFields = Form.useWatch('fields', form) ?? {};
  const selectedCatalog = catalog.find(c => c.type === selectedType);

  const isCustomMcp = selectedType === 'custom_mcp';
  const authType = watchedFields?.auth_type;
  // Default to 'sse' so built-in connectors (which don't show a transport
  // selector) and freshly-opened custom_mcp forms both render SSE copy.
  const transportKey = (watchedFields?.transport as string) || 'sse';
  const transportMeta = TRANSPORT_META[transportKey] ?? TRANSPORT_META.sse;

  // Hide the connector-type selector entirely when the user entered the
  // modal via the dedicated "自定义 MCP" CTA, or is editing a custom_mcp
  // instance. There is nothing to choose: it's always custom_mcp.
  const hideConnectorType =
    isCustomMcp &&
    (prefilledType === 'custom_mcp' || initialValues?.connector_type === 'custom_mcp');

  const visibleFields: ConnectorAuthField[] = useMemo(() => {
    if (!selectedCatalog) return [];
    // server_uri is always rendered as a top-level form field, so exclude it from auth_fields.
    // CUSTOM_RENDERED_FIELDS (transport/description) get bespoke widgets at fixed positions.
    const fields = (selectedCatalog.auth_fields ?? []).filter(
      f => f.name !== 'server_uri' && !CUSTOM_RENDERED_FIELDS.has(f.name),
    );
    if (!isCustomMcp) return fields;
    // For custom_mcp, hide token/header_name based on auth_type
    return fields.filter(field => {
      if (field.name === 'token') return authType === 'bearer' || authType === 'token';
      if (field.name === 'header_name') return authType === 'token';
      return true;
    });
  }, [selectedCatalog, isCustomMcp, authType]);

  useEffect(() => {
    if (!open) return;
    if (initialValues && prefilledType) {
      console.warn(
        'ConnectorForm: initialValues and prefilledType are mutually exclusive; initialValues takes precedence',
      );
    }
    if (initialValues) {
      // Re-hydrate from stored config (custom_mcp) or credentials (built-in).
      const merged: Record<string, string> = {};
      if (initialValues.config) {
        for (const [k, v] of Object.entries(initialValues.config)) {
          if (v != null && k !== 'server_uri') merged[k] = String(v);
        }
      }
      form.setFieldsValue({
        display_name: initialValues.display_name,
        connector_type: initialValues.connector_type,
        server_uri: String(initialValues.config?.server_uri ?? ''),
        fields: merged,
      });
    } else if (prefilledType) {
      // New instance with pre-selected type (from template activate or custom MCP button)
      form.resetFields();
      form.setFieldsValue({ connector_type: prefilledType });
    } else {
      form.resetFields();
    }
  }, [open, initialValues, prefilledType, form]);

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
    const config: Record<string, unknown> = {
      server_uri: values.server_uri,
    };

    for (const field of selectedCatalog?.auth_fields ?? []) {
      if (field.name === 'server_uri') continue; // already handled above
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
      config,
    };
    onSubmit(request);
  };

  // Transport options derived from the catalog auth_fields so the catalog
  // is the single source of truth — we just re-skin the labels.
  const transportField = selectedCatalog?.auth_fields?.find(f => f.name === 'transport');
  const transportOptions = (transportField?.options ?? ['sse', 'streamable_http']).map(opt => ({
    label: TRANSPORT_META[opt]?.displayName ?? opt,
    value: opt,
  }));
  // Bump streamable_http to the leftmost slot — it's the modern transport
  // most production MCP servers (dashscope, modelscope, ...) ship with, so
  // surfacing it first matches the path users actually take.
  transportOptions.sort((a, b) => {
    const rank = (v: string) => (v === 'streamable_http' ? 0 : v === 'sse' ? 1 : 2);
    return rank(a.value) - rank(b.value);
  });

  return (
    <Modal
      open={open}
      title={initialValues ? '编辑连接器' : '添加连接器'}
      onCancel={onClose}
      footer={null}
      destroyOnClose
      width={600}
    >
      <Form form={form} layout='vertical' onFinish={handleFinish} className='mt-4'>
        {initialValues && (
          <Alert
            type='info'
            showIcon
            message='出于安全原因，凭证（token/密钥等）不会回填。如需修改，请重新输入；留空则保持原值不变。'
            className='mb-4'
          />
        )}
        <Form.Item
          name='display_name'
          label='连接器名称'
          rules={[{ required: true, message: '请输入连接器名称' }]}
        >
          <Input placeholder='请输入连接器名称' />
        </Form.Item>

        {/* Connector type — hidden when the user is in the dedicated custom_mcp flow */}
        <Form.Item
          name='connector_type'
          label='连接器类型'
          rules={[{ required: true, message: '请选择连接器类型' }]}
          hidden={hideConnectorType}
        >
          <Select
            placeholder='请选择连接器类型'
            loading={catalogLoading}
            disabled={!!initialValues}
            options={catalog.map(entry => ({
              label: entry.display_name,
              value: entry.type,
            }))}
          />
        </Form.Item>

        {/* Transport — card-style radio. Selected card gets a brand-blue
            border + tinted fill so it reads as a primary picker, not a
            secondary segmented control. */}
        {isCustomMcp && (
          <Form.Item
            name={['fields', 'transport']}
            label='传输协议'
            rules={[{ required: true, message: '请选择传输协议' }]}
            initialValue='sse'
          >
            <Radio.Group className='w-full grid grid-cols-2 gap-3'>
              {transportOptions.map(opt => (
                <Radio
                  key={opt.value}
                  value={opt.value}
                  className='!flex items-center gap-2 px-4 py-3 !m-0 border border-solid border-gray-200 rounded-lg cursor-pointer transition-colors hover:border-gray-300 [&.ant-radio-wrapper-checked]:border-blue-500 [&.ant-radio-wrapper-checked]:bg-blue-50/40 [&.ant-radio-wrapper-checked]:shadow-sm'
                >
                  <span className='text-sm font-medium text-gray-800'>{opt.label}</span>
                </Radio>
              ))}
            </Radio.Group>
          </Form.Item>
        )}

        {selectedType && (
          <Form.Item
            name='server_uri'
            label={transportMeta.label}
            rules={[
              { required: true, message: '请输入 MCP Server 的端点 URL' },
              {
                pattern: /^https?:\/\/.+/i,
                message: 'URL 必须以 http:// 或 https:// 开头',
              },
            ]}
            extra={
              isCustomMcp
                ? transportMeta.hint
                : '请填写你部署的 MCP Server 实际端点 URL(平台不再提供默认端点)'
            }
          >
            <Input placeholder={transportMeta.placeholder} />
          </Form.Item>
        )}

        {visibleFields.map(field => {
          const isEditMode = !!initialValues;
          const isPasswordField = field.type === 'password';
          const fieldRequired = field.required && !(isEditMode && isPasswordField);
          const placeholder = isEditMode && isPasswordField
            ? '留空保持原值不变'
            : `请输入${field.label}`;
          let control: React.ReactNode;
          if (field.type === 'select') {
            // Auth-type select uses friendlier labels (e.g. "Bearer Token") while
            // keeping the wire value lowercase so the backend dispatch is unchanged.
            const optionList = (field.options ?? []).map(opt => ({
              label: field.name === 'auth_type' ? (AUTH_TYPE_LABELS[opt] ?? opt) : opt,
              value: opt,
            }));
            control = (
              <Select placeholder={`请选择${field.label}`} options={optionList} />
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
              rules={fieldRequired ? [{ required: true, message: `请输入${field.label}` }] : []}
            >
              {control}
            </Form.Item>
          );
        })}

        {/* Optional connector description — surfaced in the agent's MCP tool
            block prompt. Placed last so it doesn't push down the required
            fields; user-resizable so long descriptions stay editable. */}
        {isCustomMcp && (
          <Form.Item
            name={['fields', 'description']}
            label='连接器描述（可选）'
            extra={<span className='text-xs text-gray-400'>在 Agent 工具说明中展示</span>}
          >
            <Input.TextArea
              placeholder='一句话说清这个 MCP 提供什么能力,例如:ArXiv 论文搜索与下载'
              rows={3}
              maxLength={500}
              style={{ resize: 'vertical' }}
              className='text-sm'
            />
          </Form.Item>
        )}

        <div className='flex justify-end gap-2'>
          <Button onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button type='primary' htmlType='submit' loading={submitting} disabled={submitting}>
            {initialValues ? '保存' : '添加'}
          </Button>
        </div>
      </Form>
    </Modal>
  );
};

export default ConnectorForm;
