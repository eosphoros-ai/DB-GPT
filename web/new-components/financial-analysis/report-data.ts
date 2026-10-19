import type { EvidenceSelection, ReportData } from './types';

export const isDefined = <T>(value: T | undefined | null): value is T => value != null;
const indexById = <T extends { id: string }>(items: T[]): Record<string, T | undefined> =>
  Object.fromEntries(items.map(item => [item.id, item]));

export function indexReport(data: ReportData) {
  return {
    financialFactMap: indexById(data.facts),
    calculationTraceMap: indexById(data.calculations),
    analysisFindingMap: indexById(data.findings),
    evidenceExcerptMap: indexById(data.evidence),
    sourceDocumentMap: indexById(data.documents),
  };
}

export function resolveEvidence(data: ReportData, selection: EvidenceSelection) {
  const maps = indexReport(data);
  const finding = selection.findingId ? maps.analysisFindingMap[selection.findingId] : undefined;
  const metric = data.metrics.find(item => item.id === selection.metricId);
  const calculationIds = new Set([
    ...(finding?.calculationIds ?? []),
    ...[selection.calculationId, metric?.calculationId].filter(isDefined),
  ]);
  const calculations = [...calculationIds].map(id => maps.calculationTraceMap[id]).filter(isDefined);
  const factIds = new Set([
    ...(finding?.factIds ?? []),
    ...(metric?.factIds ?? []),
    ...[selection.factId].filter(isDefined),
    ...calculations.flatMap(item => item.inputFactIds),
    ...data.facts
      .filter(item => selection.evidenceId && item.evidenceExcerptIds.includes(selection.evidenceId))
      .map(item => item.id),
  ]);
  const facts = [...factIds].map(id => maps.financialFactMap[id]).filter(isDefined);
  const evidenceIds = new Set([
    ...(finding?.evidenceExcerptIds ?? []),
    ...facts.flatMap(item => item.evidenceExcerptIds),
    ...[selection.evidenceId].filter(isDefined),
  ]);
  const evidence = [...evidenceIds].map(id => maps.evidenceExcerptMap[id]).filter(isDefined);
  const documents = [...new Set(evidence.map(item => item.sourceDocumentId))]
    .map(id => maps.sourceDocumentMap[id])
    .filter(isDefined);
  return { finding, metric, calculations, facts, evidence, documents };
}

export function periodRange(points: Array<{ year: string }>) {
  const periods = [...new Set(points.map(item => item.year))].sort();
  return periods.length > 1 ? `${periods[0]}–${periods[periods.length - 1]}` : periods[0] || '期间未提供';
}

export const runStatusLabels = { pending: 'Pending', running: 'Running', completed: 'Completed', failed: 'Failed' };

export function reportRunState(data: ReportData) {
  if (data.mode === 'report' && data.workflow) {
    // Publication is independent of how much analysis the source supports.
    const complete = data.workflow.status === 'published';
    return { label: complete ? '报告已生成' : '分析中', working: !complete, complete };
  }
  if (data.mode === 'report' && data.analysis) {
    if (data.analysis.status === 'running') return { label: '分析中', working: true, complete: false };
    if (data.analysis.status === 'completed') return { label: '报告已生成', working: false, complete: true };
    if (data.analysis.status === 'partial') {
      const complete = !!data.analysis.completedAt;
      return { label: complete ? '报告已生成' : '分析中', working: !complete, complete };
    }
    if (data.analysis.status === 'failed') return { label: '数据可用 · 分析未完成', working: false, complete: false };
  }
  return {
    label:
      data.mode === 'report' && data.report.run.status === 'completed'
        ? '报告已生成'
        : runStatusLabels[data.report.run.status],
    working: data.report.run.status === 'running',
    complete: data.report.run.status === 'completed',
  };
}

/** Old snapshots may have a model note that contradicts their validator errors. */
export function topicStatusNote(topic: NonNullable<ReportData['workflow']>['topics'][number]): string {
  if (['failed', 'needs_revision'].includes(topic.status) && topic.errorCode === 'EXPLANATION_BOUNDARY_FAILED') {
    return '本专题结论超出当前证据的解释边界，需修订相关判断。详情及重试请查看执行过程。';
  }
  if (
    ['failed', 'needs_revision'].includes(topic.status) &&
    (topic.errorCode === 'FINDING_VALIDATION_FAILED' || (!topic.errorCode && topic.issues?.length))
  ) {
    return '本专题结论格式或引用校验失败；不代表历史数据缺失。错误详情及重试请查看执行过程。';
  }
  return topic.note;
}
