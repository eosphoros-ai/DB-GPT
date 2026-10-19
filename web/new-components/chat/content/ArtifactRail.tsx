/**
 * ArtifactRail — the mockup's contextual right-rail viewer (v2).
 *
 * Slim header + one of:
 *   - artifact preview: html iframe / image / markdown render / code mono /
 *     skill file-tree / binary meta panel
 *   - conversation artifact gallery, grouped by producing directory,
 *     with a constant fallback group carrying the final answer summary
 *     (guarantees every conversation has artifacts).
 * The legacy Execution Steps / Trace / Summary panel stays one click
 * away via the debug toggle (``onDebug``).
 */
import {
  CloseOutlined,
  CodeOutlined,
  FileExcelOutlined,
  FileMarkdownOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FolderOutlined,
  InboxOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

import MarkdownContext from '@/new-components/common/MarkdownContext';

import { resolveHtmlImageUrls, resolveImageUrl } from './image-url';

export interface RailArtifact {
  id: string;
  type: string;
  name: string;
  size?: number;
  content?: any;
  createdAt?: number;
  filePath?: string;
}

interface ArtifactRailProps {
  artifacts: RailArtifact[];
  previewArtifact: RailArtifact | null;
  onPreview: (artifact: RailArtifact | null) => void;
  onDebug: () => void;
  onClose: () => void;
  onTrace?: () => void;
}

const MD_EXTS = new Set(['md', 'markdown']);
const CODE_EXTS = new Set(['py', 'js', 'ts', 'tsx', 'jsx', 'sql', 'sh', 'json', 'csv', 'txt']);

function formatSize(size?: number): string {
  if (size == null) return '';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function extOf(name: string): string {
  const m = (name || '').toLowerCase().match(/\.([a-z0-9]+)$/);
  return m ? m[1] : '';
}

function textOf(artifact: RailArtifact): string | null {
  if (typeof artifact.content === 'string') return artifact.content;
  if (artifact.content && typeof artifact.content.content === 'string') return artifact.content.content;
  return null;
}

function typeIcon(type: string, name: string) {
  const ext = extOf(name);
  if (type === 'image') return <PictureOutlined className='text-blue-500' />;
  if (type === 'skill') return <FolderOutlined className='text-amber-500' />;
  if (MD_EXTS.has(ext)) return <FileMarkdownOutlined className='text-blue-500' />;
  if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') return <FileExcelOutlined className='text-green-600' />;
  if (ext === 'docx' || ext === 'doc') return <FileWordOutlined className='text-blue-600' />;
  if (ext === 'pptx' || ext === 'ppt') return <FilePptOutlined className='text-orange-500' />;
  if (CODE_EXTS.has(ext)) return <CodeOutlined className='text-gray-500' />;
  return <FileTextOutlined className='text-gray-400' />;
}

function typeLabel(type: string, name: string): string {
  const ext = extOf(name);
  if (type === 'html') return 'HTML';
  if (type === 'image') return '图片';
  if (type === 'skill') return '技能包';
  if (type === 'summary') return 'summary';
  if (type === 'code') return '代码';
  return ext ? ext.toUpperCase() : '文件';
}

/** Wide report glyph for gallery thumbnails (mockup gitem style). */
function ThumbGlyph({ artifact }: { artifact: RailArtifact }) {
  if (artifact.type === 'image') {
    return (
      <img src={resolveImageUrl(String(artifact.content))} alt={artifact.name} className='w-full h-full object-cover' />
    );
  }
  if (artifact.type === 'skill') {
    return (
      <svg width='100%' height='86' viewBox='0 0 480 86' preserveAspectRatio='none' aria-hidden>
        <path d='M40 18h60l14 12h120v40H40z' fill='#fff' stroke='#d8d8d2' />
        <path d='M40 18h60l14 12h120v10H40z' fill='#ecece6' />
        <g stroke='#9a9a92' strokeWidth='2' fill='none'>
          <path d='M60 40v22M60 46h16M60 54h16' />
        </g>
        <g fill='#8b8b84'>
          <rect x='84' y='44' width='60' height='4' rx='2' />
          <rect x='84' y='54' width='72' height='4' rx='2' />
        </g>
        <g fill='#9db9e8'>
          <rect x='300' y='46' width='16' height='24' />
          <rect x='324' y='34' width='16' height='36' />
          <rect x='348' y='40' width='16' height='30' />
          <rect x='372' y='26' width='16' height='44' />
        </g>
      </svg>
    );
  }
  if (artifact.type === 'html') {
    return (
      <svg width='100%' height='86' viewBox='0 0 480 86' preserveAspectRatio='none' aria-hidden>
        <rect x='12' y='10' width='150' height='8' rx='3' fill='#d5d5cf' />
        <rect x='12' y='28' width='100' height='40' rx='4' fill='#ecece6' />
        <rect x='122' y='28' width='100' height='40' rx='4' fill='#ecece6' />
        <rect x='232' y='28' width='100' height='40' rx='4' fill='#ecece6' />
        <g fill='#9db9e8'>
          <rect x='352' y='48' width='14' height='20' />
          <rect x='372' y='36' width='14' height='32' />
          <rect x='392' y='42' width='14' height='26' />
          <rect x='412' y='28' width='14' height='40' />
        </g>
      </svg>
    );
  }
  const ext = extOf(artifact.name);
  if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') {
    return (
      <svg width='100%' height='86' viewBox='0 0 480 86' preserveAspectRatio='none' aria-hidden>
        <g stroke='#7fb069' strokeWidth='2' fill='none'>
          <rect x='120' y='12' width='240' height='62' />
          <path d='M120 32h240M120 52h240M200 12v62M280 12v62' />
        </g>
      </svg>
    );
  }
  if (MD_EXTS.has(ext) || artifact.type === 'summary') {
    return (
      <svg width='100%' height='86' viewBox='0 0 480 86' preserveAspectRatio='none' aria-hidden>
        <g fill='#c9c9c2'>
          <rect x='120' y='14' width='150' height='8' rx='4' />
          <rect x='120' y='32' width='240' height='4' rx='2' />
          <rect x='120' y='42' width='240' height='4' rx='2' />
          <rect x='120' y='52' width='180' height='4' rx='2' />
          <rect x='120' y='62' width='210' height='4' rx='2' />
        </g>
      </svg>
    );
  }
  return (
    <span className='flex items-center justify-center w-full h-full text-gray-400 text-xl'>
      {typeIcon(artifact.type, artifact.name)}
    </span>
  );
}

function PreviewBody({ artifact, onPreview }: { artifact: RailArtifact; onPreview: (a: RailArtifact | null) => void }) {
  const text = textOf(artifact);
  const ext = extOf(artifact.name);
  if (artifact.type === 'image') {
    return (
      <img
        src={resolveImageUrl(String(artifact.content))}
        alt={artifact.name}
        className='max-w-full rounded-lg border border-[#e6e6e2] dark:border-[#2a2925]'
      />
    );
  }
  if (artifact.type === 'html') {
    return (
      <iframe
        title={artifact.name}
        sandbox='allow-scripts'
        srcDoc={resolveHtmlImageUrls(text || '')}
        className='w-full h-full min-h-[480px] rounded-lg border border-[#e6e6e2] dark:border-[#2a2925] bg-white'
      />
    );
  }
  if (artifact.type === 'skill') {
    const files: any[] = artifact.content?.files || [];
    return (
      <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] overflow-hidden bg-white dark:bg-[#111217]'>
        <div className='px-4 py-3 border-b border-[#efefeb] dark:border-[#232220] font-mono text-[13px] text-[#1c1c1a] dark:text-[#e6e4df]'>
          {artifact.name}
          <span className='ml-2 text-[11.5px] text-[#8b8b84] font-sans'>
            技能包 · {files.length} 文件 · {formatSize(artifact.size)}
          </span>
        </div>
        <div className='p-2'>
          {files.map(f => {
            const previewable = f.content != null;
            return (
              <div
                key={f.filePath || f.name}
                role={previewable ? 'button' : undefined}
                tabIndex={previewable ? 0 : undefined}
                onClick={() => {
                  if (!previewable) return;
                  onPreview({
                    id: f.filePath || f.name,
                    type: 'file',
                    name: f.name,
                    size: f.size,
                    content: { content: f.content },
                    filePath: f.filePath,
                  });
                }}
                title={previewable ? '预览文件' : '该文件无预览内容（历史会话或二进制）'}
                className={
                  previewable
                    ? 'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer hover:bg-[#f4f4f0] dark:hover:bg-white/[.05]'
                    : 'flex items-center gap-2 px-2 py-1.5 rounded-md opacity-60'
                }
              >
                <span className='flex-none'>{typeIcon('file', f.name)}</span>
                <span className='flex-1 min-w-0 font-mono text-xs text-[#55554f] dark:text-[#a8a59e] truncate'>
                  {f.name}
                </span>
                <span className='flex-none text-[11px] text-[#8b8b84]'>{formatSize(f.size)}</span>
                {previewable && (
                  <span className='flex-none h-6 px-2 rounded-md text-xs border border-[#e6e6e2] dark:border-[#2a2925] text-[#55554f] dark:text-[#a8a59e] flex items-center'>
                    预览
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  if (artifact.type === 'summary' || MD_EXTS.has(ext)) {
    return (
      <div className='prose prose-sm dark:prose-invert max-w-none text-[#3d3d38] dark:text-[#d4d2cc]'>
        <MarkdownContext>{text || ''}</MarkdownContext>
      </div>
    );
  }
  if (text != null) {
    return (
      <pre className='text-xs leading-5 font-mono bg-[#efefeb] dark:bg-white/[.04] rounded-lg p-3 text-[#55554f] dark:text-[#a8a59e] whitespace-pre-wrap break-all max-h-[560px] overflow-y-auto'>
        {text}
      </pre>
    );
  }
  return (
    <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] p-4 bg-white dark:bg-[#111217] space-y-2'>
      <div className='flex items-center gap-2 text-[13px] font-medium text-[#1c1c1a] dark:text-[#e6e4df]'>
        {typeIcon(artifact.type, artifact.name)}
        {artifact.name}
      </div>
      <div className='text-[11.5px] text-[#8b8b84]'>
        {typeLabel(artifact.type, artifact.name)}
        {artifact.size != null ? ` · ${formatSize(artifact.size)}` : ''}
      </div>
      <div className='text-xs text-[#8b8b84] pt-1'>二进制办公文档 v1 不在浏览器内渲染，提供元信息与下载入口。</div>
    </div>
  );
}

export default function ArtifactRail({
  artifacts,
  previewArtifact,
  onPreview,
  onDebug,
  onClose,
  onTrace,
}: ArtifactRailProps) {
  const { t } = useTranslation();
  const list = artifacts || [];

  const groups: { label: string; items: RailArtifact[] }[] = [];
  for (const a of list) {
    let label = '会话根目录';
    if (a.type === 'summary') label = '兜底产物';
    else if (a.filePath) {
      const dir = a.filePath.split('/').slice(0, -1).join('/');
      label = dir || '会话根目录';
    } else if (a.type === 'skill') {
      label = (a.filePath || a.name).replace(/\/$/, '');
    }
    const g = groups.find(x => x.label === label);
    if (g) g.items.push(a);
    else groups.push({ label, items: [a] });
  }

  return (
    <div className='flex h-full min-h-0 flex-col bg-white dark:bg-[#111217]'>
      {/* slim viewer header */}
      <div className='flex flex-shrink-0 items-center gap-2 border-b border-[#e6e6e2] dark:border-[#2a2925] px-4 h-11'>
        <InboxOutlined className='text-[#8b8b84]' />
        <span className='text-[13px] font-medium text-[#1c1c1a] dark:text-[#e6e4df] truncate'>
          {previewArtifact ? previewArtifact.name : t('rail_artifacts_title')}
        </span>
        {!previewArtifact && list.length > 0 && (
          <span className='text-xs text-[#8b8b84] flex-none'>
            {t('rail_artifacts_count', { count: list.length })} · {groups.length} 组
          </span>
        )}
        <span className='flex-1' />
        {previewArtifact && (
          <button
            type='button'
            onClick={() => onPreview(null)}
            className='h-7 px-2 rounded-md text-xs text-[#55554f] dark:text-[#a8a59e] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
          >
            {t('rail_back_gallery')}
          </button>
        )}
        {onTrace && (
          <button
            type='button'
            title={t('observability_trace_tab') || 'Trace'}
            onClick={onTrace}
            className='h-7 px-2 rounded-md flex items-center gap-1.5 text-xs text-[#55554f] dark:text-[#a8a59e] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
          >
            <svg width='13' height='13' viewBox='0 0 16 16' fill='none' stroke='currentColor' strokeWidth='1.4'>
              <circle cx='3.5' cy='8' r='1.8' />
              <circle cx='12.5' cy='3.5' r='1.8' />
              <circle cx='12.5' cy='12.5' r='1.8' />
              <path d='M5.2 7.2l5.6-2.9M5.2 8.8l5.6 2.9' />
            </svg>
            {t('observability_trace_tab') || 'Trace'}
          </button>
        )}
        <button
          type='button'
          title={t('rail_debug_view')}
          onClick={onDebug}
          className='w-7 h-7 rounded-md flex items-center justify-center text-[#8b8b84] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
        >
          <CodeOutlined />
        </button>
        <button
          type='button'
          title={t('collapse_panel')}
          onClick={onClose}
          className='w-7 h-7 rounded-md flex items-center justify-center text-[#8b8b84] hover:bg-[#f4f4f0] dark:hover:bg-white/[.06]'
        >
          <CloseOutlined />
        </button>
      </div>

      {/* body: preview or grouped gallery */}
      <div className='flex-1 min-h-0 overflow-y-auto p-4'>
        {previewArtifact ? (
          <PreviewBody artifact={previewArtifact} onPreview={onPreview} />
        ) : list.length === 0 ? (
          <div className='py-16 text-center text-sm text-[#8b8b84]'>{t('rail_no_artifacts')}</div>
        ) : (
          <div className='space-y-4'>
            {groups.map(group => (
              <div key={group.label}>
                <div className='text-[11px] tracking-[.06em] uppercase text-[#8b8b84] mb-1.5 font-mono truncate'>
                  {group.label}
                </div>
                <div className='space-y-2.5'>
                  {group.items.map(artifact => (
                    <button
                      key={artifact.id}
                      type='button'
                      onClick={() => onPreview(artifact)}
                      className='w-full text-left border border-[#e6e6e2] dark:border-[#2a2925] rounded-[10px] overflow-hidden bg-white dark:bg-[#111217] hover:shadow-[0_1px_2px_rgba(20,20,15,.05),0_4px_16px_rgba(20,20,15,.04)] transition-shadow'
                    >
                      <span className='block h-[86px] bg-[#efefeb] dark:bg-white/[.04] border-b border-[#efefeb] dark:border-[#232220] overflow-hidden'>
                        <ThumbGlyph artifact={artifact} />
                      </span>
                      <span className='flex items-center justify-between gap-2 px-3 py-2'>
                        <span className='text-[12.5px] font-medium text-[#3d3d38] dark:text-[#d4d2cc] truncate'>
                          {artifact.name}
                        </span>
                        <span className='flex-none text-[11.5px] text-[#8b8b84]'>
                          {typeLabel(artifact.type, artifact.name)}
                          {artifact.size != null ? ` · ${formatSize(artifact.size)}` : ''}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
