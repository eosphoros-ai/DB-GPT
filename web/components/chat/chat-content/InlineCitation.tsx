import MarkDownContext from '@/new-components/common/MarkdownContext';
import { Popover } from 'antd';
import React, { useMemo } from 'react';

interface ChunkRef {
  index: number;
  id: number;
  content: string;
  meta_info?: string;
  recall_score?: number;
}

interface DocRef {
  name: string;
  chunks: ChunkRef[];
}

/**
 * Inline citation badge rendered as a blue superscript [n].
 * Hovering shows a Popover with the source document name and chunk content.
 *
 * Used by the cite-index markdown component in config.tsx to replace
 * LLM-generated [1] [2] markers with interactive citation badges.
 */
const InlineCitation: React.FC<{
  index: number;
  references?: DocRef[] | null;
}> = ({ index, references }) => {
  const chunk = useMemo(() => {
    if (!references) return null;
    for (const doc of references) {
      for (const c of doc.chunks) {
        if (c.index === index) return { doc, chunk: c };
      }
    }
    return null;
  }, [index, references]);

  // No matching reference data — render as plain text badge
  if (!chunk) {
    return (
      <sup className='inline-flex items-center mx-0.5'>
        <span className='text-[10px] font-medium text-blue-500 bg-blue-50 dark:bg-blue-900/30 rounded px-1 cursor-default select-none'>
          {index}
        </span>
      </sup>
    );
  }

  const { doc, chunk: c } = chunk;

  return (
    <Popover
      trigger='hover'
      placement='top'
      overlayStyle={{ maxWidth: 420 }}
      title={
        <div className='flex items-center justify-between gap-2 text-xs'>
          <span className='font-medium truncate max-w-[280px]' title={doc.name}>
            📄 {decodeURIComponent(doc.name)}
          </span>
          {c.recall_score != null && (
            <span className='text-gray-400 flex-shrink-0'>召回 {Number(c.recall_score).toFixed(2)}</span>
          )}
        </div>
      }
      content={
        <div className='max-h-[200px] overflow-y-auto text-xs leading-relaxed'>
          <MarkDownContext>{c.content}</MarkDownContext>
        </div>
      }
    >
      <sup className='inline-flex items-center mx-0.5 cursor-pointer'>
        <span className='text-[10px] font-medium text-white bg-blue-500 hover:bg-blue-600 rounded px-1 transition-colors select-none'>
          {index}
        </span>
      </sup>
    </Popover>
  );
};

export type { ChunkRef, DocRef };
export default InlineCitation;
