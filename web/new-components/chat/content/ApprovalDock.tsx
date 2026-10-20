/**
 * ApprovalDock — human-in-the-loop confirmation UI for high-risk tool calls.
 *
 * Rendered just above the composer in the chat column (floating dock per
 * docs/design/tool-approval-design.md §8). One card per pending approval;
 * approvals stack above the question dock. Resolving posts to
 * POST /api/v1/chat/approval/{id}/resolve; the card disappears when the
 * SSE approval.resolved event arrives.
 */
import { WarningOutlined } from '@ant-design/icons';
import React, { useState } from 'react';

import type { PendingApproval } from '@/utils/react-sse-parser';

export interface ApprovalDockProps {
  approvals: PendingApproval[];
  onResolve: (
    approvalId: string,
    decision: 'approve' | 'reject',
    scope?: string,
    reason?: string,
  ) => void;
}

const SCOPE_OPTIONS = [
  { value: 'once', label: '仅本次 once' },
  { value: 'session', label: '本会话 session' },
  { value: 'always', label: '始终 always' },
];

/** Render intent bullets; **phrase** segments become red-bold risk highlights. */
const renderBullet = (text: string) =>
  text.split(/\*\*(.+?)\*\*/g).map((seg, i) =>
    i % 2 === 1 ? (
      <b key={i} className='font-semibold text-[#dc2626] dark:text-red-400'>
        {seg}
      </b>
    ) : (
      <React.Fragment key={i}>{seg}</React.Fragment>
    ),
  );

const ApprovalCard: React.FC<{
  approval: PendingApproval;
  onResolve: ApprovalDockProps['onResolve'];
}> = ({ approval, onResolve }) => {
  const [scope, setScope] = useState('once');
  const [reason, setReason] = useState('');
  const [confirmingReject, setConfirmingReject] = useState(false);

  return (
    <div className='mb-3 w-full overflow-hidden rounded-xl border border-red-200 bg-white shadow-[0_12px_40px_rgba(20,20,15,0.14)] dark:border-red-900 dark:bg-[#1e1f24]'>
      <div className='flex items-center gap-2 bg-gradient-to-r from-[#fdeaea] to-[#f8d9d9] px-4 py-2 text-[13px] font-semibold text-[#dc2626] dark:from-[#3a1d1d] dark:to-[#332020] dark:text-red-400'>
        <WarningOutlined />
        <span>高危操作 · {approval.tool}</span>
        <span className='ml-auto rounded-full border border-[#f0caca] bg-white/60 px-2 font-mono text-[11px] font-normal text-[#b45353] dark:border-red-900 dark:bg-black/20 dark:text-red-300'>
          {approval.rule_id}（confirm 档）
        </span>
      </div>
      <div className='p-4'>
        <pre className='whitespace-pre-wrap break-all rounded-lg border border-[#efefeb] bg-[#f6f6f2] p-3 font-mono text-[12px] leading-[1.7] dark:border-[#33353b] dark:bg-[#17181c]'>
          {approval.args_preview}
        </pre>
        {approval.intent && approval.intent.length > 0 ? (
          <ul className='mt-3 space-y-1.5'>
            {approval.intent.map((b, i) => (
              <li
                key={i}
                className='flex gap-2 text-[13px] leading-6 text-gray-600 dark:text-gray-300'
              >
                <span className='mt-[9px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-gray-300 dark:bg-gray-600' />
                <span>{renderBullet(b)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className='mt-3 flex items-center gap-2 text-[13px] text-gray-400'>
            <span className='h-3 w-3 animate-spin rounded-full border-2 border-gray-200 border-t-red-500' />
            正在分析命令意图…
          </div>
        )}
        <div className='mt-2 flex flex-wrap gap-3 text-[12px] text-gray-400'>
          <span>命中规则 {approval.rule_id}</span>
          <span>confirm 档</span>
          <span>ttl {approval.ttl_seconds ?? 300}s 超时自动拒绝</span>
          <span className='font-mono'>approval_id {approval.approval_id}</span>
        </div>
        {confirmingReject && (
          <input
            autoFocus
            value={reason}
            onChange={e => setReason(e.target.value)}
            placeholder='拒绝原因（可选，会回灌给模型改道）'
            className='mt-3 w-full rounded-lg border border-gray-200 px-3 py-1.5 text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'
          />
        )}
        <div className='mt-3 flex items-center gap-2 border-t border-dashed border-gray-200 pt-3 dark:border-[#33353b]'>
          <button
            className='h-8 rounded-lg border border-red-200 px-4 text-[13px] text-[#dc2626] hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950'
            onClick={() => {
              if (!confirmingReject) {
                setConfirmingReject(true);
                return;
              }
              onResolve(approval.approval_id, 'reject', scope, reason || undefined);
            }}
          >
            {confirmingReject ? '确认拒绝' : '拒绝'}
          </button>
          <button
            className='h-8 rounded-lg bg-[#1c1c1a] px-4 text-[13px] text-white hover:bg-black disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black'
            disabled={!approval.intent || approval.intent.length === 0}
            title={!approval.intent || approval.intent.length === 0 ? '意图分析到达前不可允许' : undefined}
            onClick={() => onResolve(approval.approval_id, 'approve', scope)}
          >
            允许
          </button>
          <select
            value={scope}
            onChange={e => setScope(e.target.value)}
            className='ml-auto h-8 rounded-lg border border-gray-200 bg-white px-2 text-[12.5px] text-gray-500 dark:border-[#33353b] dark:bg-[#17181c]'
          >
            {SCOPE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};

const ApprovalDock: React.FC<ApprovalDockProps> = ({ approvals, onResolve }) => (
  <>
    {approvals.map(a => (
      <ApprovalCard key={a.approval_id} approval={a} onResolve={onResolve} />
    ))}
  </>
);

export default ApprovalDock;
