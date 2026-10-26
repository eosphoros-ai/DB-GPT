import {
  archiveDashboard,
  copyDashboard,
  getDashboard,
  pageDashboards,
  refreshDashboard,
  restoreDashboard,
} from '@/client/api';
import { listDashboardFolders, moveDashboardToFolder, type DashboardFolder } from '@/client/api/dashboard';
import { AVAILABLE_CREATION_MODES, TEMPLATE_GALLERY_ENABLED } from '@/new-components/dashboard/dashboard-catalog';
import { describeDashboardError } from '@/new-components/dashboard/dashboard-errors';
import { dashboardSourceLabel } from '@/new-components/dashboard/dashboard-source-label';
import { readDashboardVisits, rememberDashboardVisit } from '@/new-components/dashboard/dashboard-visits';
import DashboardAssetCover from '@/new-components/dashboard/DashboardAssetCover';
import DashboardCoverCapture from '@/new-components/dashboard/DashboardCoverCapture';
import DashboardFolderBar from '@/new-components/dashboard/DashboardFolderWorkspace';
import styles from '@/new-components/dashboard/DashboardGallery.module.css';
import DashboardTemplateGallery from '@/new-components/dashboard/DashboardTemplateGallery';
import { DashboardListItem, DashboardRecord, DashboardSnapshot } from '@/types/dashboard';
import {
  CopyOutlined,
  HistoryOutlined,
  InboxOutlined,
  MoreOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ScheduleOutlined,
  SearchOutlined,
  UndoOutlined,
} from '@ant-design/icons';
import { Alert, App, Button, Dropdown, Empty, Input, Modal, Pagination, Select, Skeleton } from 'antd';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useRef, useState } from 'react';

type LibraryTab = 'templates' | 'folders' | 'all' | 'recent' | 'tests' | 'archived';
const tabs: { key: LibraryTab; label: string }[] = [
  ...(TEMPLATE_GALLERY_ENABLED ? [{ key: 'templates' as const, label: '模板' }] : []),
  { key: 'folders', label: '所有文件夹' },
  { key: 'all', label: '全部看板' },
  { key: 'recent', label: '最近使用' },
];
const toItem = (r: DashboardRecord): DashboardListItem => ({
  id: r.id,
  title: r.schema.dashboard.title,
  description: r.schema.dashboard.description || '',
  data_source_id: r.schema.dashboard.data_source_id,
  conversation_id: r.conversation_id,
  origin: r.origin,
  asset_state: r.asset_state,
  current_revision: r.current_revision,
  status: r.status,
  updated_at: r.updated_at,
});
const formatTime = (value: string) =>
  new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });

