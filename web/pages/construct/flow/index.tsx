import { ChatContext } from '@/app/chat-context';
import { addFlow, apiInterceptors, deleteFlowById, getFlows, newDialogue } from '@/client/api';
import MyEmpty from '@/components/common/MyEmpty';
import BlurredCard, { ChatButton, InnerDropdown } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { IFlow, IFlowUpdateParam } from '@/types/flow';
import { PlusOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Checkbox, Form, Input, Modal, Pagination, Popconfirm, Spin, Tag, message } from 'antd';
import { t } from 'i18next';
import moment from 'moment';
import { useRouter } from 'next/router';
import qs from 'querystring';
import { useContext, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

function Flow() {
  const router = useRouter();
  const { model } = useContext(ChatContext);
  const [messageApi] = message.useMessage();
  const [form] = Form.useForm<Pick<IFlow, 'label' | 'name'>>();

  const [flowList, setFlowList] = useState<Array<IFlow>>([]);
  const copyFlowTemp = useRef<IFlow>();
  const [showModal, setShowModal] = useState(false);
  const [deploy, setDeploy] = useState(false);
  const [editable, setEditable] = useState(false);

  const totalRef = useRef<{
    current_page: number;
    total_count: number;
    total_page: number;
  }>();

  const scrollRef = useRef<HTMLDivElement>(null);

  // get flow list
  const { run: getFlowListRun, loading } = useRequest(
    async (params: any) =>
      await apiInterceptors(
        getFlows({
          page: 1,
          page_size: 12,
          ...params,
        }),
      ),
    {
      cacheKey: 'query-flow-list',
      onSuccess: data => {
        const [, res] = data;
        // setFlowList((prev) => concat([...prev], res?.items || []));
        setFlowList(res?.items || []);
        totalRef.current = {
          current_page: res?.page || 1,
          total_count: res?.total_count || 0,
          total_page: res?.total_pages || 0,
        };
      },
      throttleWait: 300,
    },
  );

  const { i18n } = useTranslation();

  // 触底加载更多
  // const loadMoreData = useCallback(() => {
  //   const current = totalRef.current;
  //   if (!current) {
  //     return;
  //   }
  //   if (current.current_page < current.total_page) {
  //     getFlowListRun({
  //       page: current.current_page + 1,
  //     });
  //     current.current_page = current.current_page + 1;
  //   }
  // }, [getFlowListRun]);

  // // 滚动事件
  // const handleScroll = debounce((e: Event) => {
  //   const target = e.target as HTMLDivElement;
  //   if (target.scrollHeight - target.scrollTop <= target.clientHeight + 200) {
  //     loadMoreData();
  //   }
  // }, 200);

  // useEffect(() => {
  //   if (loading) {
  //     return;
  //   }
  //   const currentScrollRef = scrollRef.current;
  //   if (currentScrollRef) {
  //     currentScrollRef?.addEventListener('scroll', handleScroll);
  //     if (currentScrollRef.scrollHeight === currentScrollRef.clientHeight) {
  //       loadMoreData();
  //     }
  //   }
  //   return () => {
  //     if (currentScrollRef) {
  //       currentScrollRef?.removeEventListener('scroll', handleScroll);
  //     }
  //   };
  // }, [loading, handleScroll, loadMoreData]);

  const handleChat = async (flow: IFlow) => {
    const [, res] = await apiInterceptors(newDialogue({ chat_mode: 'chat_agent' }));
    if (res) {
      const queryStr = qs.stringify({
        scene: 'chat_flow',
        id: res.conv_uid,
        model: model,
        select_param: flow.uid,
      });
      router.push(`/chat?${queryStr}`);
    }
  };

  async function deleteFlow(flow: IFlow) {
    const [, , res] = await apiInterceptors(deleteFlowById(flow.uid));
    if (res?.success) {
      setFlowList(flows => flows.filter(_flow => _flow.uid !== flow.uid));
    }
  }

  const handleCopy = (flow: IFlow) => {
    copyFlowTemp.current = flow;
    form.setFieldValue('label', `${flow.label} Copy`);
    form.setFieldValue('name', `${flow.name}_copy`);
    setEditable(true);
    setShowModal(true);
  };

  const onFinish = async (val: { name: string; label: string }) => {
    if (!copyFlowTemp.current) return;
    const { source, uid, dag_id, gmt_created, gmt_modified, state, ...params } = copyFlowTemp.current;
    const data: IFlowUpdateParam = {
      ...params,
      editable,
      state: deploy ? 'deployed' : 'developing',
      ...val,
    };
    const [err] = await apiInterceptors(addFlow(data));
    if (!err) {
      messageApi.success(t('save_flow_success'));
      setShowModal(false);
      getFlowListRun({});
    }
  };

  return (
    <ConstructLayout>
      <Spin spinning={loading}>
        <div className='relative h-screen w-full p-4 md:p-6 overflow-y-auto' ref={scrollRef}>
          <div className='flex justify-between items-center mb-6'>
            <div className='flex items-center gap-4'>
              {/* <Input
              variant="filled"
              prefix={<SearchOutlined />}
              placeholder={t('please_enter_the_keywords')}
              // onChange={onSearch}
              // onPressEnter={onSearch}
              allowClear
              className="w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
            /> */}
            </div>

            <div className='flex items-center gap-4'>
              <Button
                className='border-none text-white bg-button-gradient'
                icon={<PlusOutlined />}
                onClick={() => {
                  router.push('/construct/flow/canvas');
                }}
              >
                {t('create_flow')}
              </Button>
            </div>
          </div>
          <div className='flex flex-wrap mx-[-8px] pb-12 justify-start items-stretch'>
            {flowList.map(flow => (
              <BlurredCard
                description={flow.description}
                name={flow.name}
                key={flow.uid}
                logo={`${flow.define_type === 'python' ? '/pictures/libro.png' : '/pictures/flow.png'}`}
                onClick={() => {
                  if (flow.define_type === 'json') {
                    router.push('/construct/flow/canvas?id=' + flow.uid);
                  }
                  if (flow.define_type === 'python') {
                    router.push('/construct/flow/libro?id=' + flow.uid);
                  }
                }}
                RightTop={
                  <InnerDropdown
                    menu={{
                      items: [
                        {
                          key: 'copy',
                          label: (
                            <span
                              onClick={() => {
                                handleCopy(flow);
                              }}
                            >
                              {t('Copy_Btn')}
                            </span>
                          ),
                        },
                        {
                          key: 'del',
                          label: (
                            <Popconfirm title='Are you sure to delete this flow?' onConfirm={() => deleteFlow(flow)}>
                              <span className='text-red-400'>{t('Delete_Btn')}</span>
                            </Popconfirm>
                          ),
                        },
                      ],
                    }}
                  />
                }
                rightTopHover={false}
                Tags={
                  <div>
                    <Tag color={flow.source === 'DBGPT-WEB' ? 'green' : 'blue'}>{flow.source}</Tag>
                    {flow.define_type && <Tag color={'purple'}>{flow.define_type}</Tag>}
                    <Tag color={flow.editable ? 'green' : 'gray'}>{flow.editable ? 'Editable' : 'Can not Edit'}</Tag>
                    <Tag color={flow.state === 'load_failed' ? 'red' : flow.state === 'running' ? 'green' : 'blue'}>
                      {flow.state}
                    </Tag>
                  </div>
                }
                LeftBottom={
                  <div key={i18n.language + 'flow'} className='flex gap-2'>
                    <span>{flow?.nick_name}</span>
                    <span>•</span>
                    {flow?.gmt_modified && <span>{moment(flow?.gmt_modified).fromNow() + ' ' + t('update')}</span>}
                  </div>
                }
                RightBottom={
                  <ChatButton
                    onClick={() => {
                      handleChat(flow);
                    }}
                    text={t('start_chat')}
                  />
                }
              />
            ))}
            {flowList.length === 0 && <MyEmpty description='No flow found' />}
            <div className='w-full flex justify-end shrink-0 pb-12'>
              <Pagination
                total={totalRef.current?.total_count || 0}
                pageSize={12}
                current={totalRef.current?.current_page}
                onChange={async (page, page_size) => {
                  await getFlowListRun({ page, page_size });
                }}
              />
            </div>
          </div>
        </div>
      </Spin>

      <Modal
        open={showModal}
        destroyOnClose
        title='Copy AWEL Flow'
        onCancel={() => {
          setShowModal(false);
        }}
        footer={false}
      >
        <Form form={form} onFinish={onFinish} className='mt-6'>
          <Form.Item name='name' label='Name' rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name='label' label='Label' rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label='editable'>
            <Checkbox
              value={editable}
              checked={editable}
              onChange={e => {
                const val = e.target.checked;
                setEditable(val);
              }}
            />
          </Form.Item>
          <Form.Item label='deploy'>
            <Checkbox
              value={deploy}
              checked={deploy}
              onChange={e => {
                const val = e.target.checked;
                setDeploy(val);
              }}
            />
          </Form.Item>
          <div className='flex justify-end'>
            <Button type='primary' htmlType='submit'>
              {t('Submit')}
            </Button>
          </div>
        </Form>
      </Modal>
    </ConstructLayout>
  );
}

export default Flow;
