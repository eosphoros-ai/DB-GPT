import { ChatContext } from '@/app/chat-context';
import {
  apiInterceptors,
  delApp,
  getAppAdmins,
  getAppList,
  newDialogue,
  publishApp,
  unPublishApp,
  updateAppAdmins,
} from '@/client/api';
import BlurredCard, { ChatButton, InnerDropdown } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { IApp } from '@/types/app';
import { BulbOutlined, DingdingOutlined, PlusOutlined, SearchOutlined, WarningOutlined } from '@ant-design/icons';
import { useDebounceFn, useRequest } from 'ahooks';
import { App, Button, Input, Modal, Pagination, Popover, Segmented, SegmentedProps, Select, Spin, Tag } from 'antd';
import copy from 'copy-to-clipboard';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import CreateAppModal from './components/create-app-modal';

type TabKey = 'all' | 'published' | 'unpublished';
type ModalType = 'edit' | 'add';

export default function AppContent() {
  const { t } = useTranslation();
  const [open, setOpen] = useState<boolean>(false);
  const [spinning, setSpinning] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState<TabKey>('all');
  const [apps, setApps] = useState<IApp[]>([]);
  const [modalType, setModalType] = useState<ModalType>('add');
  const { model, setAgent: setAgentToChat, setCurrentDialogInfo } = useContext(ChatContext);
  const router = useRouter();
  const { openModal = '' } = router.query;
  const [filterValue, setFilterValue] = useState('');
  const [curApp] = useState<IApp>();
  const [adminOpen, setAdminOpen] = useState<boolean>(false);
  const [admins, setAdmins] = useState<string[]>([]);
  // 分页信息
  const totalRef = useRef<{
    current_page: number;
    total_count: number;
    total_page: number;
  }>();
  // 区分是单击还是双击
  const [clickTimeout, setClickTimeout] = useState(null);

  const { message } = App.useApp();

  const handleCreate = () => {
    setModalType('add');
    setOpen(true);
    localStorage.removeItem('new_app_info');
  };

  const handleEdit = (app: any) => {
    localStorage.setItem('new_app_info', JSON.stringify({ ...app, isEdit: true }));
    router.push(`/construct/app/extra`);
  };

  const getListFiltered = useCallback(() => {
    let published = undefined;
    if (activeKey === 'published') {
      published = 'true';
    }
    if (activeKey === 'unpublished') {
      published = 'false';
    }
    initData({ app_name: filterValue, published });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeKey, filterValue]);

  const handleTabChange = (activeKey: string) => {
    setActiveKey(activeKey as TabKey);
  };

  // 发布或取消发布应用
  const { run: operate } = useRequest(
    async (app: IApp) => {
      if (app.published === 'true') {
        return await apiInterceptors(unPublishApp(app.app_code));
      } else {
        return await apiInterceptors(publishApp(app.app_code));
      }
    },
    {
      manual: true,
      onSuccess: data => {
        if (data[2]?.success) {
          message.success('操作成功');
        }
        getListFiltered();
      },
    },
  );

  const initData = useDebounceFn(
    async params => {
      setSpinning(true);
      const obj: any = {
        page: 1,
        page_size: 12,
        ...params,
      };
      const [error, data] = await apiInterceptors(getAppList(obj));
      if (error) {
        setSpinning(false);
        return;
      }
      if (!data) return;
      setApps(data?.app_list || []);
      totalRef.current = {
        current_page: data?.current_page || 1,
        total_count: data?.total_count || 0,
        total_page: data?.total_page || 0,
      };
      setSpinning(false);
    },
    {
      wait: 500,
    },
  ).run;

  const showDeleteConfirm = (app: IApp) => {
    Modal.confirm({
      title: t('Tips'),
      icon: <WarningOutlined />,
      content: `do you want delete the application?`,
      okText: 'Yes',
      okType: 'danger',
      cancelText: 'No',
      async onOk() {
        await apiInterceptors(delApp({ app_code: app.app_code }));
        getListFiltered();
      },
    });
  };

  useEffect(() => {
    if (openModal) {
      setModalType('add');
      setOpen(true);
    }
  }, [openModal]);

  const languageMap = {
    en: t('English'),
    zh: t('Chinese'),
  };
  const handleChat = async (app: IApp) => {
    // 原生应用跳转
    if (app.team_mode === 'native_app') {
      const { chat_scene = '' } = app.team_context;
      const [, res] = await apiInterceptors(newDialogue({ chat_mode: chat_scene }));
      if (res) {
        setCurrentDialogInfo?.({
          chat_scene: res.chat_mode,
          app_code: app.app_code,
        });
        localStorage.setItem(
          'cur_dialog_info',
          JSON.stringify({
            chat_scene: res.chat_mode,
            app_code: app.app_code,
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
          app_code: app.app_code,
        });
        localStorage.setItem(
          'cur_dialog_info',
          JSON.stringify({
            chat_scene: res.chat_mode,
            app_code: app.app_code,
          }),
        );
        setAgentToChat?.(app.app_code);
        router.push(`/chat/?scene=chat_agent&id=${res.conv_uid}${model ? `&model=${model}` : ''}`);
      }
    }
  };
  const items: SegmentedProps['options'] = [
    {
      value: 'all',
      label: t('apps'),
    },
    {
      value: 'published',
      label: t('published'),
    },
    {
      value: 'unpublished',
      label: t('unpublished'),
    },
  ];

  const onSearch = async (e: any) => {
    const v = e.target.value;
    setFilterValue(v);
  };

  // 获取应用权限列表
  const { run: getAdmins, loading } = useRequest(
    async (appCode: string) => {
      const [, res] = await apiInterceptors(getAppAdmins(appCode));

      return res ?? [];
    },
    {
      manual: true,
      onSuccess: data => {
        setAdmins(data);
      },
    },
  );

  // 更新应用权限
  const { run: updateAdmins, loading: adminLoading } = useRequest(
    async (params: { app_code: string; admins: string[] }) => await apiInterceptors(updateAppAdmins(params)),
    {
      manual: true,
      onSuccess: () => {
        message.success('更新成功');
      },
    },
  );

  const handleChange = async (value: string[]) => {
    setAdmins(value);
    await updateAdmins({
      app_code: curApp?.app_code || '',
      admins: value,
    });
    await initData();
  };

  useEffect(() => {
    if (curApp) {
      getAdmins(curApp.app_code);
    }
  }, [curApp, getAdmins]);

  useEffect(() => {
    getListFiltered();
  }, [getListFiltered]);

  // 单击复制分享钉钉链接
  const shareDingding = (item: IApp) => {
    if (clickTimeout) {
      clearTimeout(clickTimeout);
      setClickTimeout(null);
    }
    const timeoutId = setTimeout(() => {
      const mobileUrl = `${location.origin}/mobile/chat/?chat_scene=${item?.team_context?.chat_scene || 'chat_agent'}&app_code=${item.app_code}`;
      const dingDingUrl = `dingtalk://dingtalkclient/page/link?url=${encodeURIComponent(mobileUrl)}&pc_slide=true`;
      const result = copy(dingDingUrl);
      if (result) {
        message.success('复制成功');
      } else {
        message.error('复制失败');
      }
      setClickTimeout(null);
    }, 300); // 双击时间间隔
    setClickTimeout(timeoutId as any);
  };

  // 双击直接打开钉钉
  const openDingding = (item: IApp) => {
    if (clickTimeout) {
      clearTimeout(clickTimeout);
      setClickTimeout(null);
    }
    const mobileUrl = `${location.origin}/mobile/chat/?chat_scene=${item?.team_context?.chat_scene || 'chat_agent'}&app_code=${item.app_code}`;
    const dingDingUrl = `dingtalk://dingtalkclient/page/link?url=${encodeURIComponent(mobileUrl)}&pc_slide=true`;
    window.open(dingDingUrl);
  };

  return (
    <ConstructLayout>
      <Spin spinning={spinning}>
        <div className='h-screen w-full p-4 md:p-6 overflow-y-auto'>
          <div className='flex justify-between items-center mb-6'>
            <div className='flex items-center gap-4'>
              <Segmented
                className='backdrop-filter h-10 backdrop-blur-lg bg-white bg-opacity-30 border border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
                options={items as any}
                onChange={handleTabChange}
                value={activeKey}
              />
              <Input
                variant='filled'
                value={filterValue}
                prefix={<SearchOutlined />}
                placeholder={t('please_enter_the_keywords')}
                onChange={onSearch}
                onPressEnter={onSearch}
                allowClear
                className='w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
              />
            </div>
            <div className='flex items-center gap-4 h-10'>
              <Button
                className='border-none text-white bg-button-gradient h-full flex items-center'
                icon={<PlusOutlined className='text-base' />}
                onClick={handleCreate}
              >
                {t('create_app')}
              </Button>
            </div>
          </div>
          <div className=' w-full flex flex-wrap pb-12 mx-[-8px]'>
            {apps.map(item => {
              return (
                <BlurredCard
                  key={item.app_code}
                  code={item.app_code}
                  name={item.app_name}
                  description={item.app_describe}
                  RightTop={
                    <div className='flex items-center gap-2'>
                      <Popover
                        content={
                          <div className='flex flex-col gap-2'>
                            <div className='flex items-center gap-2'>
                              <BulbOutlined
                                style={{
                                  color: 'rgb(252,204,96)',
                                  fontSize: 12,
                                }}
                              />
                              <span className='text-sm text-gray-500'>{t('copy_url')}</span>
                            </div>
                            <div className='flex items-center gap-2'>
                              <BulbOutlined
                                style={{
                                  color: 'rgb(252,204,96)',
                                  fontSize: 12,
                                }}
                              />
                              <span className='text-sm text-gray-500'>{t('double_click_open')}</span>
                            </div>
                          </div>
                        }
                      >
                        <DingdingOutlined
                          className='cursor-pointer text-[#0069fe] hover:bg-white hover:dark:bg-black p-2 rounded-md'
                          onClick={() => shareDingding(item)}
                          onDoubleClick={() => openDingding(item)}
                        />
                      </Popover>
                      <InnerDropdown
                        menu={{
                          items: [
                            {
                              key: 'publish',
                              label: (
                                <span
                                  onClick={e => {
                                    e.stopPropagation();
                                    operate(item);
                                  }}
                                >
                                  {item.published === 'true' ? t('unpublish') : t('publish')}
                                </span>
                              ),
                            },
                            {
                              key: 'del',
                              label: (
                                <span
                                  className='text-red-400'
                                  onClick={e => {
                                    e.stopPropagation();
                                    showDeleteConfirm(item);
                                  }}
                                >
                                  {t('Delete')}
                                </span>
                              ),
                            },
                          ],
                        }}
                      />
                    </div>
                  }
                  Tags={
                    <div>
                      <Tag>{languageMap[item.language]}</Tag>
                      <Tag>{item.team_mode}</Tag>
                      <Tag>{item.published === 'true' ? t('published') : t('unpublished')}</Tag>
                    </div>
                  }
                  rightTopHover={false}
                  LeftBottom={
                    <div className='flex gap-2'>
                      <span>{item.owner_name}</span>
                      <span>•</span>
                      {item?.updated_at && <span>{moment(item?.updated_at).fromNow() + ' ' + t('update')}</span>}
                    </div>
                  }
                  RightBottom={
                    <ChatButton
                      onClick={() => {
                        handleChat(item);
                      }}
                    />
                  }
                  onClick={() => {
                    handleEdit(item);
                  }}
                  scene={item?.team_context?.chat_scene || 'chat_agent'}
                />
              );
            })}
            <div className='w-full flex justify-end shrink-0 pb-12'>
              <Pagination
                total={totalRef.current?.total_count || 0}
                pageSize={12}
                current={totalRef.current?.current_page}
                onChange={async (page, _page_size) => {
                  await initData({ page });
                }}
              />
            </div>
          </div>
          {open && (
            <CreateAppModal
              open={open}
              onCancel={() => {
                setOpen(false);
              }}
              refresh={initData}
              type={modalType}
            />
          )}
        </div>
      </Spin>
      <Modal title='权限管理' open={adminOpen} onCancel={() => setAdminOpen(false)} footer={null}>
        <Spin spinning={loading}>
          <div className='py-4'>
            <div className='mb-1'>管理员（工号，去前缀0）：</div>
            <Select
              mode='tags'
              value={admins}
              style={{ width: '100%' }}
              onChange={handleChange}
              tokenSeparators={[',']}
              options={admins?.map((item: string) => ({
                label: item,
                value: item,
              }))}
              loading={adminLoading}
            />
          </div>
        </Spin>
      </Modal>
    </ConstructLayout>
  );
}
