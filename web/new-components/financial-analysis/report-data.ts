import { financialText } from './i18n';
import type { EvidenceSelection, FinancialReportData, ReportData } from './types';

export const isDefined = <T>(value: T | undefined | null): value is T => value != null;
const indexById = <T extends { id: string }>(items: T[]): Record<string, T | undefined> =>
  Object.fromEntries(items.map(item => [item.id, item]));

export function indexReport(data: FinancialReportData) {
  return {
    financialFactMap: indexById(data.facts),
    calculationTraceMap: indexById(data.calculations),
    analysisFindingMap: indexById(data.findings),
    evidenceExcerptMap: indexById(data.evidence),
    sourceDocumentMap: indexById(data.documents),
  };
}

export function resolveEvidence(data: FinancialReportData, selection: EvidenceSelection) {
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
  return periods.length > 1
    ? `${periods[0]}–${periods[periods.length - 1]}`
    : periods[0] || financialText('financial.period_unavailable');
}

export const runStatusLabels = { pending: 'Pending', running: 'Running', completed: 'Completed', failed: 'Failed' };

export function reportRunState(data: FinancialReportData) {
  if (data.mode === 'comparison') {
    const complete = (data.workflow?.status || data.lifecycle.publicationStatus) === 'published';
    return {
      label: complete
        ? financialText('financial.report_generated')
        : data.lifecycle.stage === 'interrupted'
          ? financialText('financial.interrupted_data_retained')
          : data.lifecycle.stage === 'awaiting_analysis'
            ? financialText('financial.data_ready_awaiting_analysis')
            : data.lifecycle.stage === 'awaiting_revision'
              ? financialText('financial.awaiting_revision_data_retained')
              : data.lifecycle.dataStatus === 'incomplete'
                ? financialText('financial.files_saved_awaiting_confirmation')
                : financialText('financial.analyzing'),
      working: !complete && !['interrupted', 'awaiting_revision', 'awaiting_analysis'].includes(data.lifecycle.stage),
      complete,
    };
  }
  if (data.workflow) {
    // Publication is independent of how much analysis the source supports.
    const complete = data.workflow.status === 'published';
    return {
      label: complete ? financialText('financial.report_generated') : financialText('financial.analyzing'),
      working: !complete,
      complete,
    };
  }
  if (data.analysis) {
    if (data.analysis.status === 'running')
      return { label: financialText('financial.analyzing'), working: true, complete: false };
    if (data.analysis.status === 'completed')
      return { label: financialText('financial.report_generated'), working: false, complete: true };
    if (data.analysis.status === 'partial') {
      const complete = !!data.analysis.completedAt;
      return {
        label: complete ? financialText('financial.report_generated') : financialText('financial.analyzing'),
        working: !complete,
        complete,
      };
    }
    if (data.analysis.status === 'failed')
      return { label: financialText('financial.data_available_analysis_incomplete'), working: false, complete: false };
  }
  return {
    label:
      data.report.run.status === 'completed'
        ? financialText('financial.report_generated')
        : runStatusLabels[data.report.run.status],
    working: data.report.run.status === 'running',
    complete: data.report.run.status === 'completed',
  };
}

export function financialReportTitle(data: FinancialReportData) {
  return data.mode === 'comparison'
    ? data.comparison.title
    : financialText('financial.value_financial_analysis', { value1: data.report.companyName });
}

export function supportedFinancialProtocol(data: { schemaVersion: number; mode: string }) {
  return (
    (data.schemaVersion === 1 && data.mode === 'report') || (data.schemaVersion === 2 && data.mode === 'comparison')
  );
}

/** Old snapshots may have a model note that contradicts their validator errors. */
export function topicStatusNote(topic: NonNullable<ReportData['workflow']>['topics'][number]): string {
  if (topic.status === 'failed' && topic.errorCode === 'MODEL_TIMEOUT') {
    return financialText('financial.this_analysis_exceeded_its_time_limit_financial_data_and_calculation');
  }
  if (['failed', 'needs_revision'].includes(topic.status) && topic.errorCode === 'EXPLANATION_BOUNDARY_FAILED') {
    return financialText('financial.this_topic_s_conclusions_exceed_the_evidence_and_need_revision_see_e');
  }
  if (
    ['failed', 'needs_revision'].includes(topic.status) &&
    (topic.errorCode === 'FINDING_VALIDATION_FAILED' || (!topic.errorCode && topic.issues?.length))
  ) {
    return financialText('financial.this_topic_failed_format_or_reference_validation_historical_data_is_');
  }
  return topic.note;
}
