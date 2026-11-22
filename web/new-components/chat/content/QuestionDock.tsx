/**
 * QuestionDock — Human-in-the-loop question UI (AskUserQuestion form).
 *
 * Renders above the chat input when the agent's `question` tool pushes a
 * `question.asked` SSE event. Form follows the approved mockup
 * (docs/design/tool-approval-mockup.html, case D): group label + multi-question
 * pagination header, numbered options with inline descriptions, "Other"
 * free-input row, and a footer with Recommend / Skip / Next(Submit).
 * Semantics stay "gather information" — authorization lives in ApprovalDock.
 */

import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { PendingQuestion, questionSlots } from '@/utils/question-session';

export type QuestionRequest = PendingQuestion;

interface QuestionDockProps {
  request: QuestionRequest;
  onReply: (requestId: string, answers: string[][]) => void | Promise<void>;
  onReject: (requestId: string) => void | Promise<void>;
}

const isRecommended = (label: string, description?: string) =>
  /推荐|recommended/i.test(`${label} ${description || ''}`);

const QuestionDockForm: React.FC<QuestionDockProps> = ({ request, onReply, onReject }) => {
  const { t } = useTranslation();
  const questions = useMemo(() => questionSlots(request.questions), [request.questions]);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<string[][]>(() => questions.map(() => []));
  const [customInputs, setCustomInputs] = useState<string[]>(() => questions.map(() => ''));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const total = questions.length;
  const q = questions[page];
  const isLast = page === total - 1;

  const hasCustom = (i: number) =>
    !!questions[i] && questions[i]!.custom !== false && (customInputs[i] || '').trim() !== '';
  const pageAnswered = (i: number) => {
    const qq = questions[i];
    if (!qq) return true; // hole: preserved as empty answer, nothing to input
    const sel = selected[i] || [];
    if (qq.multiple) return sel.length > 0 || hasCustom(i);
    return sel.length === 1 || hasCustom(i);
  };
  const canSubmit = questions.some(Boolean) && questions.every((_, i) => pageAnswered(i));
  const canAdvance = pageAnswered(page);

  const toggleOption = (label: string, multiple: boolean) => {
    setSelected(prev => {
      const next = [...prev];
      const current = [...(next[page] || [])];
      if (multiple) {
        const idx = current.indexOf(label);
        if (idx >= 0) current.splice(idx, 1);
        else current.push(label);
      } else {
        current.length = 0;
        current.push(label);
      }
      next[page] = current;
      return next;
    });
    setCustomInputs(prev => {
      const next = [...prev];
      if (!questions[page]?.multiple) next[page] = '';
      return next;
    });
  };

  const setCustom = (value: string) => {
    setSelected(prev => {
      const next = [...prev];
      next[page] = [];
      return next;
    });
    setCustomInputs(prev => {
      const next = [...prev];
      next[page] = value;
      return next;
    });
  };

  const pickRecommended = () => {
    if (!q || !q.options.length) return;
    const idx = q.options.findIndex(o => isRecommended(o.label, o.description));
    toggleOption(q.options[idx >= 0 ? idx : 0].label, !!q.multiple);
  };

  const submit = async (action: () => void | Promise<void>) => {
    if (submitting) return;
    setSubmitting(true);
    setError('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t('qdock_retry_fail'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = () => {
    if (!canSubmit || submitting) return;
    const answers = questions.map((qq, i) => {
      if (!qq) return [];
      if ((selected[i] || []).length > 0) return selected[i];
      if (qq.custom !== false && (customInputs[i] || '').trim()) return [customInputs[i].trim()];
      return [];
    });
    void submit(() => onReply(request.request_id, answers));
  };

  const handleDismiss = () => {
    void submit(() => onReject(request.request_id));
  };

  const goNext = () => {
    if (!canAdvance || submitting) return;
    if (!isLast) setPage(page + 1);
    else handleSubmit();
  };

  return (
    <div
      role='region'
      aria-label='需要你的回复'
      data-request-id={request.request_id}
      onKeyDown={e => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          goNext();
        }
      }}
      className='w-full overflow-hidden rounded-xl border border-slate-200/80 bg-[#f7f7f8]/95 shadow-[0_12px_40px_rgba(20,20,15,0.14)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1b1c22]/95 dark:shadow-[0_12px_40px_rgba(0,0,0,0.35)]'
    >
      {/* Header: group label + pagination */}
      <div className='flex items-center gap-3 px-[18px] pt-3.5 text-[12.5px] text-slate-400 dark:text-slate-500'>
        <span>{q?.header || t('qdock_group')}</span>
        {total > 1 && (
          <span className='ml-auto flex items-center gap-1.5'>
            <button
              aria-label='上一页'
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className='flex h-[22px] w-[22px] items-center justify-center rounded-md hover:bg-black/5 disabled:opacity-40 dark:hover:bg-white/5'
            >
              <LeftOutlined className='text-[10px]' />
            </button>
            <span className='font-mono tracking-wider'>
              {page + 1} / {total}
            </span>
            <button
              aria-label='下一页'
              disabled={!canAdvance || isLast}
              onClick={() => setPage(page + 1)}
              className='flex h-[22px] w-[22px] items-center justify-center rounded-md hover:bg-black/5 disabled:opacity-40 dark:hover:bg-white/5'
            >
              <RightOutlined className='text-[10px]' />
            </button>
          </span>
        )}
      </div>

      {/* Question title / invalid-slot note */}
      {q ? (
        <div className='px-[18px] pb-1.5 pt-2 text-[15px] font-semibold leading-6 text-slate-800 dark:text-slate-100'>
          {q.question}
        </div>
      ) : (
        <div role='status' className='px-[18px] pb-1.5 pt-2 text-[13px] text-amber-700 dark:text-amber-400'>
          {t('qdock_invalid', { n: page + 1 })}
        </div>
      )}

      {/* Options: numbered rows */}
      <div className='max-h-[300px] space-y-1 overflow-y-auto overscroll-contain px-3 pb-1'>
        {q?.options.map((opt, oi) => {
          const isSelected = (selected[page] || []).includes(opt.label);
          return (
            <button
              key={opt.label}
              onClick={() => toggleOption(opt.label, !!q.multiple)}
              className={`flex w-full items-start gap-3 rounded-[10px] px-3 py-2 text-left transition-colors ${
                isSelected
                  ? 'bg-white shadow-[0_0_0_1px_var(--tw-ring-color,#e6e6e2)] dark:bg-white/10'
                  : 'hover:bg-white/70 dark:hover:bg-white/5'
              }`}
            >
              <span
                className={`mt-0.5 flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-full font-mono text-[12px] ${
                  isSelected
                    ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900'
                    : 'bg-[#e8e8e6] text-slate-500 dark:bg-white/10 dark:text-slate-400'
                }`}
              >
                {oi + 1}
              </span>
              <span className='min-w-0 text-[13px] leading-[22px]'>
                <span className='font-semibold text-slate-800 dark:text-slate-100'>{opt.label}</span>
                {opt.description && (
                  <span className='ml-2 font-normal text-slate-400 dark:text-slate-500'>{opt.description}</span>
                )}
              </span>
            </button>
          );
        })}
        {/* Other free-input row */}
        {q && q.custom !== false && (
          <div className='flex items-center gap-3 px-3 py-2'>
            <span className='flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-full bg-[#e8e8e6] font-mono text-[12px] text-slate-500 dark:bg-white/10 dark:text-slate-400'>
              …
            </span>
            <input
              type='text'
              aria-label={q.question}
              placeholder={t('qdock_other')}
              value={customInputs[page] || ''}
              onChange={e => setCustom(e.target.value)}
              className='w-full bg-transparent text-[13px] text-slate-700 placeholder-slate-400 outline-none dark:text-slate-200 dark:placeholder-slate-500'
            />
          </div>
        )}
      </div>

      {error && (
        <div role='alert' className='px-[18px] pb-2 text-[13px] text-red-600 dark:text-red-400'>
          {error}
        </div>
      )}

      {/* Footer: recommend | skip + next/submit */}
      <div className='flex items-center gap-2.5 px-[18px] pb-3.5 pt-2.5'>
        <button
          onClick={pickRecommended}
          disabled={!q || submitting}
          className='flex h-[30px] items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-[12.5px] text-slate-500 transition-colors hover:bg-slate-50 disabled:opacity-40 dark:border-white/10 dark:bg-white/5 dark:text-slate-400'
        >
          <svg width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2'>
            <path d='m15 4 5 5-11 11H4v-5L15 4Z' />
            <path d='m13 6 5 5' />
          </svg>
          {t('qdock_recommend')}
        </button>
        <span className='ml-auto flex items-center gap-3.5'>
          <button
            onClick={handleDismiss}
            disabled={submitting}
            className='text-[13px] text-slate-500 transition-colors hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
          >
            {t('qdock_skip')}
          </button>
          <button
            onClick={goNext}
            disabled={(isLast ? !canSubmit : !canAdvance) || submitting}
            className={`flex h-8 items-center gap-1.5 rounded-lg px-4 text-[13px] transition-colors ${
              isLast ? (canSubmit ? 'bg-slate-800 text-white hover:bg-black dark:bg-slate-200 dark:text-slate-900' : 'cursor-not-allowed bg-[#e8e8e6] text-slate-400 dark:bg-white/5 dark:text-slate-600') : canAdvance ? 'bg-slate-800 text-white hover:bg-black dark:bg-slate-200 dark:text-slate-900' : 'cursor-not-allowed bg-[#e8e8e6] text-slate-400 dark:bg-white/5 dark:text-slate-600'
            }`}
          >
            {isLast ? t('qdock_submit') : t('qdock_next')} <span className='font-mono'>↵</span>
          </button>
        </span>
      </div>
    </div>
  );
};

// A fresh request must never inherit the previous request's selected answers.
const QuestionDock: React.FC<QuestionDockProps> = props => (
  <QuestionDockForm key={`${props.request.conv_id}:${props.request.request_id}`} {...props} />
);

export default QuestionDock;
