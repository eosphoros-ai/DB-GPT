import React from 'react';
import styles from '../financial-analysis.module.css';
import type { ComparisonReportData, OpenEvidence } from '../types';
import { cellValue, comparisonReason } from './comparison-data';

const ComparisonMatrix: React.FC<{
  data: ComparisonReportData;
  codes: string[];
  onOpenEvidence: OpenEvidence;
}> = ({ data, codes, onOpenEvidence }) => {
  const objects = data.comparison.objects;
  const rows = codes.map(code => data.comparison.cells.find(cell => cell.metricCode === code)).filter(cell => !!cell);
  return (
    <div className={styles.comparisonTableScroll} tabIndex={0} aria-label='财务对比矩阵，可横向滚动'>
      <table className={styles.comparisonTable}>
        <thead>
          <tr>
            <th scope='col'>指标</th>
            {objects.map(object => (
              <th scope='col' key={`${object.entityId}:${object.period}`}>
                {data.comparison.entities.find(entity => entity.id === object.entityId)?.name}
                <br />
                <span className={styles.meta}>
                  {object.period} 年
                  {object.entityId === data.comparison.baselineEntityId &&
                    (data.comparison.kind === 'peer'
                      ? ' · 基准公司'
                      : object.period === data.comparison.baselinePeriod && ' · 基准期')}
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
                            不可比：{cell.comparability.reasons.map(comparisonReason).join('；')}
                          </div>
                        )}
                        {cell.dataStatus !== 'available' && (
                          <div className={styles.comparisonGap}>{comparisonReason(cell.selectionReason)}</div>
                        )}
                        {cell.candidateFactIds.length > 1 && (
                          <details className={styles.comparisonCandidates}>
                            <summary>{cell.candidateFactIds.length} 个来源候选</summary>
                            {cell.candidateFactIds.map(id => (
                              <button type='button' key={id} onClick={() => onOpenEvidence({ factId: id })}>
                                查看披露来源
                              </button>
                            ))}
                            <span className={styles.meta}>
                              {cell.selectionReason === 'explicit_paired_restatement'
                                ? '按明确调整前后关系选值'
                                : '保留全部披露，按版本化政策选值'}
                            </span>
                          </details>
                        )}
                      </>
                    ) : (
                      '缺失'
                    )}
                    {differences.map(calc => (
                      <div key={calc.id} className={styles.comparisonDifference}>
                        <button
                          type='button'
                          className={styles.textLink}
                          onClick={() => onOpenEvidence({ calculationId: calc.id })}
                        >
                          {calc.comparisonType === 'growth'
                            ? '同比'
                            : data.comparison.kind === 'trend'
                              ? '较基准期'
                              : '较基准'}
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
      {!objects.length && <p className={styles.meta}>等待确认公司和期间；已完成的提取结果会保留。</p>}
    </div>
  );
};
export default ComparisonMatrix;
