import { CheckCircleFilled } from '@ant-design/icons';
import React from 'react';
import { useReportData } from './ReportDataContext';
import TopicCoverage from './TopicCoverage';
import styles from './financial-analysis.module.css';
import { runStatusLabels, topicStatusNote } from './report-data';
export interface AnalysisActions {
  retry: () => void;
  refresh: () => void;
  busy: boolean;
  error?: string;
}

const analysisStatusLabels = {
  running: '分析中',
  completed: '分析完成',
  partial: '部分分析',
  failed: '分析未完成',
};

const ExecutionProcessPanel: React.FC<{
  activeStepId?: string;
  onStepSelect: (stepId: string) => void;
  analysisActions?: AnalysisActions;
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
}> = ({ activeStepId, onStepSelect, analysisActions, onTopicRetry, busy }) => {
  const { data } = useReportData();
  const agentExecutionSteps = data.steps;
  const activeStep = agentExecutionSteps.find(step => step.id === activeStepId) || agentExecutionSteps[0];
  if (!activeStep) return <div className={styles.executionPanel}>暂无执行记录</div>;
  const activeTopic = data.workflow?.topics.find(topic => activeStep.id === `topic-${topic.id}`);
  const analysis = data.mode === 'report' && activeStep.id === 'analyze' ? data.analysis : undefined;
  return (
    <div className={styles.executionPanel}>
      <nav aria-label='执行步骤' className={styles.executionSteps}>
        {agentExecutionSteps.map(step => (
          <button
            type='button'
            key={step.id}
            aria-current={step.id === activeStep.id ? 'step' : undefined}
            onClick={() => onStepSelect(step.id)}
          >
            {step.status === 'completed' && <CheckCircleFilled />}
            <span>{step.title}</span>
          </button>
        ))}
      </nav>
      <section className={styles.executionDetail}>
        <div className={styles.meta}>
          Step {activeStep.order} ·{' '}
          {analysis ? analysisStatusLabels[analysis.status] : runStatusLabels[activeStep.status]}
        </div>
        <h2>{activeStep.title}</h2>
        <p>{activeTopic ? topicStatusNote(activeTopic) : activeStep.detail}</p>
        {activeStep.id.startsWith('topic-') && (
          <TopicCoverage topicId={activeStep.id.slice(6)} onRetry={onTopicRetry} busy={busy} />
        )}
        {activeStep.id === 'review' && data.workflow?.review && (
          <ul>
            {data.workflow.review.items.map(item => (
              <li key={item.topic_id}>
                {data.workflow?.topics.find(topic => topic.id === item.topic_id)?.title}：{item.note}
              </li>
            ))}
          </ul>
        )}
        {activeStep.id === 'quality' && data.workflow?.dataQuality && (
          <p>
            已提取 {data.workflow.dataQuality.availableFacts} 个可用值，
            {data.workflow.dataQuality.unavailableCalculations.length} 项不可计算。
            这表示当前提取范围，不代表整份年报覆盖率。
          </p>
        )}
        {data.mode === 'report' && activeStep.elapsedMs !== undefined && (
          <p className={styles.meta}>耗时 {(activeStep.elapsedMs / 1000).toFixed(2)} 秒</p>
        )}
        {analysis && analysisActions && (
          <>
            {analysisActions.error && (
              <p>
                {analysisActions.error}{' '}
                <button type='button' className={styles.textLink} onClick={analysisActions.refresh}>
                  重新读取进度
                </button>
              </p>
            )}
            {(analysis.status === 'partial' || analysis.status === 'failed') && (
              <button
                type='button'
                className={styles.textLink}
                disabled={analysisActions.busy}
                onClick={analysisActions.retry}
              >
                {analysisActions.busy ? '正在创建任务…' : '重新分析此文件'}
              </button>
            )}
          </>
        )}
        <dl className={styles.driverTable}>
          {activeStep.tool && (
            <div>
              <dt>工具</dt>
              <dd>{activeStep.tool}</dd>
            </div>
          )}
          {activeStep.script && (
            <div>
              <dt>脚本</dt>
              <dd>{activeStep.script}</dd>
            </div>
          )}
        </dl>
      </section>
    </div>
  );
};
export default ExecutionProcessPanel;
