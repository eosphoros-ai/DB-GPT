import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, uploadFile } from '@/client/api';
import { getTaskflowAgentOptions } from '@/client/api/flow';
import { getDbList, getSpaceList } from '@/client/api/request';
import type { IChatDbSchema } from '@/types/db';
import type { IUploadFileResponse } from '@/types/flow';
import type { ISpace } from '@/types/knowledge';
import type { ITaskflowAgentOptions, ITaskflowConfigField, ITaskflowNode, ITaskflowNodeKind } from '@/types/taskflow';
import { groupColor, missingRequiredFields } from '@/utils/taskflow';
import { CloseOutlined, FileOutlined, UploadOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Input, InputNumber, Select, Switch, Upload, message } from 'antd';
import React, { useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

/** Profile id -> avatar emoji (aligned with docs/design/taskflow-mockups/05). */
const PROFILE_AVATARS: Record<string, string> = {
  react_data: '🧐',
  react_knowledge: '📚',
  react_general: '✍️',
};

/**
 * Right property panel: business-level config only (driven by the node kind
 * manifest). No AWEL internals (type_cls / ui_type / variables) are exposed.
 */
const PropertyPanel: React.FC<{
  node: ITaskflowNode | null;
  spec?: ITaskflowNodeKind;
  onChange: (id: string, patch: { label?: string; config: Record<string, any> }) => void;
}> = ({ node, spec, onChange }) => {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language?.startsWith('zh');
  const { modelList, refreshModelList } = useContext(ChatContext);
  const [uploading, setUploading] = useState(false);

  const { data: dbData } = useRequest(async () => apiInterceptors(getDbList()));
  const { data: agentOptionsData } = useRequest(async () => apiInterceptors(getTaskflowAgentOptions()));
  const agentOptions = useMemo(() => {
    const [, res] = (agentOptionsData as any) ?? [];
    return (res ?? null) as ITaskflowAgentOptions | null;
  }, [agentOptionsData]);
  const { data: spaceData } = useRequest(async () => apiInterceptors(getSpaceList()));
  const dbOptions = useMemo(() => {
    const [, res] = (dbData as any) ?? [];
    const list = (res ?? []) as IChatDbSchema[];
    return list.map(db => ({
      label: `${db.db_name}（${db.db_type}）`,
      value: db.db_name,
    }));
  }, [dbData]);

  const modelOptions = useMemo(() => {
    const list = (modelList ?? []) as any[];
    return list.map(item => {
      const value = typeof item === 'string' ? item : (item?.value ?? item?.label);
      return { label: String(value), value: String(value) };
    });
  }, [modelList]);

  const spaceOptions = useMemo(() => {
    const [, res] = (spaceData as any) ?? [];
    return ((res ?? []) as ISpace[]).map(s => ({ label: s.name, value: s.name }));
  }, [spaceData]);

  if (!node || !spec) {
    return (
      <aside className='w-[300px] flex-none border-l border-gray-100 dark:border-white/10 bg-white dark:bg-[#16171a] p-4'>
        <div className='text-xs text-gray-400'>{t('taskflow_select_node_hint')}</div>
      </aside>
    );
  }

  const { color, bg } = groupColor(spec.group);
  const missing = missingRequiredFields(node, spec);
  const setConfig = (name: string, value: any) => {
    onChange(node.id, { config: { ...node.config, [name]: value } });
  };

  const multiselectOptions = (field: ITaskflowConfigField) => {
    switch (field.name) {
      case 'tools':
        return (agentOptions?.tools ?? []).map(t => ({
          label: isZh ? t.label : t.label_en,
          value: t.id,
        }));
      case 'skills':
        return (agentOptions?.skills ?? []).map(s => ({
          label: s.label || s.name,
          value: s.name,
        }));
      case 'datasources':
        return dbOptions;
      case 'knowledge':
        return spaceOptions;
      default:
        return field.options ?? [];
    }
  };

  /** Checkbox-group options carry per-item descriptions (mockup style). */
  const checkboxOptions = (field: ITaskflowConfigField) => {
    if (field.name === 'tools') {
      return (agentOptions?.tools ?? []).map(t => ({
        value: t.id,
        label: (isZh ? t.label : t.label_en) as string,
        desc: (isZh ? t.desc : t.desc_en) as string | undefined,
      }));
    }
    return multiselectOptions(field).map(o => ({
      value: o.value,
      label: o.label,
      desc: undefined as string | undefined,
    }));
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('files', file);
      const [err, res] = await apiInterceptors(uploadFile(formData as any));
      const uploaded = (res as Array<IUploadFileResponse> | null)?.[0];
      if (err || !uploaded?.file_id) {
        message.error(t('taskflow_upload_failed'));
        return;
      }
      onChange(node.id, {
        config: { ...node.config, file_id: uploaded.file_id, file_name: uploaded.file_name },
      });
      message.success(t('taskflow_upload_success'));
    } finally {
      setUploading(false);
    }
  };

  const renderField = (field: ITaskflowConfigField) => {
    const value = node.config?.[field.name] ?? field.default ?? undefined;
    const label = isZh ? field.label : field.label_en;
    const desc = isZh ? field.desc : field.desc_en;
    const control = (() => {
      switch (field.type) {
        case 'textarea':
          return (
            <Input.TextArea
              value={value}
              placeholder={field.placeholder ?? undefined}
              autoSize={{ minRows: 3, maxRows: 8 }}
              onChange={e => setConfig(field.name, e.target.value)}
            />
          );
        case 'number':
          return (
            <InputNumber
              className='w-full'
              value={value}
              min={0}
              onChange={val => setConfig(field.name, val ?? field.default)}
            />
          );
        case 'switch':
          return <Switch checked={!!value} onChange={val => setConfig(field.name, val)} />;
        case 'select':
          return (
            <Select
              className='w-full'
              value={value}
              options={field.options ?? []}
              onChange={val => setConfig(field.name, val)}
            />
          );
        case 'datasource':
          return (
            <Select
              className='w-full'
              showSearch
              allowClear={!field.required}
              placeholder={field.placeholder ?? undefined}
              value={value}
              options={dbOptions}
              onChange={val => setConfig(field.name, val)}
              status={field.required && !value ? 'error' : undefined}
            />
          );
        case 'model':
          return (
            <Select
              className='w-full'
              showSearch
              allowClear
              placeholder={t('taskflow_model_default') as string}
              value={value}
              options={modelOptions}
              onChange={val => setConfig(field.name, val)}
              onDropdownVisibleChange={open => {
                // The global list is fetched once on app mount; refetch on open
                // so a list captured before the workers registered heals itself.
                if (open) refreshModelList?.();
              }}
            />
          );
        case 'agent_profile': {
          const options = (agentOptions?.profiles ?? []).map(p => ({
            value: p.id,
            label: (isZh ? p.label : p.label_en) as string,
            desc: (isZh ? p.desc : p.desc_en) as string | undefined,
          }));
          return (
            <Select
              className='w-full'
              showSearch
              allowClear
              placeholder={t('taskflow_agent_profile_placeholder') as string}
              value={value}
              options={options}
              onChange={val => setConfig(field.name, val)}
              optionRender={info => {
                const opt = info.data as (typeof options)[number];
                return (
                  <div className='flex items-center gap-2 py-0.5'>
                    <span className='w-6 h-6 rounded-full bg-violet-50 dark:bg-violet-500/15 flex items-center justify-center text-[13px] flex-none'>
                      {PROFILE_AVATARS[opt.value] ?? '🤖'}
                    </span>
                    <span className='min-w-0 flex-1'>
                      <div className='text-[12.5px] leading-tight'>{opt.label}</div>
                      {opt.desc && <div className='text-[10.5px] text-gray-400 leading-tight truncate'>{opt.desc}</div>}
                    </span>
                  </div>
                );
              }}
            />
          );
        }
        case 'checkbox_group': {
          const selected: string[] = Array.isArray(value) ? value : [];
          const toggle = (v: string) =>
            setConfig(field.name, selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v]);
          return (
            <div className='flex flex-col gap-0.5'>
              {checkboxOptions(field).map(opt => {
                const checked = selected.includes(opt.value);
                return (
                  <div
                    key={opt.value}
                    className='flex items-start gap-2 px-1.5 py-1.5 rounded-md hover:bg-gray-50 dark:hover:bg-white/5 cursor-pointer select-none'
                    onClick={() => toggle(opt.value)}
                  >
                    <span
                      className={`w-[15px] h-[15px] mt-[2px] rounded flex items-center justify-center text-[10px] flex-none ${
                        checked
                          ? 'bg-green-600 text-white'
                          : 'border-[1.5px] border-gray-300 dark:border-white/25 bg-white dark:bg-transparent'
                      }`}
                    >
                      {checked ? '✓' : ''}
                    </span>
                    <span className='flex-1 min-w-0 text-[12.5px] text-gray-800 dark:text-gray-200 leading-snug'>
                      {opt.label}
                      {opt.desc && <div className='text-[10.5px] text-gray-400 leading-snug'>{opt.desc}</div>}
                    </span>
                  </div>
                );
              })}
              {checkboxOptions(field).length === 0 && <div className='text-[11px] text-gray-400 px-1.5'>—</div>}
            </div>
          );
        }
        case 'multiselect':
          return (
            <Select
              className='w-full'
              mode='multiple'
              showSearch
              allowClear
              maxTagCount={3}
              placeholder={field.placeholder ?? (t('taskflow_multiselect_placeholder') as string)}
              value={Array.isArray(value) ? value : []}
              options={multiselectOptions(field)}
              onChange={val => setConfig(field.name, val)}
              filterOption={(input, option) =>
                String(option?.label ?? '')
                  .toLowerCase()
                  .includes(input.toLowerCase())
              }
            />
          );
        case 'file': {
          const hasUploaded = !!node.config?.file_id;
          return (
            <div className='flex flex-col gap-1.5'>
              {value && (
                <div className='flex items-center gap-1.5 border border-gray-200 dark:border-white/15 rounded-md px-2 py-1.5 text-[12px] text-gray-700 dark:text-gray-200'>
                  <FileOutlined className='flex-none text-gray-400' />
                  <span className='flex-1 truncate' title={value}>
                    {value}
                  </span>
                  <Button
                    type='text'
                    size='small'
                    className='flex-none'
                    aria-label={t('taskflow_file_clear') as string}
                    icon={<CloseOutlined />}
                    onClick={() =>
                      onChange(node.id, {
                        config: { ...node.config, file_id: undefined, file_name: undefined },
                      })
                    }
                  />
                </div>
              )}
              <Upload
                accept='.csv,.xlsx,.xls'
                showUploadList={false}
                beforeUpload={file => {
                  handleUpload(file);
                  return false;
                }}
              >
                <Button block loading={uploading} icon={<UploadOutlined />}>
                  {uploading ? t('taskflow_uploading') : t('taskflow_upload_file')}
                </Button>
              </Upload>
              {!hasUploaded && (
                <Input
                  value={value}
                  placeholder={field.placeholder ?? undefined}
                  onChange={e =>
                    onChange(node.id, {
                      config: { ...node.config, file_id: undefined, file_name: e.target.value },
                    })
                  }
                  status={field.required && !value ? 'error' : undefined}
                />
              )}
            </div>
          );
        }
        default:
          return (
            <Input
              value={value}
              placeholder={field.placeholder ?? undefined}
              onChange={e => setConfig(field.name, e.target.value)}
              status={field.required && !value ? 'error' : undefined}
            />
          );
      }
    })();
    return (
      <div key={field.name} className='mb-3.5'>
        <div className='text-[12.5px] text-gray-600 dark:text-gray-300 font-medium mb-1'>
          {label}
          {field.required && <span className='text-red-500 ml-0.5'>*</span>}
        </div>
        {control}
        {desc && <div className='text-[10.5px] text-gray-400 mt-1'>{desc}</div>}
      </div>
    );
  };

  return (
    <aside className='w-[300px] flex-none border-l border-gray-100 dark:border-white/10 bg-white dark:bg-[#16171a] overflow-y-auto min-h-0'>
      <div className='px-4 pt-3.5 pb-2.5 border-b border-gray-50 dark:border-white/5'>
        <div className='flex items-center gap-2'>
          <span
            className='w-6 h-6 rounded-md flex items-center justify-center text-[12px] flex-none'
            style={{ background: bg, color }}
          >
            {spec.icon}
          </span>
          <span className='text-[13.5px] font-bold text-gray-800 dark:text-gray-100'>
            {isZh ? spec.label : spec.label_en}
          </span>
        </div>
        <div className='text-[11px] text-gray-400 mt-1'>{isZh ? spec.desc : spec.desc_en}</div>
      </div>

      <div className='px-4 py-3 border-b border-gray-50 dark:border-white/5'>
        <div className='text-[11px] font-semibold text-gray-400 mb-2'>{t('taskflow_basic')}</div>
        <div className='mb-3.5'>
          <div className='text-[12.5px] text-gray-600 dark:text-gray-300 font-medium mb-1'>
            {t('taskflow_node_name')}
          </div>
          <Input
            value={node.label ?? ''}
            placeholder={isZh ? spec.label : spec.label_en}
            onChange={e => onChange(node.id, { label: e.target.value, config: node.config })}
          />
        </div>
        {spec.config_fields.map(renderField)}
        {missing.length > 0 && (
          <div className='text-[11px] text-amber-600 bg-amber-50 dark:bg-amber-500/10 rounded-md px-2.5 py-1.5'>
            {t('taskflow_required_config_missing')}: {missing.join(', ')}
          </div>
        )}
      </div>

      <div className='px-4 py-3'>
        <div className='text-[11px] font-semibold text-gray-400 mb-2'>{t('taskflow_io')}</div>
        <div className='border border-dashed border-gray-200 dark:border-white/15 rounded-md px-2.5 py-1.5 text-[11.5px] text-gray-500 dark:text-gray-300 mb-1.5'>
          <span className='font-semibold text-gray-700 dark:text-gray-200 mr-1.5'>{t('taskflow_inputs')}</span>
          {isZh ? spec.inputs_desc || '—' : spec.inputs_desc_en || '—'}
        </div>
        <div className='border border-dashed border-gray-200 dark:border-white/15 rounded-md px-2.5 py-1.5 text-[11.5px] text-gray-500 dark:text-gray-300'>
          <span className='font-semibold text-gray-700 dark:text-gray-200 mr-1.5'>{t('taskflow_outputs')}</span>
          {isZh ? spec.outputs_desc || '—' : spec.outputs_desc_en || '—'}
        </div>
      </div>
    </aside>
  );
};

export default PropertyPanel;