export default function DashboardListPage() {
  const router = useRouter();
  const { message } = App.useApp();
  const requestedTab = router.query.tab;
  const tab: LibraryTab =
    tabs.some(item => item.key === requestedTab) || requestedTab === 'tests' || requestedTab === 'archived'
      ? (requestedTab as LibraryTab)
      : router.query.view === 'manage' || !TEMPLATE_GALLERY_ENABLED
        ? 'all'
        : 'templates';
  const [folderId, setFolderId] = useState<string | undefined>(undefined);
  const [folders, setFolders] = useState<DashboardFolder[]>([]);
  const [movingItem, setMovingItem] = useState<DashboardListItem | null>(null);
  const [moveTarget, setMoveTarget] = useState('');
  const [moving, setMoving] = useState(false);
  const loadFolders = useCallback(async () => {
    const response = await listDashboardFolders();
    if (!response.data.success) throw new Error(response.data.err_msg || '文件夹加载失败');
    setFolders(response.data.data);
  }, []);
  useEffect(() => {
    // Initial page mount starts an external API read; state is set after it resolves.
    void loadFolders().catch(() => message.error('文件夹加载失败，请刷新重试'));
  }, [loadFolders, message]);
  const [items, setItems] = useState<DashboardListItem[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(0);
  const pageSize = 12;
  const [coverQueue, setCoverQueue] = useState<DashboardListItem[]>([]);
  const [coverJob, setCoverJob] = useState<{ record: DashboardRecord; snapshot: DashboardSnapshot } | null>(null);
  const [coverRefresh, setCoverRefresh] = useState(0);
  const [coverErrors, setCoverErrors] = useState<Record<string, string>>({});
  const attemptedCovers = useRef(new Set<string>());
  const activeCoverId = useRef<string | null>(null);
  const enqueueCover = useCallback((item: DashboardListItem, force = false) => {
    const key = `${item.id}:${item.current_revision}`;
    if (!force && attemptedCovers.current.has(key)) return;
    attemptedCovers.current.add(key);
    setCoverErrors(current => {
      const next = { ...current };
      delete next[item.id];
      return next;
    });
    setCoverQueue(current => (current.some(queued => queued.id === item.id) ? current : [...current, item]));
  }, []);
  const finishCover = useCallback(
    (_image: string | null, error?: string) => {
      const id = activeCoverId.current;
      if (id && error) setCoverErrors(current => ({ ...current, [id]: error }));
      activeCoverId.current = null;
      setCoverJob(null);
      setCoverQueue(q => q.slice(1));
      setCoverRefresh(n => n + 1);
      if (error) message.warning('此看板预览未更新：' + error);
    },
    [message],
  );
  useEffect(() => {
    if (!coverQueue.length || coverJob) return;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        activeCoverId.current = coverQueue[0].id;
        const r = await getDashboard(coverQueue[0].id);
        if (!r.data.success) throw new Error(r.data.err_msg || '读取看板失败');
        const snap = await refreshDashboard(r.data.data.id, {});
        if (!snap.data.success) throw new Error(snap.data.err_msg || '查询失败');
        if (
          !r.data.data.schema.widgets.length ||
          r.data.data.schema.widgets.some(
            w => !snap.data.data.widgets[w.id]?.rows.length || snap.data.data.widgets[w.id].error,
          )
        )
          throw new Error('存在不可用组件，保留已有预览');
        if (active) setCoverJob({ record: r.data.data, snapshot: snap.data.data });
      } catch (e) {
        if (active) finishCover(null, describeDashboardError(e, '无法生成预览'));
      }
    }, 0);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [coverQueue, coverJob, finishCover]);
  const load = useCallback(async () => {
    const id = ++requestId.current;
    if (tab === 'templates' || (tab === 'folders' && (!folderId || folderId === 'folders'))) {
      setLoading(false);
      setError('');
      return;
    }
    setLoading(true);
    setError('');
    try {
      if (tab === 'recent') {
        const visits = readDashboardVisits();
        const results = await Promise.allSettled(visits.map(visit => getDashboard(visit.id)));
        const available = results.flatMap(result =>
          result.status === 'fulfilled' && result.value.data.success ? [toItem(result.value.data.data)] : [],
        );
        const networkFailure = results.find(
          result => result.status === 'rejected' && ![403, 404].includes(result.reason?.response?.status),
        );
        if (networkFailure?.status === 'rejected') throw networkFailure.reason;
        const businessFailure = results.find(result => result.status === 'fulfilled' && !result.value.data.success);
        if (businessFailure?.status === 'fulfilled')
          throw new Error(businessFailure.value.data.err_msg || '最近看板加载失败');
        const matches = available.filter(
          item =>
            item.status !== 'archived' &&
            `${item.title} ${item.description}`.toLowerCase().includes(search.trim().toLowerCase()),
        );
        if (id === requestId.current) {
          setTotal(matches.length);
          setItems(matches.slice((page - 1) * pageSize, page * pageSize));
        }
      } else {
        const response = await pageDashboards({
          search: search || undefined,
          folder_id:
            tab === 'tests' ? '__tests__' : tab === 'all' || tab === 'folders' ? folderId || '__main__' : undefined,
          status: tab === 'archived' ? 'archived' : undefined,
          include_archived: tab === 'archived',
          exclude_origin: 'template',
          limit: pageSize,
          offset: (page - 1) * pageSize,
        });
        if (!response.data.success) throw new Error(response.data.err_msg || '加载看板失败');
        if (id === requestId.current) {
          setItems(response.data.data.items);
          setTotal(response.data.data.total);
        }
      }
    } catch (reason) {
      if (id === requestId.current) setError(describeDashboardError(reason, '无法加载看板'));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [tab, search, page, folderId]);
  useEffect(() => {
    const cancellationVersion = requestId.current;
    const timer = setTimeout(() => void load(), 250);
    return () => {
      clearTimeout(timer);
      requestId.current = Math.max(requestId.current, cancellationVersion) + 1;
    };
  }, [load]);
  const open = (item: DashboardListItem, panel?: 'access' | 'lifecycle' | 'schedule') => {
    rememberDashboardVisit(item.id);
    void router.push({ pathname: '/dashboards/' + item.id, query: panel ? { panel } : undefined });
  };
  const action = async (key: string, item: DashboardListItem) => {
    try {
      if (key === 'copy') {
        const r = await copyDashboard(item.id);
        if (!r.data.success) throw new Error(r.data.err_msg || '复制失败');
        await router.push('/dashboards/' + r.data.data.id);
        return;
      }
      const response =
        key === 'archive'
          ? await archiveDashboard(item.id, item.current_revision)
          : await restoreDashboard(item.id, item.current_revision);
      if (!response.data.success) throw new Error(response.data.err_msg || '操作失败');
      await load();
    } catch (reason) {
      message.error(describeDashboardError(reason, '操作失败'));
    }
  };
  const menu = (item: DashboardListItem) => ({
    items: [
      {
        key: 'folder',
        label: '移动到文件夹',
      },
      { key: 'copy', label: '复制为草稿', icon: <CopyOutlined /> },
      { key: 'lifecycle', label: '版本与分享', icon: <HistoryOutlined /> },
      { key: 'access', label: '权限与审计', icon: <SafetyCertificateOutlined /> },
      { key: 'schedule', label: '定时刷新', icon: <ScheduleOutlined /> },
      ...(item.conversation_id ? [{ key: 'task', label: '返回来源对话', icon: <HistoryOutlined /> }] : []),
      { type: 'divider' as const },
      item.status === 'archived'
        ? { key: 'restore', label: '恢复看板', icon: <UndoOutlined /> }
        : { key: 'archive', label: '归档看板', icon: <InboxOutlined /> },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'folder') {
        setMoveTarget(folders.some(folder => folder.id === folderId) ? folderId! : '');
        setMovingItem(item);
      } else if (key === 'access' || key === 'lifecycle' || key === 'schedule') open(item, key);
      else if (key === 'task')
        void router.push({ pathname: '/', query: { conversation_id: item.conversation_id } });
      else void action(key, item);
    },
  });
  return (
    <div className={styles.page}>
      <Modal
        title='移动到文件夹'
        open={!!movingItem}
        onCancel={() => {
          if (!moving) setMovingItem(null);
        }}
        okText='移动'
        confirmLoading={moving}
        onOk={async () => {
          if (!movingItem || moving) return;
          setMoving(true);
          try {
            const r = await moveDashboardToFolder(movingItem.id, moveTarget || null);
            if (!r.data.success) throw new Error(r.data.err_msg || '移动失败');
            await loadFolders();
            await load();
            setMovingItem(null);
          } catch (reason) {
            message.error(describeDashboardError(reason, '移动失败，请重试'));
          } finally {
            setMoving(false);
          }
        }}
      >
        <p className='mb-3 break-words'>{movingItem?.title}</p>
        <Select
          aria-label='目标文件夹'
          className='w-full'
          showSearch
          optionFilterProp='label'
          value={moveTarget}
          onChange={setMoveTarget}
          options={[
            { value: '', label: '未分类' },
            ...folders.map(folder => ({ value: folder.id, label: folder.name })),
          ]}
        />
      </Modal>
      {coverJob && (
        <DashboardCoverCapture
          key={coverJob.record.id}
          record={coverJob.record}
          snapshot={coverJob.snapshot}
          onComplete={finishCover}
        />
      )}
      <Head>
        <title>数据看板 · DB-GPT</title>
      </Head>
      <div className={styles.container}>
        <header className={styles.header}>
          <div>
            <h1>数据看板</h1>
            <p>
              {TEMPLATE_GALLERY_ENABLED ? '选一个模板开始，或继续编辑已有看板。' : '找到你的看板，继续分析与编辑。'}
            </p>
          </div>
          {AVAILABLE_CREATION_MODES.some(mode => mode.id === 'dashboard') && (
            <Button type='primary' icon={<PlusOutlined />} onClick={() => router.push('/dashboards/new')}>
              创建看板
            </Button>
          )}
        </header>
        <nav className={styles.tabs} aria-label='看板分类'>
          {tabs.map(item => (
            <button
              type='button'
              key={item.key}
              aria-pressed={tab === item.key || (item.key === 'all' && (tab === 'tests' || tab === 'archived'))}
              onClick={() => {
                setPage(1);
                setSearch('');
                setFolderId(undefined);
                setItems([]);
                setTotal(0);
                setError('');
                void router.replace({ pathname: '/dashboards', query: { tab: item.key } }, undefined, {
                  shallow: true,
                });
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        {tab === 'templates' ? (
          <DashboardTemplateGallery />
        ) : (
          <>
            {(tab === 'all' || tab === 'tests' || tab === 'archived') && (
              <nav className={styles.categories} aria-label='全部看板分类' style={{ marginBottom: 20 }}>
                {[
                  { key: 'all', label: '所有看板' },
                  { key: 'tests', label: '验收测试' },
                  { key: 'archived', label: '已归档' },
                ].map(item => (
                  <button
                    key={item.key}
                    type='button'
                    aria-pressed={tab === item.key}
                    onClick={() => {
                      setPage(1);
                      setItems([]);
                      setFolderId(undefined);
                      void router.replace({ pathname: '/dashboards', query: { tab: item.key } }, undefined, {
                        shallow: true,
                      });
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            )}
            {tab === 'folders' && (
              <DashboardFolderBar
                folders={folders}
                value={folderId || 'folders'}
                foldersOnly
                onChange={id => {
                  setFolderId(id);
                  setPage(1);
                }}
                onRefresh={loadFolders}
              />
            )}
            {!(tab === 'folders' && (!folderId || folderId === 'folders')) && (
              <>
                <div className={styles.tools}>
                  <Input
                    className={styles.search}
                    prefix={<SearchOutlined />}
                    placeholder='搜索看板'
                    aria-label='搜索看板'
                    allowClear
                    value={search}
                    onChange={event => {
                      setPage(1);
                      setSearch(event.target.value);
                    }}
                  />
                  <span className='flex-1 text-xs text-[var(--app-muted)]'>
                    {tab === 'recent'
                      ? '本浏览器最近打开的看板'
                      : tab === 'tests'
                        ? '验收看板集中展示，原始记录与版本均保留'
                        : '按最近更新排序'}
                  </span>
                  <Button
                    disabled={!items.length || !!coverQueue.length}
                    loading={!!coverQueue.length}
                    onClick={() => items.forEach(item => enqueueCover(item, true))}
                  >
                    {coverQueue.length ? `正在生成（剩余 ${coverQueue.length}）` : '更新本页预览'}
                  </Button>
                  <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void load()}>
                    刷新
                  </Button>
                </div>
                {error && (
                  <Alert
                    className='mb-5'
                    type='error'
                    showIcon
                    message={error}
                    description={
                      items.length
                        ? '已保留上次加载的内容。恢复连接后可重试。'
                        : '暂时无法读取看板，请检查服务连接后重试。'
                    }
                    action={
                      <Button onClick={() => void load()} loading={loading}>
                        重试
                      </Button>
                    }
                  />
                )}
                {loading && !items.length ? (
                  <div className={styles.grid}>
                    {Array.from({ length: 8 }, (_, i) => (
                      <Skeleton.Node active key={i} className='!w-full !h-48' />
                    ))}
                  </div>
                ) : items.length ? (
                  <div className={styles.grid}>
                    {items.map(item => (
                      <article key={item.id} className={styles.card}>
                        <button
                          type='button'
                          className={styles.cover}
                          aria-label={`打开看板 ${item.title}`}
                          onClick={() => open(item)}
                        >
                          <DashboardAssetCover
                            item={item}
                            refreshKey={coverRefresh}
                            onNeedsPreview={enqueueCover}
                            generating={coverQueue.some(queued => queued.id === item.id)}
                            failure={coverErrors[item.id]}
                          />
                          <span className={styles.coverAction}>打开看板</span>
                        </button>
                        {coverErrors[item.id] && (
                          <Button size='small' onClick={() => enqueueCover(item, true)}>
                            重试预览
                          </Button>
                        )}
                        <div className={styles.cardTitle}>
                          <button className='flex-1' onClick={() => open(item)} title={item.title}>
                            {item.title}
                          </button>
                          <Dropdown trigger={['click']} menu={menu(item)}>
                            <Button
                              size='small'
                              type='text'
                              aria-label={item.title + '更多操作'}
                              icon={<MoreOutlined />}
                            />
                          </Dropdown>
                        </div>
                        <p className={styles.description}>{item.description || '暂无看板说明'}</p>
                        <div className={styles.meta}>
                          <span title={item.data_source_id}>{dashboardSourceLabel(item.data_source_id)}</span>
                          <span>{formatTime(item.updated_at)}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  !error && (
                    <Empty
                      className={styles.empty}
                      description={
                        search
                          ? '没有找到匹配的看板'
                          : tab === 'recent'
                            ? '打开一个看板后，会在这里留下记录'
                            : tab === 'archived'
                              ? '暂无归档看板'
                              : '还没有已保存的看板'
                      }
                    />
                  )
                )}
                {total > pageSize && (
                  <div className={styles.pagination}>
                    <Pagination
                      current={page}
                      total={total}
                      pageSize={pageSize}
                      onChange={setPage}
                      showSizeChanger={false}
                    />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
