import { apiInterceptors } from '@/client/api';
import {
  getSemanticColumns,
  getSemanticEntries,
  getSemanticRelations,
  getSemanticSpace,
  getSemanticTables,
  type SemanticEntry,
  type SemanticRelation,
  type SemanticTable,
} from '@/client/api/semantic';
import MarkdownContext from '@/new-components/common/MarkdownContext';
import {
  decodeSemanticValue,
  matchSemanticSource,
  semanticCenterLink,
  splitSemanticReferenceSection,
  type QuerySource,
  type SemanticReadGap,
  type SemanticSource,
} from '@/utils/semantic-provenance';
import {
  ApartmentOutlined,
  BookOutlined,
  DatabaseOutlined,
  DownOutlined,
  LinkOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Alert, Button, Descriptions, Drawer, Empty, Spin, Tabs, Tag } from 'antd';
import Link from 'next/link';
import { useEffect, useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import QueryArtifactBlock from './QueryArtifactBlock';

export function SemanticSourceDetail({
  source,
  initialTab = 'definition',
}: {
  source: SemanticSource;
  initialTab?: 'definition' | 'lineage';
}) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<string>(initialTab);
  const [field, setField] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [related, setRelated] = useState<{
    entries: SemanticEntry[];
    tables: SemanticTable[];
    relations: SemanticRelation[];
    targets: Record<number, string>;
  } | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setRelated(null);
    setError(false);
    (async () => {
      try {
        const [spaceError, space] = await apiInterceptors(getSemanticSpace(source.dsId));
        if (spaceError || space?.conn_id !== source.connId) throw new Error('scope');
        const responses = await Promise.all([
          apiInterceptors(getSemanticEntries(source.dsId, 'published')),
          apiInterceptors(getSemanticTables(source.dsId)),
          apiInterceptors(getSemanticRelations(source.dsId)),
        ]);
        if (responses.some(r => r[0])) throw new Error('related');
        const tables = responses[1][1] ?? [];
        const definition = decodeSemanticValue(source.snapshot.metric_definition) ?? {};
        const sourceTables = new Set<string>(
          source.kind === 'metric'
            ? (definition.lineage?.sources ?? [])
                .filter((s: unknown) => typeof s === 'string')
                .map((s: string) => s.split('.')[0])
            : [source.tableName],
        );
        const columns = await Promise.all(
          tables
            .filter(table => sourceTables.has(table.table_name))
            .map(async table => {
              const [err, rows] = await apiInterceptors(getSemanticColumns(table.id, source.dsId));
              if (err) throw new Error('columns');
              return (rows ?? []).map(c => [c.id, `${table.table_name}.${c.column_name}`] as const);
            }),
        );
        if (!cancelled)
          setRelated({
            entries: responses[0][1] ?? [],
            tables,
            relations: responses[2][1] ?? [],
            targets: Object.fromEntries(columns.flat()),
          });
      } catch {
        if (!cancelled) setError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source, retry]);

  const row = source.snapshot;
  const definition = decodeSemanticValue(row.metric_definition ?? row.entry_definition) ?? {};
  const sources: string[] = Array.isArray(definition.lineage?.sources)
    ? definition.lineage.sources.filter((s: unknown) => typeof s === 'string')
    : [];
  const tableNames = new Set(source.kind === 'metric' ? sources.map(s => s.split('.')[0]) : [source.tableName]);
  const business =
    related?.entries.filter(
      entry =>
        (!field || related.targets[entry.target_id ?? -1] === field) &&
        (entry.entry_type === 'column'
          ? source.kind === 'metric'
            ? sources.includes(related.targets[entry.target_id ?? -1])
            : related.targets[entry.target_id ?? -1]?.startsWith(`${source.tableName}.`)
          : related.tables.some(table => table.id === entry.target_id && tableNames.has(table.table_name))),
    ) ?? [];
  const relations =
    related?.relations.filter(relation =>
      related.tables.some(
        table =>
          tableNames.has(table.table_name) &&
          (table.id === relation.left_table_id || table.id === relation.right_table_id),
      ),
    ) ?? [];
  const value = (v: unknown) => (typeof v === 'string' ? v : JSON.stringify(v, null, 2));
  const block = (title: string, v: unknown) =>
    v != null && v !== '' ? (
      <div className='mb-4' key={title}>
        <div className='mb-1 text-xs text-gray-500'>{title}</div>
        <pre className='whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-3 text-sm dark:bg-white/5'>
          {value(v)}
        </pre>
      </div>
    ) : null;
  const aliases = (raw: unknown) => {
    const names = decodeSemanticValue(raw);
    return Array.isArray(names) && names.length > 0 ? (
      <div className='mt-2 flex flex-wrap gap-1'>
        {names
          .filter(name => typeof name === 'string')
          .map(name => (
            <Tag key={name}>{name}</Tag>
          ))}
      </div>
    ) : null;
  };
  const relatedStatus = error ? (
    <Alert
      type='warning'
      showIcon
      message={t('semantic_provenance_related_error')}
      action={
        <Button size='small' aria-label={t('semantic_provenance_retry')} onClick={() => setRetry(n => n + 1)}>
          {t('semantic_provenance_retry')}
        </Button>
      }
    />
  ) : !related ? (
    <Spin />
  ) : null;
  return (
    <div className='text-gray-800 dark:text-gray-200'>
      <div className='mb-4 flex flex-wrap items-center gap-2'>
        <Tag color='blue'>{source.connId}</Tag>
        {source.version && (
          <Tag color='green'>
            {t('semantic_provenance_cited_version')} v{source.version}
          </Tag>
        )}
        <span className='text-xs text-gray-500'>{t('semantic_provenance_snapshot')}</span>
      </div>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: 'definition',
            label: t(
              source.kind === 'metric' ? 'semantic_provenance_metric_definition' : 'semantic_provenance_source_detail',
            ),
            children: (
              <div>
                {block(
                  t(
                    source.kind === 'metric'
                      ? 'semantic_provenance_metric_description'
                      : 'semantic_provenance_business_description',
                  ),
                  row.metric_comment ?? row.entry_comment ?? row.table_comment,
                )}
                {block(t('semantic_provenance_formula'), row.formula)}
                {Array.isArray(decodeSemanticValue(row.base_metrics)) &&
                  decodeSemanticValue(row.base_metrics).length > 0 && (
                    <div className='mb-4'>
                      <div className='mb-2 text-xs text-gray-500'>{t('semantic_provenance_base_metrics')}</div>
                      {decodeSemanticValue(row.base_metrics)
                        .filter((name: unknown) => typeof name === 'string')
                        .map((name: string) => (
                          <Link
                            key={name}
                            href={`/construct/semantic?ds=${source.dsId}&tab=metrics`}
                            target='_blank'
                            className='mr-2 inline-flex items-center gap-1 text-blue-600'
                          >
                            {name}
                            <LinkOutlined />
                          </Link>
                        ))}
                    </div>
                  )}
                {definition.unit && (
                  <Descriptions
                    size='small'
                    column={1}
                    className='mb-4'
                    items={[
                      {
                        key: 'unit',
                        label: t('semantic_provenance_unit'),
                        children:
                          definition.unit === 'CNY_cent' ? t('semantic_provenance_cny_cent') : String(definition.unit),
                      },
                      {
                        key: 'timezone',
                        label: t('semantic_provenance_timezone'),
                        children: definition.timezone ?? '—',
                      },
                      {
                        key: 'window',
                        label: t('semantic_provenance_window'),
                        children: Array.isArray(definition.window) ? definition.window.join(' → ') : '—',
                      },
                      {
                        key: 'time',
                        label: t('semantic_provenance_attribution'),
                        children:
                          (definition.time_field ??
                            [
                              definition.payment_attribution === 'payment event month'
                                ? t('semantic_provenance_payment_month')
                                : definition.payment_attribution,
                              definition.refund_attribution === 'refund event month'
                                ? t('semantic_provenance_refund_month')
                                : definition.refund_attribution,
                            ]
                              .filter(Boolean)
                              .join(' · ')) ||
                          '—',
                      },
                      {
                        key: 'freight',
                        label: t('semantic_provenance_freight'),
                        children:
                          typeof definition.freight_included === 'boolean'
                            ? definition.freight_included
                              ? t('semantic_provenance_freight_included')
                              : t('semantic_provenance_freight_excluded')
                            : '—',
                      },
                    ]}
                  />
                )}
                {block(t('semantic_provenance_filters'), definition.filters)}
                {block(t('semantic_provenance_scope'), definition.scope ?? definition.meaning)}
                {block('SQL', definition.sql)}
                {source.kind === 'table' && block(t('semantic_provenance_columns'), row.columns)}
                {source.kind === 'business' && aliases(row.synonyms)}
                <Link href={semanticCenterLink(source)} target='_blank' className='text-blue-600'>
                  <LinkOutlined /> {t('semantic_provenance_open_center')}
                </Link>
              </div>
            ),
          },
          {
            key: 'lineage',
            label: t('semantic_provenance_lineage'),
            children: (
              <div>
                <div className='mb-3 text-sm font-medium'>{t('semantic_provenance_field_dependencies')}</div>
                {sources.length ? (
                  <div className='mb-4 rounded-xl border border-blue-100 p-4 dark:border-blue-900'>
                    <div className='mb-3 text-xs text-gray-500'>{t('semantic_provenance_dependencies_hint')}</div>
                    <div className='flex flex-wrap gap-2'>
                      {sources.map(field => (
                        <button
                          type='button'
                          key={field}
                          aria-label={field}
                          onClick={() => {
                            setField(field);
                            setTab('business');
                          }}
                          className='rounded-md border border-blue-100 px-2 py-1 text-xs text-blue-700 dark:border-blue-800 dark:text-blue-300'
                        >
                          {field} <LinkOutlined />
                        </button>
                      ))}
                    </div>
                    <div className='my-2 text-center text-blue-500'>↓</div>
                    <div className='text-center font-medium'>
                      {source.name} · v{source.version}
                    </div>
                    {block(t('semantic_provenance_grain'), definition.lineage?.grain)}
                  </div>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('semantic_provenance_no_dependencies')} />
                )}
                <div className='mb-3 text-sm font-medium'>{t('semantic_provenance_table_relationships')}</div>
                {relatedStatus}
                {related &&
                  (relations.length ? (
                    relations.map(relation => (
                      <div
                        key={relation.id}
                        className='mb-2 rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700'
                      >
                        <div>
                          {related.targets[relation.left_column_id ?? -1] ?? relation.join_condition}
                          {' → '}
                          {related.targets[relation.right_column_id ?? -1] ?? ''}
                        </div>
                        <Tag>{relation.relation_type}</Tag>
                      </div>
                    ))
                  ) : (
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={t('semantic_provenance_no_relationships')}
                    />
                  ))}
                <Link href={semanticCenterLink(source, 'relations')} target='_blank' className='text-blue-600'>
                  {t('semantic_provenance_open_relationships')}
                </Link>
              </div>
            ),
          },
          {
            key: 'business',
            label: t('semantic_provenance_business'),
            children: (
              <div>
                <div className='mb-3 text-xs text-gray-500'>{t('semantic_provenance_business_hint')}</div>
                {relatedStatus}
                {field && (
                  <Button size='small' className='mb-3' onClick={() => setField(null)}>
                    {t('semantic_provenance_all_fields')}
                  </Button>
                )}
                {related &&
                  (business.length ? (
                    business.map(entry => (
                      <div key={entry.id} className='mb-3 rounded-xl border border-gray-200 p-3 dark:border-gray-700'>
                        <div className='font-medium'>
                          {entry.entry_name} <Tag>v{entry.publish_version}</Tag>
                        </div>
                        <div className='my-1 text-xs text-gray-500'>
                          {related.targets[entry.target_id ?? -1] ??
                            related.tables.find(t => t.id === entry.target_id)?.table_name}
                        </div>
                        <div className='text-sm'>{entry.entry_comment}</div>
                        {aliases(entry.synonyms)}
                      </div>
                    ))
                  ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('semantic_provenance_no_business')} />
                  ))}
                <Link href={semanticCenterLink(source, 'entries')} target='_blank' className='text-blue-600'>
                  {t('semantic_provenance_open_business')}
                </Link>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

export default function SemanticProvenance({
  content,
  sources,
  streaming = false,
  mode = 'sources',
  querySources = [],
  readGaps = [],
}: {
  content: string;
  sources: SemanticSource[];
  streaming?: boolean;
  querySources?: QuerySource[];
  readGaps?: SemanticReadGap[];
  /** Keep answer links in place while mounting the source panel after artifacts. */
  mode?: 'answer' | 'sources';
}) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<SemanticSource | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<QuerySource | null>(null);
  const [detailTab, setDetailTab] = useState<'definition' | 'lineage'>('definition');
  const [queriesExpanded, setQueriesExpanded] = useState(false);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const sourcePanelId = useId();
  const queryListId = useId();
  const groups = (['metric', 'business', 'table'] as const).filter(k => sources.some(s => s.kind === k));
  const openSource = (source: SemanticSource, tab: 'definition' | 'lineage' = 'definition') => {
    setSelectedQuery(null);
    setDetailTab(tab);
    setSelected(source);
  };
  const sourceCount = sources.length + querySources.length;
  const { answer, notes } = useMemo(() => splitSemanticReferenceSection(content, sources), [content, sources]);
  const components = useMemo(
    () => ({
      code: ({ children, className, ...props }: any) => {
        const source = !className ? matchSemanticSource(String(children), sources) : undefined;
        return source ? (
          <button
            type='button'
            onClick={() => {
              setDetailTab('definition');
              setSelected(source);
            }}
            className='inline-flex items-center gap-1 rounded-md bg-blue-50 px-1.5 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
            aria-label={t('semantic_provenance_view_source', { name: source.name })}
          >
            <LinkOutlined />
            {children}
          </button>
        ) : (
          <code className={className} {...props}>
            {children}
          </code>
        );
      },
    }),
    [sources, t],
  );
  return (
    <>
      {mode === 'sources' && (sourceCount > 0 || readGaps.length > 0) && (
        <section
          aria-label={t('semantic_provenance_title')}
          className='not-prose mt-5 overflow-hidden rounded-2xl border border-gray-200/80 bg-white text-gray-800 dark:border-gray-700 dark:bg-[#1b2029] dark:text-gray-200'
        >
          <button
            type='button'
            aria-expanded={sourcesExpanded}
            aria-controls={sourcePanelId}
            aria-label={t(sourcesExpanded ? 'semantic_provenance_collapse' : 'semantic_provenance_expand')}
            onClick={() => setSourcesExpanded(value => !value)}
            className={`flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 focus-visible:outline-blue-500 dark:hover:bg-white/5 ${sourcesExpanded ? 'border-b border-gray-100 dark:border-gray-700/60' : ''}`}
          >
            <BookOutlined aria-hidden className='text-gray-400' />
            <span className='text-sm font-semibold'>{t('semantic_provenance_title')}</span>
            {sourceCount > 0 && (
              <span className='rounded bg-gray-100 px-1.5 py-0.5 text-[11px] tabular-nums text-gray-500 dark:bg-white/5 dark:text-gray-400'>
                {sourceCount}
              </span>
            )}
            <span className='ml-auto text-xs text-gray-500 dark:text-gray-400'>
              {t(sourcesExpanded ? 'semantic_provenance_collapse_short' : 'semantic_provenance_expand_short')}
            </span>
            <DownOutlined
              aria-hidden
              className={`text-[10px] text-gray-400 transition-transform ${sourcesExpanded ? 'rotate-180' : ''}`}
            />
          </button>
          <div id={sourcePanelId} hidden={!sourcesExpanded} className='space-y-5 p-4'>
            {groups.map(group => (
              <section key={group}>
                <h4 className='mb-2.5 flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400'>
                  {t(
                    group === 'metric'
                      ? 'semantic_provenance_metric_calibers'
                      : group === 'business'
                        ? 'semantic_provenance_business'
                        : 'semantic_provenance_tables',
                  )}
                  {' · '}
                  {sources.filter(s => s.kind === group).length}
                </h4>
                <div className={`grid grid-cols-1 gap-2 ${group === 'table' ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
                  {sources
                    .filter(s => s.kind === group)
                    .map(source => {
                      const fields = decodeSemanticValue(source.snapshot.metric_definition)?.lineage?.sources;
                      const fieldCount = Array.isArray(fields) ? fields.filter(f => typeof f === 'string').length : 0;
                      const name = `${source.name}${source.version ? ` v${source.version}` : ''}`;
                      return group === 'metric' ? (
                        <div
                          key={source.key}
                          className='min-w-0 rounded-xl border border-gray-200/80 bg-gray-50/50 dark:border-gray-700 dark:bg-white/[0.02]'
                        >
                          <button
                            type='button'
                            aria-label={t('semantic_provenance_view_source', { name })}
                            onClick={() => openSource(source)}
                            className='flex w-full items-center gap-2.5 rounded-t-xl px-3 py-3 text-left hover:bg-gray-100/70 focus-visible:outline-blue-500 dark:hover:bg-white/5'
                          >
                            <span className='flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500 dark:bg-indigo-500/10 dark:text-indigo-300'>
                              <ApartmentOutlined />
                            </span>
                            <span className='min-w-0 flex-1 truncate text-sm font-medium' title={source.name}>
                              {source.name}
                            </span>
                            {source.version && (
                              <span className='shrink-0 text-[11px] text-gray-400'>v{source.version}</span>
                            )}
                            <RightOutlined className='text-[10px] text-gray-400' />
                          </button>
                          <div className='flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-gray-100 px-3 py-2 text-xs dark:border-gray-700/60'>
                            <button
                              type='button'
                              onClick={() => openSource(source)}
                              className='text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-300'
                            >
                              {t('semantic_provenance_definition_action')}
                            </button>
                            {fieldCount > 0 && (
                              <button
                                type='button'
                                aria-label={t('semantic_provenance_view_lineage', { name })}
                                onClick={() => openSource(source, 'lineage')}
                                className='flex items-center gap-1.5 text-indigo-600 hover:text-indigo-500 dark:text-indigo-300'
                              >
                                <ApartmentOutlined />
                                {t('semantic_provenance_lineage_action')}
                                <span className='text-gray-400'>
                                  · {t('semantic_provenance_dependency_count', { count: fieldCount })}
                                </span>
                              </button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <button
                          type='button'
                          key={source.key}
                          aria-label={t('semantic_provenance_view_source', { name })}
                          onClick={() => openSource(source)}
                          className='flex min-w-0 items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-gray-50 focus-visible:outline-blue-500 dark:hover:bg-white/5'
                        >
                          {group === 'business' ? (
                            <BookOutlined className='text-teal-500 dark:text-teal-400' />
                          ) : (
                            <DatabaseOutlined className='text-gray-400' />
                          )}
                          <span className='min-w-0 flex-1'>
                            <span className='block truncate text-sm' title={source.name}>
                              {source.name}
                            </span>
                            {group === 'business' && source.tableName && (
                              <span className='block truncate text-[11px] text-gray-400'>
                                {source.tableName}
                                {source.columnName ? `.${source.columnName}` : ''}
                              </span>
                            )}
                          </span>
                          {source.version && <span className='text-[11px] text-gray-400'>v{source.version}</span>}
                          <RightOutlined className='text-[10px] text-gray-400' />
                        </button>
                      );
                    })}
                </div>
              </section>
            ))}
            {querySources.length > 0 && (
              <section>
                <h4 className='mb-2 text-xs font-medium text-gray-500 dark:text-gray-400'>
                  {t('semantic_provenance_queries')} · {querySources.length}
                </h4>
                <div id={queryListId} className='divide-y divide-gray-100 dark:divide-gray-700/60'>
                  {(queriesExpanded ? querySources : querySources.slice(0, 3)).map((source, index) => (
                    <button
                      type='button'
                      key={source.key}
                      aria-label={t('semantic_provenance_view_query', {
                        number: index + 1,
                        database: source.payload.db_name,
                      })}
                      onClick={() => {
                        setSelected(null);
                        setSelectedQuery(source);
                      }}
                      className='flex w-full min-w-0 items-center gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-gray-50 focus-visible:outline-blue-500 dark:hover:bg-white/5'
                    >
                      <span className='w-5 shrink-0 text-center font-mono text-[11px] text-gray-400'>
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className='min-w-0 flex-1'>
                        <span className='block truncate font-mono text-xs text-gray-600 dark:text-gray-300'>
                          {source.payload.sql.replace(/\s+/g, ' ')}
                        </span>
                        <span className='mt-0.5 block truncate text-[11px] text-gray-400'>
                          {source.payload.db_name}
                        </span>
                      </span>
                      <RightOutlined className='text-[10px] text-gray-400' />
                    </button>
                  ))}
                </div>
                {querySources.length > 3 && (
                  <button
                    type='button'
                    aria-expanded={queriesExpanded}
                    aria-controls={queryListId}
                    onClick={() => setQueriesExpanded(v => !v)}
                    className='mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-gray-50 py-2 text-xs text-gray-500 hover:bg-gray-100 dark:bg-white/5 dark:text-gray-400 dark:hover:bg-white/10'
                  >
                    {t(
                      queriesExpanded ? 'semantic_provenance_collapse_queries' : 'semantic_provenance_expand_queries',
                      { count: querySources.length - 3 },
                    )}
                    <DownOutlined
                      aria-hidden
                      className={`text-[10px] transition-transform ${queriesExpanded ? 'rotate-180' : ''}`}
                    />
                  </button>
                )}
              </section>
            )}
            {readGaps.length > 0 && (
              <details className='border-t border-gray-100 pt-3 text-xs text-gray-500 dark:border-gray-700/60 dark:text-gray-400'>
                <summary className='cursor-pointer'>
                  {t('semantic_provenance_read_gaps', { count: readGaps.length })}
                </summary>
                <p className='my-2 leading-relaxed'>{t('semantic_provenance_missing_definitions')}</p>
                <div className='space-y-2'>
                  {readGaps.map(gap => (
                    <div key={gap.key} className='flex flex-wrap gap-x-2 gap-y-1'>
                      <span>
                        {gap.connId} ·{' '}
                        {t(
                          gap.action === 'semantic_get_metadata'
                            ? 'semantic_provenance_tables'
                            : gap.action === 'semantic_search_business'
                              ? 'semantic_provenance_business'
                              : 'semantic_provenance_metrics',
                        )}{' '}
                        · {t(`semantic_provenance_status_${gap.status}`)}
                      </span>
                      {gap.dsId && (
                        <Link
                          href={`/construct/semantic?ds=${gap.dsId}&tab=${gap.action === 'semantic_search_business' ? 'entries' : gap.action === 'semantic_get_metadata' ? 'catalog' : 'metrics'}`}
                          target='_blank'
                          className='text-blue-600 dark:text-blue-300'
                        >
                          {t('semantic_provenance_open_center')}
                        </Link>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            )}
            {notes && !streaming && (
              <details className='border-t border-gray-100 pt-3 text-xs text-gray-500 dark:border-gray-700/60 dark:text-gray-400'>
                <summary className='cursor-pointer'>{t('semantic_provenance_notes')}</summary>
                <div className='prose prose-sm dark:prose-invert mt-2 max-w-none'>
                  <MarkdownContext components={components}>{notes}</MarkdownContext>
                </div>
              </details>
            )}
          </div>
        </section>
      )}
      {mode === 'answer' &&
        (streaming ? (
          <span className='whitespace-pre-wrap break-words'>{content}</span>
        ) : (
          <MarkdownContext components={components}>{answer}</MarkdownContext>
        ))}
      <Drawer
        open={!!selected || !!selectedQuery}
        onClose={() => {
          setSelected(null);
          setSelectedQuery(null);
        }}
        title={selectedQuery ? t('semantic_provenance_query_detail') : selected?.name}
        width='min(640px, 100vw)'
        styles={{ body: { padding: 20 } }}
      >
        {selected && (
          <SemanticSourceDetail key={`${selected.key}:${detailTab}`} source={selected} initialTab={detailTab} />
        )}
        {selectedQuery && (
          <div>
            <Alert className='mb-4' type='info' showIcon message={t('semantic_provenance_query_snapshot')} />
            <QueryArtifactBlock key={selectedQuery.key} payload={selectedQuery.payload} />
          </div>
        )}
      </Drawer>
    </>
  );
}
