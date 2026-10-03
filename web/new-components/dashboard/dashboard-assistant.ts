import {
  DashboardAnnotationIntentResolution,
  DashboardAnnotationRecord,
  DashboardRecord,
  DashboardSchemaV1,
  DashboardSelectionTarget,
  DashboardSnapshot,
  DashboardWidgetResult,
} from '@/types/dashboard';

export type DashboardAnnotationIntent = 'modify' | 'explain' | 'anomaly';

export interface DashboardAnnotationDraft {
  id: string;
  target: DashboardSelectionTarget;
  intent?: DashboardAnnotationIntent;
  content: string;
}

export interface PersistedDashboardAnnotationIntent {
  annotation: DashboardAnnotationRecord;
  intent: DashboardAnnotationIntent;
}

const intentLabel: Record<DashboardAnnotationIntent, string> = {
  modify: '修改组件',
  explain: '指标解释',
  anomaly: '异常分析',
};

export const hasDashboardAnnotationWorkflowMarker = (input: string): boolean =>
  /\[\[dashboard-annotation:[^\]]+\]\]/.test(input);

export const makeDashboardAnnotationDraft = (
  target: DashboardSelectionTarget,
  intent?: DashboardAnnotationIntent,
): DashboardAnnotationDraft => ({
  id: `${target.widget_id || target.filter_id || target.kind}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 7)}`,
  target,
  intent,
  content:
    intent === 'explain'
      ? '解释这个指标的业务含义、计算口径和当前结果。'
      : intent === 'anomaly'
        ? '根据程序计算的异常证据解释可能原因，并建议下一步排查。'
        : '',
});

export const resolveDashboardAnnotationDrafts = (
  drafts: DashboardAnnotationDraft[],
  resolution: DashboardAnnotationIntentResolution,
): Array<DashboardAnnotationDraft & { intent: DashboardAnnotationIntent }> => {
  const ids = resolution.items.map(item => item.draft_id);
  if (ids.length !== drafts.length || new Set(ids).size !== ids.length || drafts.some(item => !ids.includes(item.id))) {
    throw new Error('意图识别未覆盖全部批注，请重试。');
  }
  for (const item of resolution.items) {
    const modes = [item.tasks.length > 0, Boolean(item.question?.trim()), Boolean(item.answered)].filter(Boolean);
    if (modes.length !== 1 || (item.answered && !resolution.reply?.trim()))
      throw new Error('助手返回的处理结果不完整，请重试。');
  }
  return drafts.flatMap(draft =>
    resolution.items
      .find(item => item.draft_id === draft.id)!
      .tasks.map(task => ({
        ...draft,
        id: draft.id + ':' + task.intent,
        intent: task.intent,
        content: task.prompt,
      })),
  );
};

/** Keep the current view inspectable without sending entire result tables. */
export const buildDashboardAssistantContext = (
  schema: DashboardSchemaV1,
  filters: Record<string, unknown>,
  snapshot: DashboardSnapshot | null,
): Record<string, unknown> => ({
  dashboard: schema.dashboard,
  filters: schema.filters,
  filter_values: filters,
  refreshed_at: snapshot?.refreshed_at,
  result_note: 'rows_sample 只是查询结果的前几行，不是全量数据；不能据此推断总量、同比或异常原因。',
  widget_count: schema.widgets.length,
  widgets: schema.widgets.slice(0, 40).map(widget => {
    const result = snapshot?.widgets[widget.id];
    return {
      id: widget.id,
      title: widget.title,
      type: widget.type,
      description: widget.description,
      query: { ...widget.query, sql: widget.query.sql?.slice(0, 4000) },
      encoding: widget.encoding,
      presentation: widget.presentation,
      style: widget.style,
      layout: schema.layouts.desktop.find(item => item.widget_id === widget.id),
      result: result
        ? {
            columns: result.columns.slice(0, 16),
            row_count: result.row_count,
            truncated: result.truncated,
            error: result.error,
            anomalies: result.anomalies,
            rows_sample: result.rows.slice(0, 6).map(row =>
              Object.fromEntries(
                Object.entries(row)
                  .slice(0, 16)
                  .map(([key, value]) => [key, typeof value === 'string' ? value.slice(0, 200) : value]),
              ),
            ),
          }
        : null,
    };
  }),
});

export const buildDashboardAssistantPrompt = (
  record: DashboardRecord,
  items: PersistedDashboardAnnotationIntent[],
  widgetResults: Record<string, DashboardWidgetResult> = {},
): string => {
  const lines = items.flatMap(({ annotation, intent }, index) => {
    const anomalyEvidence = annotation.target.widget_id
      ? widgetResults[annotation.target.widget_id]?.anomalies || []
      : [];
    return [
      `${index + 1}. [[dashboard-annotation:${record.id}:${annotation.id}]] [${intentLabel[intent]}] ${annotation.target.label}`,
      `   用户要求：${annotation.prompt}`,
      `   选择上下文：${JSON.stringify(annotation.target)}`,
      ...(intent === 'anomaly' ? [`   程序异常证据（只读）：${JSON.stringify(anomalyEvidence)}`] : []),
    ];
  });
  const modificationIds = items.filter(item => item.intent === 'modify').map(item => item.annotation.id);
  return [
    `继续处理现有看板 ${record.id}，不要创建重复看板。`,
    `先调用 load_dashboard_draft，dashboard_id 必须使用 ${record.id}。`,
    '以下批注属于同一批次，请逐条处理并在最终答复中按编号说明结果：',
    '修改路径必须使用稳定 ID，例如 /widgets/by-id/{widget_id}/title；禁止 /widgets/{widget_id} 和数组下标。逐条生成全部修改提案后再结束。',
    ...(items.some(item => item.annotation.target.kind === 'filter')
      ? [
          '筛选器修改需要同时更新 /filters/by-id/{filter_id}、受影响组件的 /query/filter_parameters 与包含命名参数的只读 SQL；只改名称或可选项不算完成。',
          '同步更新受影响组件的 /publication/filter_fields 和发布数据查询。日期类型绑定 start_parameter/end_parameter；单选绑定 parameter。请依据 load_dashboard_draft 返回的结构与实际数据字段生成，先验证再提案。',
          `当前筛选器：${JSON.stringify(record.schema.filters)}`,
          `当前组件绑定：${JSON.stringify(record.schema.widgets.map(widget => ({ id: widget.id, query: widget.query, publication: widget.publication })))}`,
        ]
      : []),
    ...lines,
    modificationIds.length
      ? `修改类批注必须分别调用 propose_dashboard_change（annotation_id：${modificationIds.join(
          '、',
        )}），只生成最小、受限、可验证的提案；不要直接保存，等待用户在看板中应用。`
      : '本批次没有修改类批注，不要修改看板。',
    '指标解释只能根据看板 Schema、查询口径和已有结果说明，不得改动看板。',
    '异常分析只能解释程序已计算并保存的异常证据；证据不存在、数据不足、缺失或分母为零时必须回答“无法判断”，不得凭文字猜测、重算、覆盖或改变程序结论，也不得调用任何看板修改工具。',
  ].join('\n');
};
