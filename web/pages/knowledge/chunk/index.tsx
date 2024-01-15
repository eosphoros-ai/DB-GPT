import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Breadcrumb, Card, Empty, Pagination, Spin } from 'antd';
import { useTranslation } from 'react-i18next';
import { apiInterceptors, getChunkList } from '@/client/api';
import DocIcon from '@/components/knowledge/doc-icon';

const DEDAULT_PAGE_SIZE = 10;

function ChunkList() {
  const router = useRouter();
  const { t } = useTranslation();
  const [chunkList, setChunkList] = useState<any>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const {
    query: { id, spaceName },
  } = useRouter();

  const fetchChunks = async () => {
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page: 1,
        page_size: DEDAULT_PAGE_SIZE,
      }),
    );

    setChunkList(data?.data);
    setTotal(data?.total!);
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
  }, [id, spaceName]);

  return (
    <div className="h-full overflow-y-scroll relative px-2">
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
      <Spin spinning={loading}>
        <div className="flex justify-center flex-col">
          {chunkList?.length > 0 ? (
            chunkList?.map((chunk: any) => {
              return (
                <Card
                  key={chunk.id}
                  className="mt-2"
                  title={
                    <>
                      <DocIcon type={chunk.doc_type} />
                      <span>{chunk.doc_name}</span>
                    </>
                  }
                >
                  <p className="font-semibold">{t('Content')}:</p>
                  <p>{chunk?.content}</p>
                  <p className="font-semibold">{t('Meta_Data')}: </p>
                  <p>{chunk?.meta_info}</p>
                </Card>
              );
            })
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_DEFAULT}></Empty>
          )}
        </div>
      </Spin>
      <Pagination
        className="mx-2 my-4 float-right right-6 bottom-4"
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
