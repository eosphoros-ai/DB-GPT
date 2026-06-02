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

  const authType = watchedFields?.auth_type;
  // Default to 'streamable_http' so a freshly-opened form (before the user
  // picks a transport) renders Streamable HTTP copy — it's the modern default
  // most hosted MCP servers ship with. extra_config.transport overrides at submit.
  const transportKey = (watchedFields?.transport as string) || 'streamable_http';
  const transportMeta = TRANSPORT_META[transportKey] ?? TRANSPORT_META.streamable_http;

  // Hide the connector-type selector whenever the user entered the modal
  // with a fixed type — template activation (prefilledType) or editing an
  // existing instance (initialValues). The user has nothing meaningful to
  // re-select; the selector would just be a footgun.
  const hideConnectorType =
    prefilledType !== undefined || initialValues !== undefined;

  // A built-in catalog template (github / notion / feishu / ...) — anything
  // with a catalog entry that is NOT the synthetic custom_mcp option. Used to:
  //   1. hide the "连接器名称" input (we reuse the catalog display_name), and
  //   2. seed the description field with the catalog description.
  const isBuiltinTemplate = selectedCatalog != null && selectedCatalog.is_custom !== true;

  const visibleFields: ConnectorAuthField[] = useMemo(() => {
    if (!selectedCatalog) return [];
    // server_uri is always rendered as a top-level form field, so exclude it from auth_fields.
    // CUSTOM_RENDERED_FIELDS (transport/description) get bespoke widgets at fixed positions.
    const fields = (selectedCatalog.auth_fields ?? []).filter(
      f => f.name !== 'server_uri' && !CUSTOM_RENDERED_FIELDS.has(f.name),
    );
    // Hide token / header_name unless the chosen auth_type calls for them.
    // Applies to ALL connector types now that built-ins share the unified
    // auth_fields with custom_mcp.
    return fields.filter(field => {
      if (field.name === 'token') return authType === 'bearer' || authType === 'token';
      if (field.name === 'header_name') return authType === 'token';
      return true;
    });
  }, [selectedCatalog, authType]);

  useEffect(() => {
    if (!open) return;
    // Always start from a clean slate. Without this, values from the
    // previously-opened dialog (e.g. an instance whose config.description was
    // set) leak into the next one — Form.setFieldsValue is a partial merge,
    // not a replace, so any key we don't explicitly set carries over from
    // the prior open.
    form.resetFields();
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
      form.setFieldsValue({ connector_type: prefilledType });
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
    // Seed the description with the catalog blurb for built-in templates
    // (e.g. "GitHub Issues、PR、仓库管理") so the user gets a sensible default
    // they can keep or edit. Skip for custom_mcp (no meaningful catalog
    // description) and when editing (description is re-hydrated from config).
    if (
      isBuiltinTemplate &&
      !initialValues &&
      selectedCatalog.description &&
      (next.description === undefined || next.description === '')
    ) {
      next.description = selectedCatalog.description;
      changed = true;
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
      if (CUSTOM_MCP_CONFIG_FIELDS.has(field.name)) {
        config[field.name] = value;
      } else {
        credentials[field.name] = value;
      }
    }

    // For built-in templates the name input is hidden — reuse the catalog
    // display_name (e.g. "GitHub"). custom_mcp keeps the user-entered name.
    const resolvedDisplayName =
      isBuiltinTemplate && selectedCatalog
        ? selectedCatalog.display_name
        : values.display_name;

    const request: CreateConnectorRequest = {
      connector_type: values.connector_type,
      display_name: resolvedDisplayName,
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
        {/* Connector name — hidden for built-in templates (we reuse the
            catalog display_name). Only custom_mcp asks the user to name it. */}
        <Form.Item
          name='display_name'
          label='连接器名称'
          rules={isBuiltinTemplate ? [] : [{ required: true, message: '请输入连接器名称' }]}
          hidden={isBuiltinTemplate}
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

        {/* Transport — card-style radio. Always shown; built-in templates
            default via catalog mcp_server.transport (resolved server-side at
            create time), custom_mcp defaults to SSE here on the client. */}
        <Form.Item
          name={['fields', 'transport']}
          label='传输协议'
          rules={[{ required: true, message: '请选择传输协议' }]}
          initialValue='streamable_http'
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
            extra={transportMeta.hint}
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
            fields; user-resizable so long descriptions stay editable. Shown
            for all connector types now that built-ins share the unified form. */}
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
