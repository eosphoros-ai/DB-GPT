/**
 * Knowledge source panel: binding cards + create wizard + sync logs.
 */
import {
  apiInterceptors,
  deleteSourceBinding,
  listSourceBindings,
  listSourceLogs,
  pauseSourceBinding,
  resumeSourceBinding,
  triggerSourceSync,
} from '@/client/api';
import { KsSourceBinding, KsSyncLog } from '@/types/knowledgeSource';
import { DeleteOutlined, PlusOutlined, SyncOutlined } from '@ant-design/icons';
import { Badge, Button, Drawer, Empty, Modal, Spin, Table, Tag, message } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BindingWizard } from './binding-wizard';

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  paused: 'default',
  running: 'blue',
  error: 'red',
};

export default function SourcePanel({ spaceId, spaceName }: { spaceId: string | number; spaceName?: string }) {
  const { t } = useTranslation();
  const [bindings, setBindings] = useState<KsSourceBinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [logSource, setLogSource] = useState<KsSourceBinding | null>(null);

  const loadBindings = useCallback(async () => {
    setLoading(true);
    const [, data] = await apiInterceptors(listSourceBindings(spaceId));
    setBindings(data || []);
    setLoading(false);
  }, [spaceId]);

  useEffect(() => {
    if (spaceId) loadBindings();
  }, [spaceId, loadBindings]);

  const handleSync = async (binding: KsSourceBinding) => {
    const [, summary] = await apiInterceptors(triggerSourceSync(spaceId, binding.id));
    if (summary) {
      message.success(
        t('ks_sync_done', {
          created: summary.items_created,
          updated: summary.items_updated,
          failed: summary.items_failed,
        }),
      );
    }
    loadBindings();
  };

  const handleTogglePause = async (binding: KsSourceBinding) => {
    if (binding.status === 'paused') {
      await apiInterceptors(resumeSourceBinding(spaceId, binding.id));
    } else {
      await apiInterceptors(pauseSourceBinding(spaceId, binding.id));
    }
    loadBindings();
  };

  const handleDelete = (binding: KsSourceBinding) => {
    Modal.confirm({
      title: t('ks_delete_confirm'),
      content: t('ks_delete_confirm_desc'),
      onOk: async () => {
        await apiInterceptors(deleteSourceBinding(spaceId, binding.id));
        message.success(t('ks_deleted'));
        loadBindings();
      },
    });
  };

  return (
    <div className='h-full overflow-auto p-4 bg-white dark:bg-[#232734]'>
      <div className='flex items-center mb-4'>
        <span className='text-base font-semibold text-gray-800 dark:text-gray-200'>{t('ks_panel_title')}</span>
        <Button type='primary' icon={<PlusOutlined />} className='ml-auto' onClick={() => setWizardOpen(true)}>
          {t('ks_add_binding')}
        </Button>
      </div>

      {loading ? (
        <div className='flex justify-center py-10'>
          <Spin />
        </div>
      ) : bindings.length === 0 ? (
        <Empty description={t('ks_empty_hint')} className='mt-10' />
      ) : (
        <div className='grid grid-cols-1 xl:grid-cols-2 gap-3'>
          {bindings.map(binding => (
            <div key={binding.id} className='rounded-xl border border-gray-200 dark:border-gray-700 p-4'>
              <div className='flex items-center gap-2'>
                <span className='font-semibold text-gray-800 dark:text-gray-100'>{binding.name}</span>
                <Tag color='geekblue'>{binding.type}</Tag>
                <Badge
                  status={binding.status === 'error' ? 'error' : 'processing'}
                  text={
                    <Tag color={STATUS_COLORS[binding.status] || 'default'}>{t(`ks_status_${binding.status}`)}</Tag>
                  }
                />
                <span className='ml-auto text-xs text-gray-400'>
                  {binding.last_sync_at ? new Date(binding.last_sync_at).toLocaleString() : t('ks_never_synced')}
                </span>
              </div>
              {binding.error_message && (
                <div className='mt-1 text-xs text-red-500 break-all'>{binding.error_message}</div>
              )}
              <div className='mt-2 text-xs text-gray-400 flex gap-3'>
                <span>{t('ks_mode_' + binding.sync_mode)}</span>
                <span>{t('ks_conflict_' + binding.conflict_strategy)}</span>
                <span>
                  {binding.interval_minutes > 0
                    ? t('ks_every_n_minutes', { n: binding.interval_minutes })
                    : t('ks_manual_only')}
                </span>
                <span>{t('ks_targets', { n: binding.target_resource_ids.length })}</span>
              </div>
              {binding.error_message ? (
                <div className='mt-2 text-xs text-red-500 break-all'>{binding.error_message}</div>
              ) : null}
              <div className='mt-3 flex gap-2'>
                <Button size='small' type='primary' ghost icon={<SyncOutlined />} onClick={() => handleSync(binding)}>
                  {t('ks_sync_now')}
                </Button>
                <Button size='small' onClick={() => handleTogglePause(binding)}>
                  {binding.status === 'paused' ? t('ks_resume') : t('ks_pause')}
                </Button>
                <Button size='small' onClick={() => setLogSource(binding)}>
                  {t('ks_logs')}
                </Button>
                <Button
                  size='small'
                  danger
                  icon={<DeleteOutlined />}
                  className='ml-auto'
                  onClick={() => handleDelete(binding)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      <BindingWizard
        open={wizardOpen}
        spaceId={spaceId}
        spaceName={spaceName}
        onClose={() => setWizardOpen(false)}
        onCreated={() => {
          setWizardOpen(false);
          loadBindings();
        }}
      />

      <SyncLogDrawer binding={logSource} onClose={() => setLogSource(null)} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sync logs drawer                                                    */
/* ------------------------------------------------------------------ */
function SyncLogDrawer({ binding, onClose }: { binding: KsSourceBinding | null; onClose: () => void }) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState<KsSyncLog[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!binding) return;
    setLoading(true);
    (async () => {
      const [, data] = await apiInterceptors(listSourceLogs(binding.space_id, binding.id));
      setLogs(data || []);
      setLoading(false);
    })();
  }, [binding]);

  return (
    <Drawer
      title={`${t('ks_logs')} · ${binding?.name || ''}`}
      open={!!binding}
      width={620}
      onClose={onClose}
      destroyOnClose
    >
      {loading ? (
        <Spin className='flex justify-center py-6' />
      ) : (
        <Table
          rowKey='id'
          size='small'
          dataSource={logs}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: t('ks_log_time'), dataIndex: 'started_at', width: 150 },
            { title: t('ks_log_trigger'), dataIndex: 'trigger', width: 90 },
            {
              title: t('ks_log_status'),
              dataIndex: 'status',
              width: 90,
              render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v}</Tag>,
            },
            { title: '+', dataIndex: 'items_created', width: 50 },
            { title: '~', dataIndex: 'items_updated', width: 50 },
            { title: '=', dataIndex: 'items_skipped', width: 50 },
            { title: '✗', dataIndex: 'items_failed', width: 50 },
            { title: '🗑', dataIndex: 'items_deleted', width: 50 },
          ]}
          expandable={{
            rowExpandable: record => !!record.error,
            expandedRowRender: record => <div className='text-xs text-red-500 whitespace-pre-wrap'>{record.error}</div>,
          }}
        />
      )}
    </Drawer>
  );
}
