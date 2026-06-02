import { ArrowLeftOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Button } from 'antd';
import { useRouter } from 'next/router';
import React, { memo } from 'react';

interface FromTaskBannerProps {
  taskId: string;
}

const FromTaskBanner: React.FC<FromTaskBannerProps> = ({ taskId }) => {
  const router = useRouter();

  return (
    <div className='flex items-center justify-between px-6 py-2 text-sm bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300'>
      <span className='flex items-center gap-2'>
        <ClockCircleOutlined />
        此对话由定时任务自动生成
      </span>
      <Button
        type='link'
        size='small'
        icon={<ArrowLeftOutlined />}
        onClick={() => router.push(`/construct/scheduled-tasks/${taskId}`)}
      >
        返回任务详情
      </Button>
    </div>
  );
};

export default memo(FromTaskBanner);
