import { financialText } from '../i18n';
import type { ComparisonCell, ComparisonReportData } from '../types';

export const comparisonReasons: Record<string, string> = {
  get missing_input() {
    return financialText('financial.no_usable_data');
  },
  get conflicting_basis() {
    return financialText('financial.conflicting_reporting_bases');
  },
  get unexplained_conflicting_values() {
    return financialText('financial.conflicting_disclosed_values_verification_required');
  },
  get incompatible_basis() {
    return financialText('financial.incomparable_currency_basis_or_attribution');
  },
  get unsupported_basis() {
    return financialText('financial.reporting_basis_unsupported_in_this_scope');
  },
  get comparison_objects_unresolved() {
    return financialText('financial.comparison_subjects_or_periods_need_confirmation');
  },
  get trend_basis_gap() {
    return financialText('financial.insufficient_common_reporting_basis_retain_a_gap_in_the_trend');
  },
  get nonconsecutive_periods() {
    return financialText('financial.nonconsecutive_years_year_over_year_change_not_calculated');
  },
  get zero_denominator() {
    return financialText('financial.zero_denominator');
  },
  get peer_requires_same_report_year() {
    return financialText('financial.peer_comparison_requires_the_same_reporting_year');
  },
  get trend_requires_same_company() {
    return financialText('financial.trend_comparison_requires_the_same_company');
  },
};

export function comparisonReason(reason: string) {
  return reason
    .split(',')
    .map(code => comparisonReasons[code] || code)
    .join('；');
}

export function cellValue(data: ComparisonReportData, cell: ComparisonCell) {
  if (cell.factId)
    return data.facts.find(fact => fact.id === cell.factId)?.displayValue || financialText('financial.missing');
  if (cell.calculationId)
    return (
      data.calculations.find(calc => calc.id === cell.calculationId)?.displayResult ||
      financialText('financial.not_calculable')
    );
  return cell.dataStatus === 'conflict'
    ? financialText('financial.conflict_verify')
    : cell.dataStatus === 'extraction_failed'
      ? financialText('financial.extraction_failed')
      : financialText('financial.missing');
}
