import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, collectApp, delApp, newDialogue, publishApp, unCollectApp, unPublishApp } from '@/client/api';
import { IApp } from '@/types/app';
import { DeleteFilled, MessageFilled, StarFilled, WarningOutlined } from '@ant-design/icons';
import { Modal, Popconfirm, Tooltip, message } from 'antd';
import { useRouter } from 'next/router';
import React, { useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import IconFont from '@/new-components/common/Icon';
import { useRequest } from 'ahooks';
import GPTCard from '../common/gpt-card';

interface IProps {
  updateApps: (params?: Record<string, any>) => void;
  app: IApp;
  handleEdit: (app: any) => void;
  activeKey: string;
}

const { confirm } = Modal;

export default function AppCard(props: IProps) {
  const { updateApps, app, handleEdit, activeKey } = props;
  const { model } = useContext(ChatContext);
  const router = useRouter();

  const { setAgent: setAgentToChat } = useContext(ChatContext);

  const { t } = useTranslation();

  const languageMap = {
    en: t('English'),
    zh: t('Chinese'),
  };

  const showDeleteConfirm = () => {
    confirm({
      title: t('Tips'),
      icon: <WarningOutlined />,
      content: `do you want delete the application?`,
      okText: 'Yes',
      okType: 'danger',
      cancelText: 'No',
      async onOk() {
        await apiInterceptors(delApp({ app_code: app.app_code }));
        if (activeKey === 'collected') {
          updateApps({ is_collected: 'true', ignore_user: 'true' });
        } else {
          updateApps();
        }
      },
    });
  };

  const collect = async () => {
    const [error] = await apiInterceptors(
      app.is_collected === 'true' ? unCollectApp({ app_code: app.app_code }) : collectApp({ app_code: app.app_code }),
    );
    if (error) return;
    if (activeKey === 'collected') {
      updateApps({ is_collected: 'true', ignore_user: 'true' });
    } else if (activeKey === 'common') {
      updateApps({ ignore_user: 'true', published: 'true' });
    } else {
      updateApps();
    }
  };

  const handleChat = async () => {
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
    if (res) {
      // 原生应用跳转
      if (app.team_mode === 'native_app') {
        const { chat_scene = '' } = app.team_context;
        router.push(`/chat?scene=${chat_scene}&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
      } else {
        setAgentToChat?.(app.app_code);
        router.push(`/chat/?scene=chat_agent&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
      }
    }
  };

  // 发布或取消发布应用
  const { run: operate } = useRequest(
    async () => {
      if (app.published === 'true') {
        return await apiInterceptors(unPublishApp(app.app_code));
      } else {
        return await apiInterceptors(publishApp(app.app_code));
      }
    },
    {
      manual: true,
      onSuccess: (data) => {
        if (data[2]?.success) {
          if (app.published === 'true') {
            message.success(t('cancel_success'));
          } else {
            message.success(t('published_success'));
          }
        }
        updateApps?.();
      },
    },
  );

  const publicContent = () => {
    const { published = '' } = app;
    const stopPropagationFn = (e: React.MouseEvent<HTMLDivElement>) => {
      e.stopPropagation();
    };
    return (
      <Popconfirm
        title={t('Tips')}
        description={t(published == 'true' ? 'unPublish_desc' : 'publish_desc')}
        onCancel={(e: any) => {
          stopPropagationFn(e);
        }}
        onConfirm={async (e: any) => {
          stopPropagationFn(e);
          operate();
        }}
      >
        <Tooltip title={t(published == 'true' ? 'unPublish' : 'publish')}>
          {published == 'true' ? (
            <IconFont
              type="icon-unPublish-cloud"
              style={{
                fontSize: 20,
              }}
              onClick={stopPropagationFn}
            />
          ) : (
            <IconFont
              type="icon-publish-cloud"
              style={{
                fontSize: 20,
              }}
              onClick={stopPropagationFn}
            />
          )}
        </Tooltip>
      </Popconfirm>
    );
  };

  const canDelete = useMemo(() => {
    return activeKey === 'app';
  }, [activeKey]);

  const operations = useMemo(() => {
    const defaultArr = [
      {
        label: t('Chat'),
        children: <MessageFilled />,
        onClick: handleChat,
      },
      {
        label: t('collect'),
        children: <StarFilled className={app.is_collected === 'false' ? 'text-gray-400' : 'text-yellow-400'} />,
        onClick: collect,
      },
    ];
    if (canDelete) {
      defaultArr.push({
        label: t('Delete'),
        children: <DeleteFilled />,
        onClick: () => showDeleteConfirm() as any,
      });
    }
    return defaultArr;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app, canDelete]);

  return (
    <GPTCard
      title={app.app_name}
      icon={'/icons/node/vis.png'}
      iconBorder={false}
      desc={app.app_describe}
      tags={[
        { text: languageMap[app.language], color: 'default' },
        { text: app.team_mode, color: 'default' },
      ]}
      onClick={() => {
        if (!canDelete) {
          return;
        }
        handleEdit(app);
      }}
      operations={operations}
      extraContent={canDelete && publicContent()}
    />
  );
}
