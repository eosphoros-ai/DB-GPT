import { apiInterceptors } from '@/client/api';
import {
  SemanticCoverage,
  SemanticEntry,
  SemanticExample,
  SemanticMetric,
  SemanticRelation,
  SemanticRule,
  SemanticSpace,
  SemanticTable,
  getSemanticCoverage,
  getSemanticEntries,
  getSemanticExamples,
  getSemanticMetricVersion,
  getSemanticMetrics,
  getSemanticRelations,
  getSemanticRules,
  getSemanticSpace,
  getSemanticSpaces,
  getSemanticTables,
  postEntryReview,
  postMetricPublish,
  postRuleStatus,
  postSemanticActivate,
  postSemanticBackfill,
  postSemanticDrafts,
  postSemanticSync,
} from '@/client/api/semantic';
import { SemanticSourceDetail } from '@/new-components/chat/content/SemanticProvenance';
import ConstructLayout from '@/new-components/layout/Construct';
import type { SemanticSource } from '@/utils/semantic-provenance';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  BookOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  FunctionOutlined,
  PlusOutlined,
  RightOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useAsyncEffect } from 'ahooks';
import { Button, Drawer, Empty, Input, Modal, Select, Space, Table, Typography, message } from 'antd';
import { useRouter } from 'next/router';
import { useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import styles from './semantic.module.css';

const SemanticCenter = () => {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const label = (key: string, values?: Record<string, unknown>): string => String(t(`semantic_center.${key}`, values));
  const dsId = router.query.ds ? Number(router.query.ds) : null;

  const [spaces, setSpaces] = useState<SemanticSpace[]>([]);
  const [space, setSpace] = useState<SemanticSpace | null>(null);
  const [coverage, setCoverage] = useState<SemanticCoverage | null>(null);
  const [tables, setTables] = useState<SemanticTable[]>([]);
  const [entries, setEntries] = useState<SemanticEntry[]>([]);
  const [metrics, setMetrics] = useState<SemanticMetric[]>([]);
  const [examples, setExamples] = useState<SemanticExample[]>([]);
  const [relations, setRelations] = useState<SemanticRelation[]>([]);
  const [rules, setRules] = useState<SemanticRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [busy, setBusy] = useState<string | null>(null);
  const busyRef = useRef(false);
  const [activateId, setActivateId] = useState<number | null>(null);
  const [sampling, setSampling] = useState('42');
  const [runDrafts, setRunDrafts] = useState('no');
  const [embedding, setEmbedding] = useState('bge-large-zh');
  const [citedMetric, setCitedMetric] = useState<SemanticSource | null>(null);
  const [metricLoading, setMetricLoading] = useState(false);
  const [metricOpen, setMetricOpen] = useState(false);
  const [metricError, setMetricError] = useState(false);
  const metricRequest = useRef(0);
  const tabKeys = ['catalog', 'entries', 'metrics', 'examples', 'relations', 'rules'] as const;
  const activeTab =
    typeof router.query.tab === 'string' && (tabKeys as readonly string[]).includes(router.query.tab)
      ? (router.query.tab as (typeof tabKeys)[number])
      : 'catalog';
  const statusLabel = (status: string) => label(`status_labels.${status}`, { defaultValue: status });
  const typeLabel = (value: string) => label(`type_labels.${value}`, { defaultValue: value });
  const sourceLabel = (value: string) => label(`source_labels.${value}`, { defaultValue: value });
  const statusBadge = (status: string) => (
    <span className={styles.status} data-status={status}>
      {statusLabel(status)}
    </span>
  );
  const filtered = <T extends object>(rows: T[]) =>
    rows.filter(
      row =>
        (statusFilter === 'all' || ('status' in row && row.status === statusFilter)) &&
        (!search.trim() ||
          Object.values(row).some(
            value => typeof value === 'string' && value.toLowerCase().includes(search.trim().toLowerCase()),
          )),
    );
  const runAction = async (key: string, action: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(key);
    try {
      await action();
    } finally {
      busyRef.current = false;
      setBusy(null);
    }
  };
  const tableProps = {
    rowKey: 'id',
    loading,
    className: styles.table,
    scroll: { x: 900 },
    pagination: { pageSize: 10, showSizeChanger: false, hideOnSinglePage: true },
    locale: {
      emptyText: (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={label(search || statusFilter !== 'all' ? 'no_results' : 'empty')}
        />
      ),
    },
  };
  const stats = (items: { title: string; value: number; suffix?: string }[], overview = false) => (
    <div className={`${styles.stats} ${overview ? styles.statsOverview : ''}`}>
      {items.map(item => (
        <div className={styles.stat} key={item.title}>
          <div className={styles.statLabel}>{item.title}</div>
          <div className={styles.statValue}>
            {loading ? '—' : item.value}
            <span className={styles.statSuffix}>{item.suffix}</span>
          </div>
        </div>
      ))}
    </div>
  );
  const expandedText = (title: string, text?: string) => (
    <div className={styles.expanded}>
      <div className={styles.muted}>{title}</div>
      <pre>{text || '—'}</pre>
    </div>
  );
  const switchTab = (tab: string) => {
    setSearch('');
    setStatusFilter('all');
    void router.replace({ pathname: router.pathname, query: { ds: dsId, tab } }, undefined, { shallow: true });
  };
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!offset && event.key !== 'Home' && event.key !== 'End') return;
    event.preventDefault();
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? tabKeys.length - 1
          : (index + offset + tabKeys.length) % tabKeys.length;
    switchTab(tabKeys[next]);
    document.getElementById(`semantic-tab-${tabKeys[next]}`)?.focus();
  };

  const openMetric = async (metricId: number, version: number) => {
    if (!dsId || !Number.isSafeInteger(version) || version < 1) return;
    const requestId = ++metricRequest.current;
    setMetricOpen(true);
    setMetricLoading(true);
    setMetricError(false);
    setCitedMetric(null);
    const [error, response] = await apiInterceptors(getSemanticMetricVersion(dsId, metricId, version));
    if (requestId !== metricRequest.current) return;
    if (!error && response?.metric) {
      const row = response.metric;
      setCitedMetric({
        key: `${response.conn_id}:metric:${row.id}:${row.version}`,
        kind: 'metric',
        connId: response.conn_id,
        dsId: response.ds_id,
        id: row.id,
        name: row.metric_name,
        version: row.version,
        snapshot: row,
      });
    } else setMetricError(true);
    setMetricLoading(false);
  };

  useAsyncEffect(async () => {
    const id = Number(router.query.metric);
    const version = Number(router.query.version);
    if (dsId && Number.isSafeInteger(id) && id > 0 && Number.isSafeInteger(version) && version > 0) {
      await openMetric(id, version);
    }
  }, [dsId, router.query.metric, router.query.version]);

  const loadSpaces = async () => {
    setLoading(true);
    const [, data] = await apiInterceptors(getSemanticSpaces());
    setSpaces(data ?? []);
    setLoading(false);
  };

  const loadDetail = async (id: number) => {
    setLoading(true);
    const [[, sp], [, cov], [, tb], [, en], [, me], [, ex], [, re], [, ru]] = await Promise.all([
      apiInterceptors(getSemanticSpace(id)),
      apiInterceptors(getSemanticCoverage(id)),
      apiInterceptors(getSemanticTables(id)),
      apiInterceptors(getSemanticEntries(id)),
      apiInterceptors(getSemanticMetrics(id)),
      apiInterceptors(getSemanticExamples(id)),
      apiInterceptors(getSemanticRelations(id)),
      apiInterceptors(getSemanticRules(id)),
    ]);
    setSpace(sp);
    setCoverage(cov);
    setTables(tb ?? []);
    setEntries(en ?? []);
    setMetrics(me ?? []);
    setExamples(ex ?? []);
    setRelations(re ?? []);
    setRules(ru ?? []);
    setLoading(false);
  };

  useAsyncEffect(async () => {
    if (dsId) await loadDetail(dsId);
    else await loadSpaces();
  }, [dsId]);

  const doBackfill = async () => {
    const [error, res] = await apiInterceptors(postSemanticBackfill());
    if (error) return;
    message.success(label('backfill_done', { count: res?.synced?.length ?? 0, failed: res?.failed?.length ?? 0 }));
    await loadSpaces();
  };

  const doSync = async (id: number) => {
    const [error, report] = await apiInterceptors(postSemanticSync(id));
    if (error) return;
    message.success(label('sync_done', { added: report?.tables_added ?? 0, deleted: report?.tables_deleted ?? 0 }));
    if (dsId) await loadDetail(id);
    else await loadSpaces();
  };

  const doActivate = async () => {
    if (activateId == null) return;
    const [error, res] = await apiInterceptors(
      postSemanticActivate(activateId, {
        sampling_limit: sampling === 'all' ? 9999 : Number(sampling),
        run_draft_generation: runDrafts === 'yes',
        embedding_model: embedding,
      }),
    );
    if (error) return;
    message.success(label('activate_done', { count: res?.whitelist ?? 0 }));
    setActivateId(null);
    if (dsId) await loadDetail(activateId);
    else await loadSpaces();
  };

  const doDrafts = async (id: number) => {
    const [error, res] = await apiInterceptors(postSemanticDrafts(id));
    if (error) return;
    message.success(
      label('drafts_done', {
        columns: res?.entries?.column_entries ?? 0,
        tables: res?.entries?.table_entries ?? 0,
        metrics: res?.metrics?.metrics ?? 0,
      }),
    );
    await loadDetail(id);
  };

  const review = async (entryId: number, action: 'confirm' | 'reject') => {
    const [error] = await apiInterceptors(postEntryReview(entryId, { action }));
    if (error) return;
    message.success(label('review_done'));
    if (dsId) await loadDetail(dsId);
  };

  const publish = async (metricId: number) => {
    const [error, res] = await apiInterceptors(postMetricPublish(metricId, { change_note: 'publish via UI' }));
    if (error) return;
    message.success(label('publish_done', { version: res?.version }));
    if (dsId) await loadDetail(dsId);
  };

  const toggleRule = async (ruleId: number, status: string) => {
    await apiInterceptors(postRuleStatus(ruleId, status));
    if (dsId) await loadDetail(dsId);
  };

  if (!dsId) {
    return (
      <ConstructLayout>
        <div className={styles.page}>
          <div className={styles.content}>
            <header className={styles.header}>
              <div className={styles.heading}>
                <span className={styles.emblem}>
                  <ApartmentOutlined />
                </span>
                <div>
                  <h1 className={styles.title}>{label('title')}</h1>
                  <p className={styles.subtitle}>{label('subtitle')}</p>
                </div>
              </div>
              <Button
                icon={<PlusOutlined />}
                loading={busy === 'backfill'}
                disabled={!!busy}
                onClick={() => runAction('backfill', doBackfill)}
              >
                {label('register')}
              </Button>
            </header>
            {stats(
              [
                { title: label('total_spaces'), value: spaces.length },
                { title: label('activated_spaces'), value: spaces.filter(s => s.status === 'activated').length },
                { title: label('table_count'), value: spaces.reduce((sum, s) => sum + (s.table_count ?? 0), 0) },
              ],
              true,
            )}
            <section className={styles.panel}>
              <div className={styles.toolbar}>
                <div>
                  <h2 className={styles.sectionTitle}>
                    {label('spaces')} <span className={styles.count}>{spaces.length}</span>
                  </h2>
                  <p className={styles.subtitle}>{label('spaces_hint')}</p>
                </div>
                <Input
                  className={styles.search}
                  prefix={<SearchOutlined className={styles.muted} />}
                  placeholder={label('search', { name: label('spaces') })}
                  aria-label={label('search', { name: label('spaces') })}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  allowClear
                />
              </div>
              <Table
                {...tableProps}
                dataSource={filtered(spaces)}
                columns={[
                  {
                    title: label('spaces'),
                    dataIndex: 'space_name',
                    width: 280,
                    render: (_: string, row: SemanticSpace) => (
                      <div className={styles.name}>
                        <span className={styles.nameIcon}>
                          <DatabaseOutlined />
                        </span>
                        <div>
                          <Button
                            type='link'
                            style={{ padding: 0 }}
                            onClick={() => router.push(`/construct/semantic?ds=${row.id}`)}
                          >
                            {row.conn_name || row.conn_id}
                          </Button>
                          <div className={styles.muted}>{row.db_type.toUpperCase()}</div>
                        </div>
                      </div>
                    ),
                  },
                  {
                    title: label('status'),
                    dataIndex: 'status',
                    render: statusBadge,
                  },
                  {
                    title: label('table_count'),
                    dataIndex: 'table_count',
                    width: 80,
                    render: (v?: number) => <span className={styles.nameText}>{v ?? '—'}</span>,
                  },
                  {
                    title: label('embedding'),
                    dataIndex: 'embedding_model',
                    render: (v?: string) => <span className={styles.mono}>{v || '—'}</span>,
                  },
                  {
                    title: label('synced'),
                    dataIndex: 'last_sync_at',
                    render: (v?: string) => (
                      <span className={styles.muted}>
                        {v && Number.isFinite(Date.parse(v))
                          ? new Date(v).toLocaleString(i18n.language.startsWith('en') ? 'en-US' : 'zh-CN', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : label('never_synced')}
                      </span>
                    ),
                  },
                  {
                    title: label('operations'),
                    width: 260,
                    render: (_, row: SemanticSpace) => (
                      <Space size={4}>
                        <Button type='link' onClick={() => router.push(`/construct/semantic?ds=${row.id}`)}>
                          {label('open')} <RightOutlined />
                        </Button>
                        <Button
                          type='text'
                          icon={<SyncOutlined />}
                          disabled={!!busy}
                          loading={busy === `sync-${row.id}`}
                          onClick={() => runAction(`sync-${row.id}`, () => doSync(row.id))}
                        >
                          {label('sync')}
                        </Button>
                        {row.status === 'not_activated' && (
                          <Button type='link' onClick={() => setActivateId(row.id)}>
                            {label('activate')}
                          </Button>
                        )}
                      </Space>
                    ),
                  },
                ]}
              />
            </section>
            <Modal
              rootClassName={styles.dialog}
              title={label('activate')}
              open={activateId != null}
              onOk={() => runAction('activate', doActivate)}
              onCancel={() => setActivateId(null)}
              okText={label('activate_confirm')}
              cancelText={label('cancel')}
              confirmLoading={busy === 'activate'}
            >
              <p className={styles.modalHint}>{label('activation_hint')}</p>
              <div className={styles.modalFields}>
                <div>
                  <label id='semantic-sampling'>{label('sample')}</label>
                  <Select
                    aria-labelledby='semantic-sampling'
                    value={sampling}
                    onChange={setSampling}
                    options={[
                      { value: '42', label: label('sample_top') },
                      { value: 'all', label: label('sample_all') },
                    ]}
                  />
                </div>
                <div>
                  <label id='semantic-generate'>{label('generate')}</label>
                  <Select
                    aria-labelledby='semantic-generate'
                    value={runDrafts}
                    onChange={setRunDrafts}
                    options={[
                      { value: 'no', label: label('generate_no') },
                      { value: 'yes', label: label('generate_yes') },
                    ]}
                  />
                </div>
                <div>
                  <label id='semantic-embedding'>{label('embedding')}</label>
                  <Select
                    aria-labelledby='semantic-embedding'
                    value={embedding}
                    onChange={setEmbedding}
                    options={[
                      { value: 'bge-large-zh', label: 'bge-large-zh' },
                      { value: 'text-embedding-v3', label: 'text-embedding-v3' },
                    ]}
                  />
                  <p className={styles.modalHint}>{label('embedding_hint')}</p>
                </div>
              </div>
            </Modal>
          </div>
        </div>
      </ConstructLayout>
    );
  }

  const tabItems = [
    {
      key: 'catalog',
      label: label('catalog'),
      icon: <DatabaseOutlined />,
      count: tables.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(tables)}
          expandable={{
            rowExpandable: row => !!row.table_comment,
            expandedRowRender: row => expandedText(label('description'), row.table_comment),
          }}
          columns={[
            {
              title: label('table'),
              dataIndex: 'table_name',
              width: 240,
              render: (v: string) => <span className={styles.nameText}>{v}</span>,
            },
            { title: label('description'), dataIndex: 'table_comment', ellipsis: true },
            { title: label('type'), dataIndex: 'table_type', width: 110, render: typeLabel },
            {
              title: label('whitelist'),
              dataIndex: 'is_whitelisted',
              width: 120,
              render: (v: boolean) => (
                <span className={styles.status} data-status={v ? 'active' : 'inactive'}>
                  {label(v ? 'yes' : 'no')}
                </span>
              ),
            },
            { title: label('status'), dataIndex: 'status', width: 120, render: statusBadge },
          ]}
        />
      ),
    },
    {
      key: 'entries',
      label: label('entries'),
      icon: <BookOutlined />,
      count: entries.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(entries)}
          expandable={{
            rowExpandable: row => !!row.entry_comment || !!row.synonyms,
            expandedRowRender: row => (
              <>
                {expandedText(label('description'), row.entry_comment)}
                {row.synonyms && expandedText(label('aliases'), row.synonyms)}
              </>
            ),
          }}
          columns={[
            {
              title: label('name'),
              dataIndex: 'entry_name',
              width: 180,
              render: (v?: string) => <span className={styles.nameText}>{v || '—'}</span>,
            },
            { title: label('description'), dataIndex: 'entry_comment', ellipsis: true },
            { title: label('type'), dataIndex: 'entry_type', width: 90, render: typeLabel },
            { title: label('source'), dataIndex: 'provenance', width: 100, render: sourceLabel },
            {
              title: label('confidence'),
              dataIndex: 'confidence',
              width: 90,
              render: (v?: number) => (v != null ? v.toFixed(2) : '-'),
            },
            { title: label('status'), dataIndex: 'status', width: 120, render: statusBadge },
            {
              title: label('operations'),
              width: 180,
              render: (_, row: SemanticEntry) =>
                row.status === 'draft' || row.status === 'stale' ? (
                  <Space>
                    <Button
                      type='link'
                      icon={<CheckCircleOutlined />}
                      disabled={!!busy}
                      loading={busy === `review-${row.id}`}
                      onClick={() => runAction(`review-${row.id}`, () => review(row.id, 'confirm'))}
                    >
                      {label('approve')}
                    </Button>
                    <Button
                      type='text'
                      danger
                      disabled={!!busy}
                      onClick={() => runAction(`review-${row.id}`, () => review(row.id, 'reject'))}
                    >
                      {label('reject')}
                    </Button>
                  </Space>
                ) : null,
            },
          ]}
        />
      ),
    },
    {
      key: 'metrics',
      label: label('metrics'),
      icon: <FunctionOutlined />,
      count: metrics.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(metrics)}
          expandable={{
            rowExpandable: row => !!row.formula,
            expandedRowRender: row => expandedText(label('formula'), row.formula),
          }}
          columns={[
            {
              title: label('metrics'),
              dataIndex: 'metric_name',
              width: 250,
              render: (name: string, row: SemanticMetric) =>
                row.status === 'published' && row.publish_version ? (
                  <Button
                    type='link'
                    style={{ padding: 0, fontWeight: 500 }}
                    onClick={() => openMetric(row.id, row.publish_version!)}
                  >
                    {name}
                  </Button>
                ) : (
                  name
                ),
            },
            {
              title: label('formula'),
              dataIndex: 'formula',
              ellipsis: true,
              render: (v?: string) => <span className={styles.mono}>{v || '—'}</span>,
            },
            { title: label('type'), dataIndex: 'metric_type', width: 110, render: typeLabel },
            {
              title: label('version'),
              dataIndex: 'version',
              width: 90,
              render: (v: number, row: SemanticMetric) => (
                <span className={styles.mono}>v{row.status === 'published' ? (row.publish_version ?? v) : v}</span>
              ),
            },
            { title: label('status'), dataIndex: 'status', width: 110, render: statusBadge },
            {
              title: label('operations'),
              width: 90,
              render: (_, row: SemanticMetric) =>
                row.status === 'draft' ? (
                  <Button
                    type='link'
                    disabled={!!busy}
                    loading={busy === `publish-${row.id}`}
                    onClick={() => runAction(`publish-${row.id}`, () => publish(row.id))}
                  >
                    {label('approve')}
                  </Button>
                ) : null,
            },
          ]}
        />
      ),
    },
    {
      key: 'examples',
      label: label('examples'),
      icon: <FileTextOutlined />,
      count: examples.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(examples)}
          expandable={{
            expandedRowRender: row => (
              <>
                {expandedText(label('question'), row.question)}
                {expandedText('SQL', row.sql_text)}
              </>
            ),
          }}
          columns={[
            { title: label('question'), dataIndex: 'question', ellipsis: true, width: 300 },
            {
              title: 'SQL',
              dataIndex: 'sql_text',
              ellipsis: true,
              render: (v?: string) => <span className={styles.mono}>{v || '—'}</span>,
            },
            { title: label('source'), dataIndex: 'source', width: 110, render: sourceLabel },
            { title: label('uses'), dataIndex: 'use_count', width: 100 },
            { title: label('status'), dataIndex: 'status', width: 120, render: statusBadge },
          ]}
        />
      ),
    },
    {
      key: 'relations',
      label: label('relations'),
      icon: <ApartmentOutlined />,
      count: relations.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(relations)}
          expandable={{
            rowExpandable: row => !!row.join_condition,
            expandedRowRender: row => expandedText(label('join'), row.join_condition),
          }}
          columns={[
            {
              title: label('left_table'),
              dataIndex: 'left_table_id',
              width: 150,
              render: (v?: number) => tables.find(table => table.id === v)?.table_name ?? v ?? '—',
            },
            { title: label('left_field'), dataIndex: 'left_column_id', width: 120 },
            {
              title: label('right_table'),
              dataIndex: 'right_table_id',
              width: 150,
              render: (v?: number) => tables.find(table => table.id === v)?.table_name ?? v ?? '—',
            },
            { title: label('right_field'), dataIndex: 'right_column_id', width: 120 },
            { title: label('type'), dataIndex: 'relation_type', width: 130 },
            {
              title: label('join'),
              dataIndex: 'join_condition',
              ellipsis: true,
              render: (v?: string) => <span className={styles.mono}>{v || '—'}</span>,
            },
            { title: label('confidence'), dataIndex: 'confidence', width: 90 },
          ]}
        />
      ),
    },
    {
      key: 'rules',
      label: label('rules'),
      icon: <SafetyCertificateOutlined />,
      count: rules.length,
      children: (
        <Table
          {...tableProps}
          dataSource={filtered(rules)}
          expandable={{
            rowExpandable: row => !!row.rule_definition,
            expandedRowRender: row => expandedText(label('description'), row.rule_definition),
          }}
          columns={[
            {
              title: label('rules'),
              dataIndex: 'rule_name',
              render: (v?: string) => <span className={styles.nameText}>{v || '—'}</span>,
            },
            { title: label('type'), dataIndex: 'rule_type', width: 160 },
            { title: label('priority'), dataIndex: 'priority', width: 100 },
            { title: label('status'), dataIndex: 'status', width: 140, render: statusBadge },
            {
              title: label('operations'),
              width: 110,
              render: (_, row: SemanticRule) => (
                <Button
                  type='text'
                  disabled={!!busy}
                  loading={busy === `rule-${row.id}`}
                  onClick={() =>
                    runAction(`rule-${row.id}`, () =>
                      toggleRule(row.id, row.status === 'active' ? 'inactive' : 'active'),
                    )
                  }
                >
                  {label(row.status === 'active' ? 'disable' : 'enable')}
                </Button>
              ),
            },
          ]}
        />
      ),
    },
  ];
  const activeItem = tabItems.find(item => item.key === activeTab)!;
  const activeRows = { catalog: tables, entries, metrics, examples, relations, rules }[activeTab] as (
    | SemanticTable
    | SemanticEntry
    | SemanticMetric
    | SemanticExample
    | SemanticRelation
    | SemanticRule
  )[];
  const statuses = Array.from(new Set(activeRows.flatMap(row => ('status' in row ? [row.status] : []))));
  const resultCount = filtered(activeRows).length;

  return (
    <ConstructLayout>
      <div className={styles.page}>
        <div className={styles.content}>
          <div className={styles.back}>
            <Button
              type='text'
              icon={<ArrowLeftOutlined />}
              onClick={() => {
                setSearch('');
                setStatusFilter('all');
                router.push('/construct/semantic');
              }}
            >
              {label('back')}
            </Button>
          </div>
          <header className={styles.header}>
            <div className={styles.heading}>
              <span className={styles.emblem}>
                <DatabaseOutlined />
              </span>
              <div>
                <div className={styles.titleRow}>
                  <h1 className={styles.title}>{space?.conn_name || space?.conn_id || `#${dsId}`}</h1>
                  {space && statusBadge(space.status)}
                </div>
                <p className={styles.subtitle}>
                  {label('title')}
                  {space && <> · {space.db_type.toUpperCase()}</>}
                </p>
              </div>
            </div>
            <div className={styles.actions}>
              <Button
                icon={<SyncOutlined />}
                loading={busy === 'sync'}
                disabled={!!busy}
                onClick={() => runAction('sync', () => doSync(dsId))}
              >
                {label('sync')}
              </Button>
              <Button
                type='primary'
                icon={<ThunderboltOutlined />}
                loading={busy === 'drafts'}
                disabled={!!busy}
                onClick={() => runAction('drafts', () => doDrafts(dsId))}
              >
                {label('drafts')}
              </Button>
            </div>
          </header>
          {coverage &&
            stats([
              { title: label('table_count'), value: coverage.tables },
              { title: label('whitelist'), value: coverage.whitelisted },
              { title: label('annotated'), value: coverage.tables_annotated },
              { title: label('coverage'), value: coverage.coverage_pct, suffix: '%' },
              { title: label('pending'), value: coverage.entries?.draft ?? 0 },
              { title: label('published'), value: coverage.metrics?.published ?? 0 },
            ])}
          <section className={styles.panel}>
            <nav className={styles.nav} role='tablist' aria-label={label('title')}>
              {tabItems.map((item, index) => (
                <button
                  key={item.key}
                  type='button'
                  role='tab'
                  id={`semantic-tab-${item.key}`}
                  aria-selected={item.key === activeTab}
                  aria-controls='semantic-tab-panel'
                  tabIndex={item.key === activeTab ? 0 : -1}
                  onClick={() => switchTab(item.key)}
                  onKeyDown={event => onTabKeyDown(event, index)}
                  className={styles.tab}
                >
                  <span aria-hidden='true'>{item.icon}</span>
                  {item.label}
                  <span className={styles.count}>{item.count}</span>
                </button>
              ))}
            </nav>
            <div className={styles.toolbar}>
              <div>
                <h2 className={styles.sectionTitle}>
                  {activeItem.label} <span className={styles.count}>{label('results', { count: resultCount })}</span>
                </h2>
                <p className={styles.subtitle}>{label(`${activeTab}_hint`)}</p>
              </div>
              <div className={styles.tools}>
                <Input
                  className={styles.search}
                  prefix={<SearchOutlined className={styles.muted} />}
                  placeholder={label('search', { name: activeItem.label })}
                  aria-label={label('search', { name: activeItem.label })}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  allowClear
                />
                {statuses.length > 0 && (
                  <Select
                    className={styles.statusFilter}
                    aria-label={label('status')}
                    value={statusFilter}
                    onChange={setStatusFilter}
                    options={[
                      { value: 'all', label: label('all_status') },
                      ...statuses.map(status => ({ value: status, label: statusLabel(status) })),
                    ]}
                  />
                )}
                {(search || statusFilter !== 'all') && (
                  <Button
                    type='text'
                    onClick={() => {
                      setSearch('');
                      setStatusFilter('all');
                    }}
                  >
                    {label('clear')}
                  </Button>
                )}
              </div>
            </div>
            <div role='tabpanel' id='semantic-tab-panel' aria-labelledby={`semantic-tab-${activeTab}`}>
              {activeItem.children}
            </div>
          </section>
          <Drawer
            rootClassName={styles.dialog}
            open={metricOpen}
            loading={metricLoading}
            onClose={() => {
              metricRequest.current += 1;
              setMetricOpen(false);
            }}
            title={citedMetric?.name ?? label('metric_drawer')}
            width='min(640px, 100vw)'
          >
            {citedMetric && <SemanticSourceDetail key={citedMetric.key} source={citedMetric} />}
            {metricError && <Typography.Text type='warning'>{label('metric_error')}</Typography.Text>}
          </Drawer>
        </div>
      </div>
    </ConstructLayout>
  );
};

export default SemanticCenter;
