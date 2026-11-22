import React from 'react';
import styles from '../financial-analysis.module.css';
import { financialText, useFinancialLocale } from '../i18n';
import type { ComparisonReportData, OpenEvidence } from '../types';
import { cellValue, comparisonReason } from './comparison-data';

const ComparisonMatrix: React.FC<{
  data: ComparisonReportData;
  codes: string[];
  onOpenEvidence: OpenEvidence;
}> = ({ data, codes, onOpenEvidence }) => {
  useFinancialLocale();
  const objects = data.comparison.objects;
  const rows = codes.map(code => data.comparison.cells.find(cell => cell.metricCode === code)).filter(cell => !!cell);
  return (
    <div
      className={styles.comparisonTableScroll}
      tabIndex={0}
      aria-label={financialText('financial.financial_comparison_matrix_scroll_horizontally')}
    >
      <table className={styles.comparisonTable}>
        <thead>
          <tr>
            <th scope='col'>{financialText('financial.metric')}</th>
            {objects.map(object => (
              <th scope='col' key={`${object.entityId}:${object.period}`}>
                {data.comparison.entities.find(entity => entity.id === object.entityId)?.name}
                <br />
                <span className={styles.meta}>
                  {object.period} {financialText('financial.year_2')}
                  {object.entityId === data.comparison.baselineEntityId &&
                    (data.comparison.kind === 'peer'
                      ? financialText('financial.baseline_company')
                      : object.period === data.comparison.baselinePeriod && financialText('financial.baseline_period'))}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.metricCode}>
              <th scope='row'>{row.metricName}</th>
              {objects.map(object => {
                const cell = data.comparison.cells.find(
                  item =>
                    item.entityId === object.entityId &&
                    item.period === object.period &&
                    item.metricCode === row.metricCode,
                );
                const differences = data.calculations.filter(
                  item =>
                    item.metricCode === row.metricCode &&
                    item.subjectEntityId === object.entityId &&
                    item.subjectPeriod === object.period,
                );
                return (
                  <td key={`${object.entityId}:${object.period}`} data-status={cell?.dataStatus || 'missing'}>
                    {cell ? (
                      <>
                        <button
                          type='button'
                          className={styles.comparisonValue}
                          disabled={!cell.factId && !cell.calculationId && !cell.candidateFactIds.length}
                          onClick={() =>
                            onOpenEvidence(
                              cell.calculationId
                                ? { calculationId: cell.calculationId }
                                : { factId: cell.factId || cell.candidateFactIds[0] },
                            )
                          }
                        >
                          {cellValue(data, cell)}
                        </button>
                        {cell.comparability.status === 'incomparable' && cell.dataStatus === 'available' && (
                          <div className={styles.comparisonGap}>
                            {financialText('financial.incomparable')}
                            {cell.comparability.reasons.map(comparisonReason).join('；')}
                          </div>
                        )}
                        {cell.dataStatus !== 'available' && (
                          <div className={styles.comparisonGap}>{comparisonReason(cell.selectionReason)}</div>
                        )}
                        {cell.candidateFactIds.length > 1 && (
                          <details className={styles.comparisonCandidates}>
                            <summary>
                              {cell.candidateFactIds.length} {financialText('financial.source_candidates')}
                            </summary>
                            {cell.candidateFactIds.map(id => (
                              <button type='button' key={id} onClick={() => onOpenEvidence({ factId: id })}>
                                {financialText('financial.view_disclosure_source')}
                              </button>
                            ))}
                            <span className={styles.meta}>
                              {cell.selectionReason === 'explicit_paired_restatement'
                                ? financialText('financial.select_by_an_explicit_before_after_adjustment_relationship')
                                : financialText('financial.retain_all_disclosures_select_by_versioned_policy')}
                            </span>
                          </details>
                        )}
                      </>
                    ) : (
                      financialText('financial.missing')
                    )}
                    {differences.map(calc => (
                      <div key={calc.id} className={styles.comparisonDifference}>
                        <button
                          type='button'
                          className={styles.textLink}
                          onClick={() => onOpenEvidence({ calculationId: calc.id })}
                        >
                          {calc.comparisonType === 'growth'
                            ? financialText('financial.year_over_year')
                            : data.comparison.kind === 'trend'
                              ? financialText('financial.versus_baseline_period')
                              : financialText('financial.versus_baseline')}
                          ：{calc.displayResult}
                        </button>
                        {calc.reason && <div className={styles.comparisonGap}>{comparisonReason(calc.reason)}</div>}
                      </div>
                    ))}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {!objects.length && (
        <p className={styles.meta}>
          {financialText('financial.awaiting_company_and_period_confirmation_completed_extraction_result')}
        </p>
      )}
    </div>
  );
};
export default ComparisonMatrix;
