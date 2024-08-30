import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, newDialogue } from '@/client/api';
import { IApp } from '@/types/app';
import { Card, Tag, Tooltip, Typography } from 'antd';
import Image from 'next/image';
import { useRouter } from 'next/router';
import React, { useContext } from 'react';

const languageMap = {
  en: '英文',
  zh: '中文',
};

const AppCard: React.FC<{ data: IApp }> = ({ data }) => {
  const { setAgent: setAgentToChat, model } = useContext(ChatContext);
  const router = useRouter();
  return (
    <Card
      className='flex h-full flex-col bg-white rounded-lg dark:bg-[#232734] dark:text-white'
      hoverable
      bordered={false}
      onClick={async () => {
        const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
        if (res) {
          // 原生应用跳转
          if (data.team_mode === 'native_app') {
            const { chat_scene = '' } = data.team_context;
            router.push(`/chat?scene=${chat_scene}&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
          } else {
            setAgentToChat?.(data.app_code);
            router.push(`/chat/?scene=chat_agent&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
          }
        }
      }}
    >
      {/* title & functions */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center '>
          <Image
            src={'/icons/node/vis.png'}
            width={44}
            height={44}
            alt={data.app_name}
            className='w-11 h-11 rounded-full mr-4 object-contain bg-white'
          />
          <div className='flex flex-col'>
            <Tooltip title={data?.app_name}>
              <span className='font-medium text-[16px] mb-1 line-clamp-1'>{data?.app_name}</span>
            </Tooltip>
            <div>
              <Tag color='default' className='text-xs'>
                {languageMap[data?.language]}
              </Tag>
              <Tag color='default' className='text-xs'>
                {data?.team_mode}
              </Tag>
            </div>
          </div>
        </div>
      </div>
      {/* content */}
      <Typography.Paragraph
        ellipsis={{
          rows: 2,
          tooltip: true,
        }}
        className='mt-4 text-sm text-gray-500 font-normal h-10'
      >
        {data?.app_describe}
      </Typography.Paragraph>
    </Card>
  );
};

export default AppCard;
