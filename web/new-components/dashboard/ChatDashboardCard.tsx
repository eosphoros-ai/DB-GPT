import { Button, Progress, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import type { DashboardGenerationState } from './DashboardGenerationCard';

export default function ChatDashboardCard({
  state,
  busy,
  onConfirm,
  onRevise,
  onOpen,
}: {
  state: DashboardGenerationState;
  busy: boolean;
  onConfirm: () => void;
  onRevise: () => void;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const pending = state.status === 'awaiting_confirmation';
  return (
    <div
      data-testid='chat-dashboard-card'
      className='my-3 rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/20'
    >
      <div className='font-semibold'>{state.title}</div>
      <p className='mt-1 text-sm text-gray-500'>{t(`dashboard_chat_${state.status}`)}</p>
      {state.dataSourceId && (
        <div className='text-xs text-gray-500'>
          {t('dashboard_chat_source')}: {state.dataSourceId}
        </div>
      )}
      {pending && state.plan && (
        <div className='mt-3 space-y-2 text-sm'>
          <div>{[state.plan.audience, state.plan.decision_goal].filter(Boolean).join(' · ')}</div>
          <div className='flex flex-wrap gap-1'>
            {state.plan.metrics?.map(metric => <Tag key={metric}>{metric}</Tag>)}
          </div>
          <ul className='list-disc pl-5'>
            {state.plan.widgets?.map(widget => (
              <li key={widget.id}>
                {widget.title} · {widget.type}
              </li>
            ))}
          </ul>
          {state.plan.filter_strategy && <p>{state.plan.filter_strategy}</p>}
        </div>
      )}
      {state.status === 'generating' && (
        <Progress percent={state.totalWidgets ? Math.round((100 * state.validatedWidgets) / state.totalWidgets) : 0} />
      )}
      {state.status === 'failed' && <div role='alert'>{state.errorMessage || state.retryHint}</div>}
      <div className='mt-3 flex gap-2'>
        {pending && (
          <Button type='primary' disabled={busy || !state.confirmationPrompt} onClick={onConfirm}>
            {t('dashboard_chat_confirm')}
          </Button>
        )}
        {state.revisionPrompt && (
          <Button disabled={busy} onClick={onRevise}>
            {t('dashboard_chat_revise')}
          </Button>
        )}
        {(state.status === 'created' || state.status === 'failed') && state.editorPath && (
          <Button type='primary' onClick={onOpen}>
            {t('dashboard_chat_open')}
          </Button>
        )}
      </div>
    </div>
  );
}
