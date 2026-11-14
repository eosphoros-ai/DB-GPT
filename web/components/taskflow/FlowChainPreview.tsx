import type { ITaskflowDSL, ITaskflowNodeKind } from '@/types/taskflow';
import { groupColor, kindSpecOf } from '@/utils/taskflow';
import React from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Mini node-chain preview used on flow cards: icon per node in DSL order,
 * colored by palette group.
 */
const FlowChainPreview: React.FC<{
  dsl?: ITaskflowDSL;
  manifest?: ITaskflowNodeKind[] | null;
  max?: number;
}> = ({ dsl, manifest, max = 8 }) => {
  const { t } = useTranslation();
  const nodes = dsl?.nodes ?? [];
  const shown = nodes.slice(0, max);
  const hidden = nodes.length - shown.length;
  return (
    <div className='flex items-center gap-0 bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-lg px-2.5 py-2 overflow-hidden'>
      {shown.map((node, idx) => {
        const spec = kindSpecOf(manifest, node.kind);
        const { color } = groupColor(spec?.group ?? 'boundary');
        return (
          <React.Fragment key={node.id}>
            {idx > 0 && <span className='flex-1 min-w-[6px] h-px bg-gray-200 dark:bg-white/15' />}
            <span
              className='w-6 h-6 rounded-md flex items-center justify-center text-[12px] flex-none bg-white dark:bg-white/10 border border-gray-100 dark:border-white/10'
              style={{ color }}
              title={spec?.label ?? node.kind}
            >
              {spec?.icon ?? '•'}
            </span>
          </React.Fragment>
        );
      })}
      {hidden > 0 && <span className='text-[10px] text-gray-400 ml-2 flex-none'>+{hidden}</span>}
      <span className='text-[10px] text-gray-400 ml-auto pl-2 flex-none'>
        {t('taskflow_nodes_count', { count: nodes.length })}
      </span>
    </div>
  );
};

export default FlowChainPreview;
