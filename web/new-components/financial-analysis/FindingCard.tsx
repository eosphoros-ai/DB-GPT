import { ArrowRightOutlined } from '@ant-design/icons';
import React from 'react';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';
import { AnalysisFinding, OpenEvidence, SupportStatus } from './types';

export const supportLabels: Record<SupportStatus, string> = {
  get supported() {
    return financialText('financial.supported_by_evidence');
  },
  get partial() {
    return financialText('financial.partially_supported');
  },
  get unresolved() {
    return financialText('financial.unresolved');
  },
};
interface FindingCardProps {
  finding: AnalysisFinding;
  onOpenEvidence: OpenEvidence;
  compact?: boolean;
}
const FindingCard: React.FC<FindingCardProps> = ({ finding, onOpenEvidence, compact = false }) => {
  useFinancialLocale();
  const { calculationTraceMap, evidenceExcerptMap, financialFactMap } = useReportData();
  const facts = finding.inlineTrace.filter(node => node.kind === 'fact');
  const calculations = finding.inlineTrace.filter(node => node.kind === 'calculation');
  const evidence = finding.inlineTrace.filter(node => node.kind === 'evidence');
  return (
    <article className={compact ? styles.findingRow : styles.finding}>
      <div className={styles.meta}>
        {finding.section} {financialText('financial.agent_analysis_2')}
      </div>
      <h3>{finding.title}</h3>
      <p className={styles.findingSummary}>{finding.summary}</p>
      <span className={styles.support} data-status={finding.supportStatus}>
        <span aria-hidden='true'>●</span> {supportLabels[finding.supportStatus]}
      </span>
      {!compact && (
        <div className={styles.inlineTrace}>
          <div className={styles.traceStage}>
            <div className={styles.meta}>{financialText('financial.disclosed_facts')}</div>
            <dl className={styles.factLines}>
              {facts.map(node => {
                const fact = financialFactMap[node.refId];
                if (!fact) return null;
                return (
                  <div key={node.refId}>
                    <dt>{node.label || fact.metricName}</dt>
                    <dd>{node.displayValue || fact.displayValue}</dd>
                  </div>
                );
              })}
            </dl>
          </div>
          <div className={styles.traceStage}>
            <div className={styles.meta}>{financialText('financial.deterministic_calculation_2')}</div>
            {calculations.map(node => {
              const calculation = calculationTraceMap[node.refId];
              if (!calculation) return null;
              return (
                <div className={styles.traceCalculation} key={node.refId}>
                  <div className={styles.meta}>{calculation.name}</div>
                  <div className={styles.formula}>{calculation.steps[0]}</div>
                  <strong>{calculation.displayResult}</strong>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <div className={styles.findingFooter}>
        <div className={styles.citations}>
          {evidence.map(node => {
            const excerpt = evidenceExcerptMap[node.refId];
            return excerpt ? (
              <button
                type='button'
                key={node.refId}
                onClick={() => onOpenEvidence({ findingId: finding.id, evidenceId: excerpt.id })}
              >
                {excerpt.id} · PDF {excerpt.page}
              </button>
            ) : null;
          })}
        </div>
        <button className={styles.textLink} type='button' onClick={() => onOpenEvidence({ findingId: finding.id })}>
          {financialText('financial.view_full_evidence_trail')}
          <ArrowRightOutlined />
        </button>
      </div>
    </article>
  );
};
export default FindingCard;
