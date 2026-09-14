import MarkDownContext from '@/new-components/common/MarkdownContext';
import { LinkOutlined } from '@ant-design/icons';
import type { TabsProps } from 'antd';
import { Divider, Drawer, Tabs, Typography } from 'antd';
import classNames from 'classnames';
import { useRouter } from 'next/router';
import React, { useEffect, useMemo, useState } from 'react';

const ReferencesContentView: React.FC<{ references: any; activeIndex?: number }> = ({
  references,
  activeIndex,
}) => {
  const router = useRouter();
  const [open, setOpen] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState<string>('');

  // 是否移动端页面
  const isMobile = useMemo(() => {
    return router.pathname.includes('/mobile');
  }, [router]);

  // Normalize: backend sends an array [{name, chunks}], but older code may
  // wrap it as {knowledge: [...]}. Accept both.
  const docList: any[] = useMemo(() => {
    if (!references) return [];
    if (Array.isArray(references)) return references;
    if (references.knowledge) return references.knowledge;
    return [];
  }, [references]);

  // Build a flat index map: citation index -> {docIndex, chunkIndex}
  const citationMap = useMemo(() => {
    const map: Record<number, { docIndex: number; chunkIndex: number }> = {};
    docList.forEach((doc, docIndex) => {
      doc?.chunks?.forEach((chunk: any, chunkIndex: number) => {
        if (chunk.index != null) {
          map[chunk.index] = { docIndex, chunkIndex };
        }
      });
    });
    return map;
  }, [docList]);

  // When activeIndex changes, open drawer and activate the corresponding tab
  useEffect(() => {
    if (activeIndex != null && citationMap[activeIndex]) {
      const { docIndex } = citationMap[activeIndex];
      if (docList[docIndex]) {
        // Use docIndex as key instead of doc.name — document names are not
        // guaranteed unique (no DB uniqueness constraint), and duplicate names
        // would produce duplicate Ant Design tab keys and break citation selection.
        setActiveKey(String(docIndex));
        setOpen(true);
      }
    }
  }, [activeIndex, citationMap, docList]);

  const items: TabsProps['items'] = useMemo(() => {
    return docList.map((reference: any, docIndex: number) => {
      return {
        label: (
          <div style={{ maxWidth: '120px' }}>
            <Typography.Text
              ellipsis={{
                tooltip: reference.name,
              }}
            >
              {decodeURIComponent(reference.name).split('_')[0]}
            </Typography.Text>
          </div>
        ),
        // Use docIndex as key — guaranteed unique within the current docList.
        // name is kept only as the visible label.
        key: String(docIndex),
        children: (
          <div className='h-full overflow-y-auto space-y-3'>
            {reference?.chunks?.map((chunk: any) => (
              <div
                key={chunk.id}
                className={classNames(
                  'border-b border-gray-100 dark:border-gray-700 pb-3 last:border-0 transition-colors',
                  activeIndex != null && chunk.index === activeIndex && 'bg-blue-50 dark:bg-blue-900/30 -mx-2 px-2 rounded',
                )}
              >
                <div className='flex items-center gap-2 mb-1'>
                  {chunk.index != null && (
                    <span className='text-[10px] font-medium text-white bg-blue-500 rounded px-1'>
                      {chunk.index}
                    </span>
                  )}
                  {chunk.recall_score != null && (
                    <span className='text-[10px] text-gray-400'>召回 {Number(chunk.recall_score).toFixed(2)}</span>
                  )}
                  {chunk.page != null && (
                    <span className='text-[10px] text-gray-400'>Page {chunk.page}</span>
                  )}
                </div>
                <MarkDownContext key={chunk.id}>{chunk.content}</MarkDownContext>
              </div>
            ))}
          </div>
        ),
      };
    });
  }, [docList, activeIndex]);

  return (
    <div>
      <Divider className='mb-1 mt-0' dashed />
      <div className='flex text-sm gap-2 text-blue-400' onClick={() => setOpen(true)}>
        <LinkOutlined />
        <span className='text-sm'>查看回复引用</span>
      </div>
      <Drawer
        open={open}
        title='回复引用'
        placement={isMobile ? 'bottom' : 'right'}
        onClose={() => setOpen(false)}
        destroyOnClose={true}
        className='p-0'
        {...(!isMobile && { width: '30%' })}
      >
        <Tabs items={items} activeKey={activeKey || undefined} onChange={setActiveKey} size='small' />
      </Drawer>
    </div>
  );
};

const ReferencesContent: React.FC<{ references: any; activeIndex?: number }> = ({
  references,
  activeIndex,
}) => {
  try {
    const data = JSON.parse(references);
    return <ReferencesContentView references={data} activeIndex={activeIndex} />;
  } catch {
    return null;
  }
};

export default ReferencesContent;
