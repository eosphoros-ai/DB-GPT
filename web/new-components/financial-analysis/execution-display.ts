const FINANCIAL_ACTIONS: Record<string, string> = {
  prepare_financial_report: '读取财报并分析财务数据',
  prepare_financial_comparison: '读取财报并比较财务数据',
  resolve_financial_comparison: '确认比较对象与数据口径',
  get_financial_topic: '读取专题分析依据',
  save_financial_topic: '保存本次分析结果',
  review_financial_report: '核对结论与原文依据',
  publish_financial_report: '生成分析报告',
  read_financial_report: '读取已保存的报告',
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
  if (step.status === 'failed' || step.status === 'error') return '本步骤未完成，可展开查看已保存的进展和原因。';
  if (step.status === 'running') return '正在处理，新的进展会显示在这里。';
  return '本次调用已结束，可展开查看结果。';
}
