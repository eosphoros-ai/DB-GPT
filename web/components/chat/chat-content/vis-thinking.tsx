import { DownOutlined, RightOutlined } from '@ant-design/icons';
import React from 'react';
import { useTranslation } from 'react-i18next';

interface Props {
  content: string;
}

export function VisThinking({ content }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = React.useState(true); // Control the expansion of the thinking process
  // console.log("VisThinking", content)
  return (
    <div className='my-4 border rounded-lg overflow-hidden dark:border-gray-600'>
      <div
        className='flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 cursor-pointer'
        onClick={() => setExpanded(!expanded)}
      >
        <div className='flex items-center'>
          <span className='mr-2 font-medium text-gray-700 dark:text-gray-300'>
            {expanded ? <DownOutlined /> : <RightOutlined />}
          </span>
          <span className='text-gray-700 dark:text-gray-300'>{t('cot_title')}</span>
        </div>
      </div>

      {expanded && (
        <div className='p-4 bg-white dark:bg-gray-900 border-t dark:border-gray-700'>
          <div className='py-2 px-4 border-l-4 border-blue-600 rounded bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300'>
            {content || ''}
          </div>
        </div>
      )}
    </div>
  );
}
