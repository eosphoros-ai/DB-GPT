/**
 * QuestionDock — Human-in-the-loop question confirmation UI.
 *
 * Renders above the chat input when the agent's `question` tool
 * pushes a `question.asked` SSE event.  The user selects options
 * and confirms, or dismisses the question entirely.
 */

import { CheckCircleFilled, CheckSquareFilled, CloseOutlined, QuestionCircleFilled } from '@ant-design/icons';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PendingQuestion, questionSlots } from '@/utils/question-session';

export type QuestionRequest = PendingQuestion;

interface QuestionDockProps {
  request: QuestionRequest;
  onReply: (requestId: string, answers: string[][]) => void | Promise<void>;
  onReject: (requestId: string) => void | Promise<void>;
}

const QuestionDockForm: React.FC<QuestionDockProps> = ({ request, onReply, onReject }) => {
  const { t } = useTranslation();
  const questions = useMemo(() => questionSlots(request.questions), [request.questions]);
  const [selected, setSelected] = useState<string[][]>(() => questions.map(() => []));
  const [customInputs, setCustomInputs] = useState<string[]>(() => questions.map(() => ''));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const canSubmit = useMemo(() => {
    return (
      questions.some(Boolean) &&
      questions.every((q, i) => {
        if (!q) return true; // Preserve an empty answer at this ORIGINAL index.
        if (!q.multiple) {
          return (selected[i] || []).length === 1 || (q.custom !== false && (customInputs[i] || '').trim() !== '');
        }
        return (selected[i] || []).length > 0 || (q.custom !== false && (customInputs[i] || '').trim() !== '');
      })
    );
  }, [selected, customInputs, questions]);

  const toggleOption = (qIndex: number, label: string, multiple: boolean) => {
    setSelected(prev => {
      const next = [...prev];
      const current = [...(next[qIndex] || [])];
      if (multiple) {
        const idx = current.indexOf(label);
        if (idx >= 0) current.splice(idx, 1);
        else current.push(label);
      } else {
        current.length = 0;
        current.push(label);
      }
      next[qIndex] = current;
      return next;
    });
    setCustomInputs(prev => {
      const next = [...prev];
      if (!questions[qIndex]?.multiple) next[qIndex] = '';
      return next;
    });
  };

  const setCustom = (qIndex: number, value: string) => {
    setSelected(prev => {
      const next = [...prev];
      next[qIndex] = [];
      return next;
    });
    setCustomInputs(prev => {
      const next = [...prev];
      next[qIndex] = value;
      return next;
    });
  };

  const submit = async (action: () => void | Promise<void>) => {
    if (submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '问题未提交成功，请重试或取消。');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = () => {
    if (!canSubmit || submitting) return;
    const answers = questions.map((q, i) => {
      if (!q) return [];
      if ((selected[i] || []).length > 0) return selected[i];
      if (q.custom !== false && (customInputs[i] || '').trim()) return [customInputs[i].trim()];
      return [];
    });
    void submit(() => onReply(request.request_id, answers));
  };

  const handleDismiss = () => {
    void submit(() => onReject(request.request_id));
  };

  return (
    <div
      role='region'
      aria-label={t('user_confirmation')}
      data-request-id={request.request_id}
      className='w-full overflow-hidden rounded-t-xl border border-b-0 border-slate-200/80 bg-white/95 shadow-[0_-4px_20px_rgba(15,23,42,0.08)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1b1c22]/95 dark:shadow-[0_-4px_20px_rgba(0,0,0,0.25)]'
    >
      {/* Header */}
      <div className='flex items-center justify-between gap-3 px-4 py-2.5'>
        <div className='flex items-center gap-2.5 text-slate-700 dark:text-slate-200'>
          <span className='flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 ring-1 ring-amber-200/80 dark:bg-amber-500/10 dark:ring-amber-500/20'>
            <QuestionCircleFilled className='text-[12px] text-amber-500' />
          </span>
          <span className='text-sm font-semibold leading-5 tracking-tight'>{t('user_confirmation')}</span>
        </div>
        <button
          onClick={handleDismiss}
          disabled={submitting}
          className='flex h-6 w-6 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-white/5 dark:hover:text-slate-300'
          title={t('cancel')}
        >
          <CloseOutlined className='text-[11px]' />
        </button>
      </div>

      <div className='h-px bg-slate-100 dark:bg-white/10' />

      {/* Questions */}
      <div className='max-h-[320px] space-y-4 overflow-y-auto overscroll-contain px-4 py-3'>
        {!questions.length && <div role='alert'>问题内容无效，请取消后让 AI 重新提问。</div>}
        {questions.map((q, qi) =>
          q ? (
            <div key={qi} data-question-index={qi}>
              {/* Header label */}
              {q.header && (
                <div className='mb-1 text-[11px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500'>
                  {q.header}
                </div>
              )}
              {/* Question text */}
              <div className='mb-2 text-sm leading-5 text-slate-800 dark:text-slate-100'>{q.question}</div>
              {/* Options */}
              <div
                className='grid gap-2'
                style={{
                  gridTemplateColumns: `repeat(${q.options.length <= 3 ? Math.max(1, q.options.length) : 2}, 1fr)`,
                }}
              >
                {q.options.map(opt => {
                  const isSelected = (selected[qi] || []).includes(opt.label);
                  const isMultiple = !!q.multiple;
                  return (
                    <button
                      key={opt.label}
                      onClick={() => toggleOption(qi, opt.label, isMultiple)}
                      className={`group relative flex items-start gap-2.5 rounded-lg border p-3 text-left transition-all ${
                        isSelected
                          ? 'border-sky-400 bg-sky-50/80 shadow-sm shadow-sky-100 dark:border-sky-500/50 dark:bg-sky-500/10 dark:shadow-none'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-white/20 dark:hover:bg-white/8'
                      }`}
                    >
                      <span
                        className={`mt-0.5 flex-shrink-0 text-[14px] ${
                          isSelected ? 'text-sky-500 dark:text-sky-400' : 'text-slate-300 dark:text-slate-600'
                        }`}
                      >
                        {isMultiple ? <CheckSquareFilled /> : <CheckCircleFilled />}
                      </span>
                      <span className='flex flex-col gap-0.5 overflow-hidden'>
                        <span
                          className={`text-[13px] font-medium leading-5 ${
                            isSelected ? 'text-sky-700 dark:text-sky-300' : 'text-slate-700 dark:text-slate-200'
                          }`}
                        >
                          {opt.label}
                        </span>
                        {opt.description && (
                          <span className='text-[12px] leading-4 text-slate-400 dark:text-slate-500'>
                            {opt.description}
                          </span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
              {/* Custom input */}
              {q.custom !== false && (
                <div className='mt-2'>
                  <input
                    type='text'
                    aria-label={q.question}
                    placeholder={t('or_input_custom')}
                    value={customInputs[qi] || ''}
                    onChange={e => setCustom(qi, e.target.value)}
                    className='w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] leading-4 text-slate-700 placeholder-slate-400 outline-none transition-colors focus:border-sky-400 focus:ring-1 focus:ring-sky-400/30 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:placeholder-slate-500 dark:focus:border-sky-500/50'
                  />
                </div>
              )}
            </div>
          ) : (
            <div key={qi} data-question-index={qi} role='status' className='text-sm text-amber-700 dark:text-amber-400'>
              第 {qi + 1} 项问题内容无效，该位置将保留为空答；你可以回答其他问题，或取消后让 AI 重新提问。
            </div>
          ),
        )}
      </div>

      {error && (
        <div role='alert' className='px-4 pb-2 text-sm text-red-600 dark:text-red-400'>
          {error}
        </div>
      )}

      {/* Footer with actions */}
      <div className='flex items-center justify-end gap-2 border-t border-slate-100 px-4 py-2.5 dark:border-white/10'>
        <button
          onClick={handleDismiss}
          disabled={submitting}
          className='rounded-lg px-3 py-1.5 text-[13px] text-slate-500 transition-colors hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5'
        >
          {t('cancel')}
        </button>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit || submitting}
          className={`rounded-lg px-4 py-1.5 text-[13px] font-medium transition-all ${
            canSubmit
              ? 'bg-sky-500 text-white shadow-sm hover:bg-sky-600 active:bg-sky-700 dark:bg-sky-600 dark:hover:bg-sky-500'
              : 'cursor-not-allowed bg-slate-100 text-slate-400 dark:bg-white/5 dark:text-slate-600'
          }`}
        >
          {t('confirm')}
        </button>
      </div>
    </div>
  );
};

// A fresh request must never inherit the previous request's selected answers.
const QuestionDock: React.FC<QuestionDockProps> = props => (
  <QuestionDockForm key={`${props.request.conv_id}:${props.request.request_id}`} {...props} />
);

export default QuestionDock;
