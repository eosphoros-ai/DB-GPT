import { AppstoreOutlined, CheckCircleFilled, LoadingOutlined, WarningOutlined } from '@ant-design/icons';
import { Button, Progress, Tag } from 'antd';
import { getDashboardLayoutTemplate } from './dashboard-layout-templates';
import { LAYOUT_TEMPLATES_ENABLED } from './dashboard-release-features';

export type DashboardGenerationStatus = 'planning' | 'awaiting_confirmation' | 'generating' | 'created' | 'failed';
export type DashboardWidgetGenerationStatus = 'running' | 'validated' | 'failed';

export interface DashboardPlanSummary {
  business_theme?: string;
  audience?: string;
  decision_goal?: string;
  analysis_logic?: string[];
  layout_rationale?: string;
  layout_template?: string | null;
  filter_strategy?: string;
  metrics?: string[];
  dimensions?: string[];
  filters?: Array<{ id: string; label?: string; type?: string }>;
  widgets?: Array<{
    id: string;
    title: string;
    type: string;
    metric?: string;
    dimensions?: string[];
    analysis_level?: number;
    rationale?: string;
    layout?: { width?: string; height?: string } | null;
  }>;
}

export interface DashboardGenerationState {
  status: DashboardGenerationStatus;
  title: string;
  activeWidgetTitle?: string;
  totalWidgets: number;
  validatedWidgets: number;
  failedWidgets: number;
  widgetStates: Record<string, DashboardWidgetGenerationStatus>;
  dashboardId?: string;
  sourceTurnId?: string;
  assetState?: 'generated' | 'saved';
  editorPath?: string;
  dataSourceId?: string;
  currentRevision?: number;
  confirmationPrompt?: string;
  errorMessage?: string;
  revisionPrompt?: string;
  plan?: DashboardPlanSummary;
  generationId?: string;
  limitSeconds?: number;
  stageLabel?: string;
  validatedWidgetIds?: string[];
  pendingWidgetIds?: string[];
  savedWidgetIds?: string[];
  savedRevision?: number;
  retryHint?: string;
}

interface DashboardGenerationCardProps {
  state: DashboardGenerationState;
  onOpen: () => void;
  onConfirm?: (state: DashboardGenerationState) => void;
  onRevise?: () => void;
  busy?: boolean;
}

