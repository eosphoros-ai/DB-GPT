import {
  useConnectors,
  useConnectorTypes,
  useCreateConnector,
  useDeleteConnector,
  useTestConnection,
  useUpdateConnector,
} from '@/hooks/use-connector-api';
import { ConnectorCard, ConnectorForm } from '@/new-components/connector';
import {
  ConnectorCatalogEntry,
  ConnectorInstance,
  ConnectorStatus,
  CreateConnectorRequest,
} from '@/new-components/connector/types';
import ConstructLayout from '@/new-components/layout/Construct';
import { ApiOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Input, message, Segmented, Spin } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

/* ─────────────────────────────────────────────────────────────────
   Connector management page — full visual rebuild.

   Design intent:
   - Single unified card grid (no per-template sub-headers). Templates &
     instances coexist in one stream; cards carry their own identity
     (dashed vs solid, brand-tinted icon tile, status chip).
   - Top: hero header with title + live counters.
   - Toolbar: search · status filter (Segmented) · 自定义 MCP CTA.
   - 3-col grid (1 / 2 / 3 responsive) — generous, like Linear/Vercel
     integration directories.
   - Empty / loading states are graceful, not jarring.
   ────────────────────────────────────────────────────────────────── */

type StatusFilter = 'all' | 'active' | 'inactive' | 'attention';

/** A unified item rendered into the grid — either a template or an instance. */
type GridItem =
  | { kind: 'template'; template: ConnectorCatalogEntry; instanceCount: number }
  | { kind: 'instance'; instance: ConnectorInstance; catalogEntry?: ConnectorCatalogEntry };

const STATUS_ATTENTION_SET = new Set<ConnectorStatus>(['error', 'needs_reactivation']);

