import { useConnectorTools } from '@/hooks/use-connector-api';
import { CopyOutlined, SearchOutlined, ThunderboltFilled } from '@ant-design/icons';
import { Alert, Modal, Tooltip, message } from 'antd';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  ConnectorInstance,
  ConnectorToolArgSummary,
  ConnectorToolArgTruncated,
  ConnectorToolSummary,
} from './types';

interface ConnectorToolsModalProps {
  open: boolean;
  instance: ConnectorInstance | null;
  onClose: () => void;
}

const isTruncated = (v: ConnectorToolArgSummary | ConnectorToolArgTruncated): v is ConnectorToolArgTruncated =>
  (v as ConnectorToolArgTruncated)?._truncated === true;

/* Colored chips per JSON-Schema type — matches the design preview. */
const TYPE_CHIP_CLASS: Record<string, string> = {
  string: 'bg-blue-50 text-blue-600',
  integer: 'bg-emerald-50 text-emerald-600',
  number: 'bg-emerald-50 text-emerald-600',
  boolean: 'bg-purple-50 text-purple-600',
  array: 'bg-amber-50 text-amber-700',
  object: 'bg-gray-100 text-gray-600',
  date: 'bg-rose-50 text-rose-600',
};

const TypeChip: React.FC<{ type?: string }> = ({ type }) => (
  <span
    className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium font-mono leading-tight ${
      TYPE_CHIP_CLASS[type ?? ''] ?? 'bg-gray-100 text-gray-600'
    }`}
  >
    {type ?? 'any'}
  </span>
);

const StatusDot: React.FC<{ state?: 'active' | 'inactive' | 'not_mcp' }> = ({ state }) => {
  const cls =
    state === 'active'
      ? 'bg-emerald-500'
      : state === 'inactive'
        ? 'bg-amber-500'
        : 'bg-gray-400';
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${cls}`} />;
};

