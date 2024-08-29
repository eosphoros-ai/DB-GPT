import { apiInterceptors, chunkAddQuestion, getChunkList } from '@/client/api';
import MenuModal from '@/components/MenuModal';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import { MinusCircleOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { App, Breadcrumb, Button, Card, Empty, Form, Input, Pagination, Space, Spin, Tag } from 'antd';
import cls from 'classnames';
import { debounce } from 'lodash';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const DEDAULT_PAGE_SIZE = 10;

function ChunkList() {
  const router = useRouter();
  const { t } = useTranslation();
  const [chunkList, setChunkList] = useState<any>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  // const [isExpand, setIsExpand] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentChunkInfo, setCurrentChunkInfo] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const [pageSize, setPageSize] = useState<number>(10);

  const [form] = Form.useForm();

  const { message } = App.useApp();

  const {
    query: { id, spaceName },
  } = useRouter();

  const fetchChunks = async () => {
    setLoading(true);
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page: 1,
        page_size: DEDAULT_PAGE_SIZE,
      }),
    );
    setChunkList(data?.data);
    setTotal(data?.total ?? 0);
    setLoading(false);
  };

  const loaderMore = async (page: number, page_size: number) => {
    setPageSize(page_size);
    setLoading(true);
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page,
        page_size,
      }),
    );
    setChunkList(data?.data || []);
    setLoading(false);
    setCurrentPage(page);
  };

  useEffect(() => {
    spaceName && id && fetchChunks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, spaceName]);

  const onSearch = async (e: any) => {
    const content = e.target.value;
    if (!content) {
      return;
    }
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page: currentPage,
        page_size: pageSize,
        content,
      }),
    );
    setChunkList(data?.data || []);
  };

  // 添加问题
  const { run: addQuestionRun, loading: addLoading } = useRequest(
    async (questions: string[]) => apiInterceptors(chunkAddQuestion({ chunk_id: currentChunkInfo.id, questions })),
    {
      manual: true,
      onSuccess: async () => {
        message.success('添加成功');
        setIsModalOpen(false);
        await fetchChunks();
      },
    },
  );

  return (
    <div className='flex flex-col h-full w-full px-6 pb-6'>
      <Breadcrumb
        className='m-6'
        items={[
          {
            title: 'Knowledge',
            onClick() {
              router.back();
            },
            path: '/knowledge',
          },
          {
            title: spaceName,
          },
        ]}
      />
      <div className='flex items-center gap-4'>
        <Input
          className='w-1/5 h-10 mb-4'
          prefix={<SearchOutlined />}
          placeholder={t('please_enter_the_keywords')}
          onChange={debounce(onSearch, 300)}
          allowClear
        />
      </div>
      {chunkList?.length > 0 ? (
        <div className='h-full grid sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4  grid-flow-row auto-rows-max gap-x-6 gap-y-10 overflow-y-auto relative'>
          <Spin
            className='flex flex-col items-center justify-center absolute bottom-0 top-0 left-0 right-0'
            spinning={loading}
          />
          {chunkList?.map((chunk: any, index: number) => {
            return (
              <Card
                hoverable
                key={chunk.id}
                title={
                  <Space className='flex justify-between'>
                    <Tag color='blue'># {index + (currentPage - 1) * DEDAULT_PAGE_SIZE}</Tag>
                    {/* <DocIcon type={chunk.doc_type} /> */}
                    <span className='text-sm'>{chunk.doc_name}</span>
                  </Space>
                }
                className={cls('h-96 rounded-xl overflow-hidden', {
                  // 'h-auto': isExpand,
                  'h-auto': true,
                })}
                onClick={() => {
                  setIsModalOpen(true);
                  setCurrentChunkInfo(chunk);
                }}
              >
                <p className='font-semibold'>{t('Content')}:</p>
                <p>{chunk?.content}</p>
                <p className='font-semibold'>{t('Meta_Data')}: </p>
                <p>{chunk?.meta_info}</p>
                {/* <Space
                  className="absolute bottom-0 right-0 left-0 flex items-center justify-center cursor-pointer text-[#1890ff] bg-[rgba(255,255,255,0.8)] z-30"
                  onClick={() => setIsExpand(!isExpand)}
                >
                  <DoubleRightOutlined rotate={isExpand ? -90 : 90} /> {isExpand ? '收起' : '展开'}
                </Space> */}
              </Card>
            );
          })}
        </div>
      ) : (
        <Spin spinning={loading}>
          <Empty image={Empty.PRESENTED_IMAGE_DEFAULT} />
        </Spin>
      )}
      <Pagination
        className='flex w-full justify-end'
        defaultCurrent={1}
        defaultPageSize={DEDAULT_PAGE_SIZE}
        total={total}
        showTotal={total => `Total ${total} items`}
        onChange={loaderMore}
      />
      <MenuModal
        modal={{
          title: t('Manual_entry'),
          width: '70%',
          open: isModalOpen,
          footer: false,
          onCancel: () => setIsModalOpen(false),
          afterOpenChange: open => {
            if (open) {
              form.setFieldValue(
                'questions',
                JSON.parse(currentChunkInfo?.questions || '[]')?.map((item: any) => ({ question: item })),
              );
            }
          },
        }}
        items={[
          {
            key: 'edit',
            label: t('Data_content'),
            children: (
              <div className='flex gap-4'>
                <Card size='small' title={t('Main_content')} className='w-2/3 flex-wrap overflow-y-auto'>
                  <MarkDownContext>{currentChunkInfo?.content}</MarkDownContext>
                </Card>
                <Card size='small' title={t('Auxiliary_data')} className='w-1/3'>
                  <MarkDownContext>{currentChunkInfo?.meta_info}</MarkDownContext>
                </Card>
              </div>
            ),
          },
          {
            key: 'delete',
            label: t('Add_problem'),
            children: (
              <Card
                size='small'
                extra={
                  <Button
                    size='small'
                    type='primary'
                    onClick={async () => {
                      const formVal = form.getFieldsValue();
                      if (!formVal.questions) {
                        message.warning(t('enter_question_first'));
                        return;
                      }
                      if (formVal.questions?.filter(Boolean).length === 0) {
                        message.warning(t('enter_question_first'));
                        return;
                      }
                      const questions = formVal.questions?.filter(Boolean).map((item: any) => item.question);
                      await addQuestionRun(questions);
                    }}
                    loading={addLoading}
                  >
                    {t('save')}
                  </Button>
                }
              >
                <Form form={form}>
                  <Form.List name='questions'>
                    {(fields, { add, remove }) => (
                      <>
                        {fields.map(({ key, name }) => (
                          <div key={key} className={cls('flex flex-1 items-center gap-8')}>
                            <Form.Item label='' name={[name, 'question']} className='grow'>
                              <Input placeholder={t('Please_Input')} />
                            </Form.Item>
                            <Form.Item>
                              <MinusCircleOutlined
                                onClick={() => {
                                  remove(name);
                                }}
                              />
                            </Form.Item>
                          </div>
                        ))}
                        <Form.Item>
                          <Button
                            type='dashed'
                            onClick={() => {
                              add();
                            }}
                            block
                            icon={<PlusOutlined />}
                          >
                            {t('Add_problem')}
                          </Button>
                        </Form.Item>
                      </>
                    )}
                  </Form.List>
                </Form>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}

export default ChunkList;
