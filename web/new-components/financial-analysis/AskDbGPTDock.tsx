import { ArrowRightOutlined, CloseOutlined, InfoCircleOutlined, SendOutlined } from '@ant-design/icons';
import { Button, Input, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useReportData } from './ReportDataContext';
import styles from './financial-analysis.module.css';
import { EvidenceSelection, OpenEvidence, ReportQuestionAccess, ReportQuestionAnswer } from './types';
interface AskDbGPTDockProps {
  onOpenEvidence: OpenEvidence;
  questionAccess?: ReportQuestionAccess;
}
const AskDbGPTDock: React.FC<AskDbGPTDockProps> = ({ onOpenEvidence, questionAccess }) => {
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
        answer: value.length > 1000 ? '问题请控制在 1000 字以内。' : '追问服务尚未就绪，请刷新后重试。',
      });
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setAnswer({ question: value, answer: '正在根据当前报告查找依据…' });
    try {
      const result = await questionAccess.ask(value, data.revision, controller.signal);
      if (controller.signal.aborted) return;
      if (result.runId !== data.report.run.id || result.revision !== data.revision) {
        throw new Error('报告已更新，请重新发送问题。');
      }
      setAnswer({ question: value, answer: result.answer, citations: result.citations });
    } catch (cause) {
      if (!controller.signal.aborted) {
        setAnswer({
          question: value,
          answer: cause instanceof Error ? cause.message : '追问失败，请重新发送问题。',
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
        placeholder='Ask DB-GPT about this report…'
        aria-label='向 DB-GPT 追问报告'
        className={styles.composerInput}
        suffix={
          <Button
            type='primary'
            size='small'
            icon={<SendOutlined />}
            onClick={() => submit()}
            disabled={!query.trim() || pending}
            loading={pending}
            aria-label='发送问题'
          />
        }
      />
      {answer && (
        <div className={styles.answer} role='status'>
          <div className={styles.answerHeading}>
            <span>
              DB-GPT{' '}
              <Tooltip title='基于当前报告回答，数字与引用可核对。'>
                <InfoCircleOutlined />
              </Tooltip>
            </span>
            <button
              type='button'
              aria-label='收起回答'
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
              {index === 0 ? '查看回答依据' : `查看依据 ${index + 1}`} <ArrowRightOutlined />
            </button>
          ))}
        </div>
      )}
    </section>
  );
};
export default AskDbGPTDock;
