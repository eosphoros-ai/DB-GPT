import type { ITaskflowNodeKind, TaskflowGroup } from '@/types/taskflow';
import { groupColor } from '@/utils/taskflow';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { Input } from 'antd';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const GROUP_ORDER: TaskflowGroup[] = ['source', 'analysis', 'control', 'output'];

/**
 * Left palette of the TaskFlow editor: searchable product-node list grouped
 * by capability. Click "+" (or the row) to add the node to the flow.
 */
const NodePalette: React.FC<{
  manifest: ITaskflowNodeKind[] | null;
  onAdd: (kind: ITaskflowNodeKind) => void;
}> = ({ manifest, onAdd }) => {
  const { t, i18n } = useTranslation();
  const isZh = i18n.language?.startsWith('zh');
  const [keyword, setKeyword] = useState('');

  const groups = useMemo(() => {
    const items = (manifest ?? []).filter(item => item.group !== 'boundary');
    const kw = keyword.trim().toLowerCase();
    const filtered = kw
      ? items.filter(item =>
          [item.label, item.label_en, item.desc, item.desc_en]
            .filter(Boolean)
            .some(text => text.toLowerCase().includes(kw)),
        )
      : items;
    return GROUP_ORDER.map(group => ({
      group,
      items: filtered.filter(item => item.group === group),
    })).filter(entry => entry.items.length > 0);
  }, [manifest, keyword]);

  return (
    <aside className='w-[250px] flex-none border-r border-gray-100 dark:border-white/10 bg-white dark:bg-[#16171a] flex flex-col min-h-0'>
      <div className='px-3.5 pt-3 pb-2'>
        <div className='text-[13px] font-bold text-gray-800 dark:text-gray-100 mb-2'>{t('taskflow_node_panel')}</div>
        <Input
          size='small'
          allowClear
          prefix={<SearchOutlined className='text-gray-300' />}
          placeholder={t('taskflow_search_nodes')}
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
        />
      </div>
      <div className='flex-1 overflow-y-auto px-2.5 pb-4 min-h-0'>
        {groups.map(({ group, items }) => {
          const { color } = groupColor(group);
          return (
            <div key={group} className='mt-3'>
              <div className='flex items-center gap-1.5 px-1.5 pb-1.5 text-[11px] font-semibold text-gray-400'>
                <span style={{ color }}>●</span>
                {isZh ? items[0]?.group_label : items[0]?.group_label_en}
                <span className='ml-auto font-normal'>{items.length}</span>
              </div>
              {items.map(item => (
                <div
                  key={item.kind}
                  onClick={() => onAdd(item)}
                  className='flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer border border-transparent hover:border-gray-200 dark:hover:border-white/15 hover:shadow-sm bg-white dark:bg-transparent mb-1 transition-all'
                >
                  <span
                    className='w-6 h-6 rounded-md flex items-center justify-center text-[12px] flex-none'
                    style={{ background: groupColor(item.group).bg, color }}
                  >
                    {item.icon}
                  </span>
                  <span className='flex-1 min-w-0'>
                    <span className='block text-[12.5px] font-semibold text-gray-800 dark:text-gray-100 leading-tight'>
                      {isZh ? item.label : item.label_en}
                    </span>
                    <span className='block text-[10.5px] text-gray-400 truncate'>
                      {isZh ? item.desc : item.desc_en}
                    </span>
                  </span>
                  <PlusOutlined className='text-blue-500 text-[10px] flex-none' />
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </aside>
  );
};

export default NodePalette;
