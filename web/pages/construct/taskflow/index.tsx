import i18n from '@/app/i18n';
import { apiInterceptors, deleteFlowById, getFlows, getFlowTemplates, getTaskflowNodeKinds } from '@/client/api';
import MyEmpty from '@/components/common/MyEmpty';
import FlowChainPreview from '@/components/taskflow/FlowChainPreview';
import ConstructLayout from '@/new-components/layout/Construct';
import type { IFlow } from '@/types/flow';
import type { ITaskflowNodeKind, ITaskflowRef } from '@/types/taskflow';
import { flowToRef, resolveFlowUid, templateToRef } from '@/utils/taskflow';
import {
  ApartmentOutlined,
  DeleteOutlined,
  EditOutlined,
  ImportOutlined,
  MoreOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Dropdown, Input, message, Popconfirm, Spin, Tag } from 'antd';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type TabKey = 'all' | 'templates' | 'mine';

function TaskflowCard({
  item,
  manifest,
  onRun,
  onEdit,
  onDelete,
  onCopy,
}: {
  item: ITaskflowRef & { state?: string; gmt_modified?: string };
  manifest: ITaskflowNodeKind[] | null;
  onRun: (item: ITaskflowRef) => void;
  onEdit?: (item: ITaskflowRef) => void;
  onDelete?: (item: ITaskflowRef) => void;
  onCopy?: (item: ITaskflowRef) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className='group bg-white dark:bg-[#1b1c1f] border border-gray-100 dark:border-white/10 rounded-2xl p-4 flex flex-col gap-3 hover:shadow-md hover:border-gray-200 dark:hover:border-white/20 transition-all'>
      <div className='flex items-start gap-3'>
        <div className='w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center text-lg flex-none'>
          <ApartmentOutlined />
        </div>
        <div className='min-w-0 flex-1'>
          <div className='flex items-center gap-2'>
            <span className='font-semibold text-[15px] text-gray-900 dark:text-gray-100 truncate'>{item.label}</span>
            {item.isTemplate ? (
              <Tag color='blue' className='!text-[10px] !leading-4 !px-1.5'>
                {t('taskflow_builtin')}
              </Tag>
            ) : item.state === 'running' || item.state === 'deployed' ? (
              <Tag color='green' className='!text-[10px] !leading-4 !px-1.5'>
                {t('taskflow_published')}
              </Tag>
            ) : (
              <Tag color='orange' className='!text-[10px] !leading-4 !px-1.5'>
                {t('taskflow_draft')}
              </Tag>
            )}
          </div>
          <p className='text-xs text-gray-400 mt-0.5 line-clamp-2 min-h-[2rem]'>{item.description}</p>
        </div>
        {(onDelete || onCopy) && (
          <Dropdown
            menu={{
              items: [
                onCopy
                  ? {
                      key: 'copy',
                      label: t('taskflow_edit_copy'),
                      icon: <EditOutlined />,
                      onClick: () => onCopy(item),
                    }
                  : null,
                onDelete
                  ? {
                      key: 'delete',
                      label: (
                        <Popconfirm
                          title={t('taskflow_delete_confirm')}
                          onConfirm={() => onDelete(item)}
                          okText={t('taskflow_delete')}
                          cancelText={t('cancel')}
                        >
                          <span className='text-red-500'>{t('taskflow_delete')}</span>
                        </Popconfirm>
                      ),
                      icon: <DeleteOutlined className='text-red-500' />,
                    }
                  : null,
              ].filter(Boolean) as any[],
            }}
          >
            <Button type='text' size='small' icon={<MoreOutlined />} className='text-gray-400' />
          </Dropdown>
        )}
      </div>
      <FlowChainPreview dsl={item.taskflow_source} manifest={manifest} />
      <div className='flex items-center gap-2 border-t border-gray-50 dark:border-white/5 pt-3'>
        {item.gmt_modified && <span className='text-[11px] text-gray-400'>{moment(item.gmt_modified).fromNow()}</span>}
        <span className='flex-1' />
        {onEdit && (
          <Button size='small' onClick={() => onEdit(item)}>
            {item.isTemplate ? t('taskflow_edit_copy') : t('taskflow_edit')}
          </Button>
        )}
        <Button size='small' type='primary' icon={<PlayCircleOutlined />} onClick={() => onRun(item)}>
          {t('taskflow_run')}
        </Button>
      </div>
    </div>
  );
}

