import type { ITaskflowNode, ITaskflowNodeKind } from '@/types/taskflow';
import { groupColor, missingRequiredFields } from '@/utils/taskflow';
import { DeleteOutlined, MoreOutlined, WarningFilled } from '@ant-design/icons';
import { Dropdown } from 'antd';
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Handle, Position } from 'reactflow';

export interface TaskflowNodeCardData {
  node: ITaskflowNode;
  spec?: ITaskflowNodeKind;
  index: number;
  summary: string;
  onDelete?: (id: string) => void;
}

/**
 * Product-level node card on the TaskFlow canvas: icon, name, one-line
 * summary, step number — no AWEL internals exposed.
 */
const TaskflowNodeCard: React.FC<{
  data: TaskflowNodeCardData;
  selected?: boolean;
}> = ({ data, selected }) => {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language?.startsWith('zh');
  const { node, spec, index, summary, onDelete } = data;
  const { color, bg } = groupColor(spec?.group ?? 'boundary');
  const missing = missingRequiredFields(node, spec);
  const isBoundary = node.kind === 'start' || node.kind === 'output';
  const label = node.label || (isZh ? spec?.label : spec?.label_en) || node.kind;

  return (
    <div
      className={`w-[300px] bg-white dark:bg-[#1f2126] border-[1.5px] rounded-xl px-3 py-2.5 flex items-center gap-2.5 shadow-sm transition-colors ${
        selected
          ? 'border-blue-500 ring-4 ring-blue-50 dark:ring-blue-500/10'
          : 'border-gray-100 dark:border-white/10 hover:border-gray-200 dark:hover:border-white/20'
      }`}
    >
      <Handle type='target' position={Position.Top} className='!opacity-0 !pointer-events-none' />
      <div
        className='w-8 h-8 rounded-lg flex items-center justify-center text-base flex-none'
        style={{ background: bg, color }}
      >
        {spec?.icon ?? '•'}
      </div>
      <div className='flex-1 min-w-0'>
        <div className='flex items-center gap-1.5 text-[13px] font-semibold text-gray-800 dark:text-gray-100'>
          <span className='truncate'>{label}</span>
          {missing.length > 0 && (
            <WarningFilled
              className='text-amber-500 text-[11px] flex-none'
              title={t('taskflow_required_config_missing')}
            />
          )}
          {isBoundary && (
            <span className='text-[9px] px-1 rounded bg-green-50 text-green-600 font-medium flex-none'>
              {isZh ? '边界' : 'BOUNDARY'}
            </span>
          )}
        </div>
        <div className='text-[11px] text-gray-400 truncate'>{summary}</div>
      </div>
      <span className='text-[10px] text-gray-300 font-mono flex-none'>{index + 1}</span>
      {!isBoundary && onDelete && (
        <Dropdown
          menu={{
            items: [
              {
                key: 'delete',
                danger: true,
                icon: <DeleteOutlined />,
                label: t('taskflow_delete'),
                onClick: () => onDelete(node.id),
              },
            ],
          }}
          trigger={['click']}
        >
          <MoreOutlined className='text-gray-300 hover:text-gray-500 cursor-pointer flex-none text-xs' />
        </Dropdown>
      )}
      <Handle type='source' position={Position.Bottom} className='!opacity-0 !pointer-events-none' />
    </div>
  );
};

export default TaskflowNodeCard;
