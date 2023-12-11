import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { Breadcrumb, Button, Card, Divider, Empty, List } from 'antd';
import { useTranslation } from 'react-i18next';
import { apiInterceptors, getChunkList } from '@/client/api';
import DocIcon from '@/components/knowledge/doc-icon';

const page_size = 20;

function ChunkList() {
  const router = useRouter();
  const { t } = useTranslation();
  const [chunkList, setChunkList] = useState<any>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const currentPageRef = useRef(1);
  const {
    query: { id, spaceName },
  } = useRouter();

  const hasMore = useMemo(() => {
    return chunkList?.length < total;
  }, [chunkList.length, total]);

  const fetchChunks = async () => {
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page: currentPageRef.current,
        page_size,
      }),
    );

    setChunkList(data?.data);
    setTotal(data?.total!);
  };

  const loaderMoreChunks = async () => {
    if (loading) {
      return;
    }
    setLoading(true);
    currentPageRef.current += 1;
    const [_, data] = await apiInterceptors(
      getChunkList(spaceName as string, {
        document_id: id as string,
        page: currentPageRef.current,
        page_size,
      }),
    );

    setChunkList([...chunkList, ...(data?.data || [])]);
    setLoading(false);
  };

  useEffect(() => {
    spaceName && id && fetchChunks();
  }, [id, spaceName]);

  return (
    <div className="h-full overflow-y-scroll">
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
      <div className="flex justify-center flex-col">
        <div>
          {chunkList?.length > 0 ? (
            chunkList?.map((chunk: any) => {
              return (
                <Card
                  key={chunk.id}
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
        {hasMore && (
          <Divider>
            <span className="cursor-pointer" onClick={loaderMoreChunks}>
              {t('Load_more')}
            </span>
          </Divider>
        )}
      </div>
    </div>
  );
}

export default ChunkList;
