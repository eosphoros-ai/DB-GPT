import { isFinancialReportReference } from './agent-artifact';
import type { ReportData } from './types';

/** Restore a saved result without inventing the lost user message or tool steps. */
export function recoverFinancialHistory(data: ReportData, sessionId: string) {
  const reference = {
    kind: 'financial-report',
    runId: data.report.run.id,
    sessionId,
    revision: data.revision,
    title: `${data.report.companyName}财报分析`,
  };
  if (!isFinancialReportReference(reference)) throw new Error('保存的财报引用无效');
  return {
    role: 'view',
    context: JSON.stringify({
      version: 2,
      protocol_version: 2,
      type: 'react-agent',
      final_content: '已恢复上次保存的财报分析，可查看结果或继续分析。',
      steps: [],
      financial_report: reference,
    }),
  };
}
