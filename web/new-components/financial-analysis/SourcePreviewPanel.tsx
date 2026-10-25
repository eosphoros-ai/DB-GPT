import { ArrowLeftOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import React from 'react';
import PdfPagePreview from './PdfPagePreview';
import styles from './financial-analysis.module.css';
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
        <ArrowLeftOutlined /> 返回证据链
      </button>
      <Tooltip
        title={
          sourceAccess
            ? '上方显示原 PDF 页面图像，下方保留提取摘录；未做区域高亮。'
            : '此视图按已提取片段排版，并非原始 PDF 页面图像。'
        }
      >
        <button type='button' aria-label='来源预览说明'>
          <InfoCircleOutlined />
        </button>
      </Tooltip>
    </div>
    <div className={styles.sourceDocument}>
      <div className={styles.meta}>
        {sourceAccess ? '原 PDF 与来源摘录' : '来源摘录'} · {document.version}
      </div>
      <h2>{document.fileName}</h2>
      <p className={styles.sectionDescription}>
        {document.fiscalPeriod} · {sourceAccess ? '指标引用：PDF 物理第' : 'PDF Page'} {evidence.page}
        {sourceAccess ? ' 页' : ''}
      </p>
      {!sourceAccess && (
        <p className={styles.researchNote}>离线快照保留摘录与公式；原 PDF 预览和下载需要回到应用授权访问。</p>
      )}
      {sourceAccess && (
        <PdfPagePreview
          key={`${document.id}:${evidence.id}`}
          evidence={evidence}
          document={document}
          access={sourceAccess}
        />
      )}
      <div className={styles.sourceSection}>{evidence.section || '来源片段'}</div>
      <p className={styles.meta}>{[evidence.table, evidence.row, evidence.column].filter(Boolean).join(' / ')}</p>
      <blockquote className={styles.sourceHighlight}>
        <span className={styles.meta}>{evidence.id}</span>
        <p>{evidence.snippet}</p>
      </blockquote>
      {sourceAccess && evidence.headerSnippet && (
        <p className={styles.meta}>
          表头（物理第 {evidence.headerPage} 页）：{evidence.headerSnippet}
        </p>
      )}
      {sourceAccess && evidence.unitText && (
        <p className={styles.meta}>
          单位声明（物理第 {evidence.unitPage} 页）：{evidence.unitText}
        </p>
      )}
      {evidence.extractedValue && (
        <dl className={styles.driverTable}>
          <div>
            <dt>提取值</dt>
            <dd>{evidence.extractedValue}</dd>
          </div>
        </dl>
      )}
      <div className={styles.sourcePage}>
        {sourceAccess ? `摘录来源：物理第 ${evidence.page} 页` : `— ${evidence.page} —`}
      </div>
    </div>
  </div>
);
export default SourcePreviewPanel;
