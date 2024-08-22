import { apiInterceptors, clearChatHistory } from '@/client/api';
import { ChatContentContext } from '@/pages/chat';
import { ClearOutlined, LoadingOutlined, PauseCircleOutlined, RedoOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import { Spin, Tooltip } from 'antd';
import classNames from 'classnames';
import Image from 'next/image';
import React, { useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import ModelSwitcher from './ModelSwitcher';
import Resource from './Resource';
import Temperature from './Temperature';

interface ToolsConfig {
  icon: React.ReactNode;
  can_use: boolean;
  key: string;
  tip?: string;
  onClick?: () => void;
}

const ToolsBar: React.FC<{
  ctrl: AbortController;
}> = ({ ctrl }) => {

  const { t } = useTranslation();

  const {
    history,
    scrollRef,
    canAbort,
    replyLoading,
    currentDialogue,
    appInfo,
    temperatureValue,
    resourceValue,
    setTemperatureValue,
    refreshHistory,
    setCanAbort,
    setReplyLoading,
    handleChat,
  } = useContext(ChatContentContext);

  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [clsLoading, setClsLoading] = useState<boolean>(false);

  // 左边工具栏动态可用key
  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map((i) => i.type) || [];
  }, [appInfo.param_need]);

  const rightToolsConfig: ToolsConfig[] = useMemo(() => {
    return [
      {
        tip: t('stop_replying'),
        icon: <PauseCircleOutlined className={classNames({ 'text-[#0c75fc]': canAbort })} />,
        can_use: canAbort,
        key: 'abort',
        onClick: () => {
          if (!canAbort) {
            return;
          }
          ctrl.abort();
          setTimeout(() => {
            setCanAbort(false);
            setReplyLoading(false);
          }, 100);
        },
      },
      {
        tip: t('answer_again'),
        icon: <RedoOutlined />,
        can_use: !replyLoading && history.length > 0,
        key: 'redo',
        onClick: async () => {
          const lastHuman = history.filter((i) => i.role === 'human')?.slice(-1)?.[0];
          handleChat(lastHuman?.context || '', {
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
        },
      },
      {
        tip: t('erase_memory'),
        icon: clsLoading ? <Spin spinning={clsLoading} indicator={<LoadingOutlined style={{ fontSize: 20 }} />} /> : <ClearOutlined />,
        can_use: history.length > 0,
        key: 'clear',
        onClick: async () => {
          if (clsLoading) {
            return;
          }
          setClsLoading(true);
          await apiInterceptors(clearChatHistory(currentDialogue.conv_uid)).finally(async () => {
            await refreshHistory();
            setClsLoading(false);
          });
        },
      },
    ];
  }, [
    t,
    canAbort,
    replyLoading,
    history,
    clsLoading,
    ctrl,
    setCanAbort,
    setReplyLoading,
    handleChat,
    appInfo.app_code,
    paramKey,
    temperatureValue,
    resourceValue,
    currentDialogue.select_param,
    currentDialogue.conv_uid,
    scrollRef,
    refreshHistory,
  ]);

  const returnTools = (config: ToolsConfig[]) => {
    return (
      <>
        {config.map((item) => (
          <Tooltip key={item.key} title={item.tip} arrow={false} placement="bottom">
            <div
              className={`flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)] text-lg ${
                item.can_use ? 'cursor-pointer' : 'opacity-30 cursor-not-allowed'
              }`}
              onClick={() => {
                item.onClick?.();
              }}
            >
              {item.icon}
            </div>
          </Tooltip>
        ))}
      </>
    );
  };

  const fileName = useMemo(() => {
    try {
      return JSON.parse(currentDialogue.select_param).file_name;
    } catch (error) {
      return '';
    }
  }, [currentDialogue.select_param]);

  return (
    <div className="flex flex-col  mb-2">
      <div className="flex items-center justify-between h-full w-full">
        <div className="flex gap-3 text-lg">
          <ModelSwitcher />
          <Resource fileList={fileList} setFileList={setFileList} setLoading={setLoading} fileName={fileName} />
          <Temperature temperatureValue={temperatureValue} setTemperatureValue={setTemperatureValue} />
        </div>
        <div className="flex gap-1">{returnTools(rightToolsConfig)}</div>
      </div>
      {(fileName || fileList[0]?.name) && (
        <div className="group/item flex mt-2">
          <div className="flex items-center justify-between w-64 border border-[#e3e4e6] dark:border-[rgba(255,255,255,0.6)] rounded-lg p-2">
            <div className="flex items-center">
              <Image src={`/icons/chat/excel.png`} width={20} height={20} alt="file-icon" className="mr-2" />
              <span className="text-sm text-[#1c2533] dark:text-white line-clamp-1">{fileName || fileList[0]?.name}</span>
            </div>
            <Spin spinning={loading} indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolsBar;
