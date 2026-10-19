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
  CodeOutlined,
  FileExcelOutlined,
  FileMarkdownOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FolderOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import cls from 'classnames';

import { resolveImageUrl } from './image-url';

export interface StreamArtifact {
  id: string;
  type: string;
  name: string;
  size?: number;
  content?: any;
  stepId?: string;
  filePath?: string;
}

interface ArtifactCardsProps {
  artifacts: StreamArtifact[];
  onPreview?: (artifact: StreamArtifact) => void;
}

const PREVIEW_EXTS = new Set(['md', 'markdown', 'txt', 'py', 'js', 'ts', 'tsx', 'jsx', 'json', 'csv', 'sql']);

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

export default function ArtifactCards({ artifacts, onPreview }: ArtifactCardsProps) {
  if (!artifacts || artifacts.length === 0) return null;
  return (
    <div className='flex flex-wrap gap-2.5 mt-3 mb-1'>
      {artifacts.map(artifact => {
        const isHtml = artifact.type === 'html';
        const isImage = artifact.type === 'image';
        const isSkill = artifact.type === 'skill';
        const ext = extOf(artifact.name);
        const hasTextContent = Boolean(
          typeof artifact.content === 'string' ? artifact.content : artifact.content?.content,
        );
        const previewable =
          isHtml || isImage || isSkill || (artifact.type === 'file' && PREVIEW_EXTS.has(ext) && hasTextContent);
        const downloadable = isHtml || artifact.type === 'code' || (artifact.type === 'file' && hasTextContent);
        const meta = isHtml
          ? `HTML · ${formatSize(artifact.size) || `${(artifact.content || '').length} B`}`
          : isImage
            ? '图片'
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
              isImage ? 'w-[168px] flex-col' : 'w-[340px] gap-2.5',
            )}
          >
            <div
              className={cls(
                'bg-[#efefeb] dark:bg-white/[.04] flex items-center justify-center',
                isImage
                  ? 'h-[92px] border-b border-[#efefeb] dark:border-[#232220] cursor-pointer'
                  : 'w-[84px] self-stretch',
                previewable && 'cursor-pointer',
              )}
              onClick={() => previewable && onPreview?.(artifact)}
              title={previewable ? '预览' : undefined}
            >
              {isHtml ? (
                <ReportThumb />
              ) : isImage ? (
                <img
                  src={resolveImageUrl(String(artifact.content))}
                  alt={artifact.name}
                  className='max-h-[92px] object-contain'
                />
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
                {isImage && <PictureOutlined className='text-blue-500' />}
                {isSkill && <FolderOutlined className='text-amber-500' />}
                {artifact.name}
              </div>
              <div className='text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] truncate'>{meta}</div>
              <div className='mt-auto pt-1.5 flex gap-1.5'>
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
    </div>
  );
}
