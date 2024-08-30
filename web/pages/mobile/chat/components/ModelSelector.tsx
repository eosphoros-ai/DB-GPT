import { ChatContext } from '@/app/chat-context';
import ModelIcon from '@/new-components/chat/content/ModelIcon';
import { SwapOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Dropdown, Popover } from 'antd';
import React, { useContext, useMemo } from 'react';
import { MobileChatContext } from '../';

const ModelSelector: React.FC = () => {
  const { modelList } = useContext(ChatContext);
  const { model, setModel } = useContext(MobileChatContext);

  const items: MenuProps['items'] = useMemo(() => {
    if (modelList.length > 0) {
      return modelList.map(item => {
        return {
          label: (
            <div
              className='flex items-center gap-2'
              onClick={() => {
                setModel(item);
              }}
            >
              <ModelIcon width={14} height={14} model={item} />
              <span className='text-xs'>{item}</span>
            </div>
          ),
          key: item,
        };
      });
    }
    return [];
  }, [modelList, setModel]);

  return (
    <Dropdown
      menu={{
        items,
      }}
      placement='top'
      trigger={['click']}
    >
      <Popover content={model}>
        <div className='flex items-center gap-1 border rounded-xl bg-white dark:bg-black p-2 flex-shrink-0'>
          <ModelIcon width={16} height={16} model={model} />
          <span
            className='text-xs font-medium line-clamp-1'
            style={{
              maxWidth: 96,
            }}
          >
            {model}
          </span>
          <SwapOutlined rotate={90} />
        </div>
      </Popover>
    </Dropdown>
  );
};

export default ModelSelector;
