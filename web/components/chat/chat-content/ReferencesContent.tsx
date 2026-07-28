import MarkDownContext from '@/new-components/common/MarkdownContext';
import { LinkOutlined } from '@ant-design/icons';
import type { TabsProps } from 'antd';
import { Divider, Drawer, Tabs, Typography } from 'antd';
import { useRouter } from 'next/router';
import React, { useMemo, useState } from 'react';

const ReferencesContentView: React.FC<{ references: any }> = ({ references }) => {
  const router = useRouter();
  const [open, setOpen] = useState<boolean>(false);

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

  const items: TabsProps['items'] = useMemo(() => {
    return docList.map((reference: any) => {
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
        key: reference.name,
        children: (
          <div className='h-full overflow-y-auto space-y-3'>
            {reference?.chunks?.map((chunk: any) => (
              <div key={chunk.id} className='border-b border-gray-100 dark:border-gray-700 pb-3 last:border-0'>
                <div className='flex items-center gap-2 mb-1'>
                  {chunk.index != null && (
                    <span className='text-[10px] font-medium text-white bg-blue-500 rounded px-1'>{chunk.index}</span>
                  )}
                  {chunk.recall_score != null && (
                    <span className='text-[10px] text-gray-400'>召回 {Number(chunk.recall_score).toFixed(2)}</span>
                  )}
                </div>
                <MarkDownContext key={chunk.id}>{chunk.content}</MarkDownContext>
              </div>
            ))}
          </div>
        ),
      };
    });
  }, [docList]);

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
        <Tabs items={items} size='small' />
      </Drawer>
    </div>
  );
};

const ReferencesContent: React.FC<{ references: any }> = ({ references }) => {
  try {
    const data = JSON.parse(references);
    return <ReferencesContentView references={data} />;
  } catch {
    return null;
  }
};

export default ReferencesContent;
