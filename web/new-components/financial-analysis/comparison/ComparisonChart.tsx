import React from 'react';
import styles from '../financial-analysis.module.css';
import type { ComparisonReportData, OpenEvidence } from '../types';

/** Numeric conversion scales the drawing only; values and differences are saved server results. */
const ComparisonChart: React.FC<{ data: ComparisonReportData; onOpenEvidence: OpenEvidence }> = ({
  data,
  onOpenEvidence,
}) => {
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
    <section className={styles.comparisonChart} aria-label='营业收入对比图'>
      <h3>营业收入 · 披露值</h3>
      {!points.length && <p className={styles.meta}>缺少可比值，暂不绘制图表。</p>}
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
      <p className={styles.meta}>缺失、冲突与不可比项不绘制；跨年未确认的共同披露基础保留为断点。</p>
    </section>
  );
};
export default ComparisonChart;
