import { apiInterceptors, getChunkList } from '@/client/api';
import DocIcon from '@/components/knowledge/doc-icon';
import { DoubleRightOutlined } from '@ant-design/icons';
import { Breadcrumb, Card, Empty, Pagination, Space, Spin } from 'antd';
import cls from 'classnames';
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
  const [isExpand, setIsExpand] = useState<boolean>(false);
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
    setTotal(data?.total!);
    setLoading(false);
  };

  const loaderMore = async (page: number, page_size: number) => {
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
  };

  useEffect(() => {
    spaceName && id && fetchChunks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, spaceName]);

  return (
    <div className="flex flex-col h-full w-full px-6 pb-6">
      <Breadcrumb
        className="m-6"
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
      {chunkList?.length > 0 ? (
        <div className="h-full grid sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4  grid-flow-row auto-rows-max gap-x-6 gap-y-10 overflow-y-auto relative">
          <Spin className="flex flex-col items-center justify-center absolute bottom-0 top-0 left-0 right-0" spinning={loading} />
          {chunkList?.map((chunk: any) => {
            return (
              <Card
                key={chunk.id}
                title={
                  <Space>
                    <DocIcon type={chunk.doc_type} />
                    <span>{chunk.doc_name}</span>
                  </Space>
                }
                className={cls('h-96 rounded-xl overflow-hidden', {
                  'h-auto': isExpand,
                })}
              >
                <p className="font-semibold">{t('Content')}:</p>
                <p>{chunk?.content}</p>
                <p className="font-semibold">{t('Meta_Data')}: </p>
                <p>{chunk?.meta_info}</p>
                <Space
                  className="absolute bottom-0 right-0 left-0 flex items-center justify-center cursor-pointer text-[#1890ff] bg-[rgba(255,255,255,0.8)] z-30"
                  onClick={() => setIsExpand(!isExpand)}
                >
                  <DoubleRightOutlined rotate={isExpand ? -90 : 90} /> {isExpand ? '收起' : '展开'}
                </Space>
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
        className="flex w-full justify-end"
        defaultCurrent={1}
        defaultPageSize={DEDAULT_PAGE_SIZE}
        total={total}
        showTotal={(total) => `Total ${total} items`}
        onChange={loaderMore}
      />
    </div>
  );
}

export default ChunkList;
