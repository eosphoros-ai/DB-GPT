import { filterPublicDashboard, getPublicDashboard } from '@/client/api';
import { dashboardAntdTokens, interfaceThemeVariables } from '@/lib/interface-tokens';
import { DashboardFilters, DashboardRenderer } from '@/new-components/dashboard';
import DashboardDataFreshness from '@/new-components/dashboard/DashboardDataFreshness';
import styles from '@/new-components/dashboard/DashboardWorkspace.module.css';
import { dashboardThemeCssVariables, resolveDashboardTheme } from '@/new-components/dashboard/dashboard-appearance';
import { DashboardSnapshot, PublicDashboardSnapshot } from '@/types/dashboard';
import { FilterOutlined, LockOutlined } from '@ant-design/icons';
import { Alert, ConfigProvider, Spin, theme as antdTheme } from 'antd';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';

export default function DashboardSharePage() {
  const router = useRouter();
  const token = typeof router.query.token === 'string' ? router.query.token : null;
  const [published, setPublished] = useState<PublicDashboardSnapshot | null>(null);
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [filters, setFilters] = useState<Record<string, unknown>>({});
  const [filterTouched, setFilterTouched] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [unsupportedWidgetIds, setUnsupportedWidgetIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filterError, setFilterError] = useState<string | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    if (!token) return;
    getPublicDashboard(token)
      .then(response => {
        const next = response.data.data;
        setPublished(next);
        setSnapshot(next.snapshot);
        setFilterError(next.refresh_error || null);
        setFilters(next.snapshot.filters);
        setUnsupportedWidgetIds(
          next.data_mode !== 'live' && next.schema.filters.length > 0
            ? next.schema.widgets.filter(widget => !widget.publication).map(widget => widget.id)
            : [],
        );
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : '分享链接无效或已失效'));
  }, [token]);

  useEffect(() => {
    if (!token || !published || !filterTouched) return;
    const sequence = ++requestSequence.current;
    const timer = window.setTimeout(() => {
      setFiltering(true);
      setFilterError(null);
      filterPublicDashboard(token, filters)
        .then(response => {
          if (sequence !== requestSequence.current) return;
          setSnapshot(response.data.data.snapshot);
          setFilterError(response.data.data.refresh_error || null);
          setUnsupportedWidgetIds(response.data.data.unsupported_widget_ids);
        })
        .catch(reason => {
          if (sequence !== requestSequence.current) return;
          setFilterError(reason instanceof Error ? reason.message : '发布快照筛选失败');
        })
        .finally(() => {
          if (sequence === requestSequence.current) setFiltering(false);
        });
    }, 180);
    return () => window.clearTimeout(timer);
  }, [filterTouched, filters, published, token]);

  useEffect(() => {
    if (published?.data_mode !== 'live') return;
    const refresh = () => {
      if (!document.hidden) {
        setFilterTouched(true);
        setFilters(current => ({ ...current }));
      }
    };
    const timer = window.setInterval(refresh, Math.max(60, published.refresh_interval || 60) * 1000);
    window.addEventListener('focus', refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', refresh);
    };
  }, [published?.data_mode, published?.refresh_interval]);

  if (error)
    return (
      <div className={styles.pageState}>
        <Alert type='error' showIcon message='无法打开分享看板' description={error} />
      </div>
    );
  if (!published)
    return (
      <div className={styles.pageState}>
        <div className='flex items-center gap-2 text-sm text-[var(--app-muted)]'>
          <Spin size='large' />
          <span>正在读取已发布快照…</span>
        </div>
      </div>
    );

  if (!snapshot) return null;
  const { schema } = published;
  const visualTheme = resolveDashboardTheme(schema.dashboard.theme);
  const filterScopes = Object.fromEntries(
    schema.filters.map(filter => [
      filter.id,
      schema.widgets
        .filter(widget => {
          if (Object.prototype.hasOwnProperty.call(widget.query.filter_parameters || {}, filter.id)) return true;
          return Boolean(
            widget.query.federation?.sources.some(source =>
              Object.prototype.hasOwnProperty.call(source.filter_parameters || {}, filter.id),
            ),
          );
        })
        .map(widget => widget.title),
    ]),
  );
  return (
    <ConfigProvider
      theme={{
        algorithm: visualTheme.mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        inherit: false,
        token: dashboardAntdTokens(visualTheme),
      }}
    >
      <div
        className={styles.publicRoot}
        data-dashboard-theme={visualTheme.id}
        data-dashboard-mode={visualTheme.mode}
        style={{ ...interfaceThemeVariables(visualTheme), ...dashboardThemeCssVariables(visualTheme) }}
      >
        <Head>
          <title>{schema.dashboard.title} · DB-GPT</title>
          <meta name='theme-color' content={visualTheme.canvas} />
        </Head>
        <header className={styles.publicTopbar}>
          <div className={styles.brandGroup}>
            <div className={styles.brandMark} aria-hidden='true'>
              {schema.dashboard.title.trim().slice(0, 1).toUpperCase() || 'D'}
            </div>
            <div className={styles.titleBlock}>
              <div className={styles.publicTitleRow}>
                <h1 className={styles.publicTitle}>{schema.dashboard.title}</h1>
                <span className={styles.snapshotTag}>
                  {published.data_mode === 'live'
                    ? '持续更新'
                    : published.is_latest_link
                      ? '最新版公开链接'
                      : '历史快照'}
                </span>
              </div>
              <p className={styles.publicDescription}>{schema.dashboard.description}</p>
            </div>
          </div>
          <div className={styles.publicMetaRow}>
            <span>发布版本 {published.published_revision}</span>
            <span>粒度：{schema.metric_context.grain || '未说明'}</span>
            <DashboardDataFreshness schema={schema} snapshot={snapshot} />
            <span>{new Date(published.published_at).toLocaleString()}</span>
          </div>
        </header>
        <section className={`${styles.filterBar} ${styles.publicFilterBar}`} aria-label='分享页筛选条'>
          <div className={styles.filterTitle}>
            <FilterOutlined className={styles.filterTitleIcon} />
            全局筛选
          </div>
          <div className={styles.filterBody}>
            <DashboardFilters
              filters={schema.filters}
              values={filters}
              scopeByFilter={filterScopes}
              variant='bar'
              onChange={next => {
                setFilters(next);
                setFilterTouched(true);
              }}
              onReset={next => {
                setFilters(next);
                setFilterTouched(true);
              }}
            />
          </div>
          <div className={styles.filterActions}>
            <span className={styles.liveBadge}>
              <span className={styles.liveDot} /> {published.data_mode === 'live' ? '每分钟更新' : '快照联动'}
            </span>
          </div>
        </section>
        <main className={styles.publicCanvas}>
          <div className={styles.publicContent}>
            {published.schema.filters.length > 0 && (
              <div className='flex items-center gap-2 text-xs text-[var(--app-accent)]'>
                {filtering && <Spin size='small' />}
                <span>
                  {published.data_mode === 'live'
                    ? '布局与查询固定，数据持续更新。筛选会联动本次刷新后的数据。'
                    : '可调整筛选条件；结果只在发布时冻结的数据集上计算，不会连接生产数据库。'}
                </span>
              </div>
            )}
            {!!unsupportedWidgetIds.length && (
              <Alert
                type='warning'
                showIcon
                message='这个发布版本不能完整响应筛选'
                description={`以下组件发布时没有冻结筛选数据，只能保持当时的结果：${unsupportedWidgetIds.join(
                  '、',
                )}。请让看板所有者完成发布筛选配置后重新发布一个新版本。`}
              />
            )}
            {!!filterError && (
              <Alert
                type='error'
                showIcon
                message={published.data_mode === 'live' ? '数据更新暂时不可用' : '筛选发布快照失败'}
                description={`${filterError}。已保留上一次成功显示的结果。`}
              />
            )}
            <DashboardRenderer schema={schema} snapshot={snapshot} />
            <footer className={styles.snapshotNotice}>
              <LockOutlined />
              {published.data_mode === 'live'
                ? '只读持续更新分享 · 数据由发布者授权查询 · 每分钟最多更新一次；原数据库新增或修改后会在这里体现。'
                : '这是发布时保存的只读数据快照；打开此页面不会连接或查询原始数据库。'}
            </footer>
          </div>
        </main>
      </div>
    </ConfigProvider>
  );
}