const ConnectorToolsModal: React.FC<ConnectorToolsModalProps> = ({ open, instance, onClose }) => {
  const { t } = useTranslation();
  const { data, loading, error, refetch } = useConnectorTools(instance?.id);

  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Re-fetch when modal opens or instance changes.
  useEffect(() => {
    if (open && instance?.id) {
      refetch();
    }
  }, [open, instance?.id, refetch]);

  // Reset transient UI state on close.
  useEffect(() => {
    if (!open) {
      setQuery('');
      setSelectedIdx(0);
    }
  }, [open]);

  const tools: ConnectorToolSummary[] = data?.state === 'active' ? data.tools : [];

  const filtered = useMemo(() => {
    if (!query.trim()) return tools;
    const q = query.trim().toLowerCase();
    return tools.filter(
      t =>
        (t.original_name ?? t.name).toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q) ||
        (t.description ?? '').toLowerCase().includes(q),
    );
  }, [tools, query]);

  // Clamp selected index when filter changes.
  useEffect(() => {
    if (selectedIdx >= filtered.length) setSelectedIdx(0);
  }, [filtered.length, selectedIdx]);

  const selected = filtered[selectedIdx];

  /* Keyboard shortcuts inside the modal — only when it's open. */
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (e.key === 'ArrowDown' && filtered.length > 0) {
        e.preventDefault();
        setSelectedIdx(i => Math.min(filtered.length - 1, i + 1));
      } else if (e.key === 'ArrowUp' && filtered.length > 0) {
        e.preventDefault();
        setSelectedIdx(i => Math.max(0, i - 1));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, filtered.length]);

  const copyName = useCallback(
    (name: string) => {
      navigator.clipboard?.writeText(name).then(() => {
        message.success(`${t('connector.tools.copiedToast')}  ${name}`);
      });
    },
    [t],
  );

  const titleLabel = instance?.display_name ?? instance?.connector_type ?? '';

  /* ---------------------------------------------------------------- */
  /* Render                                                            */
  /* ---------------------------------------------------------------- */

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={960}
      destroyOnClose
      closable={false}
      styles={{ body: { padding: 0 } }}
      className='connector-tools-modal'
      maskClosable
    >
      <div
        className='flex flex-col overflow-hidden rounded-lg bg-white'
        style={{ height: 'min(720px, 80vh)' }}
      >
        {/* ---------------- Header ---------------- */}
        <header className='flex items-center gap-3 px-6 py-3.5 border-b border-gray-100 bg-gradient-to-br from-white/95 to-violet-50/60'>
          <div className='flex-shrink-0 w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center text-white text-base shadow-sm ring-2 ring-white/40'>
            <ThunderboltFilled />
          </div>
          <div className='flex-1 min-w-0'>
            <div className='flex items-center gap-2'>
              <h2 className='font-semibold text-[15px] text-gray-900 truncate m-0'>{titleLabel}</h2>
              {instance?.is_custom ? (
                <span className='inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-50 text-violet-600 border border-violet-100'>
                  {t('connector.badge.custom')}
                </span>
              ) : (
                <span className='inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-50 text-violet-600 border border-violet-100'>
                  {t('connector.badge.official')}
                </span>
              )}
            </div>
            <div className='flex items-center gap-1.5 text-[11px] text-gray-500 mt-0.5'>
              <span>{instance?.connector_type}</span>
              <span className='text-gray-300'>·</span>
              <span className='inline-flex items-center gap-1'>
                <StatusDot state={data?.state} />
                {data?.state === 'active'
                  ? t('connector.tools.stateActive')
                  : data?.state === 'inactive'
                    ? t('connector.tools.stateInactive')
                    : data?.state === 'not_mcp'
                      ? t('connector.tools.stateNotMcp')
                      : '—'}
              </span>
            </div>
          </div>
          {data?.state === 'active' && (
            <span className='inline-flex items-center px-2 py-1 rounded-md text-[11px] font-medium bg-violet-50 text-violet-600'>
              {t('connector.tools.toolsCountChip', { count: tools.length })}
            </span>
          )}
          <button
            onClick={onClose}
            className='w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition'
            title='Esc'
            aria-label='close'
          >
            <svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='2'>
              <path d='M18 6L6 18M6 6l12 12' />
            </svg>
          </button>
        </header>

        {/* ---------------- Body ---------------- */}
        <div className='flex-1 flex min-h-0'>
          {loading ? (
            <SkeletonBody />
          ) : error ? (
            <ErrorState error={error} onRetry={refetch} />
          ) : data?.state === 'inactive' ? (
            <EmptyState message={t('connector.tools.inactiveHint')} />
          ) : data?.state === 'not_mcp' ? (
            <EmptyState message={t('connector.tools.notMcpHint')} />
          ) : tools.length === 0 ? (
            <EmptyState message={t('connector.tools.emptyTitle')} />
          ) : (
            <>
              {/* ----- Sidebar ----- */}
              <aside
                ref={listRef}
                className='w-[320px] flex-shrink-0 border-r border-gray-100 flex flex-col bg-gray-50/40'
              >
                <div className='p-3 pb-2'>
                  <div className='relative'>
                    <SearchOutlined className='absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-[12px]' />
                    <input
                      ref={searchRef}
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      className='w-full pl-9 pr-8 py-2 text-[13px] bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-100 transition placeholder:text-gray-400'
                      placeholder={t('connector.tools.searchPlaceholder')}
                    />
                    {query && (
                      <button
                        onClick={() => setQuery('')}
                        className='absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 flex items-center justify-center text-[10px]'
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>

                <div className='flex-1 overflow-y-auto px-2 py-1 connector-tools-scroll'>
                  {filtered.length === 0 ? (
                    <div className='text-center text-[12px] text-gray-400 py-6 px-3 leading-relaxed'>
                      {t('connector.tools.noMatch')}
                    </div>
                  ) : (
                    filtered.map((tool, i) => {
                      const active = i === selectedIdx;
                      const displayName = tool.original_name ?? tool.name;
                      return (
                        <button
                          key={tool.name}
                          onClick={() => setSelectedIdx(i)}
                          className={`w-full text-left px-3 py-2.5 my-0.5 rounded-lg flex items-center gap-2.5 transition group ${
                            active ? 'bg-violet-50/80 ring-1 ring-violet-100' : 'hover:bg-gray-100/70'
                          }`}
                          style={active ? { boxShadow: 'inset 3px 0 0 0 #7c3aed' } : undefined}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                              active ? 'bg-violet-600' : 'bg-gray-300 group-hover:bg-gray-400'
                            }`}
                          />
                          <div className='min-w-0 flex-1'>
                            <div
                              className={`font-mono text-[13px] font-medium truncate ${
                                active ? 'text-violet-700' : 'text-gray-800'
                              }`}
                            >
                              {displayName}
                            </div>
                            <div className='text-[11px] text-gray-500 truncate mt-0.5 leading-tight'>
                              {tool.description || '—'}
                            </div>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>

                <div className='px-4 py-2.5 border-t border-gray-100 text-[11px] text-gray-400 bg-white/60'>
                  {query.trim()
                    ? t('connector.tools.matchCount', { match: filtered.length, total: tools.length })
                    : t('connector.tools.totalCount', { count: tools.length })}
                </div>
              </aside>

              {/* ----- Detail ----- */}
              <main className='flex-1 overflow-y-auto connector-tools-scroll'>
                {selected && <ToolDetail tool={selected} onCopy={copyName} />}
              </main>
            </>
          )}
        </div>
      </div>

      {/* Scoped scrollbar styles (Tailwind doesn't ship custom scrollbar). */}
      <style>{`
        .connector-tools-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .connector-tools-scroll::-webkit-scrollbar-thumb { background: rgba(124,58,237,0.20); border-radius: 3px; }
        .connector-tools-scroll::-webkit-scrollbar-thumb:hover { background: rgba(124,58,237,0.35); }
        .connector-tools-scroll::-webkit-scrollbar-track { background: transparent; }
        .connector-tools-modal .ant-modal-content { padding: 0; overflow: hidden; border-radius: 16px; }
      `}</style>
    </Modal>
  );
};

/* -------------------------------------------------------------------- */
/* Sub-components                                                        */
/* -------------------------------------------------------------------- */

const ToolDetail: React.FC<{ tool: ConnectorToolSummary; onCopy: (name: string) => void }> = ({
  tool,
  onCopy,
}) => {
  const { t } = useTranslation();
  const argEntries = Object.entries(tool.args ?? {});

  // Defensive: backend may return either {_truncated: true} at args root
  // or one entry of args with _truncated: true.
  const wholeTruncated = (tool.args as unknown as ConnectorToolArgTruncated)?._truncated === true;
  const truncatedEntry = argEntries
    .map(([, v]) => v)
    .find(v => isTruncated(v as ConnectorToolArgSummary | ConnectorToolArgTruncated)) as
    | ConnectorToolArgTruncated
    | undefined;

  const summaryRows = argEntries.filter(
    ([, v]) => !isTruncated(v as ConnectorToolArgSummary | ConnectorToolArgTruncated),
  ) as Array<[string, ConnectorToolArgSummary]>;

  const hasParams = summaryRows.length > 0;
  const displayName = tool.original_name ?? tool.name;

  return (
    <div className='px-7 py-6'>
      <div className='flex items-start justify-between gap-4 mb-3'>
        <h3 className='font-mono text-[18px] font-bold text-gray-900 truncate m-0'>{displayName}</h3>
        <Tooltip title={t('connector.tools.copyTooltip')}>
          <button
            onClick={() => onCopy(displayName)}
            className='inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] text-gray-500 hover:text-violet-600 hover:bg-violet-50 rounded-md transition flex-shrink-0'
          >
            <CopyOutlined />
            <span>{t('connector.tools.copyTooltip')}</span>
          </button>
        </Tooltip>
      </div>

      <p className='text-[14px] text-gray-700 leading-relaxed whitespace-pre-wrap mb-6'>
        {tool.description || '—'}
      </p>

      <div className='h-px bg-gray-100 mb-5' />

      <div className='flex items-center gap-2 mb-3'>
        <h4 className='text-[13px] font-semibold text-gray-800 m-0'>{t('connector.tools.inputSchema')}</h4>
        {hasParams && (
          <>
            <span className='text-[12px] text-gray-400'>·</span>
            <span className='text-[12px] text-gray-500'>{summaryRows.length}</span>
          </>
        )}
      </div>

      {wholeTruncated || truncatedEntry ? (
        <Alert
          type='info'
          showIcon
          message={t('connector.tools.argsTruncated', {
            byteCount:
              (tool.args as unknown as ConnectorToolArgTruncated)?.byte_count ??
              truncatedEntry?.byte_count ??
              0,
          })}
        />
      ) : !hasParams ? (
        <div className='text-[13px] text-gray-400 italic px-1 py-3'>{t('connector.tools.noParams')}</div>
      ) : (
        <div className='overflow-hidden rounded-lg border border-gray-200'>
          <table className='w-full text-[13px]'>
            <thead>
              <tr className='bg-gray-50 text-gray-500 text-[11px] font-medium uppercase tracking-wider'>
                <th className='px-3 py-2 text-left'>{t('connector.tools.argName')}</th>
                <th className='px-3 py-2 text-left'>{t('connector.tools.argType')}</th>
                <th className='px-3 py-2 text-left w-14'>{t('connector.tools.argRequired')}</th>
                <th className='px-3 py-2 text-left'>{t('connector.tools.argDescription')}</th>
              </tr>
            </thead>
            <tbody className='divide-y divide-gray-100'>
              {summaryRows.map(([name, info]) => (
                <tr key={name} className='hover:bg-gray-50/70 transition'>
                  <td className='px-3 py-2 font-mono text-gray-900 align-top'>
                    {name}
                    {info.required && <span className='text-rose-500 ml-0.5'>*</span>}
                  </td>
                  <td className='px-3 py-2 align-top'>
                    <TypeChip type={info.type} />
                  </td>
                  <td className='px-3 py-2 align-top'>
                    {info.required ? (
                      <span className='text-emerald-600 font-semibold'>✓</span>
                    ) : (
                      <span className='text-gray-300'>—</span>
                    )}
                  </td>
                  <td className='px-3 py-2 text-gray-700 align-top'>{info.description || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className='h-12' /> {/* Bottom breathing room */}
    </div>
  );
};

const SkeletonBody: React.FC = () => (
  <div className='flex w-full'>
    <aside className='w-[320px] flex-shrink-0 border-r border-gray-100 p-3 space-y-2'>
      {[...Array(8)].map((_, i) => (
        <div key={i} className='h-12 rounded-lg bg-gray-100 animate-pulse' />
      ))}
    </aside>
    <main className='flex-1 px-7 py-6 space-y-4'>
      <div className='h-6 w-1/3 rounded bg-gray-100 animate-pulse' />
      <div className='h-4 w-full rounded bg-gray-100 animate-pulse' />
      <div className='h-4 w-5/6 rounded bg-gray-100 animate-pulse' />
      <div className='h-px bg-gray-100' />
      <div className='h-32 rounded-lg bg-gray-100 animate-pulse' />
    </main>
  </div>
);

const EmptyState: React.FC<{ message: string }> = ({ message }) => (
  <div className='flex-1 flex flex-col items-center justify-center text-center px-8'>
    <div className='w-14 h-14 rounded-2xl bg-gray-100 flex items-center justify-center text-gray-300 mb-4'>
      <svg width='28' height='28' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.6'>
        <rect x='3' y='3' width='7' height='7' rx='1' />
        <rect x='14' y='3' width='7' height='7' rx='1' />
        <rect x='3' y='14' width='7' height='7' rx='1' />
        <rect x='14' y='14' width='7' height='7' rx='1' />
      </svg>
    </div>
    <p className='text-[14px] text-gray-500 max-w-xs leading-relaxed m-0'>{message}</p>
  </div>
);

const ErrorState: React.FC<{ error: string; onRetry: () => void }> = ({ error, onRetry }) => {
  const { t } = useTranslation();
  return (
    <div className='flex-1 flex items-start justify-center pt-12 px-8'>
      <Alert
        type='warning'
        showIcon
        className='max-w-md w-full'
        message={t('connector.tools.errorTitle')}
        description={error}
        action={
          <button
            onClick={onRetry}
            className='text-violet-600 hover:text-violet-700 text-[12px] font-medium px-2 py-1'
          >
            {t('connector.tools.errorRetry')}
          </button>
        }
      />
    </div>
  );
};

export default ConnectorToolsModal;
