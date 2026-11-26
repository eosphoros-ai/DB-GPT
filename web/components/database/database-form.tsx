import { apiInterceptors, postDbAdd, postDbEdit, postDbTestConnect } from '@/client/api';
import NestedFormFields from '@/components/common/nested-form-fields';
import { ConfigurableParams } from '@/types/common';
import { DBOption, DBType, PostDbParams } from '@/types/db';
import { CheckCircleOutlined, LinkOutlined } from '@ant-design/icons';
import { Alert, Button, Checkbox, Collapse, Form, Input, InputNumber, Select, message } from 'antd';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import DatabaseTypeIcon from './database-type-icon';
import styles from './database.module.css';
import { isBasicParameter, parameterLabel, useDatabaseCopy } from './presentation';

interface DatabaseFormProps {
  onCancel: () => void;
  onSuccess: () => void;
  dbTypeList: DBOption[];
  editValue?: string;
  choiceDBType?: DBType;
  initialParams?: Record<string, any>;
  description?: string;
}

function DatabaseForm({
  onCancel,
  onSuccess,
  dbTypeList,
  editValue,
  choiceDBType,
  initialParams = {},
  description = '',
}: DatabaseFormProps) {
  const { i18n } = useTranslation();
  const { zh, copy } = useDatabaseCopy(i18n.language);
  const [form] = Form.useForm();
  const [selectedType, setSelectedType] = useState(choiceDBType);
  const [busy, setBusy] = useState<'test' | 'save'>();
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string }>();
  const revision = useRef(0);
  const selected = dbTypeList.find(type => type.value === selectedType);
  const params = selected?.parameters || [];
  const fieldOrder = [
    'host',
    'port',
    'user',
    'username',
    'password',
    'pwd',
    'database',
    'db_name',
    'schema',
    'path',
    'project',
    'access_id',
    'access_key',
    'endpoint',
  ];
  const basic = params.filter(isBasicParameter).sort((a, b) => {
    const aOrder = fieldOrder.indexOf(a.param_name);
    const bOrder = fieldOrder.indexOf(b.param_name);
    return (aOrder < 0 ? fieldOrder.length : aOrder) - (bOrder < 0 ? fieldOrder.length : bOrder);
  });
  const advanced = params.filter(param => !isBasicParameter(param));

  const invalidate = () => {
    revision.current += 1;
    setFeedback(undefined);
  };

  const handleTypeChange = (value: DBType) => {
    // Clear the previous connector's fields, including values hidden in advanced settings.
    const currentDescription = form.getFieldValue('description');
    form.resetFields();
    const defaults = Object.fromEntries(
      (dbTypeList.find(type => type.value === value)?.parameters || []).map(param => [
        param.param_name,
        param.default_value,
      ]),
    );
    form.setFieldsValue({ ...defaults, type: value, description: currentDescription });
    setSelectedType(value);
    invalidate();
  };

  const requestData = async (): Promise<PostDbParams> => {
    await form.validateFields();
    const values = form.getFieldsValue(true);
    const parameters: Record<string, any> = {};
    params.forEach(param => {
      if (values[param.param_name] !== undefined) parameters[param.param_name] = values[param.param_name];
    });
    return {
      type: selectedType,
      params: parameters as PostDbParams['params'],
      description: values.description || '',
      ...(editValue ? { id: editValue } : {}),
    };
  };

  const testConnection = async (data: PostDbParams) => {
    const [err, , response] = await apiInterceptors(postDbTestConnect(data), '*');
    if (err || response?.success === false) {
      setFeedback({
        ok: false,
        text:
          response?.err_msg ||
          err?.message ||
          copy('连接失败，请检查连接信息后重试。', 'Connection failed. Check your settings and try again.'),
      });
      return false;
    }
    setFeedback({
      ok: true,
      text: copy('连接测试通过，可以保存此数据源。', 'Connection verified. This data source is ready to save.'),
    });
    return true;
  };

  const handleTest = async () => {
    try {
      const data = await requestData();
      setBusy('test');
      setFeedback(undefined);
      const currentRevision = revision.current;
      await testConnection(data);
      if (currentRevision !== revision.current) setFeedback(undefined);
    } catch (error) {
      if (!(error as { errorFields?: unknown })?.errorFields) {
        setFeedback({
          ok: false,
          text: copy('暂时无法测试连接，请稍后重试。', 'Unable to test the connection. Please try again.'),
        });
      }
    } finally {
      setBusy(undefined);
    }
  };

  const handleSave = async () => {
    try {
      const data = await requestData();
      setBusy('save');
      if (!(await testConnection(data))) return;
      const [err, , response] = await apiInterceptors((editValue ? postDbEdit : postDbAdd)(data), '*');
      if (err || response?.success === false) {
        setFeedback({
          ok: false,
          text: response?.err_msg || err?.message || copy('保存失败，请重试。', 'Unable to save. Please try again.'),
        });
        return;
      }
      message.success(
        copy(editValue ? '数据源已更新' : '数据源已添加', editValue ? 'Data source updated' : 'Data source added'),
      );
      onSuccess();
    } catch (error) {
      if (!(error as { errorFields?: unknown })?.errorFields) {
        setFeedback({ ok: false, text: copy('保存失败，请稍后重试。', 'Unable to save. Please try again.') });
      }
    } finally {
      setBusy(undefined);
    }
  };

  const renderFields = (fields: ConfigurableParams[]) => (
    <div className={styles.fields}>
      {fields.map(param => {
        const label = parameterLabel(param, zh);
        const type = param.param_type?.toLowerCase();
        const fixed = param.ext_metadata?.tags?.includes('fixed');
        const secret =
          param.ext_metadata?.tags?.includes('privacy') || /password|pwd|access_key|secret/i.test(param.param_name);
        const boolean = type === 'bool' || type === 'boolean';
        const wide =
          param.nested_fields ||
          ['database', 'db_name', 'path', 'project', 'endpoint', 'uri', 'url'].includes(param.param_name);
        let control;
        if (param.nested_fields) {
          control = (
            <NestedFormFields
              parentName={param.param_name}
              fields={param.nested_fields as unknown as Record<string, ConfigurableParams[]>}
              form={form}
            />
          );
        } else if (param.valid_values) {
          control = (
            <Select
              disabled={fixed}
              options={param.valid_values.map(value =>
                typeof value === 'object'
                  ? { label: (value as any).label, value: (value as any).key }
                  : { label: value, value },
              )}
            />
          );
        } else if (boolean) {
          control = <Checkbox disabled={fixed}>{copy('启用', 'Enabled')}</Checkbox>;
        } else if (['int', 'integer', 'number', 'float'].includes(type)) {
          control = <InputNumber disabled={fixed} placeholder={param.param_name === 'port' ? '5432' : undefined} />;
        } else if (secret) {
          control = (
            <Input.Password
              disabled={fixed}
              autoComplete='new-password'
              placeholder={copy('输入凭据', 'Enter credential')}
            />
          );
        } else {
          const placeholder =
            param.param_name === 'path'
              ? copy('例如 /data/analytics.db', 'e.g. /data/analytics.db')
              : param.param_name === 'host'
                ? 'localhost'
                : param.param_name === 'database'
                  ? copy('例如 analytics', 'e.g. analytics')
                  : `${copy('请输入', 'Enter')} ${label}`;
          control = <Input disabled={fixed} placeholder={placeholder} autoComplete='off' />;
        }
        return (
          <Form.Item
            key={`${selectedType}-${param.param_name}`}
            className={wide ? styles.wideField : undefined}
            label={label}
            name={param.param_name}
            initialValue={
              Object.prototype.hasOwnProperty.call(initialParams, param.param_name) ? undefined : param.default_value
            }
            valuePropName={boolean ? 'checked' : 'value'}
            tooltip={param.description}
            extra={
              param.param_name === 'path' ? (
                <span className={styles.fieldHint}>
                  {copy(
                    '填写 DB-GPT 服务所在机器可访问的文件路径。',
                    'Use a file path accessible from the DB-GPT server.',
                  )}
                </span>
              ) : undefined
            }
            rules={param.required ? [{ required: true, message: `${copy('请填写', 'Please enter')} ${label}` }] : []}
          >
            {control}
          </Form.Item>
        );
      })}
    </div>
  );

  return (
    <Form
      form={form}
      layout='vertical'
      requiredMark
      onValuesChange={invalidate}
      disabled={!!busy}
      initialValues={{ type: choiceDBType, description, ...initialParams }}
    >
      <div className={styles.formBody}>
        <div className={styles.formSection}>
          <span className={styles.sectionNumber}>01</span>
          {copy('选择数据库', 'Database')}
        </div>
        <Form.Item
          label={copy('数据库类型', 'Database type')}
          name='type'
          rules={[{ required: true, message: copy('请选择数据库类型', 'Choose a database type') }]}
        >
          <Select
            showSearch
            optionFilterProp='searchLabel'
            placeholder={copy('搜索并选择数据库类型', 'Search and select a database')}
            onChange={handleTypeChange}
            disabled={!!editValue || !!busy}
            options={dbTypeList.map(type => ({
              value: type.value,
              label: (
                <span className={styles.databaseOption}>
                  <DatabaseTypeIcon icon={type.icon} label={type.label} compact />
                  <span>{type.label}</span>
                </span>
              ),
              searchLabel: type.label,
              disabled: type.disabled,
            }))}
          />
        </Form.Item>
        {selected ? (
          <>
            <div className={styles.selectedType}>
              <DatabaseTypeIcon icon={selected.icon} label={selected.label} />
              <div>
                <p>{selected.label}</p>
                <small>
                  {copy(
                    '配置连接信息，测试通过后即可开始使用。',
                    'Configure and verify your connection to get started.',
                  )}
                </small>
              </div>
            </div>
            <div className={styles.formSection}>
              <span className={styles.sectionNumber}>02</span>
              {copy('连接信息', 'Connection settings')}
            </div>
            <div key={selectedType}>{renderFields(basic)}</div>
            {advanced.length > 0 ? (
              <Collapse
                className={styles.advanced}
                ghost
                items={[
                  {
                    key: 'advanced',
                    label: copy(`高级设置 · ${advanced.length} 项`, `Advanced settings · ${advanced.length}`),
                    forceRender: true,
                    children: renderFields(advanced),
                  },
                ]}
              />
            ) : null}
          </>
        ) : (
          <p className={styles.subtitle} style={{ marginBottom: 24 }}>
            {copy('选择类型后，将展示对应的连接配置。', 'Connection settings appear after you choose a database.')}
          </p>
        )}
        <Form.Item
          label={copy('描述', 'Description')}
          name='description'
          extra={
            <span className={styles.fieldHint}>
              {copy(
                '选填，帮助团队理解这个数据源的用途。',
                'Optional. Help your team understand what this data source is for.',
              )}
            </span>
          }
        >
          <Input.TextArea
            autoSize={{ minRows: 2, maxRows: 4 }}
            placeholder={copy('例如：电商订单分析，只读数据源', 'e.g. E-commerce orders for business analysis')}
          />
        </Form.Item>
        {feedback ? (
          <Alert
            className={styles.feedback}
            role='status'
            showIcon
            type={feedback.ok ? 'success' : 'error'}
            message={feedback.text}
          />
        ) : null}
      </div>
      <div className={styles.formFooter}>
        <Button
          icon={feedback?.ok ? <CheckCircleOutlined /> : <LinkOutlined />}
          onClick={handleTest}
          loading={busy === 'test'}
          disabled={!selected || !!busy}
        >
          {copy('测试连接', 'Test connection')}
        </Button>
        <div className={styles.footerActions}>
          <Button onClick={onCancel} disabled={!!busy}>
            {copy('取消', 'Cancel')}
          </Button>
          <Button
            className={styles.primary}
            type='primary'
            onClick={handleSave}
            loading={busy === 'save'}
            disabled={!selected || !!busy}
          >
            {copy(editValue ? '保存修改' : '添加数据源', editValue ? 'Save changes' : 'Add data source')}
          </Button>
        </div>
      </div>
    </Form>
  );
}

export default DatabaseForm;