function Connectors() {
  const { t } = useTranslation();
  const { connectors, loading, refresh } = useConnectors();
  const { types: catalog, loading: catalogLoading } = useConnectorTypes();
  const { create, loading: creating } = useCreateConnector();
  const { update, loading: updating } = useUpdateConnector();
  const { remove, loading: deleting } = useDeleteConnector();
  const { test } = useTestConnection();

  const [formOpen, setFormOpen] = useState(false);
  const [editingConnector, setEditingConnector] = useState<ConnectorInstance | undefined>(undefined);
  const [prefilledType, setPrefilledType] = useState<string | undefined>(undefined);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  /* ─── Derived collections ─────────────────────────────────────── */

  // Built-in templates (exclude custom_mcp — it has its own entry point)
  const builtInTemplates = useMemo(() => catalog.filter(t => t.type !== 'custom_mcp'), [catalog]);

  // Quick lookup of catalog entry by type — used to enrich instance cards
  const catalogByType = useMemo(() => {
    const map: Record<string, ConnectorCatalogEntry> = {};
    for (const e of catalog) map[e.type] = e;
    return map;
  }, [catalog]);

  // Group instance counts by connector_type
  const instanceCountByType = useMemo(() => {
    const map: Record<string, number> = {};
    for (const inst of connectors) {
      map[inst.connector_type] = (map[inst.connector_type] ?? 0) + 1;
    }
    return map;
  }, [connectors]);

  // Build unified grid items: only show templates that have NO active
  // instance yet (once activated, the template card disappears — users add
  // additional instances via the top "+ 添加连接器" CTA instead). Instance
  // cards are always shown.
  const gridItems: GridItem[] = useMemo(() => {
    const tplItems: GridItem[] = builtInTemplates
      .filter(t => (instanceCountByType[t.type] ?? 0) === 0)
      .map(t => ({
        kind: 'template',
        template: t,
        instanceCount: instanceCountByType[t.type] ?? 0,
      }));
    const instItems: GridItem[] = connectors.map(inst => ({
      kind: 'instance',
      instance: inst,
      catalogEntry: catalogByType[inst.connector_type],
    }));
    return [...tplItems, ...instItems];
  }, [builtInTemplates, connectors, instanceCountByType, catalogByType]);

  /* ─── Filtering ───────────────────────────────────────────────── */

  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase();

    return gridItems.filter(item => {
      // status filter
      if (statusFilter !== 'all') {
        if (statusFilter === 'inactive') {
          if (item.kind !== 'template') return false;
        } else if (statusFilter === 'active') {
          if (item.kind !== 'instance' || item.instance.status !== 'active') return false;
        } else if (statusFilter === 'attention') {
          if (item.kind !== 'instance' || !STATUS_ATTENTION_SET.has(item.instance.status)) return false;
        }
      }
      // search filter — match display_name + type + description
      if (!q) return true;
      if (item.kind === 'template') {
        return (
          item.template.display_name.toLowerCase().includes(q) ||
          item.template.type.toLowerCase().includes(q) ||
          (item.template.description ?? '').toLowerCase().includes(q)
        );
      }
      return (
        item.instance.display_name.toLowerCase().includes(q) || item.instance.connector_type.toLowerCase().includes(q)
      );
    });
  }, [gridItems, search, statusFilter]);

  /* ─── Counter — only attention is still surfaced (Segmented badge below) ── */
  const counters = useMemo(() => {
    const attentionCount = connectors.filter(c => STATUS_ATTENTION_SET.has(c.status)).length;
    return { attention: attentionCount };
  }, [connectors]);

  /* ─── Handlers ────────────────────────────────────────────────── */

  const handleAddConnector = () => {
    // No prefilledType — the form's connector_type selector becomes visible
    // so the user can pick any built-in template OR custom_mcp from one entry
    // point. This is the canonical path for adding additional instances once
    // a template card has been activated (and hence hidden from the grid).
    setEditingConnector(undefined);
    setPrefilledType(undefined);
    setFormOpen(true);
  };

  const handleActivateTemplate = (template: ConnectorCatalogEntry) => {
    setEditingConnector(undefined);
    setPrefilledType(template.type);
    setFormOpen(true);
  };

  const handleEdit = (connector: ConnectorInstance) => {
    setPrefilledType(undefined);
    setEditingConnector(connector);
    setFormOpen(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await remove(id);
      message.success(t('connector.msg.deleted'));
      refresh();
    } catch {
      message.error(t('connector.msg.deleteFailed'));
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await test(id);
      if (result.success) {
        message.success(result.message || t('connector.msg.testSuccess'));
        // Backend self-heals status from 'error' → 'active' on a successful
        // probe (see ConnectorService.test_connection). Refetch so the card
        // reflects the new status without forcing the user to F5.
        refresh();
      } else {
        message.error(result.message || t('connector.msg.testFailed'));
      }
    } catch {
      message.error(t('connector.msg.testFailedCheck'));
    }
  };

  const handleSubmit = async (data: CreateConnectorRequest) => {
    try {
      if (editingConnector) {
        await update(editingConnector.id, data);
        message.success(t('connector.msg.updated'));
      } else {
        await create(data);
        message.success(t('connector.msg.created'));
      }
      setFormOpen(false);
      setEditingConnector(undefined);
      setPrefilledType(undefined);
      refresh();
    } catch {
      message.error(editingConnector ? t('connector.msg.updateFailed') : t('connector.msg.createFailed'));
    }
  };

  const handleClose = () => {
    setFormOpen(false);
    setEditingConnector(undefined);
    setPrefilledType(undefined);
  };

  const hasAnything = builtInTemplates.length > 0 || connectors.length > 0;
  const showEmptyFilter = hasAnything && visibleItems.length === 0;

  /* ─── Render ──────────────────────────────────────────────────── */

  return (
    <ConstructLayout>
      <div className='relative h-screen w-full overflow-y-auto bg-gradient-to-b from-[#f7f8fc] via-white to-[#f7f8fc] dark:from-[#1c2333] dark:via-[#1c2333] dark:to-[#161b29]'>
        <div className='max-w-[1400px] mx-auto p-4 md:p-6 lg:p-8'>
          {/* ───────────── HERO HEADER ───────────── */}
          <div className='mb-7'>
            <div className='flex items-start justify-between gap-4 flex-wrap mb-2'>
              <div>
                <h1 className='text-[26px] leading-tight font-bold text-gray-900 dark:text-white mb-1 flex items-center gap-2.5'>
                  <span className='inline-flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-[0_4px_14px_-4px_rgba(124,58,237,0.5)]'>
                    <ApiOutlined className='text-lg' />
                  </span>
                  {t('connector.page.title')}
                </h1>
                <p className='text-sm text-gray-500 dark:text-gray-400 ml-[46px]'>{t('connector.page.subtitle')}</p>
              </div>

              {/* CTA — gradient button (matches skills.tsx convention).
                  Uses ApiOutlined to mirror the sidebar nav entry and the
                  hero header so the "连接器管理" → "自定义 MCP" visual link
                  is consistent across all three touchpoints. */}
              <Button
                className='border-none text-white bg-button-gradient h-9 px-4 shadow-[0_4px_14px_-4px_rgba(124,58,237,0.45)] hover:shadow-[0_6px_18px_-4px_rgba(124,58,237,0.6)] transition-shadow'
                icon={<ApiOutlined />}
                onClick={handleAddConnector}
                loading={creating || updating}
              >
                {t('connector.page.addBtn')}
              </Button>
            </div>
          </div>

          {/* ───────────── TOOLBAR ───────────── */}
          <div className='flex items-center gap-3 mb-6 flex-wrap'>
            <Input
              prefix={<SearchOutlined className='text-gray-400' />}
              placeholder={t('connector.page.searchPlaceholder')}
              value={search}
              onChange={e => setSearch(e.target.value)}
              allowClear
              className='w-[280px] h-[36px] backdrop-filter backdrop-blur-lg bg-white bg-opacity-60 border border-gray-200 rounded-lg dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
            />

            <Segmented
              value={statusFilter}
              onChange={v => setStatusFilter(v as StatusFilter)}
              options={[
                { label: t('connector.page.filterAll'), value: 'all' },
                { label: t('connector.page.filterActive'), value: 'active' },
                { label: t('connector.page.filterInactive'), value: 'inactive' },
                {
                  label: (
                    <span className='inline-flex items-center gap-1'>
                      {t('connector.page.filterAttention')}
                      {counters.attention > 0 && (
                        <span className='inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[10px] font-medium bg-amber-500 text-white'>
                          {counters.attention}
                        </span>
                      )}
                    </span>
                  ),
                  value: 'attention',
                },
              ]}
              className='!bg-white/60 backdrop-blur-md rounded-lg dark:!bg-[#6f7f95]/40'
            />
          </div>

          {/* ───────────── GRID / EMPTY STATE ───────────── */}
          <Spin spinning={loading || catalogLoading || deleting}>
            {!hasAnything && !loading && !catalogLoading ? (
              <EmptyState onAddCustom={handleAddConnector} />
            ) : showEmptyFilter ? (
              <FilterEmpty
                onReset={() => {
                  setSearch('');
                  setStatusFilter('all');
                }}
              />
            ) : (
              <div className='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-16'>
                {visibleItems.map(item =>
                  item.kind === 'template' ? (
                    <ConnectorCard
                      key={`tpl-${item.template.type}`}
                      kind='template'
                      template={item.template}
                      instanceCount={item.instanceCount}
                      onActivate={handleActivateTemplate}
                    />
                  ) : (
                    <ConnectorCard
                      key={`inst-${item.instance.id}`}
                      kind='instance'
                      connector={item.instance}
                      catalogEntry={item.catalogEntry}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                      onTest={handleTest}
                    />
                  ),
                )}
              </div>
            )}
          </Spin>
        </div>

        <ConnectorForm
          open={formOpen}
          onClose={handleClose}
          onSubmit={handleSubmit}
          catalog={catalog}
          catalogLoading={catalogLoading}
          initialValues={editingConnector}
          prefilledType={prefilledType}
          submitting={creating || updating}
        />
      </div>
    </ConstructLayout>
  );
}

