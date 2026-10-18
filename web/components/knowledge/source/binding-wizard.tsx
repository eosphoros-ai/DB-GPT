/**
 * Binding wizard: pick type → credentials → scope → sync strategy.
 * Embeddable: set `embedded` and the host decides the chrome.
 */
import {
  addDocument,
  apiInterceptors,
  createSourceBinding,
  listConnectorTypes,
  listSourceResources,
  syncBatchDocument,
  triggerSourceSync,
  updateSourceBinding,
  uploadDocument,
} from '@/client/api';
import { KsConnectorMeta } from '@/types/knowledgeSource';
import { DownOutlined, FileAddOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Checkbox, Empty, Form, Input, Modal, Radio, Select, Spin, Steps, Tree, Upload, message } from 'antd';
import type { RcFile } from 'antd/es/upload/interface';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Dragger } = Upload;

/** Row labels never render a raw scheme:// URL (defense in depth — the
 * connector already returns friendly titles). */
function friendlyRowTitle(raw: string): string {
  return raw.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

/** Brand icons per connector type, ported from WeKnora's datasource assets. */
const FEISHU_PATH =
  'M41.0716 5.99409L3.31071 16.5187L12.3856 25.8126L20.7998 25.9594L30.4827 16.5187C30.2266 15.9943 30.0985 15.5552 30.0985 15.2013C30.0985 14.4074 30.4104 13.7786 30.8947 13.333C31.7241 12.57 32.7222 12.4558 33.8889 12.9905L41.0716 5.99409ZM42.1021 6.72842L31.5775 44.4893L22.2836 35.4144L22.1367 27.0002L31.5115 17.4816C32.0195 17.8454 32.5743 18.0105 33.1759 17.9769C34.0784 17.9264 34.6614 17.3813 34.9349 17.0602C35.2083 16.7392 35.5293 16.2051 35.5025 15.4113C35.4847 14.8821 35.3109 14.3941 34.9812 13.9472L42.1021 6.72842Z';

export function KsTypeIcon({ type }: { type: string }) {
  if (type.startsWith('feishu') || type.startsWith('lark')) {
    return (
      <svg width='28' height='28' viewBox='0 0 48 48' fill='#3370ff' className='flex-none'>
        <path d={FEISHU_PATH} />
      </svg>
    );
  }
  if (type === 'rss') {
    return (
      <svg width='28' height='28' viewBox='0 0 48 48' className='flex-none' aria-label='RSS'>
        <circle cx='14' cy='34' r='4' fill='#FF6600' />
        <path d='M10 22a18 18 0 0 1 18 18' fill='none' stroke='#FF6600' strokeWidth='4' strokeLinecap='round' />
        <path d='M10 14a26 26 0 0 1 26 26' fill='none' stroke='#FF6600' strokeWidth='4' strokeLinecap='round' />
      </svg>
    );
  }
  if (type === 'yuque') {
    // brand asset ported from WeKnora (datasource-yuque.ico, 96x96 png)
    return <img src='/pictures/ks/yuque.png' width='28' height='28' className='flex-none rounded-md' alt='yuque' />;
  }
  if (type === 'dingtalk') {
    // brand asset ported from WeKnora (im/dingtalk.svg); connector ships
    // with task #13 — icon reserved here
    return <img src='/pictures/ks/dingtalk.svg' width='28' height='28' className='flex-none' alt='dingtalk' />;
  }
  return null;
}

export {}; // keep module shape stable when tree-shaken

export function BindingWizard({
  open,
  spaceId,
  spaceName,
  onClose,
  onCreated,
  embedded,
  initialType,
}: {
  open: boolean;
  spaceId: string | number;
  onClose: () => void;
  onCreated: () => void;
  /** when embedded, render content only (host provides the chrome/stepper context) */
  embedded?: boolean;
  /** pre-selected connector (space creation already picked one) — skips step 1 */
  initialType?: string;
  /** space name — required for the builtin (local/text) ingest flows */
  spaceName?: string;
}) {
  const { t } = useTranslation();
  const [metas, setMetas] = useState<Record<string, KsConnectorMeta>>({});
  const [step, setStep] = useState<0 | 1 | 2 | 3>(0);
  const [chosenType, setChosenType] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [checkedKeys, setCheckedKeys] = useState<string[]>([]);
  const [resourceSaving, setResourceSaving] = useState(false);
  const [form] = Form.useForm();
  const [authLoading, setAuthLoading] = useState(false);
  const [metaError, setMetaError] = useState(false);
  const [localFiles, setLocalFiles] = useState<RcFile[]>([]);
  const [localUploading, setLocalUploading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(initialType ? 1 : 0);
    setChosenType(initialType || null);
    setCreatedId(null);
    setCheckedKeys([]);
    form.resetFields();
    setMetaError(false);
    (async () => {
      const [err, data] = await apiInterceptors(listConnectorTypes());
      if (err || !data || Object.keys(data).length === 0) {
        setMetaError(true);
        return;
      }
      setMetas(data);
    })();
  }, [open, form, initialType]);

  const meta = chosenType ? metas[chosenType] : null;

  const handleValidateAndCreate = async () => {
    const values = await form.validateFields();
    if (!chosenType) return;
    setAuthLoading(true);
    const [err, binding] = await apiInterceptors(
      createSourceBinding(spaceId, {
        name: values.name || metas[chosenType]?.name,
        type: chosenType,
        config: values.config || {},
        target_resource_ids: [],
        interval_minutes: 0,
        sync_mode: 'incremental',
        conflict_strategy: 'overwrite',
        sync_deletions: false,
      }),
    );
    setAuthLoading(false);
    if (err || !binding) return;
    setCreatedId(binding.id);
    setStep(2);
  };

  const handleFinishWithResources = async () => {
    if (!createdId) return;
    setResourceSaving(true);
    const [updateErr] = await apiInterceptors(
      updateSourceBinding(spaceId, createdId, {
        target_resource_ids: checkedKeys,
        interval_minutes: form.getFieldValue('interval_minutes') || 0,
        sync_mode: form.getFieldValue('sync_mode') || 'incremental',
        conflict_strategy: form.getFieldValue('conflict_strategy') || 'overwrite',
        sync_deletions: !!form.getFieldValue('sync_deletions'),
      }),
    );
    setResourceSaving(false);
    if (updateErr || checkedKeys.length === 0) {
      message.success(t('ks_created'));
      onCreated();
      return;
    }
    // kick off the first fetch immediately so content shows up right away
    const [syncErr, summary] = await apiInterceptors(triggerSourceSync(spaceId, createdId));
    if (syncErr || !summary) {
      message.success(t('ks_created'));
    } else {
      message.success(
        t('ks_first_sync_started', {
          created: summary.items_created,
          updated: summary.items_updated,
          failed: summary.items_failed,
        }),
      );
    }
    onCreated();
  };

  const builtinNeedsSpaceName = chosenType?.startsWith('builtin:') && !spaceName;

  const content = (
    <div>
      <div className='flex items-center mb-2'>
        {embedded ? (
          <div className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{t('ks_wizard_title')}</div>
        ) : null}
        {embedded && onClose ? (
          <Button size='small' type='link' className='ml-auto' onClick={onClose}>
            {t('ks_skip_bind')}
          </Button>
        ) : null}
      </div>
      <Steps
        size='small'
        className='mb-4 mt-1'
        current={step}
        items={[
          { title: t('ks_step_type') },
          {
            title: chosenType?.startsWith('builtin:') ? t('ks_builtin_content_step') : t('ks_step_credentials'),
          },
          {
            title: t('ks_step_scope'),
            disabled: !!chosenType?.startsWith('builtin:'),
          },
          {
            title: t('ks_step_strategy'),
            disabled: !!chosenType?.startsWith('builtin:'),
          },
        ]}
      />

      {/* Step 0: pick entry — builtin ingest first, then external connectors */}
      {step === 0 && (
        <div className='grid grid-cols-3 gap-3 py-2'>
          <div className='col-span-full text-xs text-gray-400'>{t('ks_builtin_section')}</div>
          <div
            data-testid='builtin-local'
            onClick={() => {
              setChosenType('builtin:local');
              setStep(1);
            }}
            className='cursor-pointer rounded-xl border-2 border-transparent p-4 hover:border-blue-400 transition-all flex items-center gap-3'
          >
            <div className='flex-none w-7 h-7 rounded-md bg-blue-50 dark:bg-blue-900/40 text-blue-500 flex items-center justify-center'>
              <FileAddOutlined />
            </div>
            <div>
              <div className='text-sm font-semibold'>{t('ks_builtin_local')}</div>
              <div className='text-xs text-gray-400 mt-1 line-clamp-2'>{t('ks_builtin_local_desc')}</div>
            </div>
          </div>
          <div
            data-testid='builtin-text'
            onClick={() => {
              setChosenType('builtin:text');
              setStep(1);
            }}
            className='cursor-pointer rounded-xl border-2 border-transparent p-4 hover:border-blue-400 transition-all flex items-center gap-3'
          >
            <div className='flex-none w-7 h-7 rounded-md bg-orange-50 dark:bg-orange-900/40 text-orange-500 flex items-center justify-center'>
              <FileTextOutlined />
            </div>
            <div>
              <div className='text-sm font-semibold'>{t('ks_builtin_text')}</div>
              <div className='text-xs text-gray-400 mt-1 line-clamp-2'>{t('ks_builtin_text_desc')}</div>
            </div>
          </div>
          <div className='col-span-full text-xs text-gray-400'>{t('ks_external_section')}</div>
          {Object.entries(metas).map(([type, m]) => (
            <div
              key={type}
              onClick={() => {
                setChosenType(type);
                setStep(1);
              }}
              className='cursor-pointer rounded-xl border-2 border-transparent p-4 hover:border-blue-400 transition-all flex items-center gap-3'
            >
              <KsTypeIcon type={type} />
              <div>
                <div className='text-sm font-semibold'>{t(`ks_type_name_${type}`, m.name)}</div>
                <div className='text-xs text-gray-400 mt-1 line-clamp-2'>{m.description}</div>
              </div>
            </div>
          ))}
          {Object.keys(metas).length === 0 && !metaError && (
            <div className='col-span-3 flex justify-center py-6'>
              <Spin />
            </div>
          )}
          {metaError && (
            <div className='col-span-3 py-6 flex flex-col items-center gap-3'>
              <Empty description={t('ks_types_load_failed')} />
              <Button size='small' icon={<ReloadOutlined />} onClick={() => setStep(0)}>
                {t('ks_retry')}
              </Button>
            </div>
          )}
        </div>
      )}

      {builtinNeedsSpaceName && <div className='mb-3 text-xs text-red-500'>{t('ks_space_name_required')}</div>}

      {/* Step 1b: builtin — local documents upload */}
      {step === 1 && chosenType === 'builtin:local' && (
        <div className='py-2'>
          <Dragger
            multiple
            fileList={localFiles as any}
            beforeUpload={file => {
              setLocalFiles(prev => [...prev, file as RcFile]);
              return false;
            }}
            onRemove={file => setLocalFiles(prev => prev.filter(f => f.uid !== (file as any).uid))}
            accept='.pdf,.ppt,.pptx,.xls,.xlsx,.doc,.docx,.txt,.md,.zip,.csv'
          >
            <p className='ant-upload-text text-sm text-gray-500 dark:text-gray-400'>{t('ks_local_drag')}</p>
            <p className='ant-upload-hint text-xs text-gray-400'>PDF, PPT, Excel, Word, Text, Markdown, CSV</p>
          </Dragger>
          <div className='flex justify-end gap-2 mt-3'>
            <Button onClick={() => setStep(0)}>{t('ks_back')}</Button>
            <Button
              type='primary'
              disabled={localFiles.length === 0 || !spaceName}
              loading={localUploading}
              onClick={async () => {
                if (!spaceName) return;
                setLocalUploading(true);
                const uploaded: Array<{ doc_id: number; name: string }> = [];
                for (const file of localFiles) {
                  const fd = new FormData();
                  fd.append('doc_name', file.name);
                  fd.append('doc_file', file);
                  fd.append('doc_type', 'DOCUMENT');
                  const [, docId] = await apiInterceptors(uploadDocument(spaceName, fd));
                  if (docId) uploaded.push({ doc_id: Number(docId), name: file.name });
                }
                if (uploaded.length > 0) {
                  await apiInterceptors(
                    syncBatchDocument(
                      spaceName,
                      uploaded.map(f => ({
                        doc_id: f.doc_id,
                        name: f.name,
                        chunk_parameters: { chunk_strategy: 'Automatic' },
                      })),
                    ),
                  );
                }
                setLocalUploading(false);
                setLocalFiles([]);
                message.success(t('ks_builtin_done', { n: uploaded.length }));
                onCreated();
              }}
            >
              {t('ks_builtin_finish')}
            </Button>
          </div>
        </div>
      )}

      {/* Step 1c: builtin — text snippet */}
      {step === 1 && chosenType === 'builtin:text' && (
        <Form form={form} layout='vertical' className='pt-2'>
          <Form.Item
            label={t('ks_text_name_label')}
            name='text_name'
            rules={[{ required: true, message: t('ks_text_name_label') }]}
          >
            <Input placeholder={t('ks_text_name_label')} />
          </Form.Item>
          <Form.Item
            label={t('ks_text_content_label')}
            name='text_content'
            rules={[{ required: true, message: t('ks_text_content_label') }]}
          >
            <Input.TextArea rows={8} placeholder={t('ks_text_content_placeholder')} />
          </Form.Item>
          <div className='flex justify-end gap-2'>
            <Button onClick={() => setStep(0)}>{t('ks_back')}</Button>
            <Button
              type='primary'
              loading={authLoading}
              onClick={async () => {
                const values = await form.validateFields();
                if (!spaceName) return;
                setAuthLoading(true);
                const [, docId] = await apiInterceptors(
                  addDocument(spaceName, {
                    doc_name: values.text_name,
                    content: values.text_content,
                    doc_type: 'TEXT',
                    questions: [],
                  } as any),
                );
                if (docId) {
                  await apiInterceptors(
                    syncBatchDocument(spaceName, [
                      {
                        doc_id: Number(docId),
                        name: values.text_name,
                        chunk_parameters: { chunk_strategy: 'Automatic' },
                      },
                    ]),
                  );
                }
                setAuthLoading(false);
                message.success(t('ks_builtin_done', { n: docId ? 1 : 0 }));
                onCreated();
              }}
            >
              {t('ks_builtin_finish')}
            </Button>
          </div>
        </Form>
      )}

      {/* Step 1: credentials form (auth_fields) */}
      {step === 1 && meta && (
        <Form form={form} layout='vertical' className='pt-2'>
          <Form.Item label={t('ks_binding_name')} name='name' initialValue={meta.name}>
            <Input />
          </Form.Item>
          {meta.auth_fields.map(field => (
            <Form.Item
              key={field.key}
              name={['config', field.key]}
              label={field.label}
              rules={field.required ? [{ required: true, message: field.label }] : []}
              extra={field.hint}
            >
              <Input.Password visibilityToggle={!!field.secret} placeholder={field.placeholder} />
            </Form.Item>
          ))}
          <div className='flex justify-end gap-2'>
            <Button onClick={() => setStep(0)}>{t('ks_back')}</Button>
            <Button type='primary' loading={authLoading} onClick={handleValidateAndCreate}>
              {t('ks_next')}
            </Button>
          </div>
        </Form>
      )}

      {/* Step 2: scope (resource tree) */}
      {step === 2 && createdId && (
        <div className='py-2'>
          <div className='text-sm font-semibold mb-2'>{t('ks_pick_resources')}</div>
          <div className='border rounded-lg p-2 max-h-64 overflow-auto mb-4'>
            <KsResourceTree
              spaceId={spaceId}
              sourceId={createdId}
              checkedKeys={checkedKeys}
              onCheck={keys => setCheckedKeys(keys as string[])}
            />
          </div>
          <div className='flex justify-end gap-2'>
            <Button onClick={() => setStep(1)}>{t('ks_back')}</Button>
            <Button type='primary' onClick={() => setStep(3)}>
              {t('ks_next')}
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: sync strategy */}
      {step === 3 && createdId && (
        <div className='py-2'>
          <Form form={form} layout='vertical'>
            <div className='grid grid-cols-3 gap-3'>
              <Form.Item label={t('ks_schedule')} name='interval_minutes' initialValue={60}>
                <Select
                  options={[
                    { value: 0, label: t('ks_manual_only') },
                    { value: 15, label: t('ks_every_n_minutes', { n: 15 }) },
                    { value: 60, label: t('ks_every_n_minutes', { n: 60 }) },
                    { value: 1440, label: t('ks_every_n_minutes', { n: 1440 }) },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t('ks_sync_mode')} name='sync_mode' initialValue='incremental'>
                <Radio.Group>
                  <Radio value='incremental'>{t('ks_mode_incremental')}</Radio>
                  <Radio value='full'>{t('ks_mode_full')}</Radio>
                </Radio.Group>
              </Form.Item>
              <Form.Item label={t('ks_conflict')} name='conflict_strategy' initialValue='overwrite'>
                <Select
                  options={[
                    { value: 'overwrite', label: t('ks_conflict_overwrite') },
                    { value: 'skip', label: t('ks_conflict_skip') },
                  ]}
                />
              </Form.Item>
            </div>
            <Form.Item name='sync_deletions' valuePropName='checked'>
              <Checkbox>{t('ks_sync_deletions')}</Checkbox>
            </Form.Item>
          </Form>
          <div className='flex justify-end items-center gap-2'>
            <span className='text-xs text-gray-400 mr-auto'>{t('ks_checked_count', { n: checkedKeys.length })}</span>
            <Button onClick={() => setStep(2)}>{t('ks_back')}</Button>
            {resourceSaving ? (
              <Spin />
            ) : (
              <Button type='primary' onClick={handleFinishWithResources}>
                {t('ks_finish')}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
  if (embedded) return open ? <div className='px-1'>{content}</div> : null;
  return (
    <Modal title={t('ks_wizard_title')} open={open} onCancel={onClose} width={720} footer={null} destroyOnClose>
      {content}
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Lazy resource tree                                                  */
/* ------------------------------------------------------------------ */
export function KsResourceTree({
  spaceId,
  sourceId,
  checkedKeys,
  onCheck,
}: {
  spaceId: string | number;
  sourceId: number;
  checkedKeys: string[];
  onCheck: (keys: any) => void;
}) {
  const { t } = useTranslation();
  const [treeData, setTreeData] = useState<any[]>([]);

  const onLoadData = async (node: any): Promise<void> => {
    if (node.children) return;
    const [, data] = await apiInterceptors(listSourceResources(spaceId, sourceId, node.key));
    const children = (data || []).map(r => ({
      key: r.external_id,
      title: r.title,
      isLeaf: !r.has_children,
    }));
    setTreeData(prev => prev.map(n => (n.key === node.key ? { ...n, children } : n)));
  };

  useEffect(() => {
    (async () => {
      const [, data] = await apiInterceptors(listSourceResources(spaceId, sourceId, ''));
      setTreeData(
        (data || []).map(r => ({
          key: r.external_id,
          title: friendlyRowTitle(r.title),
          isLeaf: !r.has_children,
        })),
      );
    })();
  }, [spaceId, sourceId]);

  if (!treeData.length) {
    return <div className='text-xs text-gray-400 py-4 text-center'>{t('ks_no_resources')}</div>;
  }
  return (
    <Tree
      checkable
      showLine={{ showLeafIcon: false }}
      switcherIcon={<DownOutlined />}
      loadData={onLoadData}
      treeData={treeData}
      checkedKeys={checkedKeys}
      onCheck={onCheck}
    />
  );
}
