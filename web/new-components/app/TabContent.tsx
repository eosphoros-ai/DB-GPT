import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, collectApp, newDialogue, unCollectApp } from '@/client/api';
import BlurredCard from '@/new-components/common/blurredCard';
import { IApp } from '@/types/app';
import { StarFilled, StarOutlined } from '@ant-design/icons';
import { Avatar, Empty, Spin } from 'antd';
import Image from 'next/image';
import { useRouter } from 'next/router';
import React, { useContext } from 'react';
import IconFont from '../common/Icon';

const TabContent: React.FC<{ apps: IApp[]; loading: boolean; refresh: () => void; type: 'used' | 'recommend' }> = ({
  apps,
  refresh,
  loading,
  type,
}) => {
  const collect = async (data: Record<string, any>) => {
    const [error] = await apiInterceptors(
      data.is_collected === 'true'
        ? unCollectApp({ app_code: data.app_code })
        : collectApp({ app_code: data.app_code }),
    );
    if (error) return;
    refresh();
  };
  const { setAgent: setAgentToChat, model, setCurrentDialogInfo } = useContext(ChatContext);
  const router = useRouter();

  const toChat = async (data: IApp) => {
    // 原生应用跳转
    if (data.team_mode === 'native_app') {
      const { chat_scene = '' } = data.team_context;
      const [, res] = await apiInterceptors(newDialogue({ chat_mode: chat_scene }));
      if (res) {
        setCurrentDialogInfo?.({
          chat_scene: res.chat_mode,
          app_code: data.app_code,
        });
        localStorage.setItem(
          'cur_dialog_info',
          JSON.stringify({
            chat_scene: res.chat_mode,
            app_code: data.app_code,
          }),
        );
        router.push(`/chat?scene=${chat_scene}&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
      }
    } else {
      // 自定义应用
      const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
      if (res) {
        setCurrentDialogInfo?.({
          chat_scene: res.chat_mode,
          app_code: data.app_code,
        });
        localStorage.setItem(
          'cur_dialog_info',
          JSON.stringify({
            chat_scene: res.chat_mode,
            app_code: data.app_code,
          }),
        );
        setAgentToChat?.(data.app_code);
        router.push(`/chat/?scene=chat_agent&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
      }
    }
  };

  if (loading) {
    return <Spin size='large' className='flex items-center justify-center h-full' spinning={loading} />;
  }
  return (
    <div className='flex flex-wrap mt-4 w-full overflow-y-auto '>
      {apps?.length > 0 ? (
        apps.map(item => (
          <BlurredCard
            key={item.app_code}
            name={item.app_name}
            description={item.app_describe}
            onClick={() => toChat(item)}
            RightTop={
              item.is_collected === 'true' ? (
                <StarFilled
                  onClick={e => {
                    e.stopPropagation();
                    collect(item);
                  }}
                  style={{
                    height: '21px',
                    cursor: 'pointer',
                    color: '#f9c533',
                  }}
                />
              ) : (
                <StarOutlined
                  onClick={e => {
                    e.stopPropagation();
                    collect(item);
                  }}
                  style={{
                    height: '21px',
                    cursor: 'pointer',
                  }}
                />
              )
            }
            LeftBottom={
              <div className='flex gap-8 items-center text-gray-500 text-sm'>
                {item.owner_name && (
                  <div className='flex gap-1 items-center'>
                    <Avatar
                      src={item?.owner_avatar_url}
                      className='bg-gradient-to-tr from-[#31afff] to-[#1677ff] cursor-pointer'
                    >
                      {item.owner_name}
                    </Avatar>
                    <span>{item.owner_name}</span>
                  </div>
                )}
                {/* 最近使用不展示热度值 */}
                {type !== 'used' && (
                  <div className='flex items-start gap-1'>
                    <IconFont type='icon-hot' className='text-lg' />
                    <span className='text-[#878c93]'>{item.hot_value}</span>
                  </div>
                )}
              </div>
            }
            scene={item?.team_context?.chat_scene || 'chat_agent'}
          />
        ))
      ) : (
        <Empty
          image={
            <Image src='/pictures/empty.png' alt='empty' width={142} height={133} className='w-[142px] h-[133px]' />
          }
          className='flex justify-center items-center w-full h-full min-h-[200px]'
        />
      )}
    </div>
  );
};

export default TabContent;
