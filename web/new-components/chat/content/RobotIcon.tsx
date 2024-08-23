import { RobotOutlined } from '@ant-design/icons';
import { useSearchParams } from 'next/navigation';
import React, { memo } from 'react';

import AppDefaultIcon from '../../common/AppDefaultIcon';
import ModelIcon from './ModelIcon';

const DEFAULT_ICON_URL = '/models/huggingface.svg';

const RobotIcon: React.FC<{ model: string }> = ({ model }) => {
  const searchParams = useSearchParams();
  const scene = searchParams?.get('scene') ?? '';

  if (scene === 'chat_agent') {
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-white dark:bg-[rgba(255,255,255,0.16)]">
        <AppDefaultIcon scene={scene} />
      </div>
    );
  }

  if (!model) {
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-white dark:bg-[rgba(255,255,255,0.16)]">
        <RobotOutlined />
      </div>
    );
  }

  return <ModelIcon width={32} height={32} model={model} />;
};

export default memo(RobotIcon);
