import React from 'react';
import styles from '../financial-analysis.module.css';
import { financialText, useFinancialLocale } from '../i18n';
import type { ComparisonReportData, OpenEvidence } from '../types';

/** Numeric conversion scales the drawing only; values and differences are saved server results. */
const ComparisonChart: React.FC<{ data: ComparisonReportData; onOpenEvidence: OpenEvidence }> = ({
  data,
  onOpenEvidence,
}) => {
  useFinancialLocale();
  const points = data.comparison.cells
    .filter(
      cell =>
        cell.metricCode === 'revenue' &&
        cell.dataStatus === 'available' &&
        cell.comparability.status === 'comparable' &&
        cell.factId,
    )
    .flatMap(cell => {
      const fact = data.facts.find(item => item.id === cell.factId);
      const value = Number(fact?.normalizedValue);
      return fact && fact.normalizedValue !== null && Number.isFinite(value) ? [{ cell, fact, value }] : [];
    });
  const maximum = Math.max(...points.map(point => Math.abs(point.value)), 1);
  return (
    <section className={styles.comparisonChart} aria-label={financialText('financial.revenue_comparison_chart')}>
      <h3>{financialText('financial.revenue_disclosed_values')}</h3>
      {!points.length && (
        <p className={styles.meta}>{financialText('financial.no_comparable_values_available_for_this_chart')}</p>
      )}
      {points.map(({ cell, fact, value }) => (
        <button
          type='button'
          key={cell.id}
          onClick={() => onOpenEvidence({ factId: fact.id })}
          className={styles.comparisonChartRow}
        >
          <span>
            {data.comparison.entities.find(entity => entity.id === cell.entityId)?.name} · {cell.period}
          </span>
          <span className={styles.comparisonBarTrack}>
            <span className={styles.comparisonBar} style={{ width: `${(Math.abs(value) / maximum) * 100}%` }} />
          </span>
          <strong>{fact.displayValue}</strong>
        </button>
      ))}
      <p className={styles.meta}>
        {financialText('financial.missing_conflicting_and_incomparable_values_are_omitted_unconfirmed_')}
      </p>
    </section>
  );
};
export default ComparisonChart;
