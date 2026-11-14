/**
 * Composer badge for the per-conversation high-risk tool permission mode.
 *
 * A small pill in the composer toolbar (left group, next to the add-context
 * button) opens a popover with three modes:
 *   default — follow the global approval policy;
 *   strict  — every confirm-tier call in this conversation pops a card
 *             (whitelist memory is ignored);
 *   open    — auto-approve confirm-tier calls in this conversation, while
 *             deny-tier commands keep their floor and stay blocked.
 *
 * The selection is stored server-side per conv_id (ApprovalCenter) and
 * audited into approval_policy_log with source="session-mode".
 */
import {
  CheckOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Popover, Tooltip } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

export type ApprovalSessionMode = 'default' | 'strict' | 'open';

const MODE_ORDER: ApprovalSessionMode[] = ['default', 'strict', 'open'];

const MODE_ICON: Record<ApprovalSessionMode, React.ReactNode> = {
  default: <SafetyCertificateOutlined />,
  strict: <LockOutlined />,
  open: <ThunderboltOutlined />,
};

const MODE_TONE: Record<ApprovalSessionMode, string> = {
  default: 'text-gray-500 dark:text-gray-300 border-gray-200/80 dark:border-white/10',
  strict: 'text-orange-500 border-orange-200 dark:border-orange-500/30',
  open: 'text-red-500 border-red-200 dark:border-red-500/30',
};

const MODE_LABEL_TONE: Record<ApprovalSessionMode, string> = {
  default: 'text-gray-800 dark:text-gray-100',
  strict: 'text-orange-500',
  open: 'text-red-500',
};

const apiBase = () => process.env.API_BASE_URL ?? '';

const ApprovalModeBadge: React.FC<{
  convId: string | null;
  ensureConvId: () => string;
}> = ({ convId, ensureConvId }) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<ApprovalSessionMode>('default');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    if (!convId) {
      setMode('default');
      return undefined;
    }
    fetch(
      `${apiBase()}/api/v1/chat/approval/session-mode?con_uid=${encodeURIComponent(convId)}`,
    )
      .then(r => (r.ok ? r.json() : null))
      .then(res => {
        const next = res?.data?.mode as ApprovalSessionMode | undefined;
        if (alive && next && MODE_ORDER.includes(next)) {
          setMode(next);
        }
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [convId]);

  const select = useCallback(
    (next: ApprovalSessionMode) => {
      const id = ensureConvId();
      setMode(next);
      setOpen(false);
      fetch(`${apiBase()}/api/v1/chat/approval/session-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ con_uid: id, mode: next }),
      }).catch(() => undefined);
    },
    [ensureConvId],
  );

  return (
    <Popover
      trigger='click'
      placement='topLeft'
      open={open}
      onOpenChange={setOpen}
      overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
      content={
        <div
          data-testid='approval-mode-popover'
          className='w-[300px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'
        >
          <div className='px-3 py-2 border-b border-gray-100 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400'>
            {t('approval_mode_tip')}
          </div>
          {MODE_ORDER.map(m => (
            <button
              key={m}
              type='button'
              data-testid={`approval-mode-${m}`}
              onClick={() => select(m)}
              className={`w-full flex items-start gap-2 px-3 py-2.5 text-left hover:bg-gray-50 dark:hover:bg-white/5 ${
                mode === m ? 'bg-gray-50/70 dark:bg-white/5' : ''
              }`}
            >
              <span className={`mt-0.5 ${MODE_LABEL_TONE[m]}`}>{MODE_ICON[m]}</span>
              <span className='flex-1'>
                <span className={`block text-sm ${MODE_LABEL_TONE[m]}`}>
                  {t(`approval_mode_${m}`)}
                </span>
                <span className='block text-xs text-gray-400 dark:text-gray-500 mt-0.5'>
                  {t(`approval_mode_${m}_desc`)}
                </span>
              </span>
              {mode === m && <CheckOutlined className='mt-1 text-sm' />}
            </button>
          ))}
        </div>
      }
    >
      <Tooltip title={t('approval_mode_tip')}>
        <button
          type='button'
          data-testid='approval-mode-badge'
          className={`flex items-center gap-1 h-7 px-2 rounded-full border text-xs bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] transition-all flex-shrink-0 ${MODE_TONE[mode]}`}
        >
          {MODE_ICON[mode]}
          <span>{t(`approval_mode_${mode}`)}</span>
        </button>
      </Tooltip>
    </Popover>
  );
};

export default ApprovalModeBadge;
