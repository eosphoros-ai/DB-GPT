import { isFinancialReportReference } from './agent-artifact';
import { financialText } from './i18n';
import { financialReportTitle } from './report-data';
import type { FinancialReportData } from './types';

/** Restore a saved result without inventing the lost user message or tool steps. */
export function recoverFinancialHistory(data: FinancialReportData, sessionId: string) {
  const reference = {
    kind: 'financial-report',
    runId: data.report.run.id,
    sessionId,
    revision: data.revision,
    title: financialReportTitle(data),
    mode: data.mode,
    published: data.workflow
      ? data.workflow.status === 'published'
      : data.analysis
        ? !!data.analysis.completedAt
        : data.report.run.status === 'completed'
          ? true
          : undefined,
  };
  if (!isFinancialReportReference(reference))
    throw new Error(financialText('financial.invalid_saved_financial_report_reference'));
  return {
    role: 'view',
    context: JSON.stringify({
      version: 2,
      protocol_version: 2,
      type: 'react-agent',
      final_content: financialText('financial.saved_financial_analysis_restored_view_the_results_or_continue_the_a'),
      steps: [],
      financial_report: reference,
    }),
  };
}
