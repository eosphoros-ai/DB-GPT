import {
  ApiOutlined,
  BookOutlined,
  CheckCircleFilled,
  DeleteOutlined,
  DingtalkOutlined,
  EditOutlined,
  ExclamationCircleFilled,
  PlusOutlined,
  ReadOutlined,
  ScheduleOutlined,
  WarningFilled,
} from '@ant-design/icons';
import { Button, Popconfirm, Tooltip } from 'antd';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import ConnectorToolsModal from './ConnectorToolsModal';
import { ConnectorCatalogEntry, ConnectorInstance, ConnectorStatus } from './types';

interface InstanceCardProps {
  kind: 'instance';
  connector: ConnectorInstance;
  onEdit: (connector: ConnectorInstance) => void;
  onDelete: (id: string) => void;
  onTest?: (id: string) => void;
  onSchedule?: (connector: ConnectorInstance) => void;
  /** Optional matching catalog entry — used to render brand icon, category, description */
  catalogEntry?: ConnectorCatalogEntry;
}

interface TemplateCardProps {
  kind: 'template';
  template: ConnectorCatalogEntry;
  /** Number of already-activated instances of this template (drives subtle counter chip) */
  instanceCount?: number;
  onActivate: (template: ConnectorCatalogEntry) => void;
}

type ConnectorCardProps = InstanceCardProps | TemplateCardProps;

/* ------------------------------------------------------------------ */
/* Brand tokens — each connector type gets a unique gradient + emoji  */
/* fallback. Keeps cards instantly recognizable in a dense grid.      */
/* ------------------------------------------------------------------ */

interface BrandToken {
  /** When set, render the real brand logo on a white tile (highest fidelity).
   *  Path is relative to /public. Takes precedence over `icon`. */
  logo?: string;
  /** Fallback glyph rendered on a gradient tile when no real logo exists. */
  icon?: React.ReactNode;
  gradient: string; // tailwind gradient classes for the icon tile
  shadow: string; // colored ring on hover
}

const BRAND_TOKENS: Record<string, BrandToken> = {
  github: {
    // Real GitHub mark (simple-icons, CC0). White tile keeps the logo crisp.
    logo: '/icons/connectors/github.svg',
    gradient: 'from-slate-800 to-slate-950',
    shadow: 'group-hover:ring-slate-300',
  },
  feishu: {
    icon: <span className='text-base font-bold tracking-tight'>Lark</span>,
    gradient: 'from-sky-500 to-blue-600',
    shadow: 'group-hover:ring-sky-200',
  },
  dingtalk: {
    icon: <DingtalkOutlined />,
    gradient: 'from-blue-500 to-blue-700',
    shadow: 'group-hover:ring-blue-200',
  },
  yuque: {
    icon: <ReadOutlined />,
    gradient: 'from-emerald-500 to-green-600',
    shadow: 'group-hover:ring-emerald-200',
  },
  notion: {
    // Real Notion mark (simple-icons, CC0).
    logo: '/icons/connectors/notion.svg',
    gradient: 'from-gray-700 to-gray-900',
    shadow: 'group-hover:ring-gray-300',
  },
  linear: {
    // Real Linear mark (simple-icons, CC0).
    logo: '/icons/connectors/linear.svg',
    gradient: 'from-indigo-500 to-violet-600',
    shadow: 'group-hover:ring-indigo-200',
  },
  tavily: {
    // No CC0 brand glyph available — letter tile on a teal/cyan gradient,
    // distinct from the project/doc tiles.
    icon: <span className='text-lg font-bold tracking-tight'>T</span>,
    gradient: 'from-teal-500 to-cyan-600',
    shadow: 'group-hover:ring-teal-200',
  },
  deepwiki: {
    // No CC0 brand glyph available — book glyph on amber to distinguish from
    // the emerald yuque doc tile.
    icon: <BookOutlined />,
    gradient: 'from-amber-500 to-orange-600',
    shadow: 'group-hover:ring-amber-200',
  },
  custom_mcp: {
    // ApiOutlined matches the sidebar "连接器管理" entry and the page hero —
    // the visual recognition is consistent across nav → header → card. The
    // violet/fuchsia gradient keeps custom_mcp distinguishable from built-in
    // brand tiles (which carry brand-specific colours).
    icon: <ApiOutlined />,
    gradient: 'from-violet-500 to-fuchsia-600',
    shadow: 'group-hover:ring-violet-200',
  },
};