const DashboardGenerationCard = ({
  state,
  onOpen,
  onConfirm,
  onRevise,
  busy = false,
}: DashboardGenerationCardProps) => {
  const completed = state.validatedWidgets + state.failedWidgets;
  const percent = state.totalWidgets > 0 ? Math.round((completed / state.totalWidgets) * 100) : 0;
  const created = state.status === 'created';
  const failed = state.status === 'failed';
  const awaitingConfirmation = state.status === 'awaiting_confirmation';
  const orderedWidgets = [...(state.plan?.widgets || [])].sort(
    (left, right) => (left.analysis_level || 3) - (right.analysis_level || 3),
  );
  const widgetTitles = (ids: string[]) =>
    ids.map(id => state.plan?.widgets?.find(widget => widget.id === id)?.title || id).join('、') || '无';

  return (
    <div className='mt-3 rounded-xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm dark:border-blue-900/50 dark:from-blue-950/30 dark:to-[#1a1b1e]'>
      <div className='flex items-start justify-between gap-3'>
        <div className='flex min-w-0 items-start gap-3'>
          <div className='flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white'>
            <AppstoreOutlined />
          </div>
          <div className='min-w-0'>
            <div className='truncate text-sm font-semibold text-gray-900 dark:text-gray-100'>{state.title}</div>
            <div className='mt-1 text-xs text-gray-500 dark:text-gray-400'>
              {failed
                ? state.errorMessage || '本次生成未完成，已保存的规划或草稿仍保留。'
                : created
                  ? state.assetState === 'saved'
                    ? '看板已保存，可在当前任务中继续编辑'
                    : '可恢复的看板草稿已生成，保存后进入资产库'
                  : awaitingConfirmation
                    ? 'SQL 尚未生成，请先确认指标、维度、筛选器和图表计划'
                    : state.status === 'planning'
                      ? '正在校验指标、维度和筛选器'
                      : state.activeWidgetTitle
                        ? `正在校验：${state.activeWidgetTitle}`
                        : '正在生成并试运行组件查询'}
            </div>
          </div>
        </div>
        {created ? (
          <CheckCircleFilled className='mt-1 text-lg text-emerald-500' />
        ) : awaitingConfirmation || failed ? (
          <WarningOutlined className='mt-1 text-lg text-amber-500' />
        ) : (
          <LoadingOutlined spin className='mt-1 text-lg text-blue-500' />
        )}
      </div>

      {state.status === 'generating' && state.limitSeconds && (
        <div className='mt-2 text-xs text-gray-500'>
          本轮生成最多 {state.limitSeconds} 秒，超时将停止并保留规划，不会自动重试。
        </div>
      )}

      {failed && (
        <div
          role='alert'
          aria-label='看板生成未完成'
          className='mt-3 space-y-2 break-words text-xs text-gray-600 dark:text-gray-300'
        >
          {state.stageLabel && <div>停在：{state.stageLabel}</div>}
          {state.validatedWidgetIds && (
            <div>SQL 试运行通过（不等于已保存）：{widgetTitles(state.validatedWidgetIds)}</div>
          )}
          {state.pendingWidgetIds && <div>尚未通过试运行：{widgetTitles(state.pendingWidgetIds)}</div>}
          {state.savedRevision ? (
            <div>
              保留的草稿修订 {state.savedRevision}；已保存的可用组件：{widgetTitles(state.savedWidgetIds || [])}
            </div>
          ) : (
            state.generationId && <div>本轮未保存可用组件；候选 SQL 只在本轮内存中暂存。</div>
          )}
          {state.retryHint && <div>{state.retryHint}</div>}
          <div className='flex flex-wrap gap-2'>
            {state.editorPath && (
              <Button size='small' onClick={onOpen} disabled={busy}>
                查看保留的规划/草稿
              </Button>
            )}
            {state.revisionPrompt && onRevise && (
              <Button size='small' onClick={onRevise} disabled={busy}>
                修改计划后重试
              </Button>
            )}
          </div>
        </div>
      )}

      {state.totalWidgets > 0 && (
        <div className='mt-3'>
          {!awaitingConfirmation && !failed && (
            <Progress percent={created ? 100 : percent} size='small' showInfo={false} />
          )}
          <div className='mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500'>
            <span>
              {awaitingConfirmation
                ? `计划包含 ${state.totalWidgets} 个组件`
                : `已校验 ${state.validatedWidgets}/${state.totalWidgets}`}
            </span>
            {state.failedWidgets > 0 && (
              <Tag color='warning' className='m-0'>
                <WarningOutlined className='mr-1' />
                {state.failedWidgets} 个组件待修正
              </Tag>
            )}
          </div>
        </div>
      )}

      {awaitingConfirmation && state.plan && (
        <div className='mt-3 rounded-lg border border-amber-100 bg-amber-50/70 p-3 text-xs text-gray-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-gray-200'>
          {state.plan.business_theme && <div className='font-medium'>{state.plan.business_theme}</div>}
          {LAYOUT_TEMPLATES_ENABLED && getDashboardLayoutTemplate(state.plan.layout_template) && (
            <div className='mt-2'>布局模板：{getDashboardLayoutTemplate(state.plan.layout_template)?.title}</div>
          )}
          {state.dataSourceId && <div className='mt-1 text-gray-500'>数据源：{state.dataSourceId}</div>}
          {(state.plan.audience || state.plan.decision_goal) && (
            <div className='mt-2 grid gap-1 rounded-md bg-white/70 p-2 dark:bg-black/20'>
              {state.plan.audience && (
                <div>
                  <span className='text-gray-500'>受众：</span>
                  {state.plan.audience}
                </div>
              )}
              {state.plan.decision_goal && (
                <div>
                  <span className='text-gray-500'>决策目标：</span>
                  {state.plan.decision_goal}
                </div>
              )}
            </div>
          )}
          {(state.plan.analysis_logic || []).length > 0 && (
            <div className='mt-2'>
              <div className='text-gray-500'>分析逻辑</div>
              <ol className='mb-0 mt-1 list-decimal space-y-1 pl-5'>
                {state.plan.analysis_logic?.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
              </ol>
            </div>
          )}
          {(state.plan.metrics || []).length > 0 && (
            <div className='mt-2 flex flex-wrap gap-1'>
              <span className='mr-1 text-gray-500'>指标</span>
              {state.plan.metrics?.map(metric => (
                <Tag key={metric} color='blue' className='m-0'>
                  {metric}
                </Tag>
              ))}
            </div>
          )}
          {(state.plan.dimensions || []).length > 0 && (
            <div className='mt-2 flex flex-wrap gap-1'>
              <span className='mr-1 text-gray-500'>维度</span>
              {state.plan.dimensions?.map(dimension => (
                <Tag key={dimension} className='m-0'>
                  {dimension}
                </Tag>
              ))}
            </div>
          )}
          {orderedWidgets.length > 0 && (
            <ul className='mb-0 mt-2 list-disc space-y-1 pl-5'>
              {orderedWidgets.map(widget => (
                <li key={widget.id}>
                  L{widget.analysis_level || 3} · {widget.title}（{widget.type}）
                  {widget.rationale && <span className='text-gray-500'> — {widget.rationale}</span>}
                </li>
              ))}
            </ul>
          )}
          {(state.plan.layout_rationale || state.plan.filter_strategy) && (
            <div className='mt-2 space-y-1 text-gray-500'>
              {state.plan.layout_rationale && <div>布局理由：{state.plan.layout_rationale}</div>}
              {state.plan.filter_strategy && <div>筛选策略：{state.plan.filter_strategy}</div>}
            </div>
          )}
          <div className='mt-3 flex flex-wrap gap-2'>
            <Button
              type='primary'
              size='small'
              onClick={() => onConfirm?.(state)}
              disabled={!onConfirm || busy}
              loading={busy}
            >
              确认并生成 SQL
            </Button>
            <Button size='small' onClick={onRevise} disabled={!onRevise || busy}>
              修改计划
            </Button>
          </div>
        </div>
      )}

      {created && state.editorPath && (
        <Button type='primary' className='mt-3' onClick={onOpen}>
          {state.assetState === 'saved' ? '继续编辑' : '查看看板'}
        </Button>
      )}
    </div>
  );
};

export default DashboardGenerationCard;
