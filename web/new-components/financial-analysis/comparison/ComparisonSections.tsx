import React from 'react';
import FindingCard from '../FindingCard';
import styles from '../financial-analysis.module.css';
import { reportRunState, topicStatusNote } from '../report-data';
import type { ComparisonReportData, OpenEvidence } from '../types';
import ComparisonChart from './ComparisonChart';
import ComparisonMatrix from './ComparisonMatrix';

const sectionCodes: Record<string, string[]> = {
  overview: ['revenue', 'net_profit', 'non_recurring_net_profit', 'operating_cash_flow'],
  profitability: [
    'gross_margin',
    'selling_expense_ratio',
    'administrative_expense_ratio',
    'research_expense_ratio',
    'financial_expense_ratio',
    'net_profit',
    'non_recurring_net_profit',
  ],
  cashflow: ['operating_cash_flow', 'net_profit', 'cash_profit_ratio'],
  balance: ['total_assets', 'total_liabilities', 'debt_ratio', 'current_assets', 'current_liabilities', 'inventory'],
};

const ComparisonSections: React.FC<{
  data: ComparisonReportData;
  section: 'overview' | 'profitability' | 'cashflow' | 'balance';
  onOpenEvidence: OpenEvidence;
}> = ({ data, section, onOpenEvidence }) => (
  <>
    <ComparisonMatrix data={data} codes={sectionCodes[section]} onOpenEvidence={onOpenEvidence} />
    {section === 'overview' && <ComparisonChart data={data} onOpenEvidence={onOpenEvidence} />}
    {data.sections[section].description && <p className={styles.researchNote}>{data.sections[section].description}</p>}
    {data.findings
      .filter(finding => data.sections[section].findingIds.includes(finding.id))
      .map(finding => (
        <FindingCard key={finding.id} finding={finding} onOpenEvidence={onOpenEvidence} />
      ))}
    {!data.sections[section].findingIds.length &&
      !data.workflow?.topics.some(
        topic => topic.section === section && ['failed', 'insufficient', 'needs_revision'].includes(topic.status),
      ) && (
        <p className={styles.sectionDescription}>
          {reportRunState(data).complete
            ? '当前章节暂无通过核验的分析结论；可先查看上方财务数据、指标计算和原文依据。'
            : '正在形成本章节的分析结论；可先查看上方财务数据、指标计算和原文依据。'}
        </p>
      )}
    {data.workflow?.topics
      .filter(topic => topic.section === section && ['failed', 'insufficient', 'needs_revision'].includes(topic.status))
      .map(topic => (
        <p className={styles.researchNote} key={topic.id}>
          {topicStatusNote(topic)}
        </p>
      ))}
  </>
);
export default ComparisonSections;