const FALLBACK_BRAND: BrandToken = {
  icon: <ApiOutlined />,
  gradient: 'from-gray-500 to-gray-700',
  shadow: 'group-hover:ring-gray-200',
};

const brandFor = (type: string): BrandToken => BRAND_TOKENS[type] ?? FALLBACK_BRAND;

const CATEGORY_LABEL: Record<string, string> = {
  communication: '协作沟通',
  document: '知识文档',
  project: '项目管理',
  search: '搜索检索',
  dev: '研发工具',
  custom: '自定义',
};

/* ------------------------------------------------------------------ */
/* Status chip — high-contrast filled dot + label                      */
/* ------------------------------------------------------------------ */

const STATUS_META: Record<
  ConnectorStatus,
  { label: string; dot: string; text: string; bg: string; icon: React.ReactNode }
> = {
  active: {
    label: '已激活',
    dot: 'bg-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-900/30',
    icon: <CheckCircleFilled className='text-emerald-500' />,
  },
  needs_reactivation: {
    label: '需要重新激活',
    dot: 'bg-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-900/30',
    icon: <WarningFilled className='text-amber-500' />,
  },
  error: {
    label: '连接错误',
    dot: 'bg-rose-500',
    text: 'text-rose-700 dark:text-rose-400',
    bg: 'bg-rose-50 dark:bg-rose-900/30',
    icon: <ExclamationCircleFilled className='text-rose-500' />,
  },
  disconnected: {
    label: '未连接',
    dot: 'bg-gray-400',
    text: 'text-gray-600 dark:text-gray-300',
    bg: 'bg-gray-100 dark:bg-gray-800/60',
    icon: <ExclamationCircleFilled className='text-gray-400' />,
  },
};

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

