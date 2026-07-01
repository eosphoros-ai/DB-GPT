// Parallel sub-agent activity card.
//
// Renders the lead agent's parallel delegation as a grouped card in the left
// timeline: a header ("并行执行 N 个子任务" + progress) and one row per
// sub-agent (status badge + name + live current-action line + drill-down step
// list). Granularity = "关键进展行 + 可下钻" (design spec §4.7), aligned with
// Claude Code / Devin / Manus. Reuses ManusLeftPanel's visual language
// (status dot, Tailwind dark/light classes) rather than inline styles.

import {
  CaretDownOutlined,
  CaretRightOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  LoadingOutlined,
  RightOutlined,
} from '@ant-design/icons';
import classNames from 'classnames';
import React, { memo, useState } from 'react';

import type { SubAgentState, SubAgentStatus } from '@/types/subagent';

export interface SubAgentSectionProps {
  subAgents: Record<string, SubAgentState>;
  artifactCount?: number;
  /** Click a sub-agent row to view its full process in the right panel. */
  onSubAgentClick?: (agentId: string) => void;
  /** The sub-agent currently shown in the right panel (highlighted). */
  activeSubAgentId?: string | null;
}

// Status badge: small icon reused from the antd set ManusLeftPanel already uses.
const StatusBadge: React.FC<{ status: SubAgentStatus }> = ({ status }) => {
  switch (status) {
    case 'done':
      return <CheckCircleFilled className='text-sm text-emerald-500' />;
    case 'failed':
      return <CloseCircleFilled className='text-sm text-red-500' />;
    case 'timeout':
      return <ClockCircleOutlined className='text-sm text-amber-500' />;
    default:
      return <LoadingOutlined spin className='text-sm text-blue-500' />;
  }
};

const STATUS_TEXT: Record<SubAgentStatus, string> = {
  running: '执行中',
  done: '完成',
  timeout: '超时',
  failed: '失败',
};

const SubAgentRow: React.FC<{
  agent: SubAgentState;
  active?: boolean;
  onClick?: (agentId: string) => void;
}> = ({ agent, active, onClick }) => {
  const hasSteps = agent.steps.length > 0;
  const isRunning = agent.status === 'running';

  // The line under the name: while running show the live action; when finished
  // show a short status summary.
  const subline = isRunning
    ? agent.currentAction || '正在思考'
    : `${STATUS_TEXT[agent.status]}${agent.steps.length ? ` · ${agent.steps.length} 步` : ''}`;

  // Whole row is clickable -> open this sub-agent's full process in the right
  // panel (Devin-style left-select-right-view).
  return (
    <div
      className={classNames('rounded-lg border px-3 py-2 flex items-center gap-2 cursor-pointer transition-colors', {
        'border-blue-300 dark:border-blue-600 bg-blue-50/60 dark:bg-blue-900/20': active,
        'border-gray-100 dark:border-gray-700/60 bg-white/60 dark:bg-gray-800/40 hover:bg-gray-50 dark:hover:bg-gray-800/70':
          !active,
      })}
      onClick={() => onClick?.(agent.agentId)}
      title='点击查看该子任务的执行过程'
    >
      <StatusBadge status={agent.status} />
      <div className='flex-1 min-w-0'>
        <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate' title={agent.goal || agent.name}>
          {agent.name}
        </div>
        <div
          className={classNames('text-xs truncate', {
            'text-blue-600 dark:text-blue-400': isRunning,
            'text-gray-400 dark:text-gray-500': !isRunning,
          })}
        >
          {subline}
        </div>
      </div>
      {hasSteps && <RightOutlined className='text-xs text-gray-400' />}
    </div>
  );
};

const SubAgentSection: React.FC<SubAgentSectionProps> = ({
  subAgents,
  artifactCount,
  onSubAgentClick,
  activeSubAgentId,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const rows = Object.values(subAgents).sort((a, b) => a.lane - b.lane);
  if (rows.length === 0) return null;

  const doneCount = rows.filter(r => r.status !== 'running').length;
  const allDone = doneCount === rows.length;
  const anyFailed = rows.some(r => r.status === 'failed' || r.status === 'timeout');

  return (
    <div className='mt-3 mb-4 px-1'>
      {/* Header — same shape as SectionBlock: status dot + title + progress. */}
      <div className='flex items-center gap-2 mb-2 cursor-pointer group' onClick={() => setCollapsed(c => !c)}>
        <div
          className={classNames('w-5 h-5 rounded-full flex items-center justify-center transition-all', {
            'bg-emerald-100 dark:bg-emerald-900/50': allDone && !anyFailed,
            'bg-red-100 dark:bg-red-900/50': anyFailed,
            'bg-blue-100 dark:bg-blue-900/50': !allDone && !anyFailed,
          })}
        >
          {allDone && !anyFailed ? (
            <CheckCircleFilled className='text-xs text-emerald-500' />
          ) : anyFailed ? (
            <CloseCircleFilled className='text-xs text-red-500' />
          ) : (
            <LoadingOutlined spin className='text-xs text-blue-500' />
          )}
        </div>
        <span className='text-sm font-medium text-gray-800 dark:text-gray-200 flex-1'>
          并行执行 {rows.length} 个子任务
        </span>
        <span className='text-[10px] text-gray-400'>
          {doneCount}/{rows.length}
          {artifactCount ? ` · ${artifactCount} 产物` : ''}
        </span>
        <span className='text-xs text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors'>
          {collapsed ? <CaretRightOutlined /> : <CaretDownOutlined />}
        </span>
      </div>

      {!collapsed && (
        <div className='ml-7 space-y-2'>
          {rows.map(agent => (
            <SubAgentRow
              key={agent.agentId}
              agent={agent}
              active={agent.agentId === activeSubAgentId}
              onClick={onSubAgentClick}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default memo(SubAgentSection);
