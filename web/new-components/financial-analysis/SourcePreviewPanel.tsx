import { ArrowLeftOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import React from 'react';
import PdfPagePreview from './PdfPagePreview';
import styles from './financial-analysis.module.css';
import { financialText } from './i18n';
import { EvidenceExcerpt, SourceDocument, SourcePreviewAccess } from './types';
interface SourcePreviewPanelProps {
  evidence: EvidenceExcerpt;
  document: SourceDocument;
  onBack: () => void;
  sourceAccess?: SourcePreviewAccess;
}
const SourcePreviewPanel: React.FC<SourcePreviewPanelProps> = ({ evidence, document, onBack, sourceAccess }) => (
  <div className={styles.sourcePanel}>
    <div className={styles.sourceToolbar}>
      <button type='button' className={styles.textLink} onClick={onBack}>
        <ArrowLeftOutlined /> {financialText('financial.back_to_evidence')}
      </button>
      <Tooltip
        title={
          sourceAccess
            ? financialText('financial.the_original_pdf_page_appears_above_with_extracted_excerpts_below_no')
            : financialText('financial.this_view_arranges_extracted_excerpts_it_is_not_an_original_pdf_imag')
        }
      >
        <button type='button' aria-label={financialText('financial.about_source_previews')}>
          <InfoCircleOutlined />
        </button>
      </Tooltip>
    </div>
    <div className={styles.sourceDocument}>
      <div className={styles.meta}>
        {sourceAccess
          ? financialText('financial.original_pdf_and_excerpts')
          : financialText('financial.source_excerpts')}{' '}
        · {document.version}
      </div>
      <h2>{document.fileName}</h2>
      <p className={styles.sectionDescription}>
        {document.fiscalPeriod} ·{' '}
        {sourceAccess
          ? financialText('financial.metric_reference_pdf_physical_page')
          : financialText('financial.pdf_page')}{' '}
        {evidence.page}
        {sourceAccess ? financialText('financial.page') : ''}
      </p>
      {!sourceAccess && (
        <p className={styles.researchNote}>
          {financialText('financial.offline_snapshots_retain_excerpts_and_formulas_return_to_the_applica')}
        </p>
      )}
      {sourceAccess && (
        <PdfPagePreview
          key={`${document.id}:${evidence.id}`}
          evidence={evidence}
          document={document}
          access={sourceAccess}
        />
      )}
      <div className={styles.sourceSection}>{evidence.section || financialText('financial.source_excerpt')}</div>
      <p className={styles.meta}>{[evidence.table, evidence.row, evidence.column].filter(Boolean).join(' / ')}</p>
      <blockquote className={styles.sourceHighlight}>
        <span className={styles.meta}>{evidence.id}</span>
        <p>{evidence.snippet}</p>
      </blockquote>
      {sourceAccess && evidence.headerSnippet && (
        <p className={styles.meta}>
          {financialText('financial.header_physical_page')}
          {evidence.headerPage} {financialText('financial.')}
          {evidence.headerSnippet}
        </p>
      )}
      {sourceAccess && evidence.unitText && (
        <p className={styles.meta}>
          {financialText('financial.unit_statement_physical_page')}
          {evidence.unitPage} {financialText('financial.')}
          {evidence.unitText}
        </p>
      )}
      {evidence.extractedValue && (
        <dl className={styles.driverTable}>
          <div>
            <dt>{financialText('financial.extracted_value')}</dt>
            <dd>{evidence.extractedValue}</dd>
          </div>
        </dl>
      )}
      <div className={styles.sourcePage}>
        {sourceAccess
          ? financialText('financial.excerpt_source_physical_page_value', { value1: evidence.page })
          : `— ${evidence.page} —`}
      </div>
    </div>
  </div>
);
export default SourcePreviewPanel;
