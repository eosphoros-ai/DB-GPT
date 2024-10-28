import AppDefaultIcon from '@/new-components/common/AppDefaultIcon';
import { ExportOutlined } from '@ant-design/icons';
import { App, Typography } from 'antd';
import copy from 'copy-to-clipboard';
import React, { memo, useContext, useState } from 'react';
import { MobileChatContext } from '../';

const Header: React.FC = () => {
  const { appInfo } = useContext(MobileChatContext);

  const { message } = App.useApp();
  const [count, setCount] = useState(0);

  if (!appInfo?.app_code) {
    return null;
  }

  const shareApp = async () => {
    const success = copy(`dingtalk://dingtalkclient/page/link?url=${encodeURIComponent(location.href)}&pc_slide=true`);
    message[success ? 'success' : 'error'](success ? '复制成功' : '复制失败');
  };

  if (count > 6) {
    message.info(JSON.stringify(window.navigator.userAgent), 2, () => {
      setCount(0);
    });
  }

  return (
    <header className='flex w-full items-center justify-between bg-[rgba(255,255,255,0.9)] border dark:bg-black dark:border-[rgba(255,255,255,0.6)] rounded-xl mx-auto px-4 py-2 mb-4 sticky top-4 z-50 mt-4 shadow-md'>
      <div className='flex gap-2 items-center' onClick={() => setCount(count + 1)}>
        <AppDefaultIcon scene={appInfo?.team_context?.chat_scene || 'chat_agent'} width={8} height={8} />
        <div className='flex flex-col ml-2'>
          <Typography.Text className='text-md font-bold line-clamp-2'>{appInfo?.app_name}</Typography.Text>
          <Typography.Text className='text-sm line-clamp-2'>{appInfo?.app_describe}</Typography.Text>
        </div>
      </div>
      <div
        onClick={shareApp}
        className='flex items-center justify-center w-10 h-10 bg-[#ffffff99] dark:bg-[rgba(255,255,255,0.2)] border border-white dark:border-[rgba(255,255,255,0.2)] rounded-[50%] cursor-pointer'
      >
        <ExportOutlined className='text-lg' />
      </div>
    </header>
  );
};
export default memo(Header);
