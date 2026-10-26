import React from 'react';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';

const labels = {
  get pending() {
    return financialText('financial.awaiting_analysis_2');
  },
  get running() {
    return financialText('financial.analyzing');
  },
  get ready() {
    return financialText('financial.awaiting_review');
  },
  get reviewed() {
    return financialText('financial.reviewed_awaiting_human_verification');
  },
  get insufficient() {
    return financialText('financial.insufficient_data_or_evidence');
  },
  get failed() {
    return financialText('financial.analysis_failed');
  },
  get needs_revision() {
    return financialText('financial.awaiting_revision');
  },
};

/** Detail of the selected execution step; never a second report card grid. */
const TopicCoverage: React.FC<{
  topicId: string;
  onRetry?: (topicId: string) => void;
  busy?: boolean;
}> = ({ topicId, onRetry, busy }) => {
  useFinancialLocale();
  const { data } = useReportData();
  const topic = data.workflow?.topics.find(item => item.id === topicId);
  if (!topic) return null;
  return (
    <div aria-label={financialText('financial.topic_execution_details')}>
      <p>
        {labels[topic.status]} · {topic.findingIds.length} {financialText('financial.findings_2')}{' '}
        {topic.saveAttempts ?? topic.history.length + topic.failures} {financialText('financial.save_attempts')}
        {topic.failures} {financialText('financial.validation_failures')}
      </p>
      {topic.errorCode && (
        <p>
          {financialText('financial.backend_status')}
          {topic.errorCode}
        </p>
      )}
      {!!topic.issues?.length && (
        <ul className={styles.topicIssues} aria-label={financialText('financial.validation_errors')}>
          {topic.issues.map((issue, index) => (
            <li key={index}>
              {issue.finding_index !== undefined
                ? financialText('financial.findings_value', { value1: issue.finding_index + 1 })
                : ''}
              {issue.field ? `${issue.field}：` : ''}
              {issue.code}
              {issue.invalid_tokens?.length ? `（${issue.invalid_tokens.join('、')}）` : ''}
              {issue.missing_metrics?.length
                ? financialText('financial.uncovered_items_value', { value1: issue.missing_metrics.join('、') })
                : ''}
              {issue.hint && <div>{issue.hint}</div>}
            </li>
          ))}
        </ul>
      )}
      {!!topic.validationHistory?.length && (
        <details>
          <summary>{financialText('financial.validation_history')}</summary>
          {topic.validationHistory.map((entry, index) => (
            <div key={index}>
              <p>
                {entry.at} · {entry.errorCode}
              </p>
              <ul className={styles.topicIssues}>
                {entry.issues.map((issue, pos) => (
                  <li key={pos}>
                    {issue.finding_index !== undefined
                      ? financialText('financial.findings_value', { value1: issue.finding_index + 1 })
                      : ''}
                    {issue.field}：{issue.code}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
      {topic.review && (
        <p>
          {financialText('financial.agent_review')}
          {topic.review.note}
        </p>
      )}
      {onRetry && (
        <button type='button' className={styles.textLink} disabled={busy} onClick={() => onRetry(topic.id)}>
          {topic.status === 'pending'
            ? financialText('financial.analyze_this_topic')
            : financialText('financial.reanalyze_this_topic')}
        </button>
      )}
    </div>
  );
};
export default TopicCoverage;
