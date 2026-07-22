import {
  apiInterceptors,
  delDocument,
  editChunk,
  getDocumentList,
  // getKnowledgeAdmins,
  searchDocumentList,
  syncDocument,
} from '@/client/api';
import { IDocument, ISpace } from '@/types/knowledge';
import {
  DeleteOutlined,
  DeploymentUnitOutlined,
  EditOutlined,
  EllipsisOutlined,
  ExperimentOutlined,
  EyeOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  PlusOutlined,
  SearchOutlined,
  SyncOutlined,
  ToolFilled,
  WarningOutlined,
} from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Divider, Dropdown, Empty, Form, Input, Modal, Space, Spin, Tag, Tooltip, message } from 'antd';
import cls from 'classnames';
import moment from 'moment';
import { useRouter } from 'next/router';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import RecallTestModal from './RecallTestModal';
import ArgumentsModal from './arguments-modal';
import DocIcon from './doc-icon';
import SearchToolsPanel from './search-tools-panel';

interface IProps {
  space: ISpace;
  addStatus?: string;
  onAddDoc: (spaceName: string) => void;
  onDeleteDoc: () => void;
  hideRecallTest?: boolean;
  hideSearchTools?: boolean;
  refreshKey?: number;
}

const { confirm } = Modal;

const SyncContent: React.FC<{ name: string; id: number }> = ({ name, id }) => {
  const [syncLoading, setSyncLoading] = useState<boolean>(false);
  const { t } = useTranslation();

  const handleSync = async (spaceName: string, id: number) => {
    setSyncLoading(true);
    const res = await apiInterceptors(syncDocument(spaceName, { doc_ids: [id] }));
    setSyncLoading(false);
    if (res[2]?.success) {
      message.success(t('Synchronization_initiated'));
    }
  };

  if (syncLoading) {
    return <Spin indicator={<LoadingOutlined spin />} />;
  }
  return (
    <Space
      onClick={() => {
        handleSync(name, id);
      }}
    >
      <SyncOutlined />
      <span>{t('Sync')}</span>
    </Space>
  );
};

