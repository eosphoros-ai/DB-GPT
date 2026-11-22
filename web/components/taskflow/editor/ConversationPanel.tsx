import { renderModelIcon } from '@/components/chat/header/model-selector';
import type { GenerationSession } from '@/types/taskflow-generation';
import { Button, Input, Select, Spin, Tag } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface Props {
  session: GenerationSession | null;
  busy: boolean;
  error: string | null;
  selectedId: string | null;
  models: string[];
  defaultModel: string;
  onRefreshModels?: () => void;
  onSend: (
    text: string,
    model: string,
    local: boolean,
    replace: boolean,
    answers: Record<string, string>,
  ) => Promise<boolean>;
  onAction: (action: 'apply' | 'discard' | 'undo' | 'cancel') => void;
  onSelect: (id: string) => void;
}

export default function ConversationPanel({
  session,
  busy,
  error,
  selectedId,
  models,
  defaultModel,
  onRefreshModels,
  onSend,
  onAction,
  onSelect,
}: Props) {
  const { i18n } = useTranslation();
  const zh = i18n.language?.startsWith('zh');
  const text = (cn: string, en: string) => (zh ? cn : en);
  const [input, setInput] = useState('');
  const [model, setModel] = useState(defaultModel);
  const [local, setLocal] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const bottom = useRef<HTMLDivElement>(null);
  const active = Object.values(session?.requests ?? {}).find(req => req.status === 'running');
  const pending = session?.candidate?.status === 'pending' ? session.candidate : null;
  const candidate = session?.candidate;
  useEffect(() => {
    if (!model && defaultModel) setModel(defaultModel);
  }, [model, defaultModel]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'nearest' });
  }, [session?.messages.length, session?.candidate?.candidate_id]);
  const questionKey = JSON.stringify(session?.questions ?? []);
  useEffect(() => setAnswers({}), [questionKey]);

  const send = async (replace = false) => {
    const value = input.trim() || Object.values(answers).filter(Boolean).join('；');
    if (!value) return;
    if (await onSend(value, model, local, replace, answers)) {
      setInput('');
      setAnswers({});
    }
  };

  return (
    <aside
      data-testid='workflow-conversation'
      className='w-[340px] xl:w-[370px] flex-none flex flex-col min-h-0 bg-white dark:bg-[#16171a] border-r border-gray-100 dark:border-white/10'
    >
      <div className='px-4 py-4 border-b border-gray-100 dark:border-white/10'>
        <div className='flex items-center gap-2 text-[14px] font-semibold'>
          <span className='text-violet-500'>✦</span>
          {text('对话创建工作流', 'Build with conversation')}
          {session && <span className='ml-auto text-[10px] text-gray-400'>v{session.draft_revision}</span>}
        </div>
        <p className='text-xs text-gray-400 mt-1.5 leading-relaxed'>
          {text(
            '描述目标，补充需求，再逐步调整 Agent 分工。',
            'Describe the goal, clarify requirements and refine Agent roles.',
          )}
        </p>
      </div>
      <div className='flex-1 min-h-0 overflow-y-auto p-4 space-y-3'>
        {!session?.messages.length && (
          <div className='rounded-xl bg-violet-50 dark:bg-violet-500/10 p-3.5'>
            <div className='text-[13px] font-medium mb-2'>
              {text('你希望 Agent 帮你完成什么？', 'What should your Agents accomplish?')}
            </div>
            <p className='text-xs text-gray-500 leading-relaxed'>
              {text(
                '可以先说目标；关键信息不足时，我会继续询问。已有流程的修改会先展示差异。',
                'Start with a goal. I will ask about missing requirements and preview changes to existing workflows.',
              )}
            </p>
            <button
              className='mt-3 text-xs text-violet-600 text-left leading-relaxed'
              onClick={() =>
                setInput(
                  text(
                    '分析用户提供的销售数据：先检查数据质量，再分析趋势，最后输出结论。不连接数据库。',
                    'Analyze sales data provided by the user: check data quality, analyze trends, then summarize findings. No database connection.',
                  ),
                )
              }
            >
              {text('试试：数据检查 → 趋势分析 → 总结', 'Try: Data checks → Trend analysis → Summary')}
            </button>
          </div>
        )}
        {(session?.messages ?? []).map((item, index) => (
          <div
            key={index}
            className={`rounded-xl px-3.5 py-3 text-[12.5px] leading-relaxed whitespace-pre-wrap break-words ${item.role === 'user' ? 'bg-violet-50 dark:bg-violet-500/10 ml-5' : 'bg-gray-50 dark:bg-white/5 mr-2'}`}
          >
            <div className='text-[10px] text-gray-400 mb-1'>
              {item.role === 'user' ? text('你', 'You') : text('工作流助手', 'Workflow assistant')}
            </div>
            {item.text}
          </div>
        ))}
        {(session?.questions ?? []).map(question => (
          <div key={question.question_id} className='rounded-xl border border-violet-100 dark:border-violet-500/20 p-3'>
            <div className='text-[12.5px] font-medium mb-2'>{question.text}</div>
            <div className='flex flex-wrap gap-1.5 mb-2'>
              {question.options.map(option => (
                <Button
                  size='small'
                  key={option}
                  type={answers[question.question_id] === option ? 'primary' : 'default'}
                  onClick={() => setAnswers(prev => ({ ...prev, [question.question_id]: option }))}
                >
                  {option}
                </Button>
              ))}
            </div>
            <Input
              size='small'
              value={answers[question.question_id] || ''}
              placeholder={text('也可以填写其他需求', 'Or enter your own answer')}
              onChange={event => setAnswers(prev => ({ ...prev, [question.question_id]: event.target.value }))}
            />
          </div>
        ))}
        {candidate && (
          <div
            data-testid='generation-preview'
            className='rounded-xl border border-gray-200 dark:border-white/10 p-3.5'
          >
            <div className='flex items-center gap-2 text-xs font-semibold mb-3'>
              {text('流程修改', 'Workflow changes')}
              <Tag
                color={candidate.status === 'pending' ? 'purple' : candidate.status === 'stale' ? 'orange' : 'default'}
                className='!m-0 !text-[10px]'
              >
                {
                  {
                    pending: text('待应用', 'Pending'),
                    applied: text('已应用', 'Applied'),
                    discarded: text('已放弃', 'Discarded'),
                    stale: text('已过期', 'Stale'),
                  }[candidate.status]
                }
              </Tag>
            </div>
            {pending && (
              <div className='mb-3 rounded-lg bg-violet-50 dark:bg-violet-500/10 px-3 py-2 text-[11px] leading-relaxed'>
                <div className='text-violet-600 mb-1'>{text('建议执行顺序', 'Proposed sequence')}</div>
                {candidate.candidate_dsl.nodes.map(node => node.label || node.kind).join(' → ')}
              </div>
            )}
            {candidate.change_summary.map((change, index) => (
              <div key={index} className='text-xs py-1.5 border-b border-gray-50 dark:border-white/5'>
                <span
                  className={
                    change.type === 'added'
                      ? 'text-green-600'
                      : change.type === 'removed'
                        ? 'text-red-500'
                        : 'text-violet-500'
                  }
                >
                  {change.type === 'added' ? '+' : change.type === 'removed' ? '−' : '↻'}
                </span>
                <span className='ml-2'>{change.label}</span>
                {change.fields.length > 0 && (
                  <div className='text-[10px] text-gray-400 mt-1 ml-4'>{change.fields.join(' · ')}</div>
                )}
                {(change.before || change.after) && (
                  <details className='mt-1.5 ml-4'>
                    <summary className='text-[11px] text-violet-600 cursor-pointer'>
                      {text('查看修改内容', 'Inspect changes')}
                    </summary>
                    {change.before && (
                      <div className='mt-2'>
                        <div className='text-gray-400 text-[10px]'>{text('修改前', 'Before')}</div>
                        <pre className='text-[10.5px] whitespace-pre-wrap break-words bg-gray-50 dark:bg-white/5 rounded p-2 mt-1'>
                          {JSON.stringify(change.before.config, null, 2)}
                        </pre>
                      </div>
                    )}
                    {change.after && (
                      <div className='mt-2'>
                        <div className='text-gray-400 text-[10px]'>{text('修改后', 'After')}</div>
                        <pre className='text-[10.5px] whitespace-pre-wrap break-words bg-violet-50 dark:bg-violet-500/10 rounded p-2 mt-1'>
                          {JSON.stringify(change.after.config, null, 2)}
                        </pre>
                      </div>
                    )}
                  </details>
                )}
              </div>
            ))}
            {candidate.assumptions?.length > 0 && (
              <div className='text-[11px] text-gray-500 mt-2'>
                {text('待确认假设：', 'Assumptions: ')}
                {candidate.assumptions.join('；')}
              </div>
            )}
            {candidate.status !== 'discarded' &&
              candidate.status !== 'stale' &&
              candidate.missing_configuration.map((gap, index) => (
                <button
                  key={index}
                  className='text-left block mt-2 w-full rounded-lg bg-amber-50 dark:bg-amber-500/10 px-2.5 py-2 text-xs text-amber-700'
                  onClick={() => onSelect(gap.node_id)}
                >
                  {gap.message} ↗
                </button>
              ))}
            {pending && (
              <div className='flex gap-2 mt-3'>
                <Button type='primary' size='small' disabled={busy} onClick={() => onAction('apply')}>
                  {text('应用修改', 'Apply changes')}
                </Button>
                <Button size='small' disabled={busy} onClick={() => onAction('discard')}>
                  {text('放弃', 'Discard')}
                </Button>
              </div>
            )}
          </div>
        )}
        {session?.undo && !pending && (
          <Button size='small' type='text' disabled={busy} onClick={() => onAction('undo')}>
            {text('撤销最近一次应用', 'Undo last application')}
          </Button>
        )}
        {active && (
          <div className='text-xs text-violet-600 flex items-center gap-2'>
            <Spin size='small' />
            {active.phase}
            <Button size='small' type='text' onClick={() => onAction('cancel')}>
              {text('取消生成', 'Cancel')}
            </Button>
          </div>
        )}
        {error && (
          <div
            role='alert'
            className='text-xs text-red-600 bg-red-50 dark:bg-red-500/10 rounded-lg p-3 whitespace-pre-wrap'
          >
            {error}
          </div>
        )}
        <div ref={bottom} />
      </div>
      <div className='border-t border-gray-100 dark:border-white/10 p-3.5 space-y-2.5'>
        <div className='flex gap-2'>
          <Select
            size='small'
            className='flex-1 min-w-0'
            aria-label={text('生成模型', 'Generation model')}
            value={model || undefined}
            placeholder={text('选择模型', 'Select model')}
            options={models.map(value => ({
              value,
              title: value,
              label: (
                <div className='flex items-center min-w-0'>
                  <span className='flex flex-none'>{renderModelIcon(value)}</span>
                  <span className='ml-2 truncate'>{value}</span>
                </div>
              ),
            }))}
            onChange={setModel}
            onDropdownVisibleChange={open => {
              if (open) onRefreshModels?.();
            }}
          />
          <Select
            size='small'
            aria-label={text('修改范围', 'Edit scope')}
            value={local ? 'nodes' : 'flow'}
            options={[
              { value: 'flow', label: text('整个流程', 'Whole flow') },
              { value: 'nodes', label: text('选中节点', 'Selected node'), disabled: !selectedId },
            ]}
            onChange={value => setLocal(value === 'nodes')}
          />
        </div>
        {local && selectedId && (
          <div className='text-[11px] text-gray-400'>
            {text('仅修改：', 'Only edit: ')}
            {selectedId}
          </div>
        )}
        <Input.TextArea
          aria-label={text('描述工作流需求', 'Describe workflow requirements')}
          value={input}
          onChange={event => setInput(event.target.value)}
          placeholder={text('描述目标，或继续调整流程…', 'Describe a goal or refine the workflow…')}
          autoSize={{ minRows: 3, maxRows: 6 }}
          onKeyDown={event => {
            if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
              event.preventDefault();
              void send(!!pending);
            }
          }}
        />
        <div className='flex items-center justify-between'>
          <span className='text-[10px] text-gray-400'>
            {text('串行 Agent · 生成不执行任务', 'Serial Agents · generation does not execute')}
          </span>
          <Button
            type='primary'
            loading={busy && !active}
            disabled={
              !!active || !model || (!input.trim() && !Object.values(answers).some(Boolean)) || (local && !selectedId)
            }
            onClick={() => void send(!!pending)}
          >
            {pending
              ? text('替换候选', 'Replace candidate')
              : session?.questions.length
                ? text('回答并继续', 'Answer & continue')
                : text('发送', 'Send')}
          </Button>
        </div>
      </div>
    </aside>
  );
}
