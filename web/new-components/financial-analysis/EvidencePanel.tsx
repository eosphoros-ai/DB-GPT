import { FilePdfOutlined } from '@ant-design/icons';
import { Select } from 'antd';
import React, { useEffect, useMemo, useRef } from 'react';
import { supportLabels } from './FindingCard';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { resolveEvidence } from './report-data';
import { EvidenceExcerpt, EvidenceSelection } from './types';

interface EvidencePanelProps {
  selection: EvidenceSelection;
  onFindingChange: (findingId: string) => void;
  onOpenSource: (evidence: EvidenceExcerpt) => void;
}
const EvidencePanel: React.FC<EvidencePanelProps> = ({ selection, onFindingChange, onOpenSource }) => {
  const { data, evidenceExcerptMap, sourceDocumentMap } = useReportData();
  const { evidenceId, findingId, factId, calculationId } = selection;
  const selectedRef = useRef<HTMLDivElement>(null);
  const resolved = useMemo(() => resolveEvidence(data, selection), [data, selection]);
  const finding = resolved.finding;
  useEffect(() => {
    if (!evidenceId && !factId && !calculationId) return;
    const frame = requestAnimationFrame(() => {
      selectedRef.current?.scrollIntoView({ block: 'center' });
      selectedRef.current?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [evidenceId, findingId, factId, calculationId, selection]);

  return (
    <div className={styles.evidencePanel}>
      <label className={styles.meta} htmlFor='financial-finding-select'>
        研究发现
      </label>
      <Select
        id='financial-finding-select'
        className={styles.findingSelect}
        value={finding?.id}
        placeholder='选择研究发现，或从指标直接查看依据'
        onChange={onFindingChange}
        options={data.findings.map(item => ({ value: item.id, label: item.title }))}
      />
      <section className={styles.evidenceSection}>
        <h2>
          <span>01</span> Agent 分析
        </h2>
        <h3 className={styles.evidenceFindingTitle}>{finding?.title || resolved.metric?.name || '指标与来源依据'}</h3>
        <p>{finding?.summary || '此处展示所选指标或来源的依据。'}</p>
        {finding && (
          <span className={styles.support} data-status={finding.supportStatus}>
            ● {supportLabels[finding.supportStatus]}
          </span>
        )}
        {finding?.counterEvidence?.map(item => (
          <p className={styles.researchNote} key={item}>
            <strong>对冲证据</strong>
            {item}
          </p>
        ))}
        {finding?.unresolvedQuestions?.map(item => (
          <p className={styles.researchNote} key={item}>
            <strong>待核查</strong>
            {item}
          </p>
        ))}
      </section>
      <section className={styles.evidenceSection}>
        <h2>
          <span>02</span> 确定性计算
        </h2>
        {!resolved.calculations.length && <p className={styles.meta}>暂无计算记录</p>}
        {resolved.calculations.map(calculation => (
          <div
            className={styles.calculationDetail}
            key={calculation.id}
            ref={calculation.id === calculationId ? selectedRef : undefined}
            tabIndex={-1}
            data-selected={calculation.id === calculationId}
            data-financial-reference={calculation.id}
          >
            <h3>{calculation.name}</h3>
            <div className={styles.meta}>{calculation.formula}</div>
            <div className={styles.calculationSteps}>
              {calculation.steps.map(step => (
                <div key={step}>{step}</div>
              ))}
            </div>
            <strong className={styles.calculationResult}>{calculation.displayResult}</strong>
            {data.mode === 'report' && calculation.steps.map((step, index) => <p key={index}>{step}</p>)}
          </div>
        ))}
      </section>
      <section className={styles.evidenceSection}>
        <h2>
          <span>03</span> 披露事实
        </h2>
        <div className={styles.evidenceFacts}>
          {resolved.facts.map(fact => (
            <div
              key={fact.id}
              ref={fact.id === factId ? selectedRef : undefined}
              tabIndex={-1}
              data-selected={fact.id === factId}
              data-financial-reference={fact.id}
            >
              <div>
                <h3>{fact.metricName}</h3>
                <span className={styles.meta}>
                  {data.mode === 'comparison' &&
                    `${data.comparison.entities.find(entity => entity.id === fact.entityId)?.name || ''} · `}
                  {fact.fiscalPeriod} · {fact.statementScope}
                </span>
              </div>
              <div>
                <strong>{fact.displayValue}</strong>
                <div className={styles.citations}>
                  {fact.evidenceExcerptIds.map(
                    id =>
                      evidenceExcerptMap[id] && (
                        <button type='button' key={id} onClick={() => onOpenSource(evidenceExcerptMap[id]!)}>
                          {evidenceExcerptMap[id]!.label || id} · PDF {evidenceExcerptMap[id]!.page}
                        </button>
                      ),
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className={styles.evidenceSection}>
        <h2>
          <span>04</span> 原始证据
        </h2>
        {!resolved.evidence.length && <p className={styles.meta}>暂无可用来源</p>}
        {resolved.evidence.map(evidence => (
          <div
            key={evidence.id}
            ref={evidence.id === evidenceId ? selectedRef : undefined}
            tabIndex={-1}
            className={styles.excerpt}
            data-selected={evidence.id === evidenceId}
          >
            <div className={styles.excerptHeading}>
              <strong>
                {evidence.label || evidence.id} · PDF {evidence.page}
              </strong>
              <button type='button' className={styles.textLink} onClick={() => onOpenSource(evidence)}>
                定位原文 →
              </button>
            </div>
            <div className={styles.meta}>
              {sourceDocumentMap[evidence.sourceDocumentId]?.fileName || '来源文件未提供'} · {evidence.section}
            </div>
            <div className={styles.meta}>
              {[evidence.table, evidence.row, evidence.column].filter(Boolean).join(' / ')}
            </div>
            <blockquote>{evidence.snippet}</blockquote>
            <div className={styles.excerptHeading}>
              <span className={styles.meta}>{evidence.extractedValue && `提取值：${evidence.extractedValue}`}</span>
              <span
                className={styles.support}
                data-status={evidence.qualityStatus === 'verified' ? 'supported' : 'partial'}
              >
                {evidence.qualityStatus === 'verified' ? '已核验' : '待复核'}
              </span>
            </div>
          </div>
        ))}
      </section>
      <section className={styles.evidenceSection}>
        <h2>
          <span>05</span> 来源文件
        </h2>
        {resolved.documents.map(document => (
          <div className={styles.fileRow} key={document.id}>
            <FilePdfOutlined />
            <div>
              <strong>{document.fileName}</strong>
              <div className={styles.meta}>
                {document.reportType} · {document.fiscalPeriod} · {document.version}
              </div>
            </div>
            <button
              type='button'
              className={styles.textLink}
              onClick={() => onOpenSource(resolved.evidence.find(item => item.sourceDocumentId === document.id)!)}
            >
              查看 →
            </button>
          </div>
        ))}
      </section>
    </div>
  );
};
export default EvidencePanel;