const ConnectorCard: React.FC<ConnectorCardProps> = props => {
  const { t } = useTranslation();
  const [toolsModalOpen, setToolsModalOpen] = useState(false);

  /* shared shell — glass card with intentional hover lift               */
  /* Templates are visually distinct via dashed border + dimmer surface  */
  const shellBase = 'group relative rounded-2xl p-5 transition-all duration-200 h-full flex flex-col overflow-hidden';

  const shellByKind =
    props.kind === 'template'
      ? 'border border-dashed border-gray-300 bg-white/40 backdrop-blur-lg hover:bg-white/70 hover:border-violet-300 hover:shadow-[0_8px_28px_-12px_rgba(124,58,237,0.25)] dark:border-gray-600 dark:bg-gray-800/30 dark:hover:bg-gray-800/60'
      : 'border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] hover:shadow-[0_12px_32px_-12px_rgba(15,23,42,0.18)] hover:-translate-y-0.5 dark:border-[#3a4456] dark:bg-[#2b303d]/70';

  // Resolve presentation pieces (display name, description, brand)
  const isTemplate = props.kind === 'template';

  const type = isTemplate ? props.template.type : props.connector.connector_type;
  const brand = brandFor(type);

  const displayName = isTemplate ? props.template.display_name : props.connector.display_name;

  // Description precedence:
  //   1. instance.config.description (user-authored in the form)
  //   2. catalog entry description — ONLY for built-in types (those are real
  //      product descriptions like "GitHub Issues / PR / 仓库管理"). For
  //      custom_mcp this falls through, because the custom_mcp catalog
  //      "description" is just the template blurb ("接入任意 SSE / Streamable
  //      HTTP MCP Server") — it's an entry-point label, not an instance fact.
  //   3. empty (the placeholder min-height keeps the card shape stable).
  const instanceUserDescription = !isTemplate
    ? ((props.connector.config?.description as string | undefined) ?? undefined)
    : undefined;
  const description = isTemplate
    ? props.template.description
    : (
        instanceUserDescription ||
        (props.connector.connector_type === 'custom_mcp'
          ? ''
          : (props.catalogEntry?.description ?? '')) ||
        ''
      );

  const category = isTemplate
    ? props.template.category
    : (props.catalogEntry?.category ?? (props.connector.connector_type === 'custom_mcp' ? 'custom' : 'project'));

  // All instance cards are clickable — the whole card surface opens the tools
  // modal. Built-in templates (github / feishu / yuque / dingtalk) now follow
  // the same unified MCP path as custom_mcp, so there's no longer a reason to
  // gate click-to-inspect on connector_type. Template cards stay non-clickable
  // since they have no tools yet.
  const isClickableForTools = !isTemplate;

  return (
    <>
      <div
        className={`${shellBase} ${shellByKind} ${isClickableForTools ? 'cursor-pointer' : ''}`}
        onClick={isClickableForTools ? () => setToolsModalOpen(true) : undefined}
        role={isClickableForTools ? 'button' : undefined}
        tabIndex={isClickableForTools ? 0 : undefined}
        onKeyDown={
          isClickableForTools
            ? e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setToolsModalOpen(true);
                }
              }
            : undefined
        }
      >
        {/* Decorative gradient wash in corner — pure CSS, brand tinted */}
        <div
          aria-hidden
          className={`pointer-events-none absolute -top-12 -right-12 w-32 h-32 rounded-full opacity-0 group-hover:opacity-40 transition-opacity duration-300 bg-gradient-to-br ${brand.gradient} blur-3xl`}
        />

        {/* ───────────────── HEADER: icon + title block ───────────────── */}
        <div className='relative flex items-start gap-3.5 mb-3'>
          {/* Brand icon tile — 48px square. Real logos sit on a white tile
              (max fidelity); fallback glyphs sit on a brand-tinted gradient. */}
          {brand.logo ? (
            <div
              className={`flex-shrink-0 w-12 h-12 rounded-xl bg-white flex items-center justify-center shadow-sm ring-1 ring-gray-200/80 ${brand.shadow} transition-shadow dark:bg-white/95`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={brand.logo} alt={`${displayName} logo`} className='w-6 h-6 object-contain' />
            </div>
          ) : (
            <div
              className={`flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br ${brand.gradient} flex items-center justify-center text-white text-xl shadow-sm ring-2 ring-white/40 ${brand.shadow} transition-shadow`}
            >
              {brand.icon}
            </div>
          )}

          {/* Title + inline tags */}
          <div className='flex-1 min-w-0'>
            <div className='flex items-center gap-2 mb-1 flex-wrap'>
              <Tooltip title={displayName} mouseEnterDelay={0.5}>
                <h4 className='font-semibold text-[15px] leading-tight text-gray-900 dark:text-gray-50 m-0 truncate max-w-full'>
                  {displayName}
                </h4>
              </Tooltip>
              {isTemplate ? (
                <span className='inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 border border-gray-200 dark:bg-gray-700/60 dark:text-gray-300 dark:border-gray-600'>
                  模板
                </span>
              ) : (
                <span
                  className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_META[props.connector.status].bg} ${STATUS_META[props.connector.status].text}`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${STATUS_META[props.connector.status].dot}`} />
                  {STATUS_META[props.connector.status].label}
                </span>
              )}
            </div>

            {/* Metadata row — category · transport · count (compact, like ref image) */}
            <div className='flex items-center gap-1.5 text-[11px] text-gray-400 dark:text-gray-500 leading-none'>
              <span>{CATEGORY_LABEL[category] ?? category}</span>
              <span className='text-gray-300 dark:text-gray-600'>·</span>
              <span>MCP / SSE</span>
              {isTemplate && (props.instanceCount ?? 0) > 0 && (
                <>
                  <span className='text-gray-300 dark:text-gray-600'>·</span>
                  <span className='text-violet-500 font-medium'>已激活 {props.instanceCount}</span>
                </>
              )}
              {!isTemplate && props.connector.created_at && (
                <>
                  <span className='text-gray-300 dark:text-gray-600'>·</span>
                  <span className='truncate'>{props.connector.created_at.slice(0, 10)}</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ───────────────── DESCRIPTION ───────────────── */}
        <p className='text-[13px] leading-relaxed text-gray-600 dark:text-gray-300 line-clamp-2 min-h-[40px] mb-4'>
          {description}
        </p>

        {/* ───────────────── FOOTER: tag chips + actions ───────────────── */}
        <div className='mt-auto flex items-end justify-between gap-2'>
          {/* Left: subtle pill chips (like ref image's tag cloud) */}
          <div className='flex flex-wrap gap-1.5 min-w-0'>
            <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-50 text-gray-600 border border-gray-100 dark:bg-gray-700/40 dark:text-gray-300 dark:border-gray-600/40'>
              {type}
            </span>
            {isTemplate ? (
              <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-violet-50 text-violet-600 border border-violet-100 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800/40'>
                {t('connector.badge.official')}
              </span>
            ) : props.connector.is_custom ? (
              <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-violet-50 text-violet-600 border border-violet-100 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800/40'>
                {t('connector.badge.custom')}
              </span>
            ) : props.catalogEntry ? (
              <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-violet-50 text-violet-600 border border-violet-100 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800/40'>
                {t('connector.badge.official')}
              </span>
            ) : null}
          </div>

          {/* Right: actions. Template → single CTA. Instance → icon button cluster */}
          <div className='flex items-center gap-1 flex-shrink-0'>
            {isTemplate ? (
              <Button
                type='primary'
                size='small'
                icon={<PlusOutlined />}
                className='border-none bg-button-gradient shadow-sm hover:shadow-md transition-shadow'
                onClick={() => props.onActivate(props.template)}
              >
                {(props.instanceCount ?? 0) > 0 ? '再添加一个' : '激活'}
              </Button>
            ) : (
              <>
                {props.onTest && (
                  <Tooltip title='测试连接'>
                    <Button
                      type='text'
                      size='small'
                      icon={<ApiOutlined />}
                      className='text-gray-500 hover:!text-violet-600 hover:!bg-violet-50 dark:hover:!bg-violet-900/30'
                      onClick={e => {
                        e.stopPropagation();
                        props.onTest!(props.connector.id);
                      }}
                    />
                  </Tooltip>
                )}
                {props.onSchedule && (
                  <Tooltip title='定时任务'>
                    <Button
                      type='text'
                      size='small'
                      icon={<ScheduleOutlined />}
                      className='text-gray-500 hover:!text-violet-600 hover:!bg-violet-50 dark:hover:!bg-violet-900/30'
                      onClick={e => {
                        e.stopPropagation();
                        props.onSchedule!(props.connector);
                      }}
                    />
                  </Tooltip>
                )}
                <Tooltip title='编辑'>
                  <Button
                    type='text'
                    size='small'
                    icon={<EditOutlined />}
                    className='text-gray-500 hover:!text-violet-600 hover:!bg-violet-50 dark:hover:!bg-violet-900/30'
                    onClick={e => {
                      e.stopPropagation();
                      props.onEdit(props.connector);
                    }}
                  />
                </Tooltip>
                <span onClick={e => e.stopPropagation()} role='presentation'>
                  <Popconfirm
                    title='确认删除'
                    description='确定要删除该连接器吗？'
                    onConfirm={() => props.onDelete(props.connector.id)}
                    okText='删除'
                    cancelText='取消'
                    okButtonProps={{ danger: true }}
                  >
                    <Tooltip title='删除'>
                      <Button
                        type='text'
                        size='small'
                        danger
                        icon={<DeleteOutlined />}
                        className='hover:!bg-rose-50 dark:hover:!bg-rose-900/30'
                      />
                    </Tooltip>
                  </Popconfirm>
                </span>
              </>
            )}
          </div>
        </div>
      </div>
      {!isTemplate && (
        <ConnectorToolsModal
          open={toolsModalOpen}
          instance={props.connector}
          onClose={() => setToolsModalOpen(false)}
        />
      )}
    </>
  );
};

export default ConnectorCard;