/* ─────────────────────────────────────────────────────────────────
   EmptyState — when there's nothing at all (catalog & instances empty)
   ────────────────────────────────────────────────────────────────── */

function EmptyState({ onAddCustom }: { onAddCustom: () => void }) {
  const { t } = useTranslation();
  return (
    <div className='flex flex-col items-center justify-center text-center py-24'>
      <div className='w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-100 to-indigo-100 dark:from-violet-900/30 dark:to-indigo-900/30 flex items-center justify-center mb-5'>
        <ApiOutlined className='text-3xl text-violet-500' />
      </div>
      <h3 className='text-lg font-semibold text-gray-800 dark:text-gray-100 mb-1'>{t('connector.page.emptyTitle')}</h3>
      <p className='text-sm text-gray-500 dark:text-gray-400 max-w-md mb-5'>{t('connector.page.emptyDesc')}</p>
      <Button type='primary' icon={<PlusOutlined />} className='border-none bg-button-gradient' onClick={onAddCustom}>
        {t('connector.page.addBtn')}
      </Button>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────
   FilterEmpty — when filters/search yield zero results
   ────────────────────────────────────────────────────────────────── */

function FilterEmpty({ onReset }: { onReset: () => void }) {
  const { t } = useTranslation();
  return (
    <div className='flex flex-col items-center justify-center text-center py-20'>
      <SearchOutlined className='text-3xl text-gray-300 dark:text-gray-600 mb-3' />
      <p className='text-sm text-gray-500 dark:text-gray-400 mb-3'>{t('connector.page.filterEmptyText')}</p>
      <Button size='small' onClick={onReset}>
        {t('connector.page.filterEmptyReset')}
      </Button>
    </div>
  );
}

export default Connectors;
