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

const TopicCoverage: React.FC<{ onRetry?: (topicId: string) => void; busy?: boolean }> = ({ onRetry, busy }) => {
  const { data } = useReportData();
  if (!data.workflow) return null;
  return (
    <section className={styles.topicCoverage} aria-label='专题分析进度'>
      {data.workflow.dataQuality && <p className={styles.meta}>
        已提取 {data.workflow.dataQuality.availableFacts} 个可用值，
        {data.workflow.dataQuality.unavailableCalculations.length} 项不可计算。
        这表示当前提取范围，不代表整份年报覆盖率。
      </p>}
      <div className={styles.meta}>
        {data.workflow.status === 'published' ? '已发布' : '分析草稿，可继续当前任务'} · 已保存 {data.findings.length}{' '}
        条发现 · 智能体复核不等于人工确认
      </div>
      <div className={styles.topicGrid}>
        {data.workflow.topics.map(topic => (
          <article key={topic.id} className={styles.topicCard}>
            <strong>{topic.title}</strong>
            <span>{topic.status === 'running' && !busy ? '尚未完成，可继续' : labels[topic.status]}</span>
            <p>{topic.note}</p>
            {topic.review && <p>复核：{topic.review.note}</p>}
            <small>
              {topic.findingIds.length} 条发现 · {topic.history.length} 次保存
            </small>
            {onRetry && (
              <button type='button' className={styles.textLink} disabled={busy} onClick={() => onRetry(topic.id)}>
                {topic.status === 'pending' ? '分析此专题' : '重新分析此专题'}
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
};

export default TopicCoverage;
