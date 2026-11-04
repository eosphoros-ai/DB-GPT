import { financialText } from './i18n';
const FINANCIAL_ACTIONS: Record<string, string> = {
  get prepare_financial_report() {
    return financialText('financial.read_report_and_analyze_financial_data');
  },
  get prepare_financial_comparison() {
    return financialText('financial.read_reports_and_compare_financial_data');
  },
  get resolve_financial_comparison() {
    return financialText('financial.confirm_comparison_subjects_and_reporting_basis');
  },
  get get_financial_topic() {
    return financialText('financial.read_topic_evidence');
  },
  get save_financial_topic() {
    return financialText('financial.save_analysis_results');
  },
  get review_financial_report() {
    return financialText('financial.review_findings_against_source_evidence');
  },
  get publish_financial_report() {
    return financialText('financial.generate_report');
  },
  get read_financial_report() {
    return financialText('financial.read_saved_report');
  },
};

interface StepOutput {
  output_type: string;
  content: unknown;
}

interface FinancialStep {
  id: string;
  title?: string;
  action?: string;
  status: string;
}

export function financialStepTitle(step: Pick<FinancialStep, 'title' | 'action'>): string | undefined {
  return FINANCIAL_ACTIONS[step.action || ''] || FINANCIAL_ACTIONS[step.title || ''];
}

/** Only public observations emitted by financial_execution/financial_tools are promoted. */
export function financialObservations(outputs: StepOutput[]): string[] {
  return outputs.flatMap(output => {
    if (output.output_type !== 'text' || typeof output.content !== 'string') return [];
    return output.content
      .split('\n')
      .map(line => line.trim())
      .filter(line => {
        if (!line || line.includes('{{') || /Thought:|Action Input:|model_context/.test(line)) return false;
        return (
          /^\[\d+:\d{2}\]\s*(读取财报|分析财务数据|核对结论|生成报告)：/.test(line) ||
          /^(已读取财务科目：|已校验的分析发现（待最终复核）：)/.test(line)
        );
      })
      .map(line => line.replace(/^\[\d+:\d{2}\]\s*/, ''));
  });
}

export function recentFinancialObservations(steps: FinancialStep[], outputs: Record<string, StepOutput[]>): string[] {
  const lines = steps
    .filter(step => financialStepTitle(step))
    .flatMap(step => financialObservations(outputs[step.id] || []));
  // A replay or repeated tool result must not displace new progress with duplicates.
  return [...new Set(lines)].slice(-3);
}

export function financialStepSubtitle(step: FinancialStep, outputs: StepOutput[]): string | undefined {
  if (!financialStepTitle(step)) return undefined;
  const latest = financialObservations(outputs).at(-1);
  if (latest) return latest;
  if (step.status === 'failed' || step.status === 'error')
    return financialText('financial.this_step_is_incomplete_expand_it_to_inspect_saved_progress_and_reas');
  if (step.status === 'running') return financialText('financial.processing_new_progress_will_appear_here');
  return financialText('financial.this_call_has_ended_expand_it_to_inspect_the_result');
}
