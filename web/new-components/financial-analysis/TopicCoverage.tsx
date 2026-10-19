import React from 'react';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';

const labels = {
  pending: '待分析',
  running: '分析中',
  ready: '待复核',
  reviewed: '已复核，待人工核对',
  insufficient: '数据或依据不足',
  failed: '分析失败',
  needs_revision: '待修订',
};

/** Detail of the selected execution step; never a second report card grid. */
const TopicCoverage: React.FC<{
  topicId: string;
  onRetry?: (topicId: string) => void;
  busy?: boolean;
}> = ({ topicId, onRetry, busy }) => {
  const { data } = useReportData();
  const topic = data.workflow?.topics.find(item => item.id === topicId);
  if (!topic) return null;
  return (
    <div aria-label='专题执行详情'>
      <p>
        {labels[topic.status]} · {topic.findingIds.length} 条发现 ·{' '}
        {topic.saveAttempts ?? topic.history.length + topic.failures} 次保存尝试 · {topic.failures} 次校验失败
      </p>
      {topic.errorCode && <p>后端状态：{topic.errorCode}</p>}
      {!!topic.issues?.length && (
        <ul className={styles.topicIssues} aria-label='校验错误'>
          {topic.issues.map((issue, index) => (
            <li key={index}>
              {issue.finding_index !== undefined ? `发现 ${issue.finding_index + 1} · ` : ''}
              {issue.field ? `${issue.field}：` : ''}
              {issue.code}
              {issue.invalid_tokens?.length ? `（${issue.invalid_tokens.join('、')}）` : ''}
              {issue.missing_metrics?.length ? `；未覆盖科目：${issue.missing_metrics.join('、')}` : ''}
              {issue.hint && <div>{issue.hint}</div>}
            </li>
          ))}
        </ul>
      )}
      {!!topic.validationHistory?.length && (
        <details>
          <summary>历史校验记录</summary>
          {topic.validationHistory.map((entry, index) => (
            <div key={index}>
              <p>
                {entry.at} · {entry.errorCode}
              </p>
              <ul className={styles.topicIssues}>
                {entry.issues.map((issue, pos) => (
                  <li key={pos}>
                    {issue.finding_index !== undefined ? `发现 ${issue.finding_index + 1} · ` : ''}
                    {issue.field}：{issue.code}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
      {topic.review && <p>智能体复核意见：{topic.review.note}</p>}
      {onRetry && (
        <button type='button' className={styles.textLink} disabled={busy} onClick={() => onRetry(topic.id)}>
          {topic.status === 'pending' ? '分析此专题' : '重新分析此专题'}
        </button>
      )}
    </div>
  );
};
export default TopicCoverage;
