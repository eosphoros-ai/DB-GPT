import { CheckCircleFilled } from '@ant-design/icons';
import React from 'react';
import { useReportData } from './ReportDataContext';
import TopicCoverage from './TopicCoverage';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';
import { runStatusLabels, topicStatusNote } from './report-data';
export interface AnalysisActions {
  retry: () => void;
  refresh: () => void;
  busy: boolean;
  error?: string;
}

const analysisStatusLabels = {
  get running() {
    return financialText('financial.analyzing');
  },
  get completed() {
    return financialText('financial.analysis_complete');
  },
  get partial() {
    return financialText('financial.partial_analysis');
  },
  get failed() {
    return financialText('financial.analysis_incomplete');
  },
};

const ExecutionProcessPanel: React.FC<{
  activeStepId?: string;
  onStepSelect: (stepId: string) => void;
  analysisActions?: AnalysisActions;
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
}> = ({ activeStepId, onStepSelect, analysisActions, onTopicRetry, busy }) => {
  useFinancialLocale();
  const { data } = useReportData();
  const agentExecutionSteps = data.steps;
  const activeStep = agentExecutionSteps.find(step => step.id === activeStepId) || agentExecutionSteps[0];
  if (!activeStep)
    return <div className={styles.executionPanel}>{financialText('financial.no_execution_records')}</div>;
  const activeTopic = data.workflow?.topics.find(topic => activeStep.id === `topic-${topic.id}`);
  const analysis = data.mode === 'report' && activeStep.id === 'analyze' ? data.analysis : undefined;
  return (
    <div className={styles.executionPanel}>
      <nav aria-label={financialText('financial.execution_steps')} className={styles.executionSteps}>
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
        {data.mode === 'comparison' && (
          <section aria-label={financialText('financial.document_status')}>
            {data.members.map(member => (
              <p key={member.file_id}>
                {member.file_name}：
                {member.status === 'completed'
                  ? financialText('financial.extracted_and_saved')
                  : member.status === 'failed'
                    ? financialText('financial.extraction_failed')
                    : member.status === 'interrupted'
                      ? financialText('financial.extraction_interrupted')
                      : financialText('financial.awaiting_extraction')}
                {member.error && ` · ${member.error}`}
              </p>
            ))}
            {analysisActions && (
              <button
                type='button'
                className={styles.textLink}
                disabled={analysisActions.busy}
                onClick={analysisActions.retry}
              >
                {financialText('financial.resume_or_retry_incomplete_files')}
              </button>
            )}
          </section>
        )}
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
        {activeStep.id === 'review' && !!data.analysis?.reviewIssues?.length && (
          <details>
            <summary>{financialText('financial.review_incomplete_data_and_validated_findings_are_retained')}</summary>
            <ul>
              {data.analysis.reviewIssues.map((issue, index) => (
                <li key={index}>{issue}</li>
              ))}
            </ul>
          </details>
        )}
        {activeStep.id === 'quality' && data.workflow?.dataQuality && (
          <p>
            {financialText('financial.extracted_summary', {
              available: data.workflow.dataQuality.availableFacts,
              unavailable: data.workflow.dataQuality.unavailableCalculations.length,
            })}
          </p>
        )}
        {activeStep.elapsedMs !== undefined && (
          <p className={styles.meta}>
            {financialText('financial.elapsed_seconds', { seconds: (activeStep.elapsedMs / 1000).toFixed(2) })}
          </p>
        )}
        {analysis && analysisActions && (
          <>
            {analysisActions.error && (
              <p>
                {analysisActions.error}{' '}
                <button type='button' className={styles.textLink} onClick={analysisActions.refresh}>
                  {financialText('financial.reload_progress')}
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
                {analysisActions.busy
                  ? financialText('financial.processing')
                  : data.mode === 'comparison'
                    ? financialText('financial.resume_comparison')
                    : financialText('financial.reanalyze_this_file')}
              </button>
            )}
          </>
        )}
        <dl className={styles.driverTable}>
          {activeStep.tool && (
            <div>
              <dt>{financialText('financial.tool')}</dt>
              <dd>{activeStep.tool}</dd>
            </div>
          )}
          {activeStep.script && (
            <div>
              <dt>{financialText('financial.script')}</dt>
              <dd>{activeStep.script}</dd>
            </div>
          )}
        </dl>
      </section>
    </div>
  );
};
export default ExecutionProcessPanel;