function TaskflowList() {
  const router = useRouter();
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabKey>('all');
  const [keyword, setKeyword] = useState('');
  const [templates, setTemplates] = useState<ITaskflowRef[]>([]);
  const [myFlows, setMyFlows] = useState<Array<ITaskflowRef & { state?: string; gmt_modified?: string }>>([]);

  const { data: manifestData } = useRequest(async () => apiInterceptors(getTaskflowNodeKinds()));
  const manifest = useMemo(() => {
    const [, data] = (manifestData as any) ?? [];
    return (data as ITaskflowNodeKind[] | null) ?? null;
  }, [manifestData]);

  const { loading: loadingTemplates } = useRequest(async () => apiInterceptors(getFlowTemplates()), {
    // Template cards ship per-language; refetch when the UI locale flips.
    refreshDeps: [i18n.language],
    onSuccess: data => {
      const [, res] = (data as any) ?? [];
      const items = (res?.items ?? []).map(templateToRef).filter(Boolean) as ITaskflowRef[];
      setTemplates(items);
    },
  });

  const { loading: loadingFlows, run: reloadFlows } = useRequest(
    async () => apiInterceptors(getFlows({ page: 1, page_size: 100 })),
    {
      onSuccess: data => {
        const [, res] = (data as any) ?? [];
        const items = ((res?.items ?? []) as IFlow[])
          .map(flow => {
            const ref = flowToRef(flow);
            return ref ? { ...ref, state: flow.state, gmt_modified: flow.gmt_modified } : null;
          })
          .filter(Boolean) as Array<ITaskflowRef & { state?: string; gmt_modified?: string }>;
        setMyFlows(items);
      },
    },
  );

  const filtered = (items: typeof myFlows) =>
    items.filter(
      item =>
        !keyword ||
        item.label?.toLowerCase().includes(keyword.toLowerCase()) ||
        item.description?.toLowerCase().includes(keyword.toLowerCase()),
    );

  const handleRun = async (item: ITaskflowRef) => {
    const uid = await resolveFlowUid(item);
    if (!uid) {
      message.error(t('error_occurred') || 'Failed to prepare flow');
      return;
    }
    router.push({ pathname: '/', query: { flow: uid } });
  };

  const handleEdit = (item: ITaskflowRef) => {
    if (item.uid) {
      router.push({ pathname: '/taskflow/editor', query: { id: item.uid } });
    } else {
      router.push({ pathname: '/taskflow/editor', query: { template: item.name } });
    }
  };

  const handleDelete = async (item: ITaskflowRef) => {
    if (!item.uid) return;
    const [err] = await apiInterceptors(deleteFlowById(item.uid));
    if (err) {
      message.error(String(err));
      return;
    }
    message.success(t('taskflow_delete_success'));
    reloadFlows();
  };

  const handleCopy = async (item: ITaskflowRef) => {
    message.success(t('taskflow_copy_success'));
    router.push({ pathname: '/taskflow/editor', query: { template: item.name } });
  };

  const showTemplates = tab === 'all' || tab === 'templates';
  const showMine = tab === 'all' || tab === 'mine';
  const loading = loadingTemplates || loadingFlows;

  return (
    <div className='flex-1 overflow-y-auto px-8 py-6 bg-gray-50/60 dark:bg-transparent min-h-0'>
      <div className='flex items-end gap-4 mb-5'>
        <div>
          <h2 className='text-xl font-bold text-gray-900 dark:text-gray-100'>{t('taskflow')}</h2>
          <p className='text-xs text-gray-400 mt-1'>{t('taskflow_select_flow_desc')}</p>
        </div>
        <div className='ml-auto flex items-center gap-2'>
          <Button icon={<ImportOutlined />} onClick={() => router.push('/taskflow/editor?import=1')}>
            {t('taskflow_import')}
          </Button>
          <Button type='primary' icon={<PlusOutlined />} onClick={() => router.push('/taskflow/editor')}>
            {t('taskflow_new')}
          </Button>
        </div>
      </div>

      <div className='flex items-center gap-3 mb-4'>
        <div className='flex bg-gray-100 dark:bg-white/5 rounded-lg p-0.5'>
          {(
            [
              ['all', t('taskflow_all')],
              ['templates', t('taskflow_templates')],
              ['mine', t('taskflow_my_flows')],
            ] as Array<[TabKey, string]>
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-3.5 py-1.5 text-xs rounded-md transition-colors ${
                tab === key
                  ? 'bg-white dark:bg-white/15 text-gray-900 dark:text-gray-100 font-semibold shadow-sm'
                  : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <Input
          allowClear
          prefix={<SearchOutlined className='text-gray-300' />}
          placeholder={t('taskflow_search_placeholder')}
          className='!w-64 ml-auto'
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
        />
      </div>

      <Spin spinning={loading}>
        {showTemplates && filtered(templates as any).length > 0 && (
          <>
            <div className='text-xs font-semibold text-gray-500 mb-3 mt-2 flex items-center gap-3'>
              {t('taskflow_templates')}
              <span className='flex-1 h-px bg-gray-100 dark:bg-white/5' />
            </div>
            <div className='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-6'>
              {filtered(templates as any).map(item => (
                <TaskflowCard
                  key={item.name}
                  item={item}
                  manifest={manifest}
                  onRun={handleRun}
                  onEdit={handleEdit}
                  onCopy={handleCopy}
                />
              ))}
            </div>
          </>
        )}

        {showMine && (
          <>
            <div className='text-xs font-semibold text-gray-500 mb-3 mt-2 flex items-center gap-3'>
              {t('taskflow_my_flows')}
              <span className='flex-1 h-px bg-gray-100 dark:bg-white/5' />
            </div>
            {filtered(myFlows).length === 0 ? (
              <MyEmpty description={t('taskflow_empty')} />
            ) : (
              <div className='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4'>
                {filtered(myFlows).map(item => (
                  <TaskflowCard
                    key={item.uid}
                    item={item}
                    manifest={manifest}
                    onRun={handleRun}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </Spin>
    </div>
  );
}

export default function TaskflowPage() {
  return (
    <ConstructLayout>
      <TaskflowList />
    </ConstructLayout>
  );
}
