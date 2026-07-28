import { CodeOutlined, CopyOutlined, InfoCircleOutlined, ReadOutlined } from '@ant-design/icons';
import { Tooltip, message } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';

interface CatResultViewerProps {
  content: string; // raw text from kbCat API
}

/**
 * Renders the raw text output from the kbCat API as a code viewer
 * with line numbers, file header, copy button, and truncation notice.
 */
const CatResultViewer: React.FC<CatResultViewerProps> = ({ content }) => {
  const { t: tt } = useTranslation();

  if (!content) {
    return (
      <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
        <ReadOutlined style={{ fontSize: 36, marginBottom: 12 }} />
        <p className='text-sm m-0'>{tt('No_Results')}</p>
      </div>
    );
  }

  const lines = content.split('\n').filter(Boolean);

  // Handle error messages (e.g., "File 'xxx' not found" or "File 'xxx' is empty")
  if (
    lines.length === 1 &&
    (content.includes('not found') || content.includes('is empty') || content.includes('does not exist'))
  ) {
    return (
      <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
        <ReadOutlined style={{ fontSize: 36, marginBottom: 12 }} />
        <p className='text-sm m-0'>{content}</p>
      </div>
    );
  }

  // Parse header: "path/to/file.py (python, 150 lines)"
  let filePath = '';
  let fileLang = '';
  let fileLines = 0;
  let codeStartIdx = 0;
  const headerMatch = lines[0]?.match(/^(.+?)\s*\((\w*)?,?\s*(\d+)\s*lines?\)/);
  if (headerMatch) {
    filePath = headerMatch[1].trim();
    fileLang = headerMatch[2] || '';
    fileLines = parseInt(headerMatch[3], 10);
    codeStartIdx = 1;
  }

  // Detect truncation line
  const truncationLine = lines.findIndex(l => l.includes('truncated, use start_line='));
  const effectiveLines = truncationLine >= 0 ? lines.slice(codeStartIdx, truncationLine) : lines.slice(codeStartIdx);

  return (
    <div className='rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 shadow-sm'>
      {/* File header bar */}
      {filePath && (
        <div className='flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-800/70 border-b border-gray-200 dark:border-gray-700'>
          <ReadOutlined style={{ color: '#13C2C2', fontSize: 14 }} />
          <span className='text-sm font-mono font-medium text-gray-700 dark:text-gray-200 truncate'>{filePath}</span>
          {fileLang && (
            <span className='text-[11px] px-1.5 py-0.5 rounded bg-teal-50 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 font-mono border border-teal-100 dark:border-teal-800/50'>
              {fileLang}
            </span>
          )}
          <span className='ml-auto flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500'>
            <span className='flex items-center gap-1'>
              <CodeOutlined style={{ fontSize: 11 }} />
              {fileLines} lines
            </span>
            <Tooltip title={tt('Copy_Btn') || 'Copy'}>
              <button
                onClick={() => {
                  const codeText = effectiveLines
                    .map(l => {
                      const m = l.match(/^\s*(\d+)\s*[|:]\s?(.*)/);
                      return m ? m[2] : l;
                    })
                    .join('\n');
                  navigator.clipboard?.writeText(codeText);
                  message.success(tt('copy_to_clipboard_success'));
                }}
                className='text-gray-400 hover:text-teal-500 dark:hover:text-teal-400 transition-colors'
              >
                <CopyOutlined style={{ fontSize: 13 }} />
              </button>
            </Tooltip>
          </span>
        </div>
      )}
      {/* Code area */}
      <div className='font-mono text-[13px] leading-[1.65] overflow-x-auto bg-white dark:bg-[#1a1d2e]'>
        {effectiveLines.map((line, i) => {
          // Numbered line (format: "  123 | code" or "  123: code")
          const match = line.match(/^\s*(\d+)\s*[|:]\s?(.*)/);
          const isEven = i % 2 === 1;
          const rowBg = isEven ? 'bg-gray-50/40 dark:bg-white/[0.015]' : 'bg-white dark:bg-transparent';
          if (match) {
            return (
              <div
                key={i}
                className={`flex ${rowBg} hover:bg-teal-50/60 dark:hover:bg-teal-900/15 transition-colors group`}
              >
                <span className='w-14 text-right pr-3 text-gray-300 dark:text-gray-600 select-none flex-shrink-0 border-r border-gray-100 dark:border-gray-700/40 group-hover:text-teal-500 dark:group-hover:text-teal-400 group-hover:bg-teal-50/50 dark:group-hover:bg-teal-900/20'>
                  {match[1]}
                </span>
                <span className='text-gray-800 dark:text-gray-200 whitespace-pre pl-3 flex-1 min-w-0'>
                  {match[2] || ' '}
                </span>
              </div>
            );
          }
          // Fallback: plain line with empty line number gutter
          return (
            <div
              key={i}
              className={`flex ${rowBg} hover:bg-teal-50/60 dark:hover:bg-teal-900/15 transition-colors group`}
            >
              <span className='w-14 flex-shrink-0 border-r border-gray-100 dark:border-gray-700/40 group-hover:bg-teal-50/50 dark:group-hover:bg-teal-900/20' />
              <span className='text-gray-800 dark:text-gray-200 whitespace-pre pl-3 flex-1 min-w-0'>{line || ' '}</span>
            </div>
          );
        })}
      </div>
      {/* Truncation notice */}
      {truncationLine >= 0 && (
        <div className='px-3 py-2 bg-amber-50/60 dark:bg-amber-900/10 border-t border-amber-100 dark:border-amber-800/40 text-xs text-amber-600 dark:text-amber-400 italic flex items-center gap-1.5'>
          <InfoCircleOutlined style={{ fontSize: 12 }} />
          {lines[truncationLine]?.trim()}
        </div>
      )}
    </div>
  );
};

export default CatResultViewer;
