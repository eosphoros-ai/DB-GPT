import {
  CheckOutlined,
  CopyOutlined,
  DownOutlined,
  FullscreenOutlined,
  LoadingOutlined,
  RightOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { Modal } from 'antd';
import cls from 'classnames';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export function isTerminalTool(name?: string): boolean {
  return /(?:^|[._])(bash|shell|shell_interpreter|exec_command|execute_command|run_command|terminal)$/.test(
    (name || '').toLowerCase(),
  );
}

/** Both pi and DBGPT send shell commands, under different argument names. */
export function terminalCommand(input?: string): string {
  if (!input) return '';
  try {
    const args = JSON.parse(input);
    if (typeof args === 'string') return args;
    if (args && typeof args === 'object') {
      for (const key of ['command', 'code', 'script', 'cmd']) {
        if (typeof args[key] === 'string') return args[key];
      }
    }
  } catch {
    // Historical command inputs can already be plain shell text.
  }
  return input;
}

export function TerminalIcon() {
  return (
    <svg width='16' height='16' viewBox='0 0 16 16' fill='none' aria-label='terminal' role='img'>
      <rect x='1.5' y='2' width='13' height='12' rx='2.5' stroke='currentColor' strokeWidth='1.5' />
      <path
        d='m4.5 5 2 2-2 2M8.5 10h3'
        stroke='currentColor'
        strokeWidth='1.5'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
    </svg>
  );
}

interface TerminalToolRowProps {
  id: string;
  tool?: string;
  input?: string;
  output?: string;
  status?: 'running' | 'success' | 'failed';
  running?: boolean;
  duration?: string;
  sub?: boolean;
}

export default function TerminalToolRow({
  id,
  tool,
  input,
  output,
  status,
  running,
  duration,
  sub,
}: TerminalToolRowProps) {
  const { t } = useTranslation();
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [fullScreen, setFullScreen] = useState(false);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle');
  const open = manualOpen ?? Boolean(running);
  const command = terminalCommand(input);
  const summary = command.split('\n').find(line => line.trim()) || '';
  const longContent =
    `${command}\n${output || ''}`.split('\n').length > 8 || command.length + (output?.length || 0) > 600;
  const label = t(
    running ? 'timeline_command_running' : status === 'failed' ? 'timeline_command_failed' : 'timeline_command_done',
  );
  const copyLabel = t(copyStatus === 'copied' ? 'timeline_command_copied' : 'timeline_command_copy');
  const bodyId = `terminal-${id}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('error');
    }
  };

  const transcript = (
    <>
      {command && (
        <div className='flex items-start gap-3'>
          <span aria-hidden className='select-none font-mono text-[#c58b22]'>
            $
          </span>
          <pre className='m-0 min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-[#3d3d38] dark:text-[#d4d2cc]'>
            {command}
          </pre>
        </div>
      )}
      {output && (
        <pre className='m-0 mt-5 whitespace-pre font-mono text-[12px] leading-6 text-[#8b8b84] dark:text-[#a8a59e]'>
          {output}
        </pre>
      )}
    </>
  );

  return (
    <div className={cls('min-w-0', sub && 'ml-5')} data-running={running || undefined}>
      <div className='flex min-w-0 items-center gap-1 py-0.5 text-[#8b8b84] dark:text-[#a8a59e]'>
        <button
          type='button'
          className='flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1 text-left hover:bg-[#f4f4f0] dark:hover:bg-white/[.05]'
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={`${label} · ${tool || 'bash'} · ${summary}`}
          onClick={() => setManualOpen(!open)}
        >
          <span className='flex-none'>
            <TerminalIcon />
          </span>
          <span className={cls('flex-none text-[12.5px]', status === 'failed' && 'text-red-500')}>{label}</span>
          {running && <LoadingOutlined className='flex-none text-xs' />}
          <span className='min-w-0 flex-1 truncate font-mono text-xs' title={summary}>
            {summary}
          </span>
          {duration && <span className='flex-none text-xs tabular-nums'>{duration}</span>}
          {open ? (
            <DownOutlined className='flex-none text-[10px]' />
          ) : (
            <RightOutlined className='flex-none text-[10px]' />
          )}
        </button>
        {command && (
          <button
            type='button'
            title={copyLabel}
            aria-label={copyLabel}
            onClick={copy}
            className='flex-none rounded-md p-1.5 hover:bg-[#efefeb] dark:hover:bg-white/[.06]'
          >
            {copyStatus === 'copied' ? <CheckOutlined /> : <CopyOutlined />}
          </button>
        )}
        <button
          type='button'
          title={t('timeline_command_expand')}
          aria-label={t('timeline_command_expand')}
          onClick={() => setFullScreen(true)}
          className='flex-none rounded-md p-1.5 hover:bg-[#efefeb] dark:hover:bg-white/[.06]'
        >
          <FullscreenOutlined />
        </button>
      </div>
      {copyStatus === 'error' && (
        <span role='status' className='ml-6 text-xs text-red-500'>
          {t('timeline_command_copy_failed')}
        </span>
      )}
      {open && (
        <div id={bodyId} className='mb-2 ml-2 border-l border-[#e6e6e2] pl-4 pt-2 dark:border-[#33353b]'>
          <div className='overflow-hidden rounded-xl border border-[#e6e6e2] bg-[#fafafa] dark:border-[#33353b] dark:bg-[#191a20]'>
            <div className={cls('select-text overflow-auto p-4', expanded ? 'max-h-[32rem]' : 'max-h-64')}>
              {transcript}
            </div>
            {longContent && (
              <button
                type='button'
                aria-expanded={expanded}
                onClick={() => setExpanded(!expanded)}
                aria-label={t(expanded ? 'timeline_command_less' : 'timeline_command_more')}
                className='flex w-full justify-center border-t border-[#e6e6e2] py-2 text-[10px] text-[#8b8b84] hover:bg-[#f4f4f0] dark:border-[#33353b] dark:hover:bg-white/[.04]'
              >
                {expanded ? <UpOutlined /> : <DownOutlined />}
              </button>
            )}
          </div>
        </div>
      )}
      <Modal
        open={fullScreen}
        onCancel={() => setFullScreen(false)}
        footer={null}
        width={960}
        title={label}
        destroyOnClose
      >
        <div className='max-h-[70vh] select-text overflow-auto rounded-lg bg-[#fafafa] p-5 dark:bg-[#191a20]'>
          {transcript}
        </div>
      </Modal>
    </div>
  );
}
