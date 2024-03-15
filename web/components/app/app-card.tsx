import React, { useContext, useEffect, useState } from 'react';
import { Modal } from 'antd';
import { apiInterceptors, collectApp, delApp, newDialogue, unCollectApp } from '@/client/api';
import { IApp } from '@/types/app';
import { DeleteFilled, MessageFilled, StarFilled, WarningOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/router';
import { ChatContext } from '@/app/chat-context';
import GPTCard from '../common/gpt-card';

interface IProps {
  updateApps: (data?: { is_collected: boolean }) => void;
  app: IApp;
  handleEdit: (app: any) => void;
  isCollected: boolean;
}

const { confirm } = Modal;

export default function AppCard(props: IProps) {
  const { updateApps, app, handleEdit, isCollected } = props;
  const { model } = useContext(ChatContext);
  const router = useRouter();

  const [isCollect, setIsCollect] = useState<string>(app.is_collected);
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
        updateApps(isCollected ? { is_collected: isCollected } : undefined);
      },
    });
  };

  useEffect(() => {
    setIsCollect(app.is_collected);
  }, [app]);

  const collect = async () => {
    const [error] = await apiInterceptors(isCollect === 'true' ? unCollectApp({ app_code: app.app_code }) : collectApp({ app_code: app.app_code }));
    if (error) return;
    updateApps(isCollected ? { is_collected: isCollected } : undefined);
    setIsCollect(isCollect === 'true' ? 'false' : 'true');
  };

  const handleChat = async () => {
    setAgentToChat?.(app.app_code);
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
    if (res) {
      router.push(`/chat/?scene=chat_agent&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
    }
  };

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
        handleEdit(app);
      }}
      operations={[
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
        {
          label: t('Delete'),
          children: <DeleteFilled />,
          onClick: () => {
            showDeleteConfirm();
          },
        },
      ]}
    />
  );
}
