import React from 'react';
import FindingCard from '../FindingCard';
import styles from '../financial-analysis.module.css';
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
    {!data.sections[section].findingIds.length && (
      <p className={styles.sectionDescription}>当前章节的分析尚未形成或依据不足，已提取数据与确定性计算仍可核对。</p>
    )}
    {data.workflow?.topics
      .filter(topic => topic.section === section && ['failed', 'insufficient', 'needs_revision'].includes(topic.status))
      .map(topic => (
        <p className={styles.researchNote} key={topic.id}>
          {topic.note}
        </p>
      ))}
  </>
);
export default ComparisonSections;
