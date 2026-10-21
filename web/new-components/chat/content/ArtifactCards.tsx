/**
 * ArtifactCards — first-class artifact cards inside the conversation
 * stream (Codex/OpenCode-style: artifacts are objects, not text).
 *
 * Rendered between the tool timeline and the answer text of a round.
 * Card tiers (mockup v2):
 *   - html report card (sandboxed iframe preview)
 *   - image card (thumbnail + preview)
 *   - skill-package card (folder aggregate: >=3 files + SKILL.md)
 *   - file cards typed by extension (md / xlsx / docx / pptx / code)
 * ``summary`` artifacts never appear here — they live in the rail
 * gallery so every conversation has artifacts without card noise.
 */
import {
  CheckOutlined,
  CodeOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FileMarkdownOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FolderOutlined,
  LoadingOutlined,
  PictureOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import cls from 'classnames';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { resolveImageUrl } from './image-url';

export interface StreamArtifact {
  id: string;
  type: string;
  name: string;
  size?: number;
  content?: any;
  stepId?: string;
  filePath?: string;
  /** 'process' intermediates collapse into a group instead of cards. */
  tier?: 'final' | 'process';
}

/** Download-zip + Add actions for a skill-package card (moved here from
 *  the legacy compact skill banner). */
const SkillActions: React.FC<{
  name: string;
  onAdd?: (name: string) => void;
  onDownload?: (name: string) => void;
}> = ({ name, onAdd, onDownload }) => {
  const { t } = useTranslation();
  const [isAdded, setIsAdded] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const bare = name.replace(/\/$/, '');
  return (
    <>
      <button
        type='button'
        title={t('download_as_zip', 'Download as zip')}
        disabled={downloading}
        onClick={() => {
          setDownloading(true);
          Promise.resolve(onDownload?.(bare)).finally(() => setDownloading(false));
        }}
        className='h-6 w-7 inline-flex items-center justify-center rounded-md border border-[#e6e6e2] dark:border-[#2a2925] text-[#8b8b84] dark:text-[#7c7972] hover:text-[#55554f] dark:hover:text-[#d4d2cc]'
      >
        {downloading ? <LoadingOutlined className='text-[11px]' /> : <DownloadOutlined className='text-[11px]' />}
      </button>
      <button
        type='button'
        onClick={() => {
          if (!isAdded) {
            setIsAdded(true);
            onAdd?.(bare);
          }
        }}
        className={
          isAdded
            ? 'h-6 px-2.5 inline-flex items-center gap-1 rounded-md text-xs font-medium bg-[#f0fdf4] text-[#15803d] border border-[#bbf7d0] dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900'
            : 'h-6 px-2.5 inline-flex items-center gap-1 rounded-md text-xs font-medium bg-[#1c1c1a] dark:bg-[#e6e4df] text-white dark:text-[#1c1c1a] hover:opacity-90'
        }
      >
        {isAdded ? <CheckOutlined className='text-[10px]' /> : <PlusOutlined className='text-[10px]' />}
        {isAdded ? t('added', 'Added') : t('add', 'Add')}
      </button>
    </>
  );
};

interface ArtifactCardsProps {
  artifacts: StreamArtifact[];
  onPreview?: (artifact: StreamArtifact) => void;
  onSkillAdd?: (name: string) => void;
  onSkillDownload?: (name: string) => void;
}

const PREVIEW_EXTS = new Set(['md', 'markdown', 'txt', 'py', 'js', 'ts', 'tsx', 'jsx', 'json', 'csv', 'sql']);
const CHART_EXT_RE = /\.(png|jpe?g|gif|svg|webp)$/i;

function extOf(name: string): string {
  const m = (name || '').toLowerCase().match(/\.([a-z0-9]+)$/);
  return m ? m[1] : '';
}

function formatSize(size?: number): string {
  if (size == null) return '';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function fileExtIcon(name: string) {
  const ext = extOf(name);
  if (ext === 'md' || ext === 'markdown') return <FileMarkdownOutlined className='text-blue-500 text-lg' />;
  if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') return <FileExcelOutlined className='text-green-600 text-lg' />;
  if (ext === 'docx' || ext === 'doc') return <FileWordOutlined className='text-blue-600 text-lg' />;
  if (ext === 'pptx' || ext === 'ppt') return <FilePptOutlined className='text-orange-500 text-lg' />;
  if (['py', 'js', 'ts', 'tsx', 'jsx', 'sql', 'sh'].includes(ext))
    return <CodeOutlined className='text-gray-500 text-lg' />;
  return <FileTextOutlined className='text-gray-400 text-lg' />;
}

function downloadArtifact(artifact: StreamArtifact) {
  const embedded = artifact.content && typeof artifact.content === 'object' ? artifact.content.content : null;
  const content =
    typeof artifact.content === 'string'
      ? artifact.content
      : typeof embedded === 'string'
        ? embedded
        : JSON.stringify(artifact.content, null, 2);
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = artifact.name || 'artifact';
  a.click();
  URL.revokeObjectURL(url);
}

/** Tiny report glyph used as the html-card thumbnail. */
export function ReportThumb() {
  return (
    <svg width='52' height='64' viewBox='0 0 52 64' aria-hidden>
      <rect x='1' y='1' width='50' height='62' rx='4' fill='#fff' stroke='#d8d8d2' />
      <rect x='6' y='7' width='26' height='4' rx='2' fill='#c9c9c2' />
      <rect x='6' y='15' width='12' height='10' rx='2' fill='#e8e8e2' />
      <rect x='20' y='15' width='12' height='10' rx='2' fill='#e8e8e2' />
      <rect x='34' y='15' width='12' height='10' rx='2' fill='#e8e8e2' />
      <g fill='#9db9e8'>
        <rect x='8' y='46' width='5' height='10' />
        <rect x='15' y='40' width='5' height='16' />
        <rect x='22' y='43' width='5' height='13' />
        <rect x='29' y='36' width='5' height='20' />
        <rect x='36' y='41' width='5' height='15' />
      </g>
      <path d='M8 34l8-4 7 3 8-6 7 4' stroke='#e8a33d' strokeWidth='1.6' fill='none' />
    </svg>
  );
}

export default function ArtifactCards({ artifacts, onPreview, onSkillAdd, onSkillDownload }: ArtifactCardsProps) {
  const { t } = useTranslation();
  const [imagesExpanded, setImagesExpanded] = useState(false);
  if (!artifacts || artifacts.length === 0) return null;
  const finals = artifacts.filter(a => a.tier !== 'process' && a.type !== 'image');
  const processes = artifacts.filter(a => a.tier === 'process');
  // Charts are not deliverables: every image artifact (thumbnail-backed or
  // plain file entry) aggregates into ONE mosaic tile that expands in place
  // into a thumbnail grid, keeping the deliverable row document-only.
  const isChart = (a: StreamArtifact) => a.type === 'image' || CHART_EXT_RE.test(a.name || '');
  const charts = processes.filter(isChart);
  const processOthers = processes.filter(a => !isChart(a));
  const chartUrl = (a: StreamArtifact) => {
    const raw = String(a.content ?? '');
    return a.type === 'image' && raw ? resolveImageUrl(raw) : '';
  };
  return (
    <div className='flex flex-wrap gap-2.5 mt-3 mb-1'>
      {finals.map(artifact => {
        const isHtml = artifact.type === 'html';
        const isSkill = artifact.type === 'skill';
        const ext = extOf(artifact.name);
        const hasTextContent = Boolean(
          typeof artifact.content === 'string' ? artifact.content : artifact.content?.content,
        );
        const previewable = isHtml || isSkill || (artifact.type === 'file' && PREVIEW_EXTS.has(ext) && hasTextContent);
        const downloadable = isHtml || artifact.type === 'code' || (artifact.type === 'file' && hasTextContent);
        const meta = isHtml
          ? `HTML · ${formatSize(artifact.size) || `${(artifact.content || '').length} B`}`
          : isSkill
            ? `技能包 · ${artifact.content?.files?.length ?? 0} 文件`
            : artifact.type === 'code'
              ? '代码'
              : `${(ext || 'file').toUpperCase()} · ${formatSize(artifact.size) || '—'}`;
        return (
          <div
            key={artifact.id}
            className={cls(
              'flex border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] bg-white dark:bg-[#111217] overflow-hidden',
              'shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)]',
              'w-[340px] gap-2.5',
            )}
          >
            <div
              className={cls(
                'bg-[#efefeb] dark:bg-white/[.04] flex items-center justify-center',
                'w-[84px] self-stretch',
                previewable && 'cursor-pointer',
              )}
              onClick={() => previewable && onPreview?.(artifact)}
              title={previewable ? '预览' : undefined}
            >
              {isHtml ? (
                <ReportThumb />
              ) : isSkill ? (
                <FolderOutlined className='text-amber-500 text-xl' />
              ) : artifact.type === 'code' ? (
                <CodeOutlined className='text-gray-400 text-lg' />
              ) : (
                fileExtIcon(artifact.name)
              )}
            </div>
            <div className='flex-1 min-w-0 px-2.5 py-2 flex flex-col gap-0.5'>
              <div className='text-[13px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df] truncate flex items-center gap-1.5'>
                {isHtml && <FileTextOutlined className='text-orange-500' />}
                {isSkill && <FolderOutlined className='text-amber-500' />}
                {artifact.name}
              </div>
              <div className='text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] truncate'>{meta}</div>
              <div className='mt-auto pt-1.5 flex gap-1.5'>
                {isSkill && <SkillActions name={artifact.name} onAdd={onSkillAdd} onDownload={onSkillDownload} />}
                {previewable && (
                  <button
                    type='button'
                    onClick={() => onPreview?.(artifact)}
                    className='h-6 px-2.5 rounded-md text-xs bg-[#1c1c1a] dark:bg-[#e6e4df] text-white dark:text-[#1c1c1a] hover:opacity-90'
                  >
                    预览
                  </button>
                )}
                {downloadable && (
                  <button
                    type='button'
                    onClick={() => downloadArtifact(artifact)}
                    className='h-6 px-2.5 rounded-md text-xs border border-[#e6e6e2] dark:border-[#2a2925] text-[#55554f] dark:text-[#a8a59e] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
                  >
                    下载
                  </button>
                )}
              </div>
            </div>
          </div>
        );
      })}
      {charts.length > 0 && !imagesExpanded && (
        <button
          type='button'
          onClick={() => setImagesExpanded(true)}
          className='w-[168px] flex flex-col border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] overflow-hidden bg-white dark:bg-[#111217] text-left shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)] hover:shadow-[0_2px_6px_rgba(20,20,15,.08),0_8px_24px_rgba(20,20,15,.06)] transition-shadow'
        >
          <span className='relative grid grid-cols-2 grid-rows-2 gap-0.5 p-0.5 h-[92px] bg-[#efefeb] dark:bg-white/[.04] border-b border-[#efefeb] dark:border-[#232220]'>
            {charts.slice(0, 4).map(im => {
              const url = chartUrl(im);
              return url ? (
                <img key={im.id} src={url} alt='' className='w-full h-full object-cover' />
              ) : (
                <span key={im.id} className='flex items-center justify-center'>
                  <PictureOutlined className='text-gray-400' />
                </span>
              );
            })}
            <span
              className='absolute inset-0 flex items-center justify-center text-white text-[12px] font-medium'
              style={{ background: 'rgba(0,0,0,0.45)' }}
            >
              {charts.length} {t('artifacts_charts_label', '图表')}
            </span>
          </span>
          <span className='block px-2.5 py-2 text-[12px] text-[#8b8b84] dark:text-[#7c7972]'>
            {t('artifacts_expand_charts', '展开全部图表')}
          </span>
        </button>
      )}
      {imagesExpanded &&
        charts.length > 0 &&
        charts.map(im => {
          const url = chartUrl(im);
          return (
            <div
              key={im.id}
              className='w-[168px] flex flex-col border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] bg-white dark:bg-[#111217] overflow-hidden shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)]'
            >
              <div
                className={cls(
                  'h-[92px] bg-[#efefeb] dark:bg-white/[.04] border-b border-[#efefeb] dark:border-[#232220] flex items-center justify-center overflow-hidden',
                  url && 'cursor-pointer',
                )}
                onClick={() => url && onPreview?.(im)}
                title={url ? '预览' : undefined}
              >
                {url ? (
                  <img src={url} alt={im.name} className='max-h-[92px] object-contain' />
                ) : (
                  <PictureOutlined className='text-gray-400 text-xl' />
                )}
              </div>
              <div className='flex-1 min-w-0 px-2.5 py-2 flex flex-col gap-0.5'>
                <div className='text-[13px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df] truncate flex items-center gap-1.5'>
                  <PictureOutlined className='text-blue-500' />
                  {im.name}
                </div>
                <div className='text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] truncate'>
                  {(extOf(im.name) || 'img').toUpperCase()} · {formatSize(im.size) || '—'}
                </div>
                {url && (
                  <div className='mt-auto pt-1.5'>
                    <button
                      type='button'
                      onClick={() => onPreview?.(im)}
                      className='h-6 px-2.5 rounded-md text-xs bg-[#1c1c1a] dark:bg-[#e6e4df] text-white dark:text-[#1c1c1a] hover:opacity-90'
                    >
                      预览
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      {imagesExpanded && charts.length > 0 && (
        <button
          type='button'
          onClick={() => setImagesExpanded(false)}
          className='h-7 px-2.5 self-center rounded-md border border-[#e6e6e2] dark:border-[#2a2925] bg-[#f4f4f0] dark:bg-white/[.04] text-[12px] text-[#8b8b84] dark:text-[#7c7972]'
        >
          {t('artifacts_collapse_charts', '收起图表')}
        </button>
      )}
      {processOthers.length > 0 && (
        <details className='w-full'>
          <summary className='cursor-pointer inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md border border-[#e6e6e2] dark:border-[#2a2925] bg-[#f4f4f0] dark:bg-white/[.04] text-[12px] text-[#8b8b84] dark:text-[#7c7972] list-none select-none'>
            ▸ {t('artifacts_process_group', '过程文件')} · {processOthers.length}
          </summary>
          <div className='flex flex-wrap gap-1.5 mt-2'>
            {processOthers.map(p => (
              <span
                key={p.id}
                title={p.filePath || p.name}
                className='inline-flex items-center h-6 px-2 rounded-md border border-[#e6e6e2] dark:border-[#2a2925] bg-[#f4f4f0] dark:bg-white/[.04] font-mono text-[11px] text-[#8b8b84] dark:text-[#7c7972]'
              >
                {p.name}
              </span>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
