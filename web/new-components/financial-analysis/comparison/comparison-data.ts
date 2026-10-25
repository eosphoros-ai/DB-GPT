import type { ComparisonCell, ComparisonReportData } from '../types';

export const comparisonReasons: Record<string, string> = {
  missing_input: '缺少可用数据',
  conflicting_basis: '来源口径冲突',
  unexplained_conflicting_values: '披露值冲突，待核对',
  incompatible_basis: '币种、口径或归属不可比',
  unsupported_basis: '当前范围不支持此口径',
  comparison_objects_unresolved: '比较对象或期间尚待确认',
  trend_basis_gap: '共同披露基础不足，保留趋势断点',
  nonconsecutive_periods: '非连续年度，不计算同比',
  zero_denominator: '分母为零',
  peer_requires_same_report_year: '横向对比要求同年度报告',
  trend_requires_same_company: '跨年对比要求同一家公司',
};

export function comparisonReason(reason: string) {
  return reason
    .split(',')
    .map(code => comparisonReasons[code] || code)
    .join('；');
}

export function cellValue(data: ComparisonReportData, cell: ComparisonCell) {
  if (cell.factId) return data.facts.find(fact => fact.id === cell.factId)?.displayValue || '缺失';
  if (cell.calculationId)
    return data.calculations.find(calc => calc.id === cell.calculationId)?.displayResult || '不可计算';
  return cell.dataStatus === 'conflict'
    ? '冲突 · 待核对'
    : cell.dataStatus === 'extraction_failed'
      ? '提取失败'
      : '缺失';
}
