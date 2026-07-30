import { CheckCircleFilled, ClockCircleOutlined, CloseCircleFilled, LoadingOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';

import type { SubAgentStatus } from '@/types/subagent';

const STATUS_KEY = {
  running: 'subagent_status_running',
  done: 'subagent_status_done',
  failed: 'subagent_status_failed',
  timeout: 'subagent_status_timeout',
} as const satisfies Record<SubAgentStatus, string>;

const STATUS_STYLE: Record<SubAgentStatus, string> = {
  running: 'bg-blue-50 text-blue-600 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-400 dark:ring-blue-500/20',
  done: 'bg-emerald-50 text-emerald-600 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20',
  failed: 'bg-red-50 text-red-600 ring-red-100 dark:bg-red-500/10 dark:text-red-400 dark:ring-red-500/20',
  timeout: 'bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/20',
};

const STATUS_TEXT_STYLE: Record<SubAgentStatus, string> = {
  running: 'text-blue-500 dark:text-blue-400',
  done: 'text-emerald-500 dark:text-emerald-400',
  failed: 'text-red-500 dark:text-red-400',
  timeout: 'text-amber-500 dark:text-amber-400',
};

const StatusIcon: React.FC<{ status: SubAgentStatus }> = ({ status }) => {
  switch (status) {
    case 'done':
      return <CheckCircleFilled aria-hidden className='text-[13px]' />;
    case 'failed':
      return <CloseCircleFilled aria-hidden className='text-[13px]' />;
    case 'timeout':
      return <ClockCircleOutlined aria-hidden className='text-[13px]' />;
    default:
      return <LoadingOutlined aria-hidden spin className='text-[13px]' />;
  }
};

export interface SubAgentStatusBadgeProps {
  status: SubAgentStatus;
  showLabel?: boolean;
  className?: string;
}

const SubAgentStatusBadge: React.FC<SubAgentStatusBadgeProps> = ({ status, showLabel = false, className }) => {
  const { t } = useTranslation();
  const label = t(STATUS_KEY[status]);

  return (
    <span
      role='status'
      aria-label={label}
      title={showLabel ? undefined : label}
      className={classNames(
        'inline-flex flex-shrink-0 items-center justify-center',
        showLabel && 'gap-1.5 rounded-full px-2 py-1 text-[11px] font-medium ring-1 ring-inset',
        !showLabel && 'text-sm',
        showLabel ? STATUS_STYLE[status] : STATUS_TEXT_STYLE[status],
        className,
      )}
    >
      <StatusIcon status={status} />
      {showLabel && <span>{label}</span>}
    </span>
  );
};

export default memo(SubAgentStatusBadge);