export default function DocPanel(props: IProps) {
  const [form] = Form.useForm();
  const { space, addStatus, hideRecallTest, hideSearchTools, refreshKey } = props;
  const { t } = useTranslation();
  const router = useRouter();
  const page_size = 18;
  // const [_, setAdmins] = useState<string[]>([]);
  const [documents, setDocuments] = useState<any>([]);
  const [searchDocuments, setSearchDocuments] = useState<any>([]);
  const [argumentsShow, setArgumentsShow] = useState<boolean>(false);
  const [total, setTotal] = useState<number>(0);

  const [editOpen, setEditOpen] = useState<boolean>(false);
  const [curDoc, setCurDoc] = useState<IDocument>();

  // 召回测试弹窗
  const [recallTestOpen, setRecallTestOpen] = useState<boolean>(false);

  // 搜索工具面板
  const [searchToolsOpen, setSearchToolsOpen] = useState<boolean>(false);

  const currentPageRef = useRef(1);

  const hasMore = useMemo(() => {
    return documents?.length < total;
  }, [documents, total]);

  // GitRepo spaces map 1:1 to a repository; once imported, disallow adding more.
  const isGitRepoImported = space.domain_type === 'GitRepo' && documents.length > 0;

  const showDeleteConfirm = (row: any) => {
    confirm({
      title: t('Tips'),
      icon: <WarningOutlined />,
      content: `${t('Del_Document_Tips')}?`,
      okText: 'Yes',
      okType: 'danger',
      cancelText: 'No',
      async onOk() {
        await handleDelete(row);
      },
    });
  };

  const {
    run: fetchDocuments,
    refresh,
    loading: isLoading,
  } = useRequest(
    async () =>
      await apiInterceptors(
        getDocumentList(space.name, {
          page: currentPageRef.current,
          page_size,
        }),
      ),
    {
      manual: true,
      onSuccess: res => {
        const [, data] = res;
        setDocuments(data?.data);
        setSearchDocuments(data?.data);
        setTotal(data?.total || 0);
      },
    },
  );

  const loadMoreDocuments = async () => {
    if (!hasMore) {
      return;
    }
    currentPageRef.current += 1;
    const [_, data] = await apiInterceptors(
      getDocumentList(space.name, {
        page: currentPageRef.current,
        page_size,
      }),
    );
    setDocuments([...documents, ...data!.data]);
    setSearchDocuments([...documents, ...data!.data]);
  };

  const handleDelete = async (row: any) => {
    await apiInterceptors(delDocument(space.name, { doc_name: row.doc_name }));
    fetchDocuments();
    props.onDeleteDoc();
  };

  const handleAddDocument = () => {
    props.onAddDoc(space.name);
  };

  const handleArguments = () => {
    setArgumentsShow(true);
  };
  const openGraphVisualPage = () => {
    router.push(`/knowledge/graph/?spaceName=${space.name}`);
  };

  const renderResultTag = (status: string, result: string) => {
    let color;
    switch (status) {
      case 'TODO':
        color = 'gold';
        break;
      case 'RUNNING':
        color = '#2db7f5';
        break;
      case 'FINISHED':
        color = 'cyan';
        break;
      case 'FAILED':
        color = 'red';
        break;
      default:
        color = 'red';
        break;
    }
    return (
      <Tooltip title={result}>
        <Tag color={color}>{status}</Tag>
      </Tooltip>
    );
  };

  useEffect(() => {
    fetchDocuments();
    // getAdmins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refresh document list when refreshKey changes (e.g. after adding a doc)
  useEffect(() => {
    if (refreshKey === undefined) return;
    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  useEffect(() => {
    if (addStatus === 'finish') {
      fetchDocuments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addStatus]);

  // const updateAdmins = useCallback(
  //   async (options: string[]) => {
  //     const { data } = await updateKnowledgeAdmins({
  //       space_id: space.id as string,
  //       user_nos: options as any,
  //     });
  //     if (!data.success) {
  //       // getAdmins();
  //       notification.error({ description: data.err_msg, message: 'Update Error' });
  //     } else {
  //       message.success(t('Edit_Success'));
  //     }
  //   },
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  //   [space.id],
  // );

  // const handleChange = (value: string[]) => {
  //   updateAdmins(value);
  //   setAdmins(value);
  // };

  const { run: search, loading: searchLoading } = useRequest(
    async (_, doc_name: string) => {
      const [, res] = await apiInterceptors(searchDocumentList(space.name, { doc_name }));
      return res;
    },
    {
      manual: true,
      debounceWait: 500,
      onSuccess: data => {
        setSearchDocuments(data?.data);
      },
    },
  );

  const { run: editChunkRun, loading: chunkLoading } = useRequest(
    async (values: any) => {
      return await editChunk(props.space.name, {
        questions: values.questions?.map((item: any) => item.question),
        doc_id: curDoc?.id || '',
        doc_name: values.doc_name,
      });
    },
    {
      manual: true,
      onSuccess: async res => {
        if (res.data.success) {
          message.success(t('Edit_Success'));
          await fetchDocuments();
          setEditOpen(false);
        } else {
          message.error(res.data.err_msg);
        }
      },
    },
  );

  const renderDocumentCard = () => {
    return (
      <div className='w-full h-full'>
        <div className='mb-4 flex items-center justify-between'>
          <Input
            className='w-64'
            prefix={<SearchOutlined />}
            placeholder={t('please_enter_the_keywords')}
            onChange={async e => {
              await search(space.id, e.target.value);
            }}
            allowClear
          />
          <Button
            type='primary'
            onClick={async () => {
              await refresh();
            }}
            loading={isLoading}
          >
            {t('Refresh_status')}
          </Button>
        </div>
        {documents?.length > 0 ? (
          <Spin spinning={searchLoading}>
            {searchDocuments.length > 0 ? (
              <div className='border rounded-lg overflow-hidden'>
                {/* Table header */}
                <div className='grid grid-cols-12 gap-2 px-4 py-2.5 bg-gray-50 dark:bg-gray-800 border-b text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider'>
                  <div className='col-span-5'>{t('Document_name')}</div>
                  <div className='col-span-2'>{t('Size')}</div>
                  <div className='col-span-2'>{t('Status')}</div>
                  <div className='col-span-2'>{t('Last_Sync')}</div>
                  <div className='col-span-1 text-right'>{t('scheduled.col.actions')}</div>
                </div>
                {/* Table rows */}
                <div className='max-h-[420px] overflow-y-auto'>
                  {searchDocuments.map((document: IDocument) => (
                    <div
                      key={document.id}
                      className='grid grid-cols-12 gap-2 px-4 py-3 border-b last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors items-center cursor-pointer'
                      onClick={() => {
                        router.push(`/construct/knowledge/chunk/?spaceName=${space.name}&id=${document.id}`);
                      }}
                    >
                      {/* Name */}
                      <div className='col-span-5 flex items-center gap-2 min-w-0'>
                        <DocIcon type={document.doc_type} />
                        <Tooltip title={document.doc_name}>
                          <span className='truncate text-sm text-gray-800 dark:text-gray-200'>{document.doc_name}</span>
                        </Tooltip>
                      </div>
                      {/* Chunks */}
                      <div className='col-span-2 text-sm text-gray-600 dark:text-gray-400'>
                        {document.chunk_size} chunks
                      </div>
                      {/* Status */}
                      <div className='col-span-2'>{renderResultTag(document.status, document.result)}</div>
                      {/* Last Sync */}
                      <div className='col-span-2 text-sm text-gray-500 dark:text-gray-400'>
                        {document.last_sync ? moment(document.last_sync).format('YYYY-MM-DD HH:mm') : '-'}
                      </div>
                      {/* Actions */}
                      <div className='col-span-1 flex justify-end' onClick={e => e.stopPropagation()}>
                        <Dropdown
                          menu={{
                            items: [
                              {
                                key: 'detail',
                                label: (
                                  <Space>
                                    <EyeOutlined />
                                    <span>{t('detail')}</span>
                                  </Space>
                                ),
                                onClick: () => {
                                  router.push(`/construct/knowledge/chunk/?spaceName=${space.name}&id=${document.id}`);
                                },
                              },
                              {
                                key: 'sync',
                                label: <SyncContent name={space.name} id={document.id} />,
                              },
                              {
                                key: 'edit',
                                label: (
                                  <Space>
                                    <EditOutlined />
                                    <span>{t('Edit')}</span>
                                  </Space>
                                ),
                                onClick: () => {
                                  setEditOpen(true);
                                  setCurDoc(document);
                                },
                              },
                              {
                                key: 'delete',
                                danger: true,
                                label: (
                                  <Space>
                                    <DeleteOutlined />
                                    <span>{t('Delete')}</span>
                                  </Space>
                                ),
                                onClick: () => {
                                  showDeleteConfirm(document);
                                },
                              },
                            ],
                          }}
                          getPopupContainer={node => node.parentNode as HTMLElement}
                          placement='bottomRight'
                          autoAdjustOverflow={false}
                        >
                          <Button type='text' size='small' icon={<EllipsisOutlined />} />
                        </Dropdown>
                      </div>
                    </div>
                  ))}
                </div>
                {hasMore && (
                  <div className='py-2 text-center border-t'>
                    <span className='text-sm text-primary cursor-pointer hover:underline' onClick={loadMoreDocuments}>
                      {t('Load_more')}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <Empty
                className='flex flex-1 w-full py-10 flex-col items-center justify-center'
                image={Empty.PRESENTED_IMAGE_DEFAULT}
              />
            )}
          </Spin>
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_DEFAULT}>
            <Button
              type='primary'
              className='flex items-center mx-auto'
              icon={<PlusOutlined />}
              onClick={handleAddDocument}
            >
              Create Now
            </Button>
          </Empty>
        )}
      </div>
    );
  };

  useEffect(() => {
    if (!curDoc) {
      return;
    }
    form.setFieldsValue({
      doc_name: curDoc.doc_name,
      questions: curDoc.questions?.map(ques => {
        return {
          question: ques,
        };
      }),
    });
  }, [curDoc, form]);

  return (
    <div className='px-4'>
      <Space>
        <Tooltip title={isGitRepoImported ? t('git_repo_already_imported') : ''}>
          <Button
            size='middle'
            type='primary'
            className='flex items-center'
            icon={<PlusOutlined />}
            onClick={handleAddDocument}
            disabled={isGitRepoImported}
          >
            {t('Add_Datasource')}
          </Button>
        </Tooltip>
        <Button size='middle' className='flex items-center mx-2' icon={<ToolFilled />} onClick={handleArguments}>
          Arguments
        </Button>
        {space.vector_type === 'KnowledgeGraph' && (
          <Button
            size='middle'
            className='flex items-center mx-2'
            icon={<DeploymentUnitOutlined />}
            onClick={openGraphVisualPage}
          >
            {t('View_Graph')}
          </Button>
        )}
        {!hideRecallTest && (
          <Button icon={<ExperimentOutlined />} onClick={() => setRecallTestOpen(true)}>
            {t('Recall_test')}
          </Button>
        )}
        {!hideSearchTools && (
          <Button icon={<SearchOutlined />} onClick={() => setSearchToolsOpen(true)}>
            {t('Search_Tools')}
          </Button>
        )}
      </Space>
      <Divider />
      <Spin spinning={isLoading}>{renderDocumentCard()}</Spin>
      <ArgumentsModal space={space} argumentsShow={argumentsShow} setArgumentsShow={setArgumentsShow} />
      {/* 编辑弹窗 */}
      <Modal
        title={t('Edit_document')}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        destroyOnClose={true}
        footer={[
          <Button key='back' onClick={() => setEditOpen(false)}>
            {t('cancel')}
          </Button>,
          <Button
            key='submit'
            type='primary'
            loading={chunkLoading}
            onClick={async () => {
              const values = form.getFieldsValue();
              await editChunkRun(values);
            }}
          >
            {t('verify')}
          </Button>,
        ]}
      >
        <Form
          form={form}
          initialValues={{
            doc_name: curDoc?.doc_name,
            questions: curDoc?.questions?.map(ques => {
              return {
                question: ques,
              };
            }),
          }}
        >
          <Form.Item label={t('Document_name')} name='doc_name'>
            <Input />
          </Form.Item>
          <Form.Item label={t('Correlation_problem')}>
            <Form.List name='questions'>
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => (
                    <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6')}>
                      <Form.Item label='' name={[name, 'question']} className='grow'>
                        <Input placeholder='请输入' />
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
                        add({ question: '', valid: false });
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
          </Form.Item>
        </Form>
      </Modal>
      {/* 召回测试弹窗 */}
      <RecallTestModal open={recallTestOpen} setOpen={setRecallTestOpen} space={space} />
      {/* 搜索工具面板 */}
      <Modal
        title={t('Search_Tools')}
        open={searchToolsOpen}
        onCancel={() => setSearchToolsOpen(false)}
        footer={null}
        width={'80%'}
        destroyOnClose={true}
      >
        <SearchToolsPanel space={space} />
      </Modal>
    </div>
  );
}
