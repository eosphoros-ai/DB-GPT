import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppList, recommendApps } from '@/client/api';
import { getRecommendQuestions } from '@/client/api/chat';
import TabContent from '@/new-components/app/TabContent';
import ChatInput from '@/new-components/chat/input/ChatInput';
import { STORAGE_INIT_MESSAGE_KET } from '@/utils';
import { useRequest } from 'ahooks';
import { ConfigProvider, Segmented, SegmentedProps } from 'antd';
import { t } from 'i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState } from 'react';

function Default() {
  const { setCurrentDialogInfo } = useContext(ChatContext);

  const router = useRouter();
  const [apps, setApps] = useState<any>({
    app_list: [],
    total_count: 0,
  });
  const [activeKey, setActiveKey] = useState('recommend');
  const getAppListWithParams = (params: Record<string, string>) =>
    apiInterceptors(
      getAppList({
        ...params,
        page_no: '1',
        page_size: '6',
      }),
    );
  const getHotAppList = (params: Record<string, string>) =>
    apiInterceptors(
      recommendApps({
        page_no: '1',
        page_size: '6',
        ...params,
      }),
    );
  // 获取应用列表
  const {
    run: getAppListFn,
    loading,
    refresh,
  } = useRequest(
    async (app_name?: string) => {
      switch (activeKey) {
        case 'recommend':
          return await getHotAppList({});
        case 'used':
          return await getAppListWithParams({
            is_recent_used: 'true',
            need_owner_info: 'true',
            ...(app_name && { app_name }),
          });
        default:
          return [];
      }
    },
    {
      manual: true,
      onSuccess: res => {
        const [_, data] = res;
        if (activeKey === 'recommend') {
          return setApps({
            app_list: data,
            total_count: data?.length || 0,
          });
        }
        setApps(data || {});
      },
      debounceWait: 500,
    },
  );
  useEffect(() => {
    getAppListFn();
  }, [activeKey, getAppListFn]);

  const items: SegmentedProps['options'] = [
    {
      value: 'recommend',
      label: t('recommend_apps'),
    },
    {
      value: 'used',
      label: t('used_apps'),
    },
  ];

  // 获取推荐问题
  const { data: helps } = useRequest(async () => {
    const [, res] = await apiInterceptors(getRecommendQuestions());
    return res ?? [];
  });

  return (
    <ConfigProvider
      theme={{
        components: {
          Button: {
            defaultBorderColor: 'white',
          },
          Segmented: {
            itemSelectedBg: '#2867f5',
            itemSelectedColor: 'white',
          },
        },
      }}
    >
      <div className='px-28 py-10 h-full flex flex-col justify-between'>
        <div>
          <div className='flex justify-between'>
            <Segmented
              className='backdrop-filter h-10 backdrop-blur-lg bg-white bg-opacity-30 border border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
              options={items}
              value={activeKey}
              onChange={value => {
                setActiveKey(value as string);
              }}
            />
            <span className='flex items-center text-gray-500 gap-1 dark:text-slate-300'>
              <span>没有心仪的应用？去</span>
              <span
                className='flex items-center cursor-pointer'
                onClick={() => {
                  router.push('/');
                }}
              >
                <Image
                  key='image_explore'
                  src={'/pictures/explore_active.png'}
                  alt='construct_image'
                  width={24}
                  height={24}
                />
                <span className='text-default'>探索广场</span>
              </span>
              <span>发现更多</span>
            </span>
          </div>
          <TabContent apps={apps?.app_list || []} loading={loading} refresh={refresh} />
          {helps && helps.length > 0 && (
            <div>
              <h2 className='font-medium text-xl my-4'>我可以帮您：</h2>
              <div className='flex justify-start gap-4'>
                {helps.map(help => (
                  <span
                    key={help.id}
                    className='flex gap-4 items-center backdrop-filter backdrop-blur-lg cursor-pointer bg-white bg-opacity-70 border-0 rounded-lg shadow p-2 relative dark:bg-[#6f7f95] dark:bg-opacity-60'
                    onClick={() => {
                      setCurrentDialogInfo?.({
                        chat_scene: help.chat_mode,
                        app_code: help.app_code,
                      });
                      localStorage.setItem(
                        'cur_dialog_info',
                        JSON.stringify({
                          chat_scene: help.chat_mode,
                          app_code: help.app_code,
                        }),
                      );
                      localStorage.setItem(
                        STORAGE_INIT_MESSAGE_KET,
                        JSON.stringify({ id: help.app_code, message: help.question }),
                      );
                      router.push(`/chat/?scene=${help.chat_mode}&id=${help.app_code}`);
                    }}
                  >
                    <span>{help.question}</span>
                    <Image key='image_explore' src={'/icons/send.png'} alt='construct_image' width={20} height={20} />
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        <div>
          <ChatInput />
        </div>
      </div>
    </ConfigProvider>
  );
}

export default Default;
