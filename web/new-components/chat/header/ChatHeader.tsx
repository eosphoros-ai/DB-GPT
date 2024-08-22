import { apiInterceptors, collectApp, unCollectApp } from '@/client/api';
import { ChatContentContext } from '@/pages/chat';
import { ExportOutlined, LoadingOutlined, StarFilled, StarOutlined } from '@ant-design/icons';
import { Spin, Typography, message, Tag } from 'antd';
import copy from 'copy-to-clipboard';
import React, { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { useRequest } from 'ahooks';
import AppDefaultIcon from '../../common/AppDefaultIcon';

const tagColors = ['magenta', 'orange', 'geekblue', 'purple', 'cyan', 'green'];

const ChatHeader: React.FC<{ isScrollToTop: boolean }> = ({ isScrollToTop }) => {
  const { appInfo, refreshAppInfo, handleChat, scrollRef, temperatureValue, resourceValue, currentDialogue } = useContext(ChatContentContext);

  const { t } = useTranslation();

  const appScene = useMemo(() => {
    return appInfo?.team_context?.chat_scene || 'chat_agent';
  }, [appInfo]);

  // 应用收藏状态
  const isCollected = useMemo(() => {
    return appInfo?.is_collected === 'true';
  }, [appInfo]);

  const { run: operate, loading } = useRequest(
    async () => {
      const [error] = await apiInterceptors(isCollected ? unCollectApp({ app_code: appInfo.app_code }) : collectApp({ app_code: appInfo.app_code }));
      if (error) {
        return;
      }
      return await refreshAppInfo();
    },
    {
      manual: true,
    },
  );

  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map((i) => i.type) || [];
  }, [appInfo.param_need]);

  if (!Object.keys(appInfo).length) {
    return null;
  }

  const shareApp = async () => {
    const success = copy(location.href);
    message[success ? 'success' : 'error'](success ? t('copy_success') : t('copy_failed'));
  };

  // 正常header
  const headerContent = () => {
    return (
      <header className="flex items-center justify-between w-5/6 h-full px-6  bg-[#ffffff99] border dark:bg-[rgba(255,255,255,0.1)] dark:border-[rgba(255,255,255,0.1)] rounded-2xl mx-auto transition-all duration-400 ease-in-out relative">
        <div className="flex items-center">
          <div className="flex w-12 h-12 justify-center items-center rounded-xl mr-4 bg-white">
            <AppDefaultIcon scene={appScene} width={16} height={16} />
          </div>
          <div className="flex flex-col flex-1">
            <div className="flex items-center text-base text-[#1c2533] dark:text-[rgba(255,255,255,0.85)] font-semibold gap-2">
              <span>{appInfo?.app_name}</span>
              <div className="flex gap-1">
                {appInfo?.team_mode && <Tag color="green">{appInfo?.team_mode}</Tag>}
                {appInfo?.team_context?.chat_scene && <Tag color="cyan">{appInfo?.team_context?.chat_scene}</Tag>}
              </div>
            </div>
            <Typography.Text
              className="text-sm text-[#525964] dark:text-[rgba(255,255,255,0.65)] leading-6"
              ellipsis={{
                tooltip: true,
              }}
            >
              {appInfo?.app_describe}
            </Typography.Text>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div
            onClick={async () => {
              await operate();
            }}
            className="flex items-center justify-center w-10 h-10 bg-[#ffffff99] dark:bg-[rgba(255,255,255,0.2)] border border-white dark:border-[rgba(255,255,255,0.2)] rounded-[50%] cursor-pointer"
          >
            {loading ? (
              <Spin spinning={loading} indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            ) : (
              <>
                {isCollected ? (
                  <StarFilled style={{ fontSize: 18 }} className="text-yellow-400 cursor-pointer" />
                ) : (
                  <StarOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
                )}
              </>
            )}
          </div>
          <div
            onClick={shareApp}
            className="flex items-center justify-center w-10 h-10 bg-[#ffffff99] dark:bg-[rgba(255,255,255,0.2)] border border-white dark:border-[rgba(255,255,255,0.2)] rounded-[50%] cursor-pointer"
          >
            <ExportOutlined className="text-lg" />
          </div>
        </div>
        {!!appInfo?.recommend_questions?.length && (
          <div className="absolute  bottom-[-40px] left-0">
            <span className="text-sm text-[#525964] dark:text-[rgba(255,255,255,0.65)] leading-6">或许你想问：</span>
            {appInfo.recommend_questions.map((item, index) => (
              <Tag
                key={item.id}
                color={tagColors[index]}
                className="text-xs p-1 px-2 cursor-pointer"
                onClick={async () => {
                  handleChat(item?.question || '', {
                    app_code: appInfo.app_code,
                    ...(paramKey.includes('temperature') && { temperature: temperatureValue }),
                    ...(paramKey.includes('resource') && {
                      select_param: typeof resourceValue === 'string' ? resourceValue : JSON.stringify(resourceValue) || currentDialogue.select_param,
                    }),
                  });
                  setTimeout(() => {
                    scrollRef.current?.scrollTo({
                      top: scrollRef.current?.scrollHeight,
                      behavior: 'smooth',
                    });
                  }, 0);
                }}
              >
                {item.question}
              </Tag>
            ))}
          </div>
        )}
      </header>
    );
  };
  // 吸顶header
  const topHeaderContent = () => {
    return (
      <header className="flex items-center justify-between w-full h-14 bg-[#ffffffb7] dark:bg-[rgba(41,63,89,0.4)]  px-8 transition-all duration-500 ease-in-out">
        <div className="flex items-center">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg mr-2 bg-white">
            <AppDefaultIcon scene={appScene} />
          </div>
          <div className="flex items-center text-base text-[#1c2533] dark:text-[rgba(255,255,255,0.85)] font-semibold gap-2">
            <span>{appInfo?.app_name}</span>
            <div className="flex gap-1">
              {appInfo?.team_mode && <Tag color="green">{appInfo?.team_mode}</Tag>}
              {appInfo?.team_context?.chat_scene && <Tag color="cyan">{appInfo?.team_context?.chat_scene}</Tag>}
            </div>
          </div>
        </div>
        <div
          className="flex gap-8"
          onClick={async () => {
            await operate();
          }}
        >
          {loading ? (
            <Spin spinning={loading} indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
          ) : (
            <>
              {isCollected ? (
                <StarFilled style={{ fontSize: 18 }} className="text-yellow-400 cursor-pointer" />
              ) : (
                <StarOutlined style={{ fontSize: 18, cursor: 'pointer' }} />
              )}
            </>
          )}
          <ExportOutlined
            className="text-lg"
            onClick={(e) => {
              e.stopPropagation();
              shareApp();
            }}
          />
        </div>
      </header>
    );
  };

  return (
    <div
      className={`h-20 mt-6 ${
        appInfo?.recommend_questions && appInfo?.recommend_questions?.length > 0 ? 'mb-6' : ''
      } sticky top-0 bg-transparent z-30 transition-all duration-400 ease-in-out`}
    >
      {isScrollToTop ? topHeaderContent() : headerContent()}
    </div>
  );
};

export default ChatHeader;
