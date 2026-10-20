import { interfaceThemeVariables } from '@/lib/interface-tokens';
import { DashboardLayoutItem, DashboardSchemaV1, DashboardSelectionTarget, DashboardSnapshot } from '@/types/dashboard';
import {
  AppstoreOutlined,
  BarChartOutlined,
  GlobalOutlined,
  LineChartOutlined,
  ShopOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { ConfigProvider, theme as antdTheme } from 'antd';
import { useEffect, useRef, useState, type RefObject } from 'react';
import ReactGridLayout, { Layout, useContainerWidth } from 'react-grid-layout';
import { dashboardThemeCssVariables, resolveDashboardTheme } from './dashboard-appearance';
import type { DashboardAnnotationDraft } from './dashboard-assistant';
import { catalogPresentation, catalogTheme, presentationNames } from './dashboard-catalog-presentation';
import { dashboardGridCompactor } from './dashboard-grid-interaction';
import sceneStyles from './DashboardCatalogScene.module.css';
import { DashboardResearchRail } from './DashboardResearchScene';
import researchStyles from './DashboardResearchScene.module.css';
import showcaseStyles from './DashboardShowcase.module.css';
import DashboardShowcaseControls, { DashboardMarketingRail } from './DashboardShowcaseControls';
import DashboardWidgetCard from './DashboardWidgetCard';
import DashboardWidgetDetail from './DashboardWidgetDetail';
import styles from './DashboardWorkspace.module.css';

interface DashboardRendererProps {
  schema: DashboardSchemaV1;
  snapshot?: DashboardSnapshot | null;
  editable?: boolean;
  selectedWidgetId?: string | null;
  selectedEditorMode?: 'visual' | 'query';
  loadingWidgetIds?: Set<string>;
  onSelectWidget?: (widgetId: string) => void;
  onEditWidget?: (widgetId: string) => void;
  onOpenWidgetQueryEditor?: (widgetId: string) => void;
  onRequestAgentWidgetConfiguration?: (widgetId: string, anchor: DOMRect) => void;
  agentConfigurationDisabled?: boolean;
  onRetryWidget?: (widgetId: string) => void;
  onLayoutChange?: (items: DashboardLayoutItem[]) => void;
  filters?: Record<string, unknown>;
  onChangeFilters?: (filters: Record<string, unknown>) => void;
  annotationMode?: boolean;
  annotationDrafts?: DashboardAnnotationDraft[];
  onEditAnnotationDraft?: (id: string, anchor: DOMRect) => void;
  onSelectAnnotationTarget?: (target: DashboardSelectionTarget, anchor: DOMRect) => void;
}

const toGridLayout = (items: DashboardLayoutItem[], chartIds: Set<string>): Layout =>
  items.map(item => ({
    i: item.widget_id,
    x: item.x,
    y: item.y,
    w: item.w,
    // Reserve enough room for the plot, legend and complete category labels.
    // Older generated schemas can have only five rows, leaving a nearly flat plot.
    h: chartIds.has(item.widget_id) && item.max_h == null ? Math.max(7, item.h) : item.h,
    minW: item.min_w ?? undefined,
    minH: chartIds.has(item.widget_id) && item.max_h == null ? Math.max(7, item.min_h || 0) : (item.min_h ?? undefined),
    maxW: item.max_w ?? undefined,
    maxH: item.max_h ?? undefined,
  }));

const fromGridLayout = (items: Layout): DashboardLayoutItem[] =>
  items.map(item => ({
    widget_id: item.i,
    x: item.x,
    y: item.y,
    w: item.w,
    h: item.h,
    min_w: item.minW,
    min_h: item.minH,
    max_w: item.maxW,
    max_h: item.maxH,
  }));

export default function DashboardRenderer({
  schema,
  snapshot,
  editable,
  selectedWidgetId,
  selectedEditorMode = 'visual',
  loadingWidgetIds = new Set(),
  onSelectWidget,
  onEditWidget,
  onOpenWidgetQueryEditor,
  onRequestAgentWidgetConfiguration,
  agentConfigurationDisabled = false,
  onRetryWidget,
  onLayoutChange,
  filters,
  onChangeFilters,
  annotationMode = false,
  annotationDrafts = [],
  onEditAnnotationDraft,
  onSelectAnnotationTarget,
}: DashboardRendererProps) {
  const { width, containerRef, mounted } = useContainerWidth({ initialWidth: 1200 });
  const mobile = width < 900;
  const presentation = catalogPresentation(schema);
  const branded = presentation === 'brand';
  const marketing = presentation === 'marketing';
  const research = !!presentation && ['clinical_insight', 'cardio_journal', 'voice_observatory'].includes(presentation);
  const journal = presentation === 'cardio_journal';
  const voice = presentation === 'voice_observatory';
  const wall = !!presentation && ['command', 'clinical', 'rural'].includes(presentation);
  const showcase = marketing || wall || research;
  const gridWidth = research
    ? width - (mobile ? 24 : journal ? 232 : 48)
    : branded && !mobile
      ? width - 176
      : marketing && !mobile
        ? width - 210
        : wall
          ? width - 24
          : width;
  const [detailId, setDetailId] = useState<string | null>(null);
  const detailWidget = schema.widgets.find(w => w.id === detailId);
  const gridRows = Math.max(1, ...schema.layouts.desktop.map(p => p.y + p.h));
  const theme = catalogTheme(
    resolveDashboardTheme(schema.dashboard.theme),
    presentation,
    schema.dashboard.theme?.overrides,
  );
  const sceneRef = useRef<HTMLDivElement>(null);
  const [fullscreenHeight, setFullscreenHeight] = useState(0);
  useEffect(() => {
    const sync = () =>
      setFullscreenHeight(document.fullscreenElement === containerRef.current ? window.innerHeight : 0);
    document.addEventListener('fullscreenchange', sync);
    window.addEventListener('resize', sync);
    return () => {
      document.removeEventListener('fullscreenchange', sync);
      window.removeEventListener('resize', sync);
    };
  }, [containerRef]);
  const positions = new Map(schema.layouts.desktop.map(item => [item.widget_id, item]));
  const orderedWidgets = [...schema.widgets].sort((left, right) => {
    const a = positions.get(left.id);
    const b = positions.get(right.id);
    return (a?.y ?? Infinity) - (b?.y ?? Infinity) || (a?.x ?? Infinity) - (b?.x ?? Infinity);
  });
  const cards = orderedWidgets.map(widget => {
    const metric = (widget.presentation?.visualization || widget.type) === 'kpi';
    return (
      <div
        key={widget.id}
        data-catalog-kind={metric ? 'metric' : 'chart'}
        className={mobile ? `${styles.mobileGridItem} ${metric ? styles.mobileMetricItem : ''}` : undefined}
      >
        <DashboardWidgetCard
          widget={widget}
          metricContext={schema.metric_context}
          result={snapshot?.widgets[widget.id]}
          loading={loadingWidgetIds.has(widget.id)}
          editable={editable}
          compact={wall || voice}
          selected={selectedWidgetId === widget.id}
          editorMode={selectedEditorMode}
          onSelect={() => onSelectWidget?.(widget.id)}
          onExpand={showcase ? () => setDetailId(widget.id) : undefined}
          onSelectData={
            showcase && !annotationMode && onChangeFilters && widget.style.map_region === 'china'
              ? datum => {
                  const field = widget.encoding.x || 'segment';
                  const value = String(datum[field] ?? '');
                  if (schema.filters.some(f => f.id === 'segment' && f.options.some(o => String(o.value) === value))) {
                    onChangeFilters({ ...(filters || snapshot?.filters || {}), segment: value });
                  }
                }
              : undefined
          }
          onEditWidget={() => onEditWidget?.(widget.id)}
          onOpenQueryEditor={() => onOpenWidgetQueryEditor?.(widget.id)}
          onRequestAgentConfiguration={anchor => onRequestAgentWidgetConfiguration?.(widget.id, anchor)}
          agentConfigurationDisabled={agentConfigurationDisabled}
          onRetry={() => onRetryWidget?.(widget.id)}
          annotationMode={annotationMode}
          annotationMarkers={annotationDrafts
            .map((draft, index) => ({
              id: draft.id,
              number: index + 1,
              content: draft.content,
              widgetId: draft.target.widget_id,
            }))
            .filter(item => item.widgetId === widget.id)}
          onEditAnnotationDraft={onEditAnnotationDraft}
          theme={theme}
          onSelectAnnotationTarget={(target, anchor) => onSelectAnnotationTarget?.(target, anchor)}
        />
      </div>
    );
  });

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: theme.primary,
          colorBgContainer: theme.card,
          colorFillAlter: theme.cardMuted,
          colorText: theme.text,
          colorTextSecondary: theme.muted,
          colorBorder: theme.border,
          colorBorderSecondary: theme.border,
        },
      }}
    >
      <div
        ref={containerRef as RefObject<HTMLDivElement>}
        className={`${styles.rendererRoot} ${presentation ? `${sceneStyles.scene} ${sceneStyles[presentation] || ''}` : ''} ${marketing || wall ? `${showcaseStyles.showcase} ${showcaseStyles[presentation!] || ''}` : ''} ${wall ? showcaseStyles.wall : ''} ${research ? `${researchStyles.research} ${researchStyles[presentation!] || ''}` : ''}`}
        data-catalog-presentation={presentation}
        data-brand-compact={branded || marketing ? mobile : undefined}
        data-research-compact={research ? mobile : undefined}
        data-dashboard-theme={theme.id}
        data-dashboard-mode={theme.mode}
        style={{ ...interfaceThemeVariables(theme), ...dashboardThemeCssVariables(theme) }}
      >
        {journal && (
          <DashboardResearchRail
            schema={schema}
            onNavigate={id => {
              const node = Array.from(
                sceneRef.current?.querySelectorAll<HTMLElement>('[data-dashboard-widget-id]') || [],
              ).find(n => n.dataset.dashboardWidgetId === id);
              node?.scrollIntoView({
                block: 'start',
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
              });
            }}
          />
        )}
        {marketing && (
          <DashboardMarketingRail
            onNavigate={id => {
              const node = Array.from(
                sceneRef.current?.querySelectorAll<HTMLElement>('[data-dashboard-widget-id]') || [],
              ).find(n => n.dataset.dashboardWidgetId === id);
              node?.scrollIntoView({
                block: 'center',
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
              });
            }}
          />
        )}
        {branded && (
          <aside className={sceneStyles.brandRail} aria-label='品牌看板导航'>
            <div className={sceneStyles.brandIdentity}>
              <span>
                <ShopOutlined />
              </span>
              <strong>Northwind</strong>
              <small>BUSINESS INTELLIGENCE</small>
            </div>
            <nav>
              {[
                { id: 'hero', label: '经营总览', icon: <AppstoreOutlined /> },
                { id: 'trend', label: '收入趋势', icon: <LineChartOutlined /> },
                { id: 'world', label: '全球市场', icon: <GlobalOutlined /> },
                { id: 'contribution', label: '品类贡献', icon: <BarChartOutlined /> },
                { id: 'customers', label: '客户规模', icon: <TeamOutlined /> },
              ]
                .filter(item => positions.has(item.id))
                .map(item => (
                  <button
                    type='button'
                    key={item.id}
                    onClick={() => {
                      const node = Array.from(
                        sceneRef.current?.querySelectorAll<HTMLElement>('[data-dashboard-widget-id]') || [],
                      ).find(node => node.dataset.dashboardWidgetId === item.id);
                      node?.scrollIntoView({
                        block: 'center',
                        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
                      });
                    }}
                  >
                    {item.icon}
                    {item.label}
                  </button>
                ))}
            </nav>
            <div className={sceneStyles.brandRailFooter}>
              Revenue. Markets. People.
              <br />
              经营数据，尽在此处。
            </div>
          </aside>
        )}
        {presentation && (
          <header className={sceneStyles.heading} data-catalog-heading>
            <span className={sceneStyles.eyebrow}>{presentationNames[presentation]}</span>
            <h2>{schema.dashboard.title}</h2>
            <p>{schema.dashboard.description}</p>
            {showcase && (
              <DashboardShowcaseControls
                schema={schema}
                snapshot={snapshot}
                rootRef={containerRef as RefObject<HTMLDivElement>}
                filters={filters}
                onChange={onChangeFilters}
              />
            )}
          </header>
        )}
        {presentation && ['timeline', 'story', 'dossier'].includes(presentation) && (
          <nav className={sceneStyles.chapters} aria-label='看板章节'>
            {orderedWidgets
              .filter(widget => widget.type !== 'kpi')
              .map((widget, index) => (
                <button
                  key={widget.id}
                  type='button'
                  onClick={() => {
                    const node = Array.from(
                      sceneRef.current?.querySelectorAll<HTMLElement>('[data-dashboard-widget-id]') || [],
                    ).find(item => item.dataset.dashboardWidgetId === widget.id);
                    node?.scrollIntoView({
                      block: 'center',
                      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
                    });
                  }}
                >
                  {String(index + 1).padStart(2, '0')} · {widget.title}
                </button>
              ))}
          </nav>
        )}
        <div ref={sceneRef} data-scene-content className={presentation ? sceneStyles.content : undefined}>
          {presentation === 'skill_tree' && !mobile && positions.has('total') && (
            <svg className={sceneStyles.tree} height={8 * (44 + theme.gap)} aria-hidden='true'>
              {['customers', 'regions'].map(id => {
                const root = positions.get('total')!;
                const child = positions.get(id);
                if (!child) return null;
                const x1 = ((root.x + root.w / 2) * width) / 12;
                const y1 = (root.y + root.h) * (44 + theme.gap) - theme.gap;
                const x2 = ((child.x + child.w / 2) * width) / 12;
                const y2 = child.y * (44 + theme.gap);
                return (
                  <path
                    key={id}
                    d={`M ${x1} ${y1} V ${(y1 + y2) / 2} H ${x2} V ${y2}`}
                    fill='none'
                    stroke={theme.primary}
                    strokeOpacity='.45'
                    strokeWidth='1.5'
                  />
                );
              })}
            </svg>
          )}
          {mobile ? (
            <div className={`${styles.mobileGrid} ${presentation === 'receipt' ? sceneStyles.paperList : ''}`}>
              {cards}
            </div>
          ) : mounted ? (
            <ReactGridLayout
              width={gridWidth}
              layout={toGridLayout(
                schema.layouts.desktop,
                new Set(
                  schema.widgets
                    .filter(widget => !['kpi', 'table'].includes(widget.presentation?.visualization || widget.type))
                    .map(widget => widget.id),
                ),
              )}
              gridConfig={{
                cols: 12,
                rowHeight:
                  wall || voice
                    ? Math.max(
                        16,
                        Math.min(
                          44,
                          (fullscreenHeight ? fullscreenHeight - 240 : gridWidth * 0.61 - 140) / gridRows - theme.gap,
                        ),
                      )
                    : theme.density === 'compact'
                      ? 42
                      : theme.density === 'spacious'
                        ? 48
                        : 44,
                margin: [theme.gap, theme.gap],
                containerPadding: [0, 0],
              }}
              dragConfig={{ enabled: !!editable, handle: '.dashboard-widget-drag-handle' }}
              resizeConfig={{ enabled: !!editable }}
              compactor={dashboardGridCompactor}
              onDragStop={(layout: Layout) => onLayoutChange?.(fromGridLayout(layout))}
              onResizeStop={(layout: Layout) => onLayoutChange?.(fromGridLayout(layout))}
            >
              {cards}
            </ReactGridLayout>
          ) : null}
        </div>
        {showcase && detailWidget && (
          <DashboardWidgetDetail
            widget={detailWidget}
            result={snapshot?.widgets[detailWidget.id]}
            schema={schema}
            theme={theme}
            onClose={() => setDetailId(null)}
            getContainer={() => containerRef.current || document.body}
          />
        )}
        {presentation && !!schema.metric_context.source_notes.length && (
          <details className={sceneStyles.notes}>
            <summary>数据来源与计算口径</summary>
            {schema.metric_context.source_notes.map(note => (
              <p key={note}>{note}</p>
            ))}
          </details>
        )}
      </div>
    </ConfigProvider>
  );
}
