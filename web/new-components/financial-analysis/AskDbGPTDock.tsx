import { ArrowRightOutlined, CloseOutlined, InfoCircleOutlined, SendOutlined } from '@ant-design/icons';
import { Button, Input, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';
import { EvidenceSelection, OpenEvidence, ReportQuestionAccess, ReportQuestionAnswer } from './types';
interface AskDbGPTDockProps {
  onOpenEvidence: OpenEvidence;
  questionAccess?: ReportQuestionAccess;
}
const AskDbGPTDock: React.FC<AskDbGPTDockProps> = ({ onOpenEvidence, questionAccess }) => {
  useFinancialLocale();
  const { data } = useReportData();
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<
    (Pick<ReportQuestionAnswer, 'question' | 'answer'> & { citations?: EvidenceSelection[] }) | null
  >(null);
  const [pending, setPending] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const submit = async () => {
    const value = query.trim();
    if (!value || request.current) return;
    setQuery(value);
    if (value.length > 1000 || !questionAccess) {
      setAnswer({
        question: value,
        answer:
          value.length > 1000
            ? financialText('financial.keep_your_question_within_1_000_characters')
            : financialText('financial.report_questions_are_not_ready_refresh_and_retry'),
      });
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setAnswer({ question: value, answer: financialText('financial.finding_evidence_in_the_current_report') });
    try {
      const result = await questionAccess.ask(value, data.revision, controller.signal);
      if (controller.signal.aborted) return;
      if (result.runId !== data.report.run.id || result.revision !== data.revision) {
        throw new Error(financialText('financial.the_report_has_changed_please_resend_your_question'));
      }
      setAnswer({ question: value, answer: result.answer, citations: result.citations });
    } catch (cause) {
      if (!controller.signal.aborted) {
        setAnswer({
          question: value,
          answer:
            cause instanceof Error ? cause.message : financialText('financial.the_question_failed_please_resend_it'),
        });
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setPending(false);
      }
    }
  };
  return (
    <section className={styles.composer} aria-label='Ask DB-GPT'>
      <Input
        value={query}
        onChange={event => setQuery(event.target.value)}
        onPressEnter={event => {
          if (!event.nativeEvent.isComposing) submit();
        }}
        placeholder={financialText('financial.ask_db_gpt_about_this_report')}
        aria-label={financialText('financial.ask_db_gpt_about_this_report')}
        className={styles.composerInput}
        suffix={
          <Button
            type='primary'
            size='small'
            icon={<SendOutlined />}
            onClick={() => submit()}
            disabled={!query.trim() || pending}
            loading={pending}
            aria-label={financialText('financial.send_question')}
          />
        }
      />
      {answer && (
        <div className={styles.answer} role='status'>
          <div className={styles.answerHeading}>
            <span>
              DB-GPT{' '}
              <Tooltip
                title={financialText('financial.answers_use_this_report_with_verifiable_figures_and_references')}
              >
                <InfoCircleOutlined />
              </Tooltip>
            </span>
            <button
              type='button'
              aria-label={financialText('financial.collapse_answer')}
              onClick={() => {
                request.current?.abort();
                request.current = null;
                setPending(false);
                setAnswer(null);
              }}
            >
              <CloseOutlined />
            </button>
          </div>
          <p>{answer.answer}</p>
          {answer.citations?.map((selection, index) => (
            <button
              type='button'
              key={selection.calculationId || selection.factId}
              className={styles.textLink}
              onClick={() => onOpenEvidence(selection)}
            >
              {index === 0
                ? financialText('financial.view_answer_evidence')
                : financialText('financial.view_evidence_value', { value1: index + 1 })}{' '}
              <ArrowRightOutlined />
            </button>
          ))}
        </div>
      )}
    </section>
  );
};
export default AskDbGPTDock;
