import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Card, Space, Divider, Empty, Spin, Tag, Tooltip, Modal } from 'antd';
import { DeleteFilled, InteractionFilled, PlusOutlined, ToolFilled, EyeFilled, WarningOutlined } from '@ant-design/icons';
import { apiInterceptors, delDocument, getDocumentList, syncDocument } from '@/client/api';
import { IDocument, ISpace } from '@/types/knowledge';
import moment from 'moment';
import ArgumentsModal from './arguments-modal';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/router';
import DocIcon from './doc-icon';

interface IProps {
  space: ISpace;
  onAddDoc: (spaceName: string) => void;
  onDeleteDoc: () => void;
}

const { confirm } = Modal;

export default function DocPanel(props: IProps) {
  const { space } = props;
  const { t } = useTranslation();
  const router = useRouter();
  const page_size = 18;

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [documents, setDocuments] = useState<any>([]);
  const [argumentsShow, setArgumentsShow] = useState<boolean>(false);
  const [total, setTotal] = useState<number>(0);
  const currentPageRef = useRef(1);

  const hasMore = useMemo(() => {
    return documents.length < total;
  }, [documents.length, total]);

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

  async function fetchDocuments() {
    setIsLoading(true);
    const [_, data] = await apiInterceptors(
      getDocumentList(space.name, {
        page: currentPageRef.current,
        page_size,
      }),
    );
    setDocuments(data?.data);
    setTotal(data?.total);
    setIsLoading(false);
  }

  const loadMoreDocuments = async () => {
    if (!hasMore) {
      return;
    }
    setIsLoading(true);
    currentPageRef.current += 1;
    const [_, data] = await apiInterceptors(
      getDocumentList(space.name, {
        page: currentPageRef.current,
        page_size,
      }),
    );
    setDocuments([...documents, ...data!.data]);
    setIsLoading(false);
  };

  const handleSync = async (spaceName: string, id: number) => {
    await apiInterceptors(syncDocument(spaceName, { doc_ids: [id] }));
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
        color = '#87d068';
        break;
      case 'FAILED':
        color = 'f50';
        break;
      default:
        color = 'f50';
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
  }, [space]);

  const renderDocumentCard = () => {
    if (documents?.length > 0) {
      return (
        <div className="max-h-96 overflow-auto max-w-3/4">
          <div className="mt-3 grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2 lg:grid-cols-3 xl:gap-x-5">
            {documents.map((document: IDocument) => {
              return (
                <Card
                  key={document.id}
                  className=" dark:bg-[#484848] relative  shrink-0 grow-0 cursor-pointer rounded-[10px] border border-gray-200 border-solid w-full"
                  title={
                    <Tooltip title={document.doc_name}>
                      <div className="truncate ">
                        <DocIcon type={document.doc_type} />
                        <span>{document.doc_name}</span>
                      </div>
                    </Tooltip>
                  }
                  extra={
                    <div className="mx-3">
                      <Tooltip title={'detail'}>
                        <EyeFilled
                          className="mr-2 !text-lg"
                          style={{ color: '#1b7eff', fontSize: '20px' }}
                          onClick={() => {
                            router.push(`/knowledge/chunk/?spaceName=${space.name}&id=${document.id}`);
                          }}
                        />
                      </Tooltip>
                      <Tooltip title={'Sync'}>
                        <InteractionFilled
                          className="mr-2 !text-lg"
                          style={{ color: '#1b7eff', fontSize: '20px' }}
                          onClick={() => {
                            handleSync(space.name, document.id);
                          }}
                        />
                      </Tooltip>
                      <Tooltip title={'Delete'}>
                        <DeleteFilled
                          className="text-[#ff1b2e] !text-lg"
                          onClick={() => {
                            showDeleteConfirm(document);
                          }}
                        />
                      </Tooltip>
                    </div>
                  }
                >
                  <p className="mt-2 font-semibold ">{t('Size')}:</p>
                  <p>{document.chunk_size} chunks</p>
                  <p className="mt-2 font-semibold ">{t('Last_Synch')}:</p>
                  <p>{moment(document.last_sync).format('YYYY-MM-DD HH:MM:SS')}</p>
                  <p className="mt-2 mb-2">{renderResultTag(document.status, document.result)}</p>
                </Card>
              );
            })}
          </div>
          {hasMore && (
            <Divider>
              <span className="cursor-pointer" onClick={loadMoreDocuments}>
                {t('Load_More')}
              </span>
            </Divider>
          )}
        </div>
      );
    }
    return (
      <Empty image={Empty.PRESENTED_IMAGE_DEFAULT}>
        <Button type="primary" className="flex items-center mx-auto" icon={<PlusOutlined />} onClick={handleAddDocument}>
          Create Now
        </Button>
      </Empty>
    );
  };

  return (
    <div className="collapse-container pt-2 px-4">
      <Space>
        <Button size="middle" type="primary" className="flex items-center" icon={<PlusOutlined />} onClick={handleAddDocument}>
          {t('Add_Datasource')}
        </Button>
        <Button size="middle" className="flex items-center mx-2" icon={<ToolFilled />} onClick={handleArguments}>
          Arguments
        </Button>
      </Space>
      <Divider />
      <Spin spinning={isLoading}>{renderDocumentCard()}</Spin>
      <ArgumentsModal space={space} argumentsShow={argumentsShow} setArgumentsShow={setArgumentsShow} />
    </div>
  );
}
