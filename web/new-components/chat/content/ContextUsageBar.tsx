/**
 * Context Usage Bar
 *
 * Floating progress bar that shows the current context window usage.
 * Colors change based on usage state:
 * - Green (OK): usage < 70%
 * - Yellow (WARNING): 70% <= usage < 90%
 * - Red (ERROR): usage >= 90%
 */

import React from 'react';

export interface ContextUsageBarProps {
  used: number;
  budget: number;
  ratio: number;
  state: 'OK' | 'WARNING' | 'ERROR';
  compactLayer?: string | null;
  variant?: 'bar' | 'compact';
  className?: string;
}

const STATE_COLORS: Record<string, { bar: string; bg: string; text: string; ring: string; label: string }> = {
  OK: {
    bar: 'bg-green-500',
    bg: 'bg-green-50 dark:bg-green-950/30',
    text: 'text-green-700 dark:text-green-300',
    ring: '#10b981',
    label: 'Context',
  },
  WARNING: {
    bar: 'bg-yellow-500',
    bg: 'bg-yellow-50 dark:bg-yellow-950/30',
    text: 'text-yellow-700 dark:text-yellow-300',
    ring: '#f59e0b',
    label: 'Context (compressing)',
  },
  ERROR: {
    bar: 'bg-red-500',
    bg: 'bg-red-50 dark:bg-red-950/30',
    text: 'text-red-700 dark:text-red-300',
    ring: '#ef4444',
    label: 'Context (critical)',
  },
};

function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) {
    return '0';
  }
  if (n >= 1000000) {
    return `${Math.round(n / 1000000)}m`;
  }
  if (n >= 1000) {
    return `${Math.round(n / 1000)}k`;
  }
  return String(n);
}

const ContextUsageBar: React.FC<ContextUsageBarProps> = ({
  used,
  budget,
  ratio,
  state,
  compactLayer,
  variant = 'bar',
  className = '',
}) => {
  const colors = STATE_COLORS[state] || STATE_COLORS.OK;
  const safeRatio = Number.isFinite(ratio) ? ratio : 0;
  const pct = Math.min(Math.max(safeRatio * 100, 0), 100);
  const radius = 8;
  const circumference = 2 * Math.PI * radius;
  const strokeOffset = circumference * (1 - pct / 100);

  if (variant === 'compact') {
    return (
      <div className={`group relative inline-flex items-center justify-center ${className}`}>
        <button
          type='button'
          aria-label={`Context window ${Math.round(pct)}% full`}
          className='relative flex h-8 w-8 items-center justify-center rounded-full border border-slate-200/80 bg-white/90 text-slate-500 shadow-[0_8px_24px_rgba(15,23,42,0.08)] backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-300 dark:border-white/10 dark:bg-[#202124]/90 dark:text-slate-300'
        >
          <svg width='22' height='22' viewBox='0 0 22 22' className='-rotate-90'>
            <circle
              cx='11'
              cy='11'
              r={radius}
              fill='none'
              stroke='currentColor'
              strokeWidth='3'
              className='text-slate-200 dark:text-slate-700'
            />
            <circle
              cx='11'
              cy='11'
              r={radius}
              fill='none'
              stroke={colors.ring}
              strokeWidth='3'
              strokeLinecap='round'
              strokeDasharray={circumference}
              strokeDashoffset={strokeOffset}
              className='transition-[stroke-dashoffset] duration-500'
            />
          </svg>
        </button>
        <div className='pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-[188px] -translate-x-1/2 translate-y-1 rounded-2xl border border-white/10 bg-[#2f2f2f] px-4 py-3 text-center text-white opacity-0 shadow-[0_18px_50px_rgba(15,23,42,0.22)] transition-all duration-150 group-hover:translate-y-0 group-hover:opacity-100 dark:bg-[#2b2b2b]'>
          <div className='text-[13px] font-medium leading-5 text-white/55'>Context window:</div>
          <div className='mt-1 text-[17px] leading-6 text-white/70'>{Math.round(pct)}% full</div>
          <div className='mt-2 text-[15px] font-medium leading-5 tabular-nums text-white'>
            {formatTokens(used)} / {formatTokens(budget)} tokens used
          </div>
          {compactLayer && <div className='mt-1 text-[11px] text-white/40'>{compactLayer}</div>}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${colors.bg} text-xs font-mono transition-colors duration-300`}
    >
      <span className={`${colors.text} whitespace-nowrap font-medium`}>{colors.label}</span>
      <div className='relative flex-1 h-1.5 bg-black/10 dark:bg-white/10 rounded-full overflow-hidden min-w-[80px] max-w-[160px]'>
        <div
          className={`absolute inset-y-0 left-0 ${colors.bar} rounded-full transition-all duration-500 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`${colors.text} whitespace-nowrap tabular-nums`}>
        {formatTokens(used)}/{formatTokens(budget)}
      </span>
      {compactLayer && <span className={`${colors.text} opacity-60 whitespace-nowrap`}>L{compactLayer}</span>}
    </div>
  );
};

export default ContextUsageBar;
